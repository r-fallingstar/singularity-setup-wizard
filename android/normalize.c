#define _GNU_SOURCE
#include <unistd.h>
#include <grp.h>
#include <linux/capability.h>
#include <sys/syscall.h>
#include <sys/stat.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (getuid() != 0 || argc < 2) return 64;
    gid_t group = 0;
    if (setgroups(1, &group) || setresgid(0, 0, 0) || setresuid(0, 0, 0)) {
        perror("normalize credentials"); return 65;
    }
    struct __user_cap_header_struct header = {_LINUX_CAPABILITY_VERSION_3, 0};
    struct __user_cap_data_struct caps[2] = {{0}};
    if (syscall(SYS_capget, &header, caps)) return 66;
    caps[0].inheritable = caps[1].inheritable = 0;
    caps[1].effective &= 0x3f;
    caps[1].permitted &= 0x3f;
    if (syscall(SYS_capset, &header, caps)) return 67;
    // Magisk's client-accessible runtime directories must be traversable.
    // Private application data and helper status files set their own modes.
    umask(0022);
    execvp(argv[1], argv + 1);
    perror("exec"); return 68;
}
