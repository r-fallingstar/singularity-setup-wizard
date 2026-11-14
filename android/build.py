"""Build with local Android SDK/NDK and a signing key kept outside this repository."""
from pathlib import Path
import argparse
import os
import secrets
import subprocess
import zipfile

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--sdk',default=os.environ.get('ANDROID_HOME',str(Path.home()/'AppData/Local/Android/Sdk')))
    p.add_argument('--java',default=os.environ.get('JAVA_HOME',''))
    p.add_argument('--ndk',default=os.environ.get('ANDROID_NDK_HOME',''))
    p.add_argument('--key-dir',default=str(Path.home()/'.singularity-setup-wizard/signing'))
    p.add_argument('--keystore');p.add_argument('--password-file');p.add_argument('--alias',default='wizard')
    a=p.parse_args(); root=Path(__file__).resolve().parent; repo=root.parent
    sdk=Path(a.sdk); java=Path(a.java)/'bin'; android=sdk/'platforms/android-35/android.jar'
    bt=sdk/'build-tools/36.0.0'; ndk=Path(a.ndk)
    build=root/'build'; out=repo/'artifacts';out.mkdir(exist_ok=True)
    for name in ('classes','dex'): (build/name).mkdir(parents=True,exist_ok=True)
    def exe(name): return java/(name+'.exe' if os.name=='nt' else name)
    def run(items): subprocess.run([str(x) for x in items],check=True)
    clang=ndk/'toolchains/llvm/prebuilt'/('windows-x86_64' if os.name=='nt' else 'linux-x86_64')/'bin'/('clang.exe' if os.name=='nt' else 'clang')
    if not clang.is_file(): raise SystemExit('Set ANDROID_NDK_HOME or --ndk to an Android NDK installation.')
    run([clang,'--target=aarch64-linux-android29','-O2','-Wall','-Wextra','-fPIE','-pie',root/'normalize.c','-o',out/'quest-root-normalize'])
    run([exe('javac'),'-encoding','UTF-8','-source','8','-target','8','-bootclasspath',android,'-d',build/'classes',*root.glob('src/**/*.java')])
    run([exe('java'),'-cp',bt/'lib/d8.jar','com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',build/'dex',*build.glob('classes/**/*.class')])
    (build/'wifi-classes').mkdir(exist_ok=True);(build/'wifi-dex').mkdir(exist_ok=True)
    run([exe('javac'),'-encoding','UTF-8','-source','8','-target','8','-bootclasspath',android,'-d',build/'wifi-classes',root/'wifi/QuestWifiAdmin.java'])
    run([exe('java'),'-cp',bt/'lib/d8.jar','com.android.tools.r8.D8','--min-api','26','--lib',android,'--output',build/'wifi-dex',build/'wifi-classes/QuestWifiAdmin.class'])
    with zipfile.ZipFile(out/'ssw-wifi-admin.jar','w',zipfile.ZIP_DEFLATED) as z:z.write(build/'wifi-dex/classes.dex','classes.dex')
    unsigned=build/'unsigned.apk'; aligned=build/'aligned.apk'
    run([bt/('aapt.exe' if os.name=='nt' else 'aapt'),'package','-f','-M',root/'AndroidManifest.xml','-I',android,'-F',unsigned])
    with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as z:z.write(build/'dex/classes.dex','classes.dex')
    run([bt/('zipalign.exe' if os.name=='nt' else 'zipalign'),'-f','4',unsigned,aligned])
    keydir=Path(a.key_dir).resolve()
    if keydir.is_relative_to(repo.resolve()): raise SystemExit('Signing files must be outside the repository.')
    keydir.mkdir(parents=True,exist_ok=True)
    key=Path(a.keystore) if a.keystore else keydir/'wizard.p12'
    password=Path(a.password_file) if a.password_file else keydir/'password.txt'
    if key.resolve().is_relative_to(repo.resolve()) or password.resolve().is_relative_to(repo.resolve()):
        raise SystemExit('Signing files must be outside the repository.')
    if not key.exists():
        if a.keystore: raise SystemExit('Specified signing key was not found.')
        password.write_text(secrets.token_hex(24),encoding='utf-8')
        run([exe('keytool'),'-genkeypair','-keystore',key,'-storepass:file',password,'-keypass:file',password,'-alias',a.alias,'-keyalg','RSA','-keysize','3072','-validity','3650','-dname','CN=Singularity Setup Wizard'])
    run([exe('java'),'-jar',bt/'lib/apksigner.jar','sign','--ks',key,'--ks-key-alias',a.alias,'--ks-pass','file:'+str(password),'--out',out/'QuestSetupCompanion.apk',aligned])
    run([exe('java'),'-jar',bt/'lib/apksigner.jar','verify','--verbose',out/'QuestSetupCompanion.apk'])

if __name__=='__main__': main()
