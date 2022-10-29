import libvirt
import os
import time

from avocado import Test
from avocado.utils.process import run
from avocado.utils.ssh import Session
from xml.dom import minidom

# Guest parameters
URI = "qemu:///system"
DOMAIN = "fedora36"
USERNAME = "avocado"
PASSWORD = "avocado"

# hotplug disk configuration
TARGET_DEV = 'vdb'
DISK_XML_CONTENT = """<disk type='file' device='disk'>
   <driver name='qemu' type='raw' cache='none'/>
   <source file='%s'/>
   <target dev='%s'/>
</disk>
"""

def start_guest():
    """
    Start a guest by its domain name

    :return: guest information or None if an exception happens
    :rtype: dict
    """
    # connect with the hypervisor URI
    try:
        conn = libvirt.open(URI)
    except libvirt.libvirtError:
        return None

    # look for the domain
    try:
        dom = conn.lookupByName(DOMAIN)
    except libvirt.libvirtError:
        return None

    # bring the domain up
    try:
        dom.create()
    except libvirt.libvirtError as e:
        if not 'domain is already running' in e.err:
            return None

    # look for the domain IP address
    source = libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE
    # when the guest is started for the first time in the hypervisor, the
    # network information is still not available. After the first boot, the
    # IP will be available as soon as the guest starts.
    for i in range(10):
        try:
            ip = list(dom.interfaceAddresses(
                source).items())[0][1]['addrs'][0]['addr']
            break
        except IndexError:
            time.sleep(i)

    # guest information
    guest = {'conn': conn,
             'dom': dom,
             'ip': ip}
    return guest


def stop_guest(guest):
    """
    Stop a guest

    :return: True or None if an exception happens
    :rtype: bool
    """
    # shutdown the guest
    try:
        guest['dom'].shutdown()
    except libvirt.libvirtError:
        return None

    # close the connection with the hypervisor URI
    try:
        guest['conn'].close()
    except libvirt.libvirtError:
        return None
    return True


def attach_device(domain, path, device_name):
    """Attach a device to a guest"""
    domain.attachDevice(DISK_XML_CONTENT % (path, device_name))


def detach_device(domain, path, device_name):
    """Detach a device from a guest"""
    domain.detachDevice(DISK_XML_CONTENT % (path, device_name))


def get_disks_available_libvirt(domain):
    """
    Get the disks objects available to the guest on the libvirt side

    :return: list of disks objects
    :rtype: list
    """
    raw_xml = domain.XMLDesc()
    xml = minidom.parseString(raw_xml)
    disks = xml.getElementsByTagName("disk")
    return disks


def get_disks_quantity_libvirt(domain):
    """
    Get number of disks available to the guest on the libvirt side

    :return: number of disks
    :rtype: int
    """
    return len(get_disks_available_libvirt(domain))


def get_disks_available_guest(session):
    """
    Get the disks names available to the guest on the guest side

    :return: list of disks name
    :rtype: list
    """
    disks_cmd = session.cmd('ls /sys/block')
    disks = disks_cmd.stdout_text.strip().split(sep='\n')
    return disks


def get_disks_quantity_guest(session):
    """
    Get number of disks available to the guest on the guest side

    :return: number of disks
    :rtype: int
    """
    return len(get_disks_available_guest(session))


class LibVirt(Test):
    def setUp(self):
        # create the new disk image
        self.new_disk_path = os.path.join(self.workdir, 'new_disk.raw')
        run(f'qemu-img create -f raw {self.new_disk_path} 1G')

        # start the guest
        self.guest = start_guest()
        if self.guest is None:
            self.fail('Could not bring up the guest')

        # set up an ssh session
        self.session = Session(self.guest['ip'],
                               user=USERNAME,
                               password=PASSWORD)
        # make sure the guest is up and running
        for i in range(10):
            if not self.session.connect():
                time.sleep(i)
            else:
                break
        if not self.session.connect():
            self.fail("Could not establish SSH connection")

    def test_devices_quantity(self):
        """Attach a device to the guest and count the number of disks"""
        original_disks_libvirt = get_disks_quantity_libvirt(self.guest['dom'])
        original_disks_guest = get_disks_quantity_guest(self.session)

        attach_device(self.guest['dom'], self.new_disk_path, TARGET_DEV)

        new_disks_libvirt = get_disks_quantity_libvirt(self.guest['dom'])
        new_disks_guest = get_disks_quantity_guest(self.session)

        self.assertEqual(original_disks_libvirt+1, new_disks_libvirt)
        self.assertEqual(original_disks_guest+1, new_disks_guest)

        detach_device(self.guest['dom'], self.new_disk_path, TARGET_DEV)

        new_disks_libvirt = get_disks_quantity_libvirt(self.guest['dom'])
        new_disks_guest = get_disks_quantity_guest(self.session)

        self.assertEqual(original_disks_libvirt, new_disks_libvirt)
        self.assertEqual(original_disks_guest, new_disks_guest)


    def test_device_name(self):
        """Attach a device to the guest and check its name"""
        attach_device(self.guest['dom'], self.new_disk_path, TARGET_DEV)
        disks_guest = get_disks_available_guest(self.session)
        self.assertTrue(TARGET_DEV in disks_guest)

        detach_device(self.guest['dom'], self.new_disk_path, TARGET_DEV)
        disks_guest = get_disks_available_guest(self.session)
        self.assertFalse(TARGET_DEV in disks_guest)


    def test_multiple_attach_detach(self):
        """Attach a device to the guest and count the number of disks 10 times"""
        for i in range(10):
            original_disks_libvirt = get_disks_quantity_libvirt(self.guest['dom'])
            original_disks_guest = get_disks_quantity_guest(self.session)

            attach_device(self.guest['dom'], self.new_disk_path, TARGET_DEV)

            new_disks_libvirt = get_disks_quantity_libvirt(self.guest['dom'])
            new_disks_guest = get_disks_quantity_guest(self.session)

            self.assertEqual(original_disks_libvirt+1, new_disks_libvirt)
            self.assertEqual(original_disks_guest+1, new_disks_guest)

            detach_device(self.guest['dom'], self.new_disk_path, TARGET_DEV)

            new_disks_libvirt = get_disks_quantity_libvirt(self.guest['dom'])
            new_disks_guest = get_disks_quantity_guest(self.session)

            self.assertEqual(original_disks_libvirt, new_disks_libvirt)
            self.assertEqual(original_disks_guest, new_disks_guest)

    def tearDown(self):
        # in case of failure in any test, make sure to detach the disk
        if TARGET_DEV in get_disks_available_guest(self.session):
            detach_device(self.guest['dom'], self.new_disk_path, TARGET_DEV)

        # bring down the guest
        if not stop_guest(self.guest):
            self.log.debug('Error trying to bring the guest down')
        # an immediate stop/start in the guest is not working. This is a
        # workaround to give some time to libvirt to set itself up.
        time.sleep(1)

        # remove the disk file
        try:
            os.remove(self.new_disk_path)
        except OSError as e:
            self.log.debug("Could not delete file %s - %s." % (e.filename,
                                                               e.strerror))
