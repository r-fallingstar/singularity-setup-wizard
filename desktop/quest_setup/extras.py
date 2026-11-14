from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import sys
from .core import SetupError
from .wireless import BASE

def startup_file():
    return Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup/Singularity Setup Wizard ADB.vbs'

def enable_wireless(adb):
    info=adb.inspect()
    if not info['supported'] or not info['ready']:raise SetupError('Wireless setup requires the validated headset/build and working root.')
    identity=adb.shell('getprop ro.serialno').strip()
    if not re.fullmatch(r'[A-Za-z0-9_-]{4,80}',identity):raise SetupError('Invalid headset identity')
    BASE.mkdir(parents=True,exist_ok=True)
    if getattr(sys,'frozen',False):
        binary=BASE.parent/'SingularitySetupWizard.exe'
        if binary.resolve()!=Path(sys.executable).resolve():shutil.copy2(sys.executable,binary)
        command=[str(binary),'--watch']
    else:
        binary=Path(sys.executable).with_name('pythonw.exe')
        if not binary.exists():binary=Path(sys.executable)
        command=[str(binary),str(Path(__file__).resolve().parents[1]/'run.py'),'--watch']
    # Persist only the selected headset identity and local ADB path; never keys.
    (BASE/'config.json').write_text(json.dumps({'serial':identity,'adb':adb.executable,'interval_seconds':15}),encoding='utf-8')
    adb.shell('runcon u:r:init:s0 setprop persist.adb.tcp.port 5555',root=True)
    adb.run('-s',adb.serial,'tcpip','5555')
    startup=startup_file();startup.parent.mkdir(parents=True,exist_ok=True)
    line=subprocess.list2cmdline(command).replace('"','""')
    startup.write_text('CreateObject("WScript.Shell").Run "'+line+'", 0, False\r\n',encoding='utf-16')
    subprocess.Popen(command,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return 'Wireless ADB auto-connect enabled for the selected headset. Discovery follows its identity, not a fixed IP.'

def disable_wireless():
    BASE.mkdir(parents=True,exist_ok=True)
    (BASE/'stop.request').touch()
    startup_file().unlink(missing_ok=True)
    return 'PC auto-connect disabled. Headset wireless ADB settings are unchanged.'
