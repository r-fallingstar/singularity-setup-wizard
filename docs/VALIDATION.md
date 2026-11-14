# Validation scope

## Hardware evidence from the original helpers

The original local implementation was tested on Quest Pro / build 51503870035800340 / Singularity 1.0.8.5:

- Both normal official boot setup and the invalid-GID path were observed; after repair, ordinary `su -c id` returned UID/GID 0, including requests from shell UID 2000.
- A USB-disconnected power cycle restored root, and the user confirmed Virtual Desktop PC image display.
- Identity-based wireless ADB discovery and reconnection were tested, including IP change/offline behavior in mocks.
- Power-button-only sleep was confirmed by the user, including physical sleep and wake by button.
- A saved 6GHz BSSID pin, Wi-Fi off/on reconnection, a headset reboot, wireless ADB and actual Virtual Desktop image display were tested.

The historic kernel panic's precise cause was not established. Credential normalization fixed an independently reproduced user-space problem; it is not a claim to have fixed every kernel crash.

## New wizard release

The release introduces a new bilingual interface, installer preflight, snapshot restoration, optional controls and packaging. Prior helper evidence does **not** by itself validate the whole installer on a fresh device.

Release checks should record:

- Python tests: preserve unrelated XML preferences; reject unselected targets, unsupported builds, unavailable root and incorrect official APKs; restrict mDNS identity and handle IP changes/mismatches.
- Android compilation and APK signature verification.
- Windows executable build, preview in both languages, and read-only diagnostics on the existing supported device.
- Shell syntax validation on the target OS without running apply/restore.
- A staged-file and release-archive check for private files and credentials.

The firmware profile deliberately has no fallback that edits live PackageManager XML. Applying it on a fresh configuration can fail if the vendor blocks updater disablement. The GUI reports the error and provides restoration. Full end-to-end fresh-install and restore tests should be completed on a dedicated test headset before calling this stable. Do not describe this preview as universal protection.

## Release 0.1.0 checks — 2026-11-14

- 17 automated tests passed, including the actual Android package/component command distinction, explicit-device targeting, snapshot-before-install ordering, partial-failure cleanup, incomplete-verification rejection, and discovery identity checks.
- APK compiled for arm64/API 26+ and verified with APK Signature Schemes v2 and v3. The compatibility gate restricts modifications to the validated model/build.
- The new installer applied successfully on the existing configured test Quest Pro. The ordinary shell reported UID/GID 0, the firmware updater was disabled, and update_engine was stopped.
- Its snapshot restore completed, preserved previously disabled components and working root, and the same profile was successfully reapplied. The legacy AwakeService remained available. This was an upgrade/restore test on an already configured headset, not a factory-clean installation test.
- The firmware shell scripts passed Android shell syntax checks. Windows source compilation and executable packaging passed.
- This release did not repeat a fresh-device exploitation test. Virtual Desktop, unplugged boot, physical power-button sleep and 6GHz reboot evidence above comes from the preceding helper verification; those claims are not expanded to other builds.
