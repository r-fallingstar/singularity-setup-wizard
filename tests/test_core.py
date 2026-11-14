import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import subprocess
import os

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from quest_setup.core import Adb, Installer, Profile, SetupError, update_preferences
from quest_setup.strings import COPY, tr
from quest_setup.wireless import Connector, parse_mdns

class CoreTests(unittest.TestCase):
    def test_preferences_preserve_unrelated_values_and_remove_duplicates(self):
        xml='<map><string name="language">ja</string><boolean name="root_on_boot" value="false"/><boolean name="root_on_boot" value="false"/></map>'
        root=ET.fromstring(update_preferences(xml,{'root_on_boot':True}))
        self.assertEqual(root.find("string[@name='language']").text,'ja')
        self.assertEqual(len(root.findall("boolean[@name='root_on_boot']")),1)
        self.assertEqual(root.find("boolean[@name='root_on_boot']").get('value'),'true')
    def test_shell_requires_explicit_target(self):
        with patch('subprocess.run') as run:
            with self.assertRaises(SetupError):Adb('adb.exe').shell('id',root=True)
            run.assert_not_called()
    def test_shell_uses_stdin_and_argv_not_host_shell(self):
        with patch('subprocess.run') as run:
            run.return_value.returncode=0;run.return_value.stdout=b'uid=0';run.return_value.stderr=b''
            Adb('adb.exe','EXAMPLE_SERIAL').shell('echo "literal; value"',root=True)
            args,kwargs=run.call_args
            self.assertEqual(args[0],['adb.exe','-s','EXAMPLE_SERIAL','shell','su','-c','sh'])
            self.assertFalse(kwargs.get('shell',False))
            self.assertEqual(kwargs['input'],b'echo "literal; value"\n')
    def test_unsupported_build_cannot_mutate(self):
        class Fake:
            def inspect(self):return {'supported':False}
            def shell(self,*a,**k):raise AssertionError('Mutation attempted')
        with self.assertRaises(SetupError):Installer(Fake(),'.').apply(Profile())
    def test_no_root_cannot_mutate(self):
        class Fake:
            def inspect(self):return {'supported':True,'singularity':'versionName=1.0.8.5','ready':False}
            def shell(self,*a,**k):raise AssertionError('Mutation attempted')
        with self.assertRaises(SetupError):Installer(Fake(),'.').apply(Profile())
    def test_wrong_official_apk_is_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            apk=Path(tmp)/'wrong.apk';apk.write_bytes(b'not-official')
            with patch.object(Adb,'install') as install:
                with self.assertRaises(SetupError):Adb('adb.exe','EXAMPLE_SERIAL').install_official(apk)
                install.assert_not_called()
    def test_all_copy_has_both_languages(self):
        for key,values in COPY.items():
            self.assertEqual(len(values),2,key)
            self.assertTrue(all(values),key)
            self.assertEqual(tr(key,'ja'),values[0]);self.assertEqual(tr(key,'en'),values[1])
        self.assertEqual(len(tr('steps','ja').split('|')),len(tr('steps','en').split('|')))
    def test_optional_remote_actions_default_off(self):
        self.assertFalse(Profile().remote_actions)

class DiscoveryTests(unittest.TestCase):
    def test_excludes_other_devices_and_pairing_ports(self):
        self.assertEqual(parse_mdns('adb-EXAMPLE_SERIAL _adb._tcp 192.0.2.10:5555\nadb-OTHER _adb._tcp 192.0.2.11:5555\nadb-EXAMPLE_SERIAL _adb-tls-pairing._tcp 192.0.2.10:30000','EXAMPLE_SERIAL'),['192.0.2.10:5555'])
    def test_changed_ip_is_discovered_and_verified(self):
        calls=[];connected=set()
        def run(*args):
            calls.append(args)
            if args==('devices','-l'):return 'List of devices attached\n'+('192.0.2.20:5555 device transport_id:1\n' if connected else '')
            if args==('mdns','services'):return 'adb-EXAMPLE_SERIAL _adb._tcp 192.0.2.20:5555'
            if args==('connect','192.0.2.20:5555'):connected.add(True);return 'connected'
            if args==('-s','192.0.2.20:5555','shell','getprop','ro.serialno'):return 'EXAMPLE_SERIAL'
            raise AssertionError(args)
        with tempfile.TemporaryDirectory() as tmp:
            connector=Connector('EXAMPLE_SERIAL',run,Path(tmp)/'status.json')
            self.assertEqual(connector.tick()['endpoint'],'192.0.2.20:5555')
        self.assertNotIn(('kill-server',),calls)
    def test_identity_mismatch_disconnects_only_new_candidate(self):
        calls=[];connected=set()
        def run(*args):
            calls.append(args)
            if args==('devices','-l'):return '192.0.2.20:5555 device transport_id:1' if connected else ''
            if args==('mdns','services'):return 'adb-EXAMPLE_SERIAL _adb._tcp 192.0.2.20:5555'
            if args[0]=='connect':connected.add(True);return ''
            if args[0]=='disconnect':return ''
            return 'OTHER_SERIAL'
        with tempfile.TemporaryDirectory() as tmp:
            result=Connector('EXAMPLE_SERIAL',run,Path(tmp)/'status.json').tick()
        self.assertEqual(result['state'],'waiting')
        self.assertIn(('disconnect','192.0.2.20:5555'),calls)

class InstallerTests(unittest.TestCase):
    class FakeAdb:
        def __init__(self,fail_apply=False):self.calls=[];self.fail_apply=fail_apply
        def shell(self,script,**kwargs):
            self.calls.append(('shell',script))
            if script.startswith('cat ') or script.startswith('if [ -f '):return '<map><string name="keep">value</string></map>'
            if script.startswith('set -e\nam force-stop') and self.fail_apply:raise SetupError('apply failed')
            if script.endswith('/protect.sh status'):return 'update_engine=stopped\npackage:com.oculus.updater'
            return 'test status'
        def push(self,local,remote):self.calls.append(('push',remote))
        def install(self,local):self.calls.append(('install',str(local)))
        def launch(self,package):self.calls.append(('launch',package))
        def inspect(self):return {'ready':True}
    def installer(self,adb):
        installer=Installer(adb,Path(__file__).resolve().parents[1])
        installer.preflight=lambda:{'ready':True}
        return installer
    def test_snapshot_precedes_install_and_preferences(self):
        adb=self.FakeAdb();self.installer(adb).apply(Profile())
        snapshot=next(i for i,v in enumerate(adb.calls) if v==('shell','sh /data/local/tmp/ssw-protect.sh snapshot'))
        install=next(i for i,v in enumerate(adb.calls) if v[0]=='install')
        mutation=next(i for i,v in enumerate(adb.calls) if v[0]=='shell' and v[1].startswith('set -e\nam force-stop'))
        self.assertLess(snapshot,install);self.assertLess(install,mutation)
        script=adb.calls[mutation][1]
        self.assertIn("owner=$(stat -c '%u:%g'",script)
        self.assertIn('echo 0 >',script)
    def test_failure_releases_singularity_force_stop(self):
        adb=self.FakeAdb(fail_apply=True)
        with self.assertRaises(SetupError):self.installer(adb).apply(Profile())
        self.assertEqual(adb.calls[-2:],[('launch','com.lumi.singularity'),('launch','com.codex.questroothelper')])
    def test_restore_failure_still_reopens_singularity(self):
        adb=self.FakeAdb()
        def fail(*args,**kwargs):raise SetupError('restore failed')
        adb.shell=fail
        with self.assertRaises(SetupError):self.installer(adb).restore()
        self.assertEqual(adb.calls[-2:],[('launch','com.lumi.singularity'),('launch','com.codex.questroothelper')])
    def test_disabled_firmware_profile_cannot_write(self):
        adb=self.FakeAdb()
        with self.assertRaises(SetupError):self.installer(adb).apply(Profile(firmware=False))
        self.assertEqual(adb.calls,[])
    def test_incomplete_verification_is_not_success(self):
        adb=self.FakeAdb();adb.inspect=lambda:{'ready':False}
        progress=[]
        with self.assertRaises(SetupError):self.installer(adb).apply(Profile(),progress.append)
        self.assertNotIn('applied',progress)

class AndroidCommandTests(unittest.TestCase):
    def test_component_uses_disabled_not_disabled_user(self):
        bash=Path('C:/Program Files/Git/bin/bash.exe')
        if not bash.is_file():self.skipTest('Git Bash not installed')
        source=(Path(__file__).resolve().parents[1]/'payload/protect.sh').read_text()
        function=source[source.index('disable() {'):source.index('\ncase "${1:-status}"')]
        mock='pm() { return 0; }\nsu() { printf "%s\\n" "$*"; }\n'
        result=subprocess.run([str(bash),'--noprofile','--norc','-c',mock+function+'\ndisable com.example/.Service\ndisable com.example'],capture_output=True,text=True,check=True)
        self.assertEqual(result.stdout.splitlines(),['1000 -c pm disable --user 0 com.example/.Service','1000 -c pm disable-user --user 0 com.example'])

class DaemonRestartTests(unittest.TestCase):
    def run_daemon_simulation(self,behavior):
        bash=Path('C:/Program Files/Git/bin/bash.exe')
        if not bash.is_file():self.skipTest('Git Bash not installed')
        source=(Path(__file__).resolve().parents[1]/'payload/root-helper.sh').read_text()
        functions=source[source.index('daemon_pid() {'):source.index('\nensure_normal_daemon ||')]
        return subprocess.run([str(bash),'--noprofile','--norc','-c',functions+'\n'+behavior],capture_output=True,text=True,check=True).stdout
    def test_bad_gid_waits_and_recovers_after_one_startup_reset(self):
        output=self.run_daemon_simulation('''
state=bad; starts=0; kills=0; waits=0
daemon_pid() { [ "$state" != none ] && echo 42; }
daemon_group() { if [ "$state" = good ]; then echo 0; else echo 999; fi; }
start_daemon() { starts=$((starts+1)); [ "$starts" = 1 ] && return 1; state=good; }
kill() { kills=$((kills+1)); state=none; }
sleep() { waits=$((waits+1)); }
chmod() { :; }
su() { [ "$state" = good ]; }
ensure_normal_daemon || exit 99
printf 'RESULT %s %s %s\\n' "$starts" "$kills" "$waits"
''')
        self.assertIn('RESULT 2 1 3',output)
    def test_daemon_failure_is_bounded(self):
        output=self.run_daemon_simulation('''
starts=0
daemon_pid() { :; }
start_daemon() { starts=$((starts+1)); return 1; }
sleep() { :; }
if ensure_normal_daemon; then exit 99; else printf 'RESULT %s %s\\n' "$?" "$starts"; fi
''')
        self.assertIn('RESULT 18 8',output)

if __name__=='__main__':unittest.main()
