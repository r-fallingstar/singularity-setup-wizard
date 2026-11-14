# Building

Use Python 3.11+ with Tk, a JDK, Android SDK platform 35, build-tools 36.0.0, and an Android NDK capable of arm64 API 29. The original device verification used JDK 24 and NDK r21e. Windows releases are built on Windows.

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python android/build.py --java <JDK-directory> --ndk <NDK-directory>
.venv\Scripts\python tools/build_windows.py
```

Set `ANDROID_HOME` for a non-default SDK path. `JAVA_HOME` and `ANDROID_NDK_HOME` can replace the corresponding arguments. Build output goes to ignored `artifacts/`, `build/`, `dist/` and `release/` folders. The Windows ZIP contains the executable, companion APK and both READMEs. The executable includes the native normalizer, Wi-Fi administration JAR and shell helpers.

Signing keys are generated under `~/.singularity-setup-wizard/signing/`, **outside the repository**. Preserve and back up the same key for updates. Never commit or upload the key or its password file. To use an existing key, provide `--keystore`, `--password-file` and `--alias`; paths inside this repository are rejected. The release signing key is not part of the source archive. A different key cannot update an installed helper with the same app ID.

Preview without device writes:

```text
python desktop/run.py --preview --lang ja --preview-step 3
python desktop/run.py --preview --lang en --preview-step 0
```

Before publishing, review the **exact Git index and release ZIP contents**. Run `python tools/check_public_files.py` after staging. Never copy a working device folder wholesale: it can contain signing keys, ADB keys, dumps, backups, Wi-Fi credentials and personally identifying logs.

Singularity is downloaded by the end user from its author's official releases. Do not add its APK, decompiled code, bundled scripts, exploit binaries or images to this project. Public release packaging must contain only this project's own code plus the declared build runtime dependencies.
