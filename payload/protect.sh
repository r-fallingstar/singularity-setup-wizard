#!/system/bin/sh
# Firmware-only profile; no hosts, firewall, DNS, account or app-updater changes.
set -eu
BASE=/data/adb/singularity-setup-wizard
BACK=$BASE/backup
UPDATER=com.oculus.updater
COMPONENTS='com.oculus.nux.ota/.NuxOtaIntentService'
REMOTE='com.oculus.companion.server/.RemoteWipeJobService com.oculus.companion.server/.DisabledDeviceJobService com.oculus.companion.server/.WipeReceiver'
[ "$(id -u)" = 0 ] || exit 40
mkdir -p "$BASE" "$BACK"

snapshot() {
    [ ! -f "$BACK/complete" ] || return 0
    umask 077
    # Refuse to pretend that a partially written snapshot is complete.
    for name in singularity_prefs.xml payload_prefs.xml; do
        source=/data/user/0/com.lumi.singularity/shared_prefs/$name
        [ -f "$source" ] || { echo "Missing Singularity preferences: $name"; exit 41; }
        cp -p "$source" "$BACK/$name"
    done
    settings get global ota_update_server_url >"$BACK/ota_update_server_url"
    settings get global ota_download_url >"$BACK/ota_download_url"
    pm list packages -d --user 0 >"$BACK/disabled-packages"
    dumpsys package "$UPDATER" >"$BACK/updater-package"
    grep -q 'User 0:.*enabled=[0-4]' "$BACK/updater-package" || { echo 'Cannot snapshot updater state'; exit 46; }
    # Package dump preserves whether each named component was default/enabled/disabled.
    dumpsys package com.oculus.nux.ota >"$BACK/nux-package"
    dumpsys package com.oculus.companion.server >"$BACK/companion-package"
    helper=/data/user/0/com.codex.questroothelper/shared_prefs/wizard.xml
    if [ -f "$helper" ]; then cp -p "$helper" "$BACK/wizard.xml"; fi
    touch "$BACK/complete"
}

disable() {
    target=$1
    # Existing disabled packages need no new permission or state transition.
    pm list packages -d --user 0 | grep -qx "package:$target" && return 0
    case "$target" in
        */*) su 1000 -c "pm disable --user 0 $target";;
        *) su 1000 -c "pm disable-user --user 0 $target";;
    esac
}

case "${1:-status}" in
snapshot) snapshot ;;
apply)
    [ -f "$BACK/complete" ] || { echo 'Take a snapshot before applying'; exit 42; }
    settings put global ota_update_server_url http://127.0.0.1/
    settings put global ota_download_url http://127.0.0.1/
    # If the firmware package is protected on a different build, fail visibly.
    # Never edit Android's live package-restrictions.xml behind PackageManager.
    disable "$UPDATER" || { echo 'Firmware updater could not be disabled; setup is incomplete'; exit 43; }
    for component in $COMPONENTS; do disable "$component" || exit 44; done
    if [ "$(cat "$BASE/remote-actions" 2>/dev/null)" = 1 ]; then
        for component in $REMOTE; do disable "$component" || exit 45; done
    fi
    update_engine_client --cancel 2>/dev/null || true
    stop update_engine
    stop update_verifier_nonencrypted 2>/dev/null || true
    stop update_verifier 2>/dev/null || true
    if ! cmp -s /proc/sys/kernel/random/boot_id "$BASE/mounts-boot-id"; then
        : >"$BASE/mounts-created"
        cp /proc/sys/kernel/random/boot_id "$BASE/mounts-boot-id"
    fi
    # Transient bind mounts disappear on reboot; the root boot hook reapplies them.
    for target in /system/bin/update_engine /system/bin/update_engine_client /system/bin/update_verifier; do
        [ -f "$target" ] || continue
        if ! grep -q " $target " /proc/mounts; then
            mount -o bind /system/bin/true "$target"
            echo "$target" >>"$BASE/mounts-created"
        fi
    done
    echo 'Firmware profile applied. App updates, account services and network policy were not changed.'
    ;;
status)
    echo "update_engine=$(getprop init.svc.update_engine)"
    echo "ota_update_server_url=$(settings get global ota_update_server_url)"
    pm list packages -d --user 0 | grep -x "package:$UPDATER" || true
    ;;
*) exit 64 ;;
esac
