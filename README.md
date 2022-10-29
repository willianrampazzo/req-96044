# req-96044

## System configuration

Make sure to do the following configurations on your system before running the
test.

Note: the instructions assume you are running a fedora system.

### Install libvirt-devel package

```
sudo dnf install libvirt-devel
```

### Update the libvirtd.conf

Uncomment the following options on your `/etc/libvirt/libvirtd.conf` file:

```
unix_sock_group = "libvirt"
unix_sock_rw_perms = "0770"
```

### Update the qemu.conf

Uncomment and update the following options on your `/etc/libvirt/libvirtd.conf`
file:

```
user = "willianr"
group = "libvirt"
```

## Running the test

As the tests are using the same disk definition, it is not possible to run them
in parallel. Make sure to use the `--nrunner-max-parallel-tasks=1` to run it.

```
avocado run --nrunner-max-parallel-tasks=1 disk_hotplug.py
```
