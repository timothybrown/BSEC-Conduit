#!/usr/bin/env python3

"""BSEC-Conduit Installer - 2018.11.16 - (C) 2018 TimothyBrown
Usage: Run `sudo python3 install.py` in the directory you want to install to.
"""

import os
import sys
import subprocess
import urllib.request
import shutil
import zipfile
import time
import pwd

install_dir = os.path.abspath(os.getcwd())
install_uid = os.stat(install_dir).st_uid
install_gid = os.stat(install_dir).st_gid
install_username = pwd.getpwuid(install_uid).pw_name
bsec_url = 'https://ae-bst.resource.bosch.com/media/_tech/media/bsec'
bsec_ver = 'BSEC_1.4.7.4_Generic_Release'
bsec_zip = '{}/{}.zip'.format(install_dir, bsec_ver)
bsec_dir = '{}/{}'.format(install_dir, bsec_ver)
systemd_dir = "/etc/systemd/system"
systemd_name = "bsec-conduit.service"

print("****************************************************************************")
print("************************** BSEC-Conduit Installer **************************")
print("****************************************************************************")
if os.getuid() != 0:
    print("Error: This script must be run as root! Please re-run with sudo.")
    exit(1)
### Install
print("\n  Install Location: {}".format(install_dir))
for i in range(5):
    print("  Press CTRL-C to abort. Starting in {}...".format(5 - i), end='\r')
    time.sleep(1)

### BSEC Setup
print("\n\n# Bosch Sensortec Environmental Cluster (BSEC) Setup")
if not os.path.isfile(bsec_zip) and not os.path.isdir(bsec_dir):
    print("> Downloading the BSEC source archive...", end='\r')
    with urllib.request.urlopen('{}/{}.zip'.format(bsec_url, bsec_ver)) as response, open(bsec_zip, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)
        print("- Downloading the BSEC source archive...Done")

    print("> Extracting the BSEC source archive...", end='\r')
    with open(bsec_zip, 'rb') as f:
        unzip = zipfile.ZipFile(f)
        unzip.extractall(install_dir)
        os.remove(bsec_zip)
        print("- Extracting the BSEC source archive...Done")
else:
    print("- Found exsisting copy of the BSEC source, skipping download.")

time.sleep(1)
print("\n# Checking for Python Dependencies")

def install_module(module_name):
    current_env = os.environ.copy()
    command = ['pip', 'install', module_name]
    pip = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=current_env)
    if pip.returncode != 0:
        systemctl_error = systemctl.stdout.decode()
        print('* Attempting to install [{}] into our venv...Error'.format(module_name))
        print("  Please use pip to install these packages inside your venv manually.")
        print("$ pip3 install systemd-python")
    else:
        print('- Attempting to install [{}] into our venv...Done'.format(module_name))


has_mqtt = True
has_systemd = True
print('> Checking enviroment...', end='\r')
if (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)):
    is_venv = True
    print("- Checking enviroment...Done")
    print("  Detected a virtual enviroment.")
else:
    is_venv = False
    print("- Checking enviroment...Done")
    print("  No venv found. Assuming we're running under the system Python enviroment.")

try:
    import paho.mqtt
except ImportError:
    has_mqtt = False
except ModuleNotFoundError:
    has_mqtt = False
if os.path.isdir(systemd_dir):
    try:
        import systemd
    except ImportError:
        has_systemd = False
    except ModuleNotFoundError:
        has_systemd = False

if has_mqtt:
    print('- Module [paho-mqtt] found.')
else:
    print('* Module [paho-mqtt] not found.')
    if is_venv:
        print("> Attempting to install [paho-mqtt] into our venv...", end="\r")
        install_module('paho-mqtt')
    else:
        print("  Please use your system package manager or pip to install.")
        print("$ sudo pip3 install paho-mqtt")
if has_systemd and os.path.isdir(systemd_dir):
    print('- Module [systemd-python] found.')
else:
    print('* Module [systemd-python] not found.')
    if is_venv:
        print("> Attempting to install [systemd-python] into our venv...", end="\r")
        install_module('systemd-python')
    else:
        print("  Please use your system package manager or pip to install.")
        print("$ sudo pip3 install systemd-python")
if is_venv:
    dst_dir = '{}/lib/python{}.{}/site-packages/'.format(install_dir, sys.version_info[0], sys.version_info[1])
    src_dir = '{}/bseclib'.format(install_dir)
    if not os.path.isdir(dst_dir + 'bseclib'):
        try:
            print("> Attempting to install [bseclib] into our venv...", end="\r")
            shutil.move(src_dir, dst_dir)
        except:
            print("* Attempting to install [bseclib] into our venv...Error")
            print("  Please manually copy [bseclib] into the venv site-packages folder.")
            print("$ sudo mv {} {}".format(src_dir, dst_dir))
        else:
            print("- Attempting to install [bseclib] into our venv...Done")
            print("  {}=>{}bseclib".format(src_dir, dst_dir))
    else:
        print('- Module [bseclib] found.')

time.sleep(1)
print("\n# Systemd Unit Setup")
if os.path.isdir(systemd_dir):
    systemd_reload = False
    print("> Writing service file [{}]...".format(systemd_name), end='\r')
    try:
        unit_user = 'User={user}'.format(user=install_username)
        unit_dir = 'WorkingDirectory={dir}'.format(dir=install_dir)
        if is_venv:
            unit_exec = 'ExecStart={dir}/bin/python {dir}/bsec-conduit'.format(dir=install_dir)
        else:
            unit_exec = 'ExecStart={python} {dir}/bsec-conduit'.format(python=shutil.which('python3'), dir=install_dir)
        outpath = '{}/{}'.format(systemd_dir, systemd_name)
        inpath = '{}/systemd-template'.format(install_dir, systemd_name)
        with open(inpath, 'rt') as input, open(outpath, 'wt') as output:
            for line in input:
                line = line.rstrip()
                if line.startswith("User="):
                    line = unit_user
                elif line.startswith("WorkingDirectory="):
                    line = unit_dir
                elif line.startswith("ExecStart="):
                    line = unit_exec
                output.write(line + '\n')
                time.sleep(0.1)
        #os.remove(inpath)
        print("- Writing service file [{}]...Done".format(systemd_name))
        systemd_reload = True
    except:
        print("* Writing service file [{}]...Error".format(systemd_name))
        print("  Please manually edit and copy the service file:")
        print("$ sudo mv {} {}".format(inpath, outpath))
        print("$ sudo systemctl daemon-reload")
        print("$ sudo systemctl edit --full {}".format(systemd_name))
        print("  Fill out the following fields:")
        print('  ' + unit_user)
        print('  ' + unit_dir)
        print('  ' + unit_exec)

    if systemd_reload:
        print("> Reloading Systemd...", end='\r')
        systemctl_cmd = ['systemctl', 'daemon-reload']
        systemctl = subprocess.run(systemctl_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if systemctl.returncode != 0:
            systemctl_error = systemctl.stdout.decode()
            print('* Reloading Systemd...Error')
            print('  Systemd must reload all units before the new service is available:')
            print('$ sudo systemctl daemon-reload')
        else:
            print("- Reloading Systemd...Done")
else:
    print("- This system does not appear to be running Systemd, skipping.")

time.sleep(1)
print("\n# I2C Access")
if os.path.isfile('/boot/config.txt'):
    print("> Checking for I2C-1 device tree entry......", end='\r')
    dt_i2c = False
    with open('/boot/config.txt', 'rt') as f:
        for line in f:
            line = line.rstrip()
            if 'i2c_arm' in line:
                dt_i2c = True
    if not dt_i2c:
        print("* Checking for I2C-1 device tree entry...Not Enabled")
        try:
            print("> Enabling I2C-1 entry in device tree...", end='\r')
            with open('/boot/config.txt', 'at') as f:
                shutil.copy('/boot/config.txt', '/boot/config.bsec')
                f.write('dtparam=i2c_arm=on')
        except:
            print("* Enabling I2C-1 entry in device tree...Error")
            print("  Problem writing to file. Please add the following line to /boot/config.txt:")
            print("  dtparam=i2c_arm=on")
        else:
            print("- Enabling I2C-1 entry in device tree...Done")
    else:
        print("* Checking for I2C-1 device tree entry...Enabled")

    print("> Checking for I2C kernel module...", end='\r')
    mod_i2c = False
    lsmod = subprocess.run(['lsmod'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    lsmod_return = lsmod.stdout.decode()
    for line in lsmod_return.splitlines():
        if 'i2c_dev' in line:
            mod_i2c = True
    if not mod_i2c:
        print("* Checking for I2C kernel module...Not Enabled")
        try:
            print("> Enabling I2C-DEV kernel module...", end='\r')
            with open('/etc/modules-load.d/i2c.conf', 'wt') as f:
                f.write('i2c-dev')
        except:
            print("* Enabling I2C-DEV kernel module...Error")
            print("  Please add the following line to /etc/modules-load.d/i2c.conf:")
            print("  i2c-dev")
        else:
            print("- Enabling I2C-DEV kernel module...Done")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!                   Please Reboot your Pi to Activate I2C                   !!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        print("* Checking for I2C kernel module...Enabled")

print('> Checking group permissions...', end='\r')
groups_exec = subprocess.run(['groups', install_username], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
if groups_exec.returncode != 0:
    print('* Checking group permissions...Error')
else:
    print('- Checking group permissions...Done')
    groups = groups_exec.stdout.decode().rstrip().split()
    if 'i2c' in groups:
        print('  User [{}] is a member of group [i2c].'.format(install_username))
    else:
        print('  User [{}] does not appear to have non-root I2C access.'.format(install_username))
        print("> Attempting to add user to I2C group...", end='\r')
        usermod_exec = subprocess.run(['usermod', '-a', '-G', 'i2c', install_username], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if groups_exec.returncode != 0:
            print('* Attempting to add user to I2C group...Error')
            print('  Please run:')
            print('$ sudo usermod -aG i2c {}'.format(install_username))
        else:
            print("- Attempting to add user to I2C group...Done")

time.sleep(1)
time.sleep(1)
print("\n# Directory Permissions")
print("> Setting permissions on BSEC directory...", end='\r')
try:
    shutil.chown(install_dir, user=install_uid, group=install_gid)
    for dirpath, dirnames, filenames in os.walk(install_dir):
        if len(dirnames) > 0:
            for dir in dirnames:
                shutil.chown(os.path.join(dirpath, dir), user=install_uid, group=install_gid)
        if len(filenames) > 0:
            for file in filenames:
                shutil.chown(os.path.join(dirpath, file), user=install_uid, group=install_gid)
except Exception:
    print("* Setting permissions on BSEC source directory...Error")
    print("  Please run the following command after this script has finished:")
    print("  sudo chown -R {}:{} {}".format(install_uid, install_gid, bsec_dir))
else:
    print("- Setting permissions on BSEC source directory...Done")

time.sleep(1)
print("\n# Readme First")
print("""Congratulations! The BSEC-Conduit installation has completed.

Please review the above log and follow any instructions given.

Your next step is to edit 'bsec-conduit.ini' and set your options:
$ nano bsec-conduit.ini

Then you're ready to start the program with one of the following commands.

>>> Systemd Based Distros <<<
Start the daemon and watch the log for errors:
$ sudo systemctl start bsec-conduit; journalctl -f -u bsec-conduit

If no errors appear you can now enable the daemon to start at boot:
$ sudo systemctl enable bsec-conduit.service

>>> Other Distros <<<
If you're running in a Python venv:
$ source bin/activate
Run the daemon and monitor the console for errors:
$ ./bsec-conduit

If no errors appear you can now create a startup entry in your init system
and reboot.

If you run into problems please report them by opening a new issue on GitHub.

https://github.com/timothybrown/BSEC-Conduit
""".format(install_dir))
print("****************************************************************************")
