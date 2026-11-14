"""Validate exactly staged source paths; never scan private working directories."""
from pathlib import Path
import re
import subprocess

root=Path(__file__).resolve().parents[1]
paths=subprocess.check_output(['git','ls-files','--cached','-z'],cwd=root).decode().split('\0')
bad=[]
for name in filter(None,paths):
    path=Path(name)
    if path.suffix.lower() in ('.p12','.jks','.keystore','.apk','.exe','.zip','.log') or any(part in ('artifacts','build','dist','release','.venv') for part in path.parts):
        bad.append(name+': disallowed published path');continue
    content=subprocess.check_output(['git','show',':'+name],cwd=root).decode('utf-8','replace')
    # Deliberately report only file names, never a matched secret.
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{30,}',content):
        bad.append(name+': possible private key/token')
if bad:raise SystemExit('\n'.join(bad))
print('Staged source check passed:',len(list(filter(None,paths))),'files')
