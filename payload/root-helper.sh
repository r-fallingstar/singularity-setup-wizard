#!/system/bin/sh
# Runs only after the official Singularity exploit has already obtained uid 0.
# No kernel writes, firmware flashing, network filtering or account changes.
PATH=/debug_ramdisk:/system/bin:/system/xbin:$PATH
mkdir /dev/.quest-root-helper-lock 2>/dev/null || exit 0
trap 'rmdir /dev/.quest-root-helper-lock' EXIT
mkdir -p /data/adb/singularity
exec >>/data/adb/singularity/root-helper.log 2>&1
echo "=== $(date) action=$1 uid=$(id -u) gid=$(id -g) ==="
if [ -z "$(pidof magiskd)" ]; then
    [ "$1" = bootstrap ] || exit 11
    [ -s /data/local/tmp/singularity_magisk.sh ] || exit 12
    [ -s /data/local/tmp/singularity-Magisk.apk ] || exit 13
    sh /data/local/tmp/singularity_magisk.sh || exit 14
fi
daemon=$(pidof magiskd | awk '{print $1}')
[ -n "$daemon" ] || exit 15
daemon_gid=$(awk '/^Gid:/{print $2}' "/proc/$daemon/status")
if [ "$daemon_gid" != 0 ]; then
    # Retain existing mounts and policy database; restart just the daemon with
    # normal user-space credentials. Existing privileged clients stay alive.
    kill -KILL "$daemon" || exit 16
    /debug_ramdisk/magisk64 --daemon || true
fi
sleep 1
daemon=$(pidof magiskd | awk '{print $1}')
[ -n "$daemon" ] || exit 18
awk '/^Uid:|^Gid:|^Groups:|^CapInh:/{print}' "/proc/$daemon/status"
daemon_gid=$(awk '/^Gid:/{print $2}' "/proc/$daemon/status")
[ "$daemon_gid" = 0 ] || exit 19
chmod 755 /debug_ramdisk/.magisk /debug_ramdisk/.magisk/device
su -c id || exit 20
su 2000 -c 'su -c id' || exit 21
cat /proc/sys/kernel/random/boot_id >/data/adb/singularity/root-helper-ready
chmod 600 /data/adb/singularity/root-helper-ready
echo ROOT_HELPER_READY
