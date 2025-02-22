# in order to put the cache / working-directory onto a tmpfs, you'll need to add an entry to /etc/fstab:

tmpfs   /tmp/rgb_cache  tmpfs   noauto,user 0 0
tmpfs   /tmp/rgb_cache  tmpfs   noauto,user,uid=1000,gid=1000,size=0,X-mount.mkdir    0 0

# or create/mount it manually (mounting filesystems normally requires root permissions):
mkdir /tmp/rgb_cache
mount --types tmpfs -o uid=1000,gid=1000,size=48g tmpfs /tmp/rgb_cache
mount --types tmpfs -o user,uid=1000,gid=1000,size=0,X-mount.mkdir tmpfs /tmp/rgb_cache

# 'size' can be an absolute size ('16g'), or percentage of total RAM ('75%'). default: "size=50%"
# "size=0" allows unlimited size

# 'X-mount.mkdir' - option allows creation of tmpfs without a pre-existing directory at the mountpoint
# 'noswap' - disables swapping from tmpfs (swapping enabled by default since 6.4)


mounting tmpfs only seems to work properly when the mountpoint has been created manually before running the script???
otherwise it claims permission denied, or it apparently succeeds, but the directory is not actually a tmpfs.
the full mount command seems less reliable than the simple command that relies on /etc/fstab


