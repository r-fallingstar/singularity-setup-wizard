"""Explicit-target ADB operations. No exploit, firmware writes, or global ADB resets."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import hashlib
import re
import shlex
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

PACKAGE = 'com.codex.questroothelper'
SINGULARITY = 'com.lumi.singularity'
TESTED = {('seacliff', '51503870035800340')}
BASE = '/data/adb/singularity-setup-wizard'
RELEASES = 'https://github.com/Lumince/singularity/releases/tag/v1.0.8.5'
OFFICIAL_SHA256 = 'ddbbab522bbbada16db70770d3b0c456b031dc641d1afdc776b5422c21f09fe6'

class SetupError(RuntimeError): pass

def find_adb():
    candidates = [Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Android/Sdk/platform-tools/adb.exe']
    for var in ('ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        if os.environ.get(var): candidates.append(Path(os.environ[var]) / 'platform-tools/adb.exe')
    for name in ('adb.exe', 'adb'):
        item = shutil.which(name)
        if item and Path(item).suffix.lower() not in ('.cmd', '.bat'): candidates.append(Path(item))
    return next((str(p) for p in candidates if p.is_file()), '')

def update_preferences(text, updates):
    root = ET.fromstring(text)
    if root.tag != 'map': raise SetupError('Invalid preferences XML')
    for name, value in updates.items():
        matches = [node for node in root if node.get('name') == name]
        for node in matches: root.remove(node)
        if isinstance(value, bool): ET.SubElement(root, 'boolean', name=name, value=str(value).lower())
        else: ET.SubElement(root, 'string', name=name).text = str(value)
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)

@dataclass(frozen=True)
class Profile:
    firmware: bool = True
    auto_root: bool = True
    remote_actions: bool = False

class Adb:
    def __init__(self, executable, serial=''):
        self.executable, self.serial = executable, serial
    def run(self, *args, data=None, timeout=30):
        result = subprocess.run([self.executable, *args], input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=timeout,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            raise SetupError((result.stderr or result.stdout).decode('utf-8', 'replace').strip()[:800])
        return result.stdout.decode('utf-8', 'replace').strip()
    def devices(self):
        found = []
        for line in self.run('devices', '-l').splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0] != 'List' and not fields[0].startswith('*'):
                found.append((fields[0], fields[1]))
        return found
    def shell(self, script, root=False, timeout=30):
        if not self.serial: raise SetupError('Select one headset first')
        return self.run('-s', self.serial, 'shell', *(['su', '-c', 'sh'] if root else ['sh']),
                        data=(script+'\n').encode('utf-8'), timeout=timeout)
    def inspect(self):
        info = {}
        for key, prop in [('model','ro.product.model'),('device','ro.product.device'),
                          ('build','ro.build.version.incremental'),('android','ro.build.version.release')]:
            info[key] = self.shell('getprop '+prop)
        info['supported'] = (info['device'], info['build']) in TESTED
        info['singularity'] = self.shell('dumpsys package '+SINGULARITY+' | grep versionName= || true')
        try: info['root'] = self.shell('id', root=True)
        except (SetupError, subprocess.TimeoutExpired): info['root'] = ''
        info['ready'] = bool(re.search(r'\buid=0\(root\)', info['root']) and re.search(r'\bgid=0\(root\)', info['root']))
        return info
    def install(self, apk):
        path = Path(apk)
        if path.suffix.lower() != '.apk' or not path.is_file(): raise SetupError('Select an APK file')
        if not self.serial: raise SetupError('Select one headset first')
        return self.run('-s', self.serial, 'install', '--no-incremental', '-r', '-g', str(path), timeout=120)
    def push(self, local, remote):
        return self.run('-s', self.serial, 'push', str(local), remote)
    def launch(self, package):
        activities = {SINGULARITY: SINGULARITY+'/com.lumi.singularity.ui.activities.MainActivity',
                      PACKAGE: PACKAGE+'/.MainActivity'}
        return self.shell('am start -n '+activities[package])
    def install_official(self, apk):
        with Path(apk).open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != OFFICIAL_SHA256: raise SetupError('APK does not match the validated official Singularity 1.0.8.5 release.')
        return self.install(apk)

class Installer:
    def __init__(self, adb, resources): self.adb, self.resources = adb, Path(resources)
    def preflight(self):
        info = self.adb.inspect()
        if not info['supported']: raise SetupError('This model/build has not been validated. Setup is disabled; diagnostics remain available.')
        if 'versionName=1.0.8.5' not in info['singularity']: raise SetupError('This release requires official Singularity 1.0.8.5.')
        if not info['ready']: raise SetupError('Complete initial root in Singularity and grant shell root access first (uid=0 / gid=0).')
        for name in ('QuestSetupCompanion.apk', 'quest-root-normalize', 'ssw-wifi-admin.jar'):
            if not (self.resources/'artifacts'/name).is_file(): raise SetupError('Missing build artifact: '+name)
        for name in ('root-helper.sh','protect.sh','restore.sh','power.sh'):
            if not (self.resources/'payload'/name).is_file(): raise SetupError('Missing helper: '+name)
        return info
    def apply(self, profile, emit=lambda text: None):
        self.preflight()
        a = self.adb
        # This version uses an additive setup only; it never silently removes existing protection.
        if not profile.firmware: raise SetupError('Firmware protection is required by this setup profile.')
        a.shell('set -e; umask 077; mkdir -p '+BASE+'/backup '+BASE+'/files', root=True)
        for name in ('root-helper.sh', 'protect.sh', 'restore.sh', 'power.sh'):
            a.push(self.resources/'payload'/name, '/data/local/tmp/ssw-'+name)
        for name in ('QuestSetupCompanion.apk','quest-root-normalize','ssw-wifi-admin.jar'):
            a.push(self.resources/'artifacts'/name, '/data/local/tmp/ssw-'+name)
        # Back up before APK installation or preference changes; never overwrite the first snapshot.
        a.shell('sh /data/local/tmp/ssw-protect.sh snapshot', root=True)
        emit('backup')
        a.install(self.resources/'artifacts/QuestSetupCompanion.apk')
        pref_dir = '/data/user/0/'+SINGULARITY+'/shared_prefs/'
        patches = {
          'singularity_prefs.xml': {'root_on_boot':profile.auto_root, 'selected_exploit_binary':'KUGEL',
            'auto_reboot_on_exploit_fail':False},
          'payload_prefs.xml': {'payload_soft_reboot':False,'payload_disable_ota':False,
            'payload_bootanimation':False,'payload_singularity_magisk':True}}
        with tempfile.TemporaryDirectory(prefix='ssw-') as temp:
            for name, updates in patches.items():
                text = a.shell('cat '+shlex.quote(pref_dir+name), root=True)
                local = Path(temp)/name
                local.write_bytes(update_preferences(text, updates))
                a.push(local, '/data/local/tmp/ssw-'+name)
            wizard_path='/data/user/0/'+PACKAGE+'/shared_prefs/wizard.xml'
            text=a.shell('if [ -f '+wizard_path+' ]; then cat '+wizard_path+"; else echo '<map />'; fi",root=True)
            local=Path(temp)/'wizard.xml'
            local.write_bytes(update_preferences(text, {'auto_root':profile.auto_root}))
            a.push(local,'/data/local/tmp/ssw-wizard.xml')
        remote = '1' if profile.remote_actions else '0'
        script = f'''set -e
am force-stop {SINGULARITY}
am force-stop {PACKAGE}
for name in singularity_prefs.xml payload_prefs.xml; do
 target={pref_dir}$name
 owner=$(stat -c '%u:%g' "$target")
 cp /data/local/tmp/ssw-$name "$target"
 chown "$owner" "$target"
 chmod 660 "$target"
 restorecon "$target"
done
cp /data/local/tmp/ssw-quest-root-normalize /data/local/tmp/quest-root-normalize
cp /data/local/tmp/ssw-root-helper.sh /data/local/tmp/quest-root-helper.sh
chmod 755 /data/local/tmp/quest-root-normalize
chmod 700 /data/local/tmp/quest-root-helper.sh
cp /data/local/tmp/ssw-power.sh {BASE}/power.sh
cp /data/local/tmp/ssw-ssw-wifi-admin.jar /data/local/tmp/ssw-wifi-admin.jar
mkdir -p /data/user/0/{PACKAGE}/shared_prefs
helper_owner=$(stat -c '%u:%g' /data/user/0/{PACKAGE})
chown "$helper_owner" /data/user/0/{PACKAGE}/shared_prefs
cp /data/local/tmp/ssw-wizard.xml /data/user/0/{PACKAGE}/shared_prefs/wizard.xml
chown "$helper_owner" /data/user/0/{PACKAGE}/shared_prefs/wizard.xml
chmod 600 /data/user/0/{PACKAGE}/shared_prefs/wizard.xml
restorecon -R /data/user/0/{PACKAGE}/shared_prefs
cp /data/local/tmp/ssw-protect.sh {BASE}/protect.sh
cp /data/local/tmp/ssw-restore.sh {BASE}/restore.sh
chmod 700 {BASE}/*.sh
echo {remote} >{BASE}/remote-actions
mkdir -p /data/adb/service.d
printf '#!/system/bin/sh\\nsh {BASE}/protect.sh apply\\n' >/data/adb/service.d/65-singularity-setup-wizard.sh
chmod 700 /data/adb/service.d/65-singularity-setup-wizard.sh
sh {BASE}/protect.sh apply
'''
        try:
            a.shell(script, root=True, timeout=60)
        finally:
            # Release force-stop without invoking Root Now or rebooting.
            try: a.launch(SINGULARITY)
            except SetupError: pass
            try: a.launch(PACKAGE)
            except SetupError: pass
        if not profile.auto_root:a.shell('am stopservice -n '+PACKAGE+'/.RootService')
        report = a.inspect()
        report['protection'] = a.shell('sh '+BASE+'/protect.sh status',root=True)
        if not report['ready'] or 'update_engine=stopped' not in report['protection'] or 'package:com.oculus.updater' not in report['protection']:
            raise SetupError('Changes were applied, but verification is incomplete. Check status or restore the snapshot.')
        emit('applied')
        return report
    def restore(self):
        try:
            result = self.adb.shell('sh '+BASE+'/restore.sh',root=True,timeout=60)
        finally:
            try: self.adb.launch(SINGULARITY)
            except SetupError: pass
            try: self.adb.launch(PACKAGE)
            except SetupError: pass
        return result
