# in order to put the cache / working-directory onto a tmpfs, you'll need to add an entry to /etc/fstab:
tmpfs   /tmp/rgb_cache  tmpfs   noauto,user,uid=1000,gid=1000,X-mount.mkdir    0 0

# or create/mount it manually (mount requires root permissions here):
mkdir /tmp/rgb_cache
sudo mount --types tmpfs -o user,uid=1000,gid=1000,X-mount.mkdir tmpfs /tmp/rgb_cache

# you can add an option to control size of tmpfs like this: 'size=32g'
# 'size' can be an absolute size ('32g'), or percentage of total RAM ('75%'). default: "size=50%"
# "size=0" allows unlimited size

# 'X-mount.mkdir' - option allows creation of tmpfs without a pre-existing directory at the mountpoint
# 'noswap' - disables swapping from tmpfs (swapping enabled by default since 6.4)
# 'noauto' - don't automount (on boot)

'noauto' is important because otherwise the mountpoint will be created with root ownership (regardless of uid/gid option)
which consequently requires root-permissions to mount onto and unmount. (no such restriction if mountpoint is user-created)

RGBifier cannot create the tmpfs automatically unless an entry has been added to '/etc/fstab';
mounting filesystems normally requires root permissions

