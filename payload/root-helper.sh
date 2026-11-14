#!/system/bin/sh
# Runs only after the official Singularity exploit has already obtained uid 0.
# No kernel writes, firmware flashing, network filtering or account changes.
PATH=/debug_ramdisk:/system/bin:/system/xbin:$PATH
mkdir /dev/.quest-root-helper-lock 2>/dev/null || exit 0
trap 'rmdir /dev/.quest-root-helper-lock' EXIT
mkdir -p /data/adb/singularity
exec >>/data/adb/singularity/root-helper.log 2>&1
echo "=== $(date) action=$1 uid=$(id -u) gid=$(id -g) ==="
if [ -z "$(pidof magiskd)" ]; then
    if [ ! -x /debug_ramdisk/magisk64 ]; then
        [ "$1" = bootstrap ] || exit 11
        [ -s /data/local/tmp/singularity_magisk.sh ] || exit 12
        [ -s /data/local/tmp/singularity-Magisk.apk ] || exit 13
        sh /data/local/tmp/singularity_magisk.sh || exit 14
    fi
fi
daemon_pid() { pidof magiskd | awk '{print $1}'; }
daemon_group() { awk '/^Gid:/{print $2}' "/proc/$1/status" 2>/dev/null; }
start_daemon() { /debug_ramdisk/magisk64 --daemon; }
ensure_normal_daemon() {
    # A just-killed daemon can still reset the startup client's connection.
    # Wait and retry only user-space daemon startup, never the exploit.
    for attempt in 1 2 3 4 5 6 7 8; do
        daemon=$(daemon_pid)
        if [ -n "$daemon" ]; then
            daemon_gid=$(daemon_group "$daemon")
            if [ "$daemon_gid" = 0 ]; then
                chmod 755 /debug_ramdisk/.magisk /debug_ramdisk/.magisk/device
                if su -c id && su 2000 -c 'su -c id'; then return 0; fi
            else
                echo "Restarting daemon with invalid GID (attempt $attempt)."
                kill -KILL "$daemon" || return 16
                sleep 1
            fi
        fi
        if [ -z "$(daemon_pid)" ]; then
            echo "Starting normalized daemon (attempt $attempt)."
            start_daemon || true
        fi
        sleep 1
    done
    return 18
}
ensure_normal_daemon || exit $?
daemon=$(pidof magiskd | awk '{print $1}')
[ -n "$daemon" ] || exit 18
awk '/^Uid:|^Gid:|^Groups:|^CapInh:/{print}' "/proc/$daemon/status"
daemon_gid=$(awk '/^Gid:/{print $2}' "/proc/$daemon/status")
[ "$daemon_gid" = 0 ] || exit 19
chmod 755 /debug_ramdisk/.magisk /debug_ramdisk/.magisk/device
su -c id || exit 20
su 2000 -c 'su -c id' || exit 21
cat /proc/sys/kernel/random/boot_id >/data/adb/singularity/root-helper-ready
chmod 600 /data/adb/singularity/root-helper-ready
echo ROOT_HELPER_READY
