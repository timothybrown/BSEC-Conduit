# BSEC-Conduit Daemon - 2018.11.06 - (C) 2018 TimothyBrown
A first class Systemd process which acts as a conduit between between BSEC Library
and MQTT. Provides an alternative method of getting data out of an I2C connected
Bosch BME680 sensor and into Home Assistant. Much more accurate than the native
HA BME680 module, as it uses the Bosch Sensortec Environmental Cluster (BSEC)
fusion library to process the raw BME680 senor readings.

Thanks to @rstoermer for `bsec_bme680.py` upon which I based this.
(https://github.com/rstoermer/bsec_bme680_python/)

### Attribution
- BSEC-Conduit:
    - @TimothyBrown (2018)
    - MIT License

### Requirements
- python-systemd
- paho.mqtt

`sudo apt-get install python3-systemd python3-paho.mqtt`
  *or*
`pip3 install python-systemd paho.mqtt`

### Installation
In this example we'll be installing into `/opt/bsec` with the user `homeassistant`
on a recent Debian based distro (Raspbian/Hassbian):
- `sudo mkdir /opt/bsec`
- `sudo chown homeassistant:homeassistant /opt/bsec`
- `sudo -u homeassistant -H -s`
- `git clone https://github.com/timothybrown/BSEC-Conduit.git /opt/bsec`
- `cd /opt/bsec`
- `sudo python3 install.py`
- `nano BSEC-Conduit` Edit the config section at the top of the file. Use `CTRL-X` to save.
- `sudo systemctl start BSEC-Conduit.service; journalctl -f -u BSEC-Conduit.service`

### Version History
- v0.1.0: 2018.08.01
    - Rstoermer's original script.
- v0.2.0: 2018.10.20
  - Initial rewrite of rstoermer's code.
  - Changed paho.mqtt to use connect_async method. This means it will establish
  an connection and stay connected until the daemon exits. The original code
  used the single publish function for each message, which connected/disconnected
  to/from the server for every message. This causes a lot of log spam and
  churning of the Mosquitto persistence database.
  - Changed from publishing to a single topic with a JSON payload to publishing to
  multiple topics with a standard payload, one for each sensor value.
  (I.e., sensors/BME680/Temperature, sensors/BME680/Humidity, etc.)
  This means you no longer have to use a value_template in Home Assistant and
  seems a more MQTTy way of doing things.
  - Made small changes to the way the BSEC Library process is opened.
  - Changed the way that output floats are rounded.
  - Added a counter for the sample loop instead of relying on len().
  - Added a signal handler to exit cleanly (sends SIGTERM to the BSEC Library
  process, sets the `status` topic and stops the MQTT client loop).
  - No longer publish the BSEC Library Status value, as it's not a useful metric.
  Instead we monitor it in the script and if it changes to a non-zero value
  we report the value as an error in the system log and exit. (Systemd should
  restart the daemon up to 5 times, so if it was a temporary problem no user
  action is required.)
  - Made the main loop a function.
  - Many other small changes.
- v0.2.1: 2018.10.23
  - Added Systemd Journal logging output.
  - Moved all user editable options to the top of the script for
    ease of configuration.
  - Adds ability to run as a Systemd `notify` process.
  - Adds Systemd Watchdog support.
  - Adds Home Assistant MQTT Discovery support!
  - Added basic sanity checking on some of the user configuration.
  - Made all MQTT topics persistant, which prevents gaps in your history graph if
  HA starts before we publish our first reading. Likewise it also allows the
  discovery feature to work if the daemon starts *before* HA, which it should.
  (The way to fix the latter problem would be for the daemon to monitor the
  `homeassistant/status` topic and only publish discovery when it changes
  to `online`; that said, making the topics persistant solves the problem, so...)
  - Added a feature to automatically generate an MQTT client ID out of the last
  eight digits of the RPi's serial number. Example: BME680-A12BC3D4
  This is more descriptive than paho.mqtt's default random ID, which we fall back
  on if we're not running on a Raspberry Pi.
- v0.2.2: 2018.10.24
  - Lots of code cleanup and refactoring!
  - Made several changes to the way samples are stored and processed:
    1) Switched from a list to a deque for storing the samples.
    2) Switched from statistics.median() to statistics.mean() for processing
       sample data. The BSEC Library already takes care of filtering outliers,
       so the mean value of the period should be a better representation of the
       data, even without weighting enabled.
    3) Implemented an option to enable increasing the sample cache size.
       We now store Cache Multiplier * (Update Rate / BSEC Sample Rate [3|300]) worth of samples.
  - Added an option to report IAQ in percentage instead of the raw value. This seems
  to be an easier to read metric than an arbitrary number. (Though we lose
  one digit of precision in the process.)
  - Changed the IAQ Accuracy output from a number to a descriptive string:
  0 = Stabilizing, 1 = Low, 2 = Medium, 3 = High
- v0.2.3: 2018.10.27
  - Added automatic detection of BSEC Library file parameters. This will help
  with implementing automatic configuration and builds in the next version.
  - Added startup checks to verify the BSEC Library directory, bsec_bme680 executable
  and bsec_iaq.config file all exist.
- v0.3.0: 2018.11.05
  - Major changes!
  - Spent over a week stability testing previous code. BSEC-Conduit ran non-stop for
  5 days with no memory leaks or crashes.
  - Implemented the BSECLibrary class, which takes care of building the bsec_library
  executable, copying the config file and running the process. This now makes BSEC-Conduit
  fully stand-alone! You no longer have to build the bsec_library executable as our
  class takes care of all of that for you. Simply supply the Bosch BSEC source
  and we'll take care of the rest! See the revision information of BSECLibrary for
  more information.
  - Added an `install.py` script to take care of setting up the Systemd service,
  downloading the BSEC source and so on. This is in preperation for release.
- v0.3.1: 2018.11.07
  - Public Release

# BSECLibrary
Uses the Bosch BSEC sensor fusion library to communicate with a BME680.

### Attribution
- BSEC-Conduit:
  - @TimothyBrown (2018)
  - MIT License
- bsec_library.c:
  - Original by @alexh.name (2017)
  - I2C Code by @twartzek (2017)
  - Modifications by @TimothyBrown (2018)
  - MIT License
- BSEC 1.4.7.1 Generic Release (20180907):
  - Bosch Sensortec GmbH
  - Private License

### Usage
```
BSECLIbrary(i2c_address, temp_offset, sample_rate, voltage, retain_state)
```
- i2c_address: Address of the sensor.                             [0x76|0x77]
- temp_offset: An offset to add to the temperature sensor.    [10.0 to -10.0]
- sample_rate: Seconds between samples.                               [3|300]
- voltage: The voltage the sensor is run at.                    [3.3|1.8]
- retain_state: Number of days to retain the IAQ state data.            [4|28]
- logger: Logger instance to use. Use None for console output.
- base_dir: Directory to store the executable, config and state files. Must also include a sub-directory named `src` that contains an untouched copy of the Bosch Sensortec BSEC Library source.

Example:
```
from bseclib import BSECLibrary

bsec_lib = BSECLibrary(0x77, 2.0, 3, 3.3, 4)
count = 0
bsec_lib.open()
for sample in bsec_lib.output():
    print(sample)
    if count == 10:
        bsec_lib.close()
        exit()
    else:
        count += 1
```

### Version History
- v0.1.0: 2018.11.05
  - Initial version!
  - Moved all the bsec_library process creation code from BSEC-Conduit into this class.
  - Created functions to build the bsec_library process, copy config and create a state file.
  - Embedded the underlying `bsec_library.c` file directly into the library.
  - Currently using a hack to determine processor type. Fix in next release.
- v0.1.1: 2018.11.06
  - Implemented a function to decode the `Revision` line from
  `/proc/cpuinfo`. This gives specific information like the BCM processor used and
  the model number. We use this to figure out if we've got an ARMv8 processor;
  this is required because platform.machine() will return ARMv7 even on the RPi 3.
  The code will also detect non-Pi ARM machines, like the BeagleBone.
  - Modified the underlying `bme680_bsec.c` file to support setting options
  via command line arguments, instead of static #defines in the source.
  This allows us to dynamically change configurations on the fly.
  - Implemented the output() generator, which takes care of reading JSON data from the
  underlying bsec_library process and converting it and returning a dict of sensor values.
  This allows you to directly iterate over output() in your script without worrying about
  JSON, strings or bytes.
  - Added tons of error handling to the get_exec(), get_config() and get_state() functions.
- v0.1.2: 2018.11.07
  - Public Release!
