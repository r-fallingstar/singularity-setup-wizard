"""Package only declared public artifacts, never a whole working directory."""
from pathlib import Path
import hashlib
import shutil
import zipfile

def main():
    root=Path(__file__).resolve().parents[1]
    release=root/'release';release.mkdir(exist_ok=True)
    version='0.1.1'
    apk=release/f'QuestSetupCompanion-{version}.apk'
    archive=release/f'SingularitySetupWizard-{version}-windows.zip'
    shutil.copy2(root/'artifacts/QuestSetupCompanion.apk',apk)
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in (root/'dist/SingularitySetupWizard.exe',root/'artifacts/QuestSetupCompanion.apk',root/'README.md',root/'README.ja.md',root/'LICENSE'):
            z.write(path,path.name)
        for path in sorted((root/'docs').rglob('*')):
            if path.is_file() and path.suffix in ('.md','.png','.txt'):
                z.write(path,path.relative_to(root).as_posix())
    lines=[]
    for path in sorted([archive,apk]):
        lines.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+path.name)
    (release/'SHA256SUMS.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Packaged Windows ZIP, companion APK, and SHA256SUMS.txt')

if __name__=='__main__':main()
