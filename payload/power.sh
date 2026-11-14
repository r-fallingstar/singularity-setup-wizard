#!/system/bin/sh
set -eu
[ "$(id -u)" = 0 ] || exit 40
case "${1:-}" in
enabled)
    oculuspreferences --setc autosleep_time -1
    am broadcast -a com.oculus.vrpowermanager.prox_close
    cat >/data/adb/service.d/80-ssw-manual-sleep.sh <<'HOOK'
#!/system/bin/sh
PREF=/data/user/0/com.codex.questroothelper/shared_prefs/power_settings.xml
grep -q 'name="manual_sleep_only" value="true"' "$PREF" || exit 0
oculuspreferences --setc autosleep_time -1
am broadcast -a com.oculus.vrpowermanager.prox_close
am start-foreground-service -n com.codex.questroothelper/.AwakeService
HOOK
    chmod 700 /data/adb/service.d/80-ssw-manual-sleep.sh
    ;;
disabled)
    oculuspreferences --setc autosleep_time 60
    rm -f /data/adb/service.d/80-ssw-manual-sleep.sh
    ;;
*) exit 64;;
esac
