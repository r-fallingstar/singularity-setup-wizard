"""Reconnect only the configured Quest using its ADB mDNS serial identity."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import ipaddress
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import subprocess
import sys
import time

BASE = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'SingularitySetupWizard' / 'wireless'


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def valid_endpoint(value):
    if not isinstance(value, str):
        return False
    host, sep, port = value.rpartition(":")
    if not sep or not port.isdigit() or not 1 <= int(port) <= 65535:
        return False
    try:
        ipaddress.ip_address(host.strip("[]").split("%", 1)[0])
        return True
    except ValueError:
        return False


def parse_mdns(output, serial):
    identity = re.compile(r"^adb-" + re.escape(serial) + r"(?:$|[-.])", re.I)
    found = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) != 3:
            continue
        name, kind, endpoint = fields
        if kind.rstrip(".") not in ("_adb._tcp", "_adb-tls-connect._tcp"):
            continue
        if identity.match(name) and valid_endpoint(endpoint) and endpoint not in found:
            found.append(endpoint)
    return found


def parse_devices(output):
    devices = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0] == "List" or fields[0].startswith("*"):
            continue
        transport = next((v.split(":", 1)[1] for v in fields[2:] if v.startswith("transport_id:")), "")
        devices[fields[0]] = (fields[1], transport)
    return devices


class Adb:
    def __init__(self, executable):
        self.executable = executable

    def __call__(self, *args):
        result = subprocess.run(
            [self.executable, *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=9,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout).strip()[:250])
        return result.stdout


class Connector:
    def __init__(self, serial, run, status_path):
        self.serial, self.run, self.status_path = serial, run, status_path
        self.verified = None
        self.verified_at = 0.0
        self.last_success = None
        self.previous = None
        self.known_endpoint = None
        try:
            old = json.loads(status_path.read_text(encoding="utf-8"))
            if old.get("serial") == serial and valid_endpoint(old.get("endpoint", "")):
                self.known_endpoint = old["endpoint"]
                self.last_success = old.get("last_connected_at")
        except (OSError, ValueError):
            pass

    def save(self, state, endpoint=None, detail=""):
        data = {"serial": self.serial, "state": state, "endpoint": endpoint,
                "updated_at": timestamp(), "last_connected_at": self.last_success,
                "detail": detail}
        temp = self.status_path.with_name(self.status_path.name + f".{os.getpid()}.tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, self.status_path)
        change = (state, endpoint, detail)
        if change != self.previous:
            logging.info("%s endpoint=%s %s", state, endpoint or "-", detail)
            self.previous = change
        return data

    def verify(self, endpoint, transport):
        actual = self.run("-s", endpoint, "shell", "getprop", "ro.serialno").strip()
        if actual != self.serial:
            raise ValueError("Advertised device identity did not match; not selecting this device")
        self.verified = (endpoint, transport)
        self.verified_at = time.monotonic()
        self.known_endpoint = endpoint
        self.last_success = timestamp()

    def tick(self):
        devices = parse_devices(self.run("devices", "-l"))
        if self.known_endpoint and devices.get(self.known_endpoint, (None,))[0] == "device":
            transport = devices[self.known_endpoint][1]
            try:
                if self.verified != (self.known_endpoint, transport) or time.monotonic() - self.verified_at > 180:
                    self.verify(self.known_endpoint, transport)
                return self.save("connected", self.known_endpoint)
            except ValueError:
                # A previously used IP may now belong to a different device.
                # Leave its existing connection alone and rediscover the Quest.
                self.known_endpoint = None
                self.verified = None

        candidates = parse_mdns(self.run("mdns", "services"), self.serial)
        if not candidates:
            return self.save("waiting", detail="Quest Pro has not advertised an ADB service on this LAN")
        failures = []
        for endpoint in candidates:
            existing = devices.get(endpoint)
            opened = False
            try:
                if existing and existing[0] == "offline":
                    self.run("disconnect", endpoint)
                if not existing or existing[0] != "device":
                    self.run("connect", endpoint)
                    opened = True
                current = parse_devices(self.run("devices", "-l")).get(endpoint)
                if not current or current[0] != "device":
                    raise RuntimeError("Waiting for the Quest to accept this PC's ADB key")
                self.verify(endpoint, current[1])
                return self.save("connected", endpoint)
            except ValueError as exc:
                if opened:
                    self.run("disconnect", endpoint)
                failures.append(str(exc))
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                failures.append(str(exc)[:250])
        return self.save("waiting", detail="; ".join(failures))


def singleton(serial):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    ctypes.set_last_error(0)
    handle = kernel.CreateMutexW(None, False, "Local\\QuestProADB_" + serial)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        kernel.CloseHandle(handle)
        return None, kernel
    return handle, kernel


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Discover and connect once")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true")
    args = parser.parse_args(argv)
    BASE.mkdir(parents=True,exist_ok=True)
    config = json.loads((BASE / "config.json").read_text(encoding="utf-8-sig"))
    status_path = BASE / "status.json"
    if args.status:
        print(status_path.read_text(encoding="utf-8") if status_path.exists() else "Not started")
        return 0
    if args.stop:
        (BASE / "stop.request").touch()
        return 0
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[RotatingFileHandler(BASE / "connection.log", maxBytes=500000, backupCount=2, encoding="utf-8")])
    connector = Connector(config["serial"], Adb(config["adb"]), status_path)
    if args.once:
        result = connector.tick()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["state"] == "connected" else 2
    handle, kernel = singleton(config["serial"])
    if not handle:
        return 0
    stop = BASE / "stop.request"
    stop.unlink(missing_ok=True)
    (BASE / "watcher.pid").write_text(str(os.getpid()), encoding="ascii")
    logging.info("Watcher started; target=%s; discovery interval=%ss", config["serial"], config["interval_seconds"])
    try:
        while not stop.exists():
            try:
                connector.tick()
            except Exception as exc:
                connector.save("waiting", detail=str(exc)[:250])
            for _ in range(config["interval_seconds"]):
                if stop.exists():
                    break
                time.sleep(1)
        connector.save("stopped", connector.known_endpoint)
    finally:
        (BASE / "watcher.pid").unlink(missing_ok=True)
        stop.unlink(missing_ok=True)
        kernel.CloseHandle(handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
