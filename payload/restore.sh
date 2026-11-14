#!/system/bin/sh
# Restore only this wizard's snapshot. Keep pre-existing restrictions intact.
set -eu
BASE=/data/adb/singularity-setup-wizard
BACK=$BASE/backup
[ "$(id -u)" = 0 ] || exit 40
[ -f "$BACK/complete" ] || { echo 'No complete wizard snapshot'; exit 41; }
updater_state=$(sed -n '/^[ ]*User 0:/s/.*enabled=\([0-4]\).*/\1/p' "$BACK/updater-package" | head -n 1)
case "$updater_state" in [0-4]) ;; *) echo 'Invalid updater snapshot'; exit 42;; esac
am force-stop com.lumi.singularity
am force-stop com.codex.questroothelper
helper=/data/user/0/com.codex.questroothelper/shared_prefs/wizard.xml
if [ -f "$BACK/wizard.xml" ]; then
    cp -p "$BACK/wizard.xml" "$helper"; restorecon "$helper"
else
    rm -f "$helper"
fi
for name in singularity_prefs.xml payload_prefs.xml; do
    target=/data/user/0/com.lumi.singularity/shared_prefs/$name
    cp -p "$BACK/$name" "$target"
    restorecon "$target"
done
for key in ota_update_server_url ota_download_url; do
    value=$(cat "$BACK/$key")
    if [ "$value" = null ]; then settings delete global "$key"; else settings put global "$key" "$value"; fi
done
current_updater_state=$(dumpsys package com.oculus.updater | sed -n '/^[ ]*User 0:/s/.*enabled=\([0-4]\).*/\1/p' | head -n 1)
if [ "$updater_state" != "$current_updater_state" ]; then
case "$updater_state" in
    0) su 1000 -c 'pm default-state --user 0 com.oculus.updater';;
    1) su 1000 -c 'pm enable --user 0 com.oculus.updater';;
    2) su 1000 -c 'pm disable --user 0 com.oculus.updater';;
    3) su 1000 -c 'pm disable-user --user 0 com.oculus.updater';;
    4) su 1000 -c 'pm disable-until-used --user 0 com.oculus.updater';;
    *) echo 'Snapshot has no updater enabled state; stopping restoration'; exit 42;;
esac
fi
# Restore the named component overrides from the user-0 dump only.
restore_component() {
    component=$1; dump=$2; full=$3
    # Only the user 0 section is relevant. Other users cannot influence restoration.
    state=$(awk -v name="$full" '
        /^[ ]*User 0:/ {user=1; section=""; next}
        /^[ ]*User [1-9][0-9]*:/ {user=0}
        user && /enabledComponents:/ {section="enable"; next}
        user && /disabledComponents:/ {section="disable"; next}
        user && /^[ ]*[A-Za-z][A-Za-z ]*:/ {section=""}
        user && $1==name {print section; exit}
    ' "$dump")
    case "$state" in enable) action=enable;; disable) action=disable;; *) action=default-state;; esac
    su 1000 -c "pm $action --user 0 $component"
}
restore_component com.oculus.nux.ota/.NuxOtaIntentService "$BACK/nux-package" com.oculus.nux.ota.NuxOtaIntentService
if [ "$(cat "$BASE/remote-actions" 2>/dev/null)" = 1 ]; then
    for cls in RemoteWipeJobService DisabledDeviceJobService WipeReceiver; do
        restore_component "com.oculus.companion.server/.$cls" "$BACK/companion-package" "com.oculus.companion.server.$cls"
    done
fi
if [ -f "$BASE/mounts-created" ] && cmp -s /proc/sys/kernel/random/boot_id "$BASE/mounts-boot-id"; then
    while read -r target; do
        case "$target" in
            /system/bin/update_engine|/system/bin/update_engine_client|/system/bin/update_verifier)
                grep -q " $target " /proc/mounts && umount "$target" || true;;
        esac
    done <"$BASE/mounts-created"
    rm -f "$BASE/mounts-created"
fi
rm -f /data/adb/service.d/65-singularity-setup-wizard.sh
echo 'Wizard profile restored. Reboot manually to clear transient root state.'
