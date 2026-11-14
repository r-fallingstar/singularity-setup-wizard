from pathlib import Path
import subprocess
import sys
import os
from package_release import main as package_release

root=Path(__file__).resolve().parents[1]
build_env=os.environ.copy()
# Prefer this Python installation's DLLs over unrelated tools on the host PATH.
build_env['PATH']=str(Path(sys.base_prefix)/'Library/bin')+os.pathsep+str(Path(sys.base_prefix)/'DLLs')+os.pathsep+build_env.get('PATH','')
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed',
    '--name','SingularitySetupWizard','--paths',str(root/'desktop'),
    '--add-data',str(root/'payload')+':payload','--add-data',str(root/'artifacts')+':artifacts',
    '--distpath',str(root/'dist'),'--workpath',str(root/'build/pyinstaller'),
    '--specpath',str(root/'build'),str(root/'desktop/run.py')],cwd=root,env=build_env,check=True)
package_release()
