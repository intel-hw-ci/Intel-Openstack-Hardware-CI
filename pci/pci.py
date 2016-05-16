import base64
import guestfs
from functools import partial
import os
import six
import stat
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

from oslo_utils import encodeutils
from tempest import config
from tempest_lib.common.utils import data_utils


CONF = config.CONF

def __init__(self):
    self.get_pci_config(self)

def get_pci_config(self):
    self.nameList = []
    self.countList = []
    self.pci_idList = []
    self.infoList = []
    parameter = os.getenv('pci_info')
    parameter = parameter.strip()
    parameter = parameter.split(';')
    for i in parameter:
        if i is not "":
            i = i.split(',')
            name = i[0].split(':')
            self.nameList.append(name[1])
            count = i[3].split(':')
            self.countList.append(count[1])
            pciid = i[2].split(':')
            self.pci_idList.append(pciid[1])
            info = name[1] + ":" + pciid[1]
            self.infoList.append(info)
    self.infoList = tuple(self.infoList)
    self.countList = tuple(self.countList)
    return self.infoList,self.countList

def create_flavor_with_extra_specs(self,name,count=1):
    flavor_with_pci_name = data_utils.rand_name('pci_flavor')
    flavor_with_pci_id = data_utils.rand_int_id(start=1000)
    ram = 2048
    vcpus = 1
    disk = 2
    pci_name = name
    pci_name = "%s:%d"%(pci_name,count)
    specs = {"pci_passthrough:alias": pci_name}

    # Create a flavor with extra specs
    flavor = (self.flavor_client.
              create_flavor(name=flavor_with_pci_name,
                                ram=ram, vcpus=vcpus, disk=disk,
                                id=flavor_with_pci_id))
    self.flavor_client.set_flavor_extra_spec(flavor['flavor']['id'], **specs)
    self.addCleanup(flavor_clean_up, self, flavor['flavor']['id'])

    return flavor['flavor']['id']

def flavor_clean_up(self, flavor_id):
    body = self.flavor_client.delete_flavor(flavor_id)
    self.assertEqual(body.response.status, 202)
    self.flavor_client.wait_for_resource_deletion(flavor_id)


def shell_command(cmd, log=False):
    # cmd = ['sudo', 'ip', 'netns', 'exec', ns, 'ssh', "%s@%s" %(name, ip),
    # "'%s;ifconfig eth1 %s/24'" % (name ip)]
    p = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if log:
        print out
        print err
        if len(err):
            return False
    return out


VM_MOUNT_POINT = "/mnt"
PCI_PATH = "/pci.info"
RC_LOCAL = "/etc/rc.local"
USER_DATA = ['#!/bin/sh -e',
             '# mount -a',
             'mount /dev/vdb %s' % VM_MOUNT_POINT,
             'touch %s%s' % (VM_MOUNT_POINT, PCI_PATH),
             'lspci > %s%s' % (VM_MOUNT_POINT, PCI_PATH),
             '# umount /mnt/',
             'exit 0']


PCIINFO_DELIMITER = "*" * 40 + "%s" + "*" * 40
PCIINFO_DELIMITER_BEGIN = PCIINFO_DELIMITER % "PCI INFO BEGIN"
PCIINFO_DELIMITER_END = PCIINFO_DELIMITER % "PCI INFO END"

CONSOLE_DATA = [
    '#!/bin/sh -e',
    'echo "============================================="',
    'if [ -f /etc/rc.local ]; then echo "/ete/rc.local exist"; else echo "/ete/rc.local not exist"; fi',
    'while [ ! -f /etc/rc.local ]; do "waiting for /etc/rc.local"; done;',
    'chmod a+x /etc/rc.local',
    'sudo echo "%s"' % PCIINFO_DELIMITER_BEGIN,
    'sudo lspci',
    'sudo echo "%s"'  % PCIINFO_DELIMITER_END,
    'exit 0']

RC_LSPCI = [
    '#!/bin/sh -e',
    'echo "%s" > /dev/console' % (PCIINFO_DELIMITER % "RC LSPCI BEGIN"),
    'lspci > /dev/console',
    'echo "%s" > /dev/console'  % (PCIINFO_DELIMITER % "RC LSPCI END"),
    'exit 0']

SUSPEND_PAUSE_CONSOLE_DATA = [
    '#!/bin/sh -e',
    'echo "============================================="',
    'echo "%s"' % PCIINFO_DELIMITER_BEGIN,
    'lspci',
    'echo "%s"'  % PCIINFO_DELIMITER_END,
    'cat /dev/ttyS1 > /pm_state &',
    'sleep 3',
    'touch /pm_state',
    'echo "1" > /pm_state',
    'echo "begein to waiting for parameter"',
    'while true;',
    'do',
    '  echo "in waiting for parameter"',
    '  if [ 1 -ne `tail -n1 /pm_state` ]; then',
    '    echo "get for parameter"',
    '    echo "2" > /dev/ttyS1',
    '    echo "1" > /pm_state',
    '    echo "%s" > /dev/console' % (PCIINFO_DELIMITER % "SP LSPCI BEGIN"),
    '    lspci > /dev/console',
    '    echo "%s" > /dev/console'  % (PCIINFO_DELIMITER % "SP LSPCI END"),
    '  else',
    '    sleep 1',
    '    echo "waiting for parameter"',
    '  fi',
    'done',
    'exit 0']



def gen_rc_local_file(pci_path=PCI_PATH):
    """please remove the file: os.remove(p)
       print gen_rc_local()
    """
    l, p = tempfile.mkstemp("local", "rc")
    f = open(p, 'w+b')
    f.writelines(['#!/bin/sh -e\n',
                  'mount -a\n',
                  'touch %s%s\n' % (VM_MOUNT_POINT, pci_path),
                  'lspci > %s%s\n' % (VM_MOUNT_POINT, pci_path),
                  'umount /mnt/\n',
                  'exit 0\n'])
    os.chmod(p, stat.S_IRWXU + stat.S_IXGRP + stat.S_IXOTH)
    f.close()
    return p, pci_path


MOUNT_DATA = ['#!/bin/sh -e',
              'mount -a',
              'touch %s%s' % (VM_MOUNT_POINT, PCI_PATH),
              'lspci > %s%s' % (VM_MOUNT_POINT, PCI_PATH),
              'cd ~',
              'umount /mnt/',
              'exit 0']


def gen_rc_local_dict(data=MOUNT_DATA, pci_path=PCI_PATH):
    """
    usage: personality = {}
           personality.append({
               'path': filepath,
               'contents': cont,
           })

    """
    data = "\n".join(data)
    if six.PY3 and isinstance(data, str):
        data = data.encode('utf-8')
    cont = base64.b64encode(data).decode('utf-8')
    return cont


def gen_user_data(userdata=USER_DATA):
    if hasattr(userdata, 'read'):
        userdata = userdata.read()
    # NOTE(melwitt): Text file data is converted to bytes prior to
    # base64 encoding. The utf-8 encoding will fail for binary files.
    if six.PY3:
        try:
            userdata = userdata.encode("utf-8")
        except AttributeError:
            # In python 3, 'bytes' object has no attribute 'encode'
            pass
    else:
        try:
            userdata = encodeutils.safe_encode(userdata)
        except UnicodeDecodeError:
            pass

    userdata_b64 = base64.b64encode(userdata).decode('utf-8')
    return userdata_b64


def gen_etc_fstab():
    """
    usage: personality = {}
           personality.append({
               'path': filepath,
               'contents': cont,
           })

    """
    data = ["/dev/root  /         auto     rw,noauto                 0 1",
            "proc       /proc     proc     defaults                  0 0",
            "devpts     /dev/pts  devpts   defaults,gid=5,mode=620   0 0",
            "tmpfs      /dev/shm  tmpfs    mode=0777                 0 0",
            "sysfs      /sys      sysfs    defaults                  0 0",
            "tmpfs      /run      tmpfs    rw,nosuid,relatime,size=200k,mode=755 0 0",
            "/dev/vdb    /mnt/ auto    defaults                0 0"]

    data = "\n".join(data)
    if six.PY3 and isinstance(data, str):
        data = data.encode('utf-8')
    cont = base64.b64encode(data).decode('utf-8')
    return cont

def get_pci_info(disk, pci_path=PCI_PATH):
    """please remove the dir: os.rmdir(p)
    mount the disk by guestfs and get the pci info.
    need:
    $ sudo chmod g+rw /boot/vmlinuz-/boot/vmlinuz-`uname -r`
    $ sudo usermod -a -G root jenkins
    need to install these 2 packages
    $ sudo apt-get install libguestfs-tools
    $ sudo apt-get install python-guestfs
    need to add use to kvm group
    $ sudo usermod -a -G kvm jenkins
    or
    $ sudo chmod 0666 /dev/kvm
    ref http://libguestfs.org/guestfs-python.3.html
    for debug:
    $ export LIBGUESTFS_DEBUG=1
    $ export LIBGUESTFS_TRACE=1
    ref http://libguestfs.org/guestfs-faq.1.html#debugging-libguestfs
    """
    p = tempfile.mkdtemp("guestfs", "mount")
    g = guestfs.GuestFS(python_return_dict=True)
    # g.add_drive_opts(disk, format="qcow2", readonly=1)
    g.add_drive_opts(disk, readonly=1)
    g.launch()
    g.mount('/dev/sda', '/')
    return g.read_lines(pci_path)


def nbd_mount(f, disk, path=PCI_PATH):
    """please remove the dir: os.rmdir(p)
    mount the disk by guestfs and get the pci info.
    need:
    $ sudo rmmod nbd
    $ sudo modprobe nbd max_part=16
    ref https://en.wikibooks.org/wiki/QEMU/Images
    ref https://blogs.gnome.org/muelli/2010/03/mounting-qemu-qcow2-image-using-nbd/
    """
    mount_point = "/mnt/nbd"
    cmd = ["sudo", "modinfo", "nbd"]
    out = shell_command(cmd)
    if "modinfo: ERROR:" in out:
        cmd = ["sudo", "modprobe", "nbd", "max_part=16"]
        shell_command(cmd)

    if not os.path.exists(mount_point):
        cmd = ["sudo", "mkdir", mount_point]
        shell_command(cmd)

    if os.path.ismount(mount_point):
        cmd = ["sudo", "umount", mount_point]
        shell_command(cmd)

    cmd = ["sudo", "qemu-nbd", "-d", "/dev/nbd0"]
    shell_command(cmd)

    cmd = ["sudo", "killall", "qemu-nbd"]
    shell_command(cmd)

    # cmd = ["sudo", "qemu-nbd", "-r", "-c", "/dev/nbd0", disk]
    cmd = ["sudo", "qemu-nbd", "-c", "/dev/nbd0", disk]
    shell_command(cmd)

    cmd = ["sudo", "mount", "/dev/nbd0", mount_point]
    shell_command(cmd)

    cmd = ["sudo", "qemu-nbd", "-d", "/dev/nbd0"]
    shell_command(cmd)
    raise Exception("Can't mount the VM disk!")

    out = f(mount_point, path)

    cmd = ["sudo", "umount", mount_point]
    shell_command(cmd)

    cmd = ["sudo", "qemu-nbd", "-d", "/dev/nbd0"]
    shell_command(cmd)
    return out


def cat_file(mount, pci_path):
    cmd = ["sudo", "cat", mount + pci_path]
    pci_info = shell_command(cmd, True)
    if pci_info is False:
        return pci_info
    return pci_info.splitlines()


get_pci_info_by_nbd = partial(nbd_mount, cat_file)


def x_file(mount, rc_path):
    cmd = ["sudo", "chmod", "a+x", mount + rc_path]
    out = shell_command(cmd)
    return out

rc_local_add_x = partial(nbd_mount, x_file)


def get_vda_path(xml):
    # tree = ET.parse('/etc/libvirt/qemu/instance-0000001f.xml')
    # root = tree.getroot()
    root = ET.fromstring(xml)
    disks = root.findall("./devices/disk[@device='disk'][@type='file']")
    for d in disks:
        t = d.find("target")
        if t.attrib.get("dev") == "vda":
            return d.find("./source").get("file")

def get_config_drive_path(xml):
    # tree = ET.parse('/etc/libvirt/qemu/instance-0000001f.xml')
    # root = tree.getroot()
    root = ET.fromstring(xml)
    disks = root.findall("./devices/disk[@device='disk'][@type='file']")
    for d in disks:
        f = d.find("./source").get("file")
        if "disk.config" in f:
            return f

def get_serial_path(xml):
    # tree = ET.parse('/etc/libvirt/qemu/instance-0000001f.xml')
    # root = tree.getroot()
    root = ET.fromstring(xml)
    s = root.findall("./devices/serial")
    for i in s:
        t = i.find("target")
        if t.get("port") == "1":
            return i.find("source").get("path")


def get_pci_output(get_console_output, server_id, DELIMITER='PCI INFO'):
    output = get_console_output(server_id)['output']
    print output
    lines = output.split('\n')
    delimiter_begin = PCIINFO_DELIMITER % (DELIMITER + " BEGIN")
    delimiter_end = PCIINFO_DELIMITER % (DELIMITER + " END")
    if (len(lines) > 0 and lines.count(delimiter_begin) > 0
        and lines.count(delimiter_end)):
        begin = lines.index(delimiter_begin) + 1
        end = lines.index(delimiter_end)
        return lines[begin : end]


def retry_get_pci_output(get_console_output, server_id,
                         retry=20, DELIMITER='PCI INFO'):
    while retry > 0:
        out = get_pci_output(get_console_output, server_id, DELIMITER)
        if out is None:
            retry = retry - 1
            time.sleep(10)
        else:
            return out
    raise Exception("Can't get the pci.info from VM!")
