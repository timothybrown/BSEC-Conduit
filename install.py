#!/usr/bin/env python3

"""BSEC-Conduit Installer - 2018.11.06 - (C) 2018 TimothyBrown
Usage: Run `sudo python3 install.py` in the directory you want to install to.
"""

import os
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
bsec_ver = 'BSEC_1.4.7.1_Generic_Release_20180907'
bsec_zip = '{}/{}.zip'.format(install_dir, bsec_ver)
bsec_dir = '{}/{}'.format(install_dir, bsec_ver)
systemd_dir = "/etc/systemd/system"
systemd_name = "bsec-conduit.service"
systemd_unit = """[Unit]
Description=BSEC-Conduit Daemon
After=mosquitto.service
Wants=mosquitto.service
Before=home-assistant.service
StartLimitBurst=5
StartLimitIntervalSec=30

[Service]
Type=notify
User={}
WorkingDirectory={}
ExecStart={}/bsec-conduit
WatchdogSec=30s
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""

print("****************************************************************************")
print("************************** BSEC-Conduit Installer **************************")
print("****************************************************************************")
if os.getuid() != 0:
    print("Error: This script must be run as root! Please re-run with sudo.")
    exit(1)
### Install
print("\n* Install Location: {}".format(install_dir))
for i in range(5):
    print("  Press CTRL-C to abort. Starting in {}...".format(5 - i), end='\r')
    time.sleep(1)

### BSEC Setup
print("\n\n* Bosch Sensortec Environmental Cluster (BSEC) Setup")
if not os.path.isfile(bsec_zip):
    print("  Downloading the BSEC source archive...", end='\r')
    with urllib.request.urlopen('{}/{}.zip'.format(bsec_url, bsec_ver)) as response, open(bsec_zip, 'wb') as out_file:
        shutil.copyfileobj(response, out_file)
        print("  Downloading the BSEC source archive...Done!")
else:
    print("  Found exsisting copy of the BSEC source archive, skipping download.")

if not os.path.isdir(bsec_dir):
    print("  Extracting the BSEC source archive...", end='\r')
    with open(bsec_zip, 'rb') as f:
        unzip = zipfile.ZipFile(f)
        unzip.extractall(install_dir)
        os.remove(bsec_zip)
        print("  Extracting the BSEC source archive...Done!")
else:
    os.remove(bsec_zip)
    print("  Found exsisting BSEC source directory, skipping extraction!")

print("  Setting permissions on BSEC source directory...", end='')
try:
    shutil.chown(bsec_dir, user=install_uid, group=install_gid)
    for dirpath, dirnames, filenames in os.walk(bsec_dir):
        if len(dirnames) > 0:
            for dir in dirnames:
                shutil.chown(os.path.join(dirpath, dir), user=install_uid, group=install_gid)
        if len(filenames) > 0:
            for file in filenames:
                shutil.chown(os.path.join(dirpath, file), user=install_uid, group=install_gid)
except Exception:
    print("Error!")
    print("# Unable to change permissions on BSEC source directory.")
    print("# Please run the following command after this script has finished:")
    print("# sudo chown -R {}:{} {}".format(install_uid, install_gid, bsec_dir))
else:
    print("Done!")

print("\n* Systemd Unit Setup")
if os.path.isdir(systemd_dir):
    print("  Writing service file [{}]...".format(systemd_name), end='')
    with open('{}/{}'.format(systemd_dir, systemd_name), 'w+b') as f:
        f.write(systemd_unit.format(install_username, install_dir, install_dir).encode('UTF-8'))
    print("Done!")

    print("  Enabling service...", end='')
    systemctl_cmds = [['systemctl', 'daemon-reload'], ['systemctl', 'enable', systemd_name]]
    for cmd in systemctl_cmds:
        systemctl = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if systemctl.returncode != 0:
            systemctl_error = systemctl.stdout.decode()
            print('Error!')
            print('# Could not enable the service!')
            print(systemctl_error)
            exit(1)
    print("Done!")
else:
    print("  This system does not appear to be running Systemd, skipping.")

print("\n* Install Python Dependencies")
if os.path.isfile('/usr/bin/apt-get'):
    print("  Using APT to install required modules...", end='')
    apt_cmd = ['apt-get', '-qq', 'install', 'python3-systemd' 'python3-paho-mqtt']
    apt = subprocess.run(apt_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if apt.returncode != 0:
        print('Warning!')
        print('# Either the modules are already installed or we ran into a problem.')
        print('# Please make sure the following Python 3 modules are available:')
        print("# [systemd-python>=233] [paho-mqtt>=1.4.0]")
else:
    print("# You appear to be on a non-Debian based system or have installed")
    print("# this script into a virtual enviroment, so we are unable to automatically")
    print("# install the dependencies.")
    print('# Please make sure the following Python 3 modules are available:')
    print("# [systemd-python>=233] [paho-mqtt>=1.4.0]")

print("\n* Readme First")
print("""Congratulations! The BSEC-Conduit installation has completed.
Your next step is to edit bsec-conduit.ini and set your options.
You can edit the file with the command `nano bsec-conduit.ini`.
Then you're ready to start the program with one of the following commands:
> Systemd Based Systems:
  sudo systemctl start BSEC-Conduit.service; journalctl -f -u BSEC-Conduit.service
> Other Systems:
  ./BSEC-Conduit
If no errors appear you should be good to go! On Systemd based systems you can safely
reboot and the program will start automatically. On other systems you'll need to create
a startup entry in your init system (runit, init.d, etc.) or add the following command
to /etc/rc.local (if available): `{}/BSEC-Conduit &`

If you run into problems please report them by opening a new issue on GitHub.

https://github.com/timothybrown/BSEC-Conduit
""".format(install_dir))
print("****************************************************************************")
