#!/usr/bin/env python3
"""
# BSECLibrary - (C) 2018 TimothyBrown

Uses the Bosch BSEC sensor fusion library to communicate with a BME680.



MIT License
"""
__program__ = 'BSECLibrary'
__version__ = '0.1.4'
__date__ = '2018.11.10'
__author__ = 'Timothy S. Brown'

import os
import subprocess
import logging
import platform
from time import sleep
from shutil import copy
from hashlib import md5
import json

class BSECLibraryError(Exception):
    """Base class for exceptions."""
    # Todo: Expand this into real exception handling sub-classes.
    pass

class BSECLibrary:
    """Handles communication with a BME680 using the Bosch BSEC fusion library."""

    def __init__(self, i2c_address, temp_offset, sample_rate, voltage, retain_state, logger=None, base_dir=None):
        # If the user doesn't pass a logger object, create one.
        if logger is None:
            logger = __name__
        self.log = logging.getLogger(logger)

        # Check the instance variables.
        if 119 > i2c_address < 118:
            self.log.error("Error: <i2c_address> must be one of 0x76 or 0x77.")
            raise BSECLibraryError()
        else:
            self.i2c_address = i2c_address

        if 10.0 > temp_offset < -10.0:
            self.log.error("Error: <temp_offset> must be in the range of 10.0 and -10.0.")
            raise BSECLibraryError()
        else:
            self.temp_offset = temp_offset

        if sample_rate != 3 and sample_rate != 300:
            self.log.error("Error: <sample_rate> must be one of 3 or 300.")
            raise BSECLibraryError()
        else:
            self.sample_rate = sample_rate

        if voltage != 3.3 and voltage != 1.8:
            self.log.error("Error: <voltage> must be one of 3.3 or 1.8.")
            raise BSECLibraryError()
        else:
            self.voltage = voltage

        if retain_state != 4 and retain_state != 28:
            self.log.error("Error: <retain_state> must be one of 4 or 28.")
            raise BSECLibraryError()
        else:
            self.retain_state = retain_state

        if base_dir is None:
            self.base_dir = os.getcwd()
        elif os.path.isdir(base_dir):
            self.base_dir = os.path.abspath(base_dir)
        else:
            self.log.error("Error: <base_dir> value of ({}) is not a valid directory.".format(base_dir))

        # Make sure the BSEC source directory exsists.
        src_dirs = [i for i in os.listdir(self.base_dir) if os.path.isdir(i) and 'BSEC_' in i]
        if len(src_dirs) == 0:
            self.log.error('The BSEC source directory could not be located!')
            self.log.error("Expected a directory name starting with 'BSEC_' under '{}' containing the the Bosch BSEC source files.".format(self.base_dir))
            self.log.error("Please download and unzip them from the URL below:")
            self.log.error("https://www.bosch-sensortec.com/bst/products/all_products/bsec")
            raise BSECLibraryError()
        else:
            self.src_dir = os.path.abspath(src_dirs[0])

        # Get executable, config and state file paths.
        self.exec_path = self._get_exec(self.src_dir, self.base_dir)
        self.config_path = self._get_config(self.src_dir, self.base_dir, self.config_string)
        self.state_path = self._get_state(self.base_dir)

        # Set the process variable.
        self.proc = None

    # Property function to generate the config_string variable.
    @property
    def config_string(self):
        return 'generic_{}v_{}s_{}d'.format(str(self.voltage)[0]+str(self.voltage)[2], str(self.sample_rate), str(self.retain_state))

    # Property function to generate the sample_rate_string variable.
    @property
    def sample_rate_string(self):
        return {3: 'LP', 300: 'ULP'}[self.sample_rate]

    # Function to start the bsec-library process.
    def open(self):
        if self.proc is not None:
            self.log.warning("BSEC Library is already running!")
        else:
            try:
                with open('/etc/timezone', 'rt') as f:
                    timezone = f.read().strip()
            except FileNotFoundError:
                self.log.warning("Could not determine timezone from /etc/timezone file. Using [UTC] as a default.")
                timezone = "UTC"
            os.putenv("TZ", timezone)
            run_command = [self.exec_path, str(self.i2c_address), str(self.temp_offset), self.sample_rate_string]
            self.proc = subprocess.Popen(run_command, stdout=subprocess.PIPE)
            if self.proc.returncode is not None:
                self.log.error('BSEC Library encountered an error ({}) during startup.'.format(self.proc.returncode))
                raise BSECLibraryError()
            else:
                self.log.info('BSEC Library started.')

    # Function to stop the bsec-library process.
    def close(self):
        if self.proc is None:
            self.log.warning("BSEC Library is not running!")
        else:
            self.proc.send_signal(15)
            sleep(1)
            self.log.info("BSEC Library stopped.")
            self.proc = None

    # Function to allow the user to iterate over the output.
    def output(self):
        if self.proc is not None:
            for line in iter(self.proc.stdout.readline, b''):
                data = dict(json.loads(line.decode('UTF-8')))
                if data['Status'] != '0':
                    # If there's a problem, yo we'll log it...
                    self.log.error("BSEC Library returned error {}.".format(data['Status']))
                    # ...kill the process and hope that resolves it! (Ice, ice, baby.)
                    raise BSECLibraryError()
                else:
                    yield data
            self.log.warning("BSEC Library ran out of data to yield!")
        else:
            self.log.warning("No data to to parse! Have you started the BSEC Library process?")
            return None

    # Private function to build the executable. Returns the executable path.
    def _get_exec(self, src_dir, base_dir):
        def arch():
            # Make sure we're running under Linux.
            system = platform.system()
            if system != 'Linux':
                self.log.error("This library requires Linux: Got {} as our OS.".format(system))
                raise BSECLibraryError()
            # Try to detect if we're running on an ARM processor.
            machine = platform.machine()
            if 'arm' not in machine:
                self.log.error("This library requires an ARM processor: Got {} as our architecture.".format(machine))
                raise BSECLibraryError()
            # Now that we know we're on an ARM machine, try to detect if we're on a Pi.
            # This is required because platform.machine() will return ARMv7 even for ARMv8 (3B, 3B+) machines.
            rpi_processor = None
            try:
                with open('/proc/cpuinfo') as f:
                    for line in f:
                        if line.startswith('Revision'):
                            code = int(line.split(':', 1)[1].strip()[1:], 16)
                            if bool(code >> 23 & 0x000000001):
                                rpi_processor = {0: 'BCM2835', 1: 'BCM2836', 2: 'BCM2837'}[code >> 12 & 0b00000000000000001111]
                            else:
                                rpi_processor = 'BCM2835'
            except FileNotFoundError:
                pass
            if rpi_processor is not None:
                # If we are, test to see if we're on a ARMv8 machine.
                if rpi_processor is 'BCM2837':
                    self.log.info('Detected architecture as ARMv8 64-Bit.')
                    return 'Normal_version/RaspberryPI/PiThree_ArmV8-a-64bits'
                # Then test for ARMv7.
                elif rpi_processor is 'BCM2836':
                    self.log.info('Detected architecture as ARMv7 32-Bit.')
                    return 'Normal_version/RaspberryPI/PiZero_ArmV6-32bits'
                # Finally test for ARMv6.
                elif rpi_processor is 'BCM2835':
                    self.log.info('Detected architecture as ARMv6 32-Bit.')
                    return 'Normal_version/RaspberryPI/PiZero_ArmV6-32bits'
            # Well, I guess we're not on a Pi... Let's take a stab at it anyway!
            # Note: The underlying `RaspberryPI/Pi*` libraries will work on non-Pi
            # systems, as long as it's an ARM processor running Linux.
            else:
                # Test for ARMv8.
                if 'armv8' in machine:
                    self.log.info('Detected architecture as ARMv8 64-Bit.')
                    return 'Normal_version/RaspberryPI/PiThree_ArmV8-a-64bits'
                # Then we must be on a 32-Bit platform.
                else:
                    self.log.info('Detected architecture as ARM{} 32-Bit.'.format(machine[3:]))
                    return 'Normal_version/RaspberryPI/PiZero_ArmV6-32bits'
            # Catch all in case something went wrong.
            self.log.error("Encountered an unknown error trying to determine system architecture.")
            raise BSECLibraryError()

        # Build the executable if needed.
        exec_dst = '{}/bsec-library'.format(base_dir)
        build_flag = True
        if os.path.isfile(exec_dst) and os.path.isfile('{}.md5'.format(exec_dst)):
            with open(exec_dst, 'rb') as f:
                source_hash = md5(f.read()).hexdigest().strip()
            with open('{}.md5'.format(exec_dst), 'rt') as f:
                target_hash = f.read().strip()
            if target_hash == source_hash:
                build_flag = False
                self.log.info('Found existing BSEC Library executable, skipping build.')
            else:
                self.log.warning("BSEC Library executable and hash file don't match, rebuilding.")
        else:
            self.log.warning('BSEC Library executable or hash file not found, starting build process.')
        if build_flag:
            # See if we need to write the source file.
            if not os.path.isfile('{}/bsec-library.c'.format(src_dir)):
                self.log.warning("BSEC Library source file not found, writing file: {}/bsec-library.c".format(src_dir))
                with open('{}/bsec-library.c'.format(src_dir), 'wb') as f:
                    f.write(bsec_library_c.encode('UTF-8'))

            lib_arch = arch()
            # Generate the build command.
            build_command = [
                            'cc',
                            '-Wall',
                            '-Wno-unused-but-set-variable',
                            '-Wno-unused-variable',
                            '-static',
                            '-iquote{}/API'.format(src_dir),
                            '-iquote{}/algo/bin/{}'.format(src_dir, lib_arch),
                            '-iquote{}/examples'.format(src_dir),
                            '{}/API/bme680.c'.format(src_dir),
                            '{}/examples/bsec_integration.c'.format(src_dir),
                            '{}/bsec-library.c'.format(src_dir),
                            '-L{}/algo/bin/{}'.format(src_dir, lib_arch),
                            '-lalgobsec',
                            '-lm',
                            '-lrt',
                            '-o',
                            exec_dst
                            ]
            # Run the build process.
            build_process = subprocess.run(build_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

            # Check for errors.
            if build_process.returncode != 0:
                build_error = build_process.stdout.decode()
                self.log.error('Encountered an error during the build process!')
                self.log.error(build_error)
                raise BSECLibraryError()
            else:
                self.log.info("Build process complete.")

            # Write an MD5SUM of the executable.
            with open(exec_dst, 'rb') as f:
                exec_md5 = md5(f.read()).hexdigest()
            with open('{}.md5'.format(exec_dst), 'wt') as f:
                f.write(exec_md5)

        return exec_dst

    # Private function to copy the config file. Returns the config file path.
    def _get_config(self, src_dir, base_dir, config):

        config_dst = '{}/bsec-library.config'.format(base_dir)
        config_hash_table = {
            '305c5398b0359f7956584a7a52bb48ea': {'string': 'generic_18v_300s_28d', 'voltage': 1.8, 'sample rate': 300, 'retain state': 28},
            'eecd6e4000afa21901bb28e182a75c6e': {'string': 'generic_18v_300s_4d', 'voltage': 1.8, 'sample rate': 300, 'retain state': 4},
            '19389190311bbdbf3432791eb9a258b7': {'string': 'generic_18v_3s_28d', 'voltage': 1.8, 'sample rate': 3, 'retain state': 28},
            '0505f6120e216f19987b59dc011fc609': {'string': 'generic_18v_3s_4d', 'voltage': 1.8, 'sample rate': 3, 'retain state': 4},
            '344ff63b9f11c0427d7d205242ffd606': {'string': 'generic_33v_300s_28d', 'voltage': 3.3, 'sample rate': 300, 'retain state': 28},
            '16851fcb6becb9b814263deb3d31623b': {'string': 'generic_33v_300s_4d', 'voltage': 3.3, 'sample rate': 300, 'retain state': 4},
            'a401d7712179350a7b6ff6fc035d49c2': {'string': 'generic_33v_3s_28d', 'voltage': 3.3, 'sample rate': 3, 'retain state': 28},
            '1107f7ce9fcb414de64e899babc1a1ee': {'string': 'generic_33v_3s_4d', 'voltage': 3.3, 'sample rate': 3, 'retain state': 4}
            }
        try:
            with open(config_dst, 'rb') as f:
                hash = md5(f.read()).hexdigest().lower()
        except FileNotFoundError:
            hash = None

        if hash in config_hash_table and config_hash_table[hash]['string'] == config:
            self.log.info("Using existing BSEC Library configuration [{}].".format(config))
        else:
            config_new = copy('{}/config/{}/bsec_iaq.config'.format(src_dir, config), config_dst)
            if config_new != os.path.abspath(config_dst):
                self.log.error("Error creating config file!")
                raise BSECLibraryError()
            self.log.info("Created new BSEC Library configuration [{}].".format(config))

        return config_dst

    # Private function to create the state file if needed. Returns the state file path.
    def _get_state(self, base_dir):
        state_dst = '{}/bsec-library.state'.format(base_dir)
        try:
            open(state_dst, 'xb')
        except FileExistsError:
            self.log.info('Found existing BSEC Library state file, skipping creation.')
        else:
            self.log.info('Created blank BSEC Library state file.')
        return state_dst

# The C code for the BSEC Library process itself.
bsec_library_c = """/* Copyright (C) 2017 alexh.name */
/* I2C code by twartzek 2017 */
/* argv[] code by TimothyBrown 2018 */
/**
  *  MIT License
  *
  *    Permission is hereby granted, free of charge, to any person obtaining a copy
  *    of this software and associated documentation files (the "Software"), to deal
  *    in the Software without restriction, including without limitation the rights
  *    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  *    copies of the Software, and to permit persons to whom the Software is
  *    furnished to do so, subject to the following conditions:
  *
  *    The above copyright notice and this permission notice shall be included in all
  *    copies or substantial portions of the Software.
  *
  *    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  *    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  *    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  *    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  *    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  *    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
  *    SOFTWARE.
  */

/*
 * Read the BME680 sensor with the BSEC library by running an endless loop in
 * the bsec_iot_loop() function under Linux.
 *
 */

/* header files */

#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <inttypes.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <linux/i2c-dev.h>
#include "bsec_datatypes.h"
#include "bsec_integration.h"
#include "bme680.h"

/* definitions */
int g_i2cFid; // I2C Linux device handle
int i2c_address; // Changed from #define to argv[1].
float temp_offset; // Changed from #define to argv[2].
float sample_rate_mode; // Changed from #define to argv[3].
char *filename_state = "bsec-library.state";
char *filename_config = "bsec-library.config";

/* functions */

// open the Linux device
void i2cOpen()
{
  g_i2cFid = open("/dev/i2c-1", O_RDWR);
  if (g_i2cFid < 0) {
    perror("i2cOpen");
    exit(1);
  }
}

// close the Linux device
void i2cClose()
{
  close(g_i2cFid);
}

// set the I2C slave address for all subsequent I2C device transfers
void i2cSetAddress(int address)
{
  if (ioctl(g_i2cFid, I2C_SLAVE, address) < 0) {
    perror("i2cSetAddress");
    exit(1);
  }
}

/*
 * Write operation in either I2C or SPI
 *
 * param[in]        dev_addr        I2C or SPI device address
 * param[in]        reg_addr        register address
 * param[in]        reg_data_ptr    pointer to the data to be written
 * param[in]        data_len        number of bytes to be written
 *
 * return          result of the bus communication function
 */
int8_t bus_write(uint8_t dev_addr, uint8_t reg_addr, uint8_t *reg_data_ptr,
                 uint16_t data_len)
{
  int8_t rslt = 0; /* Return 0 for Success, non-zero for failure */

  uint8_t reg[16];
  reg[0]=reg_addr;

  for (int i=1; i<data_len+1; i++)
    reg[i] = reg_data_ptr[i-1];

  if (write(g_i2cFid, reg, data_len+1) != data_len+1) {
    perror("user_i2c_write");
    rslt = 1;
    exit(1);
  }

  return rslt;
}

/*
 * Read operation in either I2C or SPI
 *
 * param[in]        dev_addr        I2C or SPI device address
 * param[in]        reg_addr        register address
 * param[out]       reg_data_ptr    pointer to the memory to be used to store
 *                                  the read data
 * param[in]        data_len        number of bytes to be read
 *
 * return          result of the bus communication function
 */
int8_t bus_read(uint8_t dev_addr, uint8_t reg_addr, uint8_t *reg_data_ptr,
                uint16_t data_len)
{
  int8_t rslt = 0; /* Return 0 for Success, non-zero for failure */

  uint8_t reg[1];
  reg[0]=reg_addr;

  if (write(g_i2cFid, reg, 1) != 1) {
    perror("user_i2c_read_reg");
    rslt = 1;
  }

  if (read(g_i2cFid, reg_data_ptr, data_len) != data_len) {
    perror("user_i2c_read_data");
    rslt = 1;
  }

  return rslt;
}

/*
 * System specific implementation of sleep function
 *
 * param[in]       t_ms    time in milliseconds
 *
 * return          none
 */
void _sleep(uint32_t t_ms)
{
  struct timespec ts;
  ts.tv_sec = 0;
  /* mod because nsec must be in the range 0 to 999999999 */
  ts.tv_nsec = (t_ms % 1000) * 1000000L;
  nanosleep(&ts, NULL);
}

/*
 * Capture the system time in microseconds
 *
 * return          system_current_time    system timestamp in microseconds
 */
int64_t get_timestamp_us()
{
  struct timespec spec;
  //clock_gettime(CLOCK_REALTIME, &spec);
  /* MONOTONIC in favor of REALTIME to avoid interference by time sync. */
  clock_gettime(CLOCK_MONOTONIC, &spec);

  int64_t system_current_time_ns = (int64_t)(spec.tv_sec) * (int64_t)1000000000
                                   + (int64_t)(spec.tv_nsec);
  int64_t system_current_time_us = system_current_time_ns / 1000;

  return system_current_time_us;
}

/*
 * Handling of the ready outputs
 *
 * param[in]       timestamp       time in microseconds
 * param[in]       iaq             IAQ signal
 * param[in]       iaq_accuracy    accuracy of IAQ signal
 * param[in]       temperature     temperature signal
 * param[in]       humidity        humidity signal
 * param[in]       pressure        pressure signal
 * param[in]       raw_temperature raw temperature signal
 * param[in]       raw_humidity    raw humidity signal
 * param[in]       gas             raw gas sensor signal
 * param[in]       bsec_status     value returned by the bsec_do_steps() call
 *
 * return          none
 */
void output_ready(int64_t timestamp, float iaq, uint8_t iaq_accuracy,
                  float temperature, float humidity, float pressure,
                  float raw_temperature, float raw_humidity, float gas,
                  bsec_library_return_t bsec_status,
                  float static_iaq, float co2_equivalent,
                  float breath_voc_equivalent)
{
  //int64_t timestamp_s = timestamp / 1000000000;
  ////int64_t timestamp_ms = timestamp / 1000;

  //time_t t = timestamp_s;
  /*
   * timestamp for localtime only makes sense if get_timestamp_us() uses
   * CLOCK_REALTIME
   */
  time_t t = time(NULL);
  struct tm tm = *localtime(&t);

  printf("{\\"IAQ_Accuracy\\": \\"%d\\"", iaq_accuracy);
  printf(", \\"IAQ\\": \\"%.2f\\"", iaq);
  printf(", \\"Temperature\\": \\"%.2f\\"", temperature);
  printf(", \\"Humidity\\": \\"%.2f\\"", humidity);
  printf(", \\"Pressure\\": \\"%.2f\\"", pressure / 100);
  printf(", \\"Gas\\": \\"%.0f\\"", gas);
  printf(", \\"Status\\": \\"%d\\"}", bsec_status);
  printf("\\r\\n");
  fflush(stdout);
}

/*
 * Load binary file from non-volatile memory into buffer
 *
 * param[in,out]   state_buffer    buffer to hold the loaded data
 * param[in]       n_buffer        size of the allocated buffer
 * param[in]       filename        name of the file on the NVM
 * param[in]       offset          offset in bytes from where to start copying
 *                                  to buffer
 * return          number of bytes copied to buffer or zero on failure
 */
uint32_t binary_load(uint8_t *b_buffer, uint32_t n_buffer, char *filename,
                     uint32_t offset)
{
  int32_t copied_bytes = 0;
  int8_t rslt = 0;

  struct stat fileinfo;
  rslt = stat(filename, &fileinfo);
  if (rslt != 0) {
    fprintf(stderr,"stat'ing binary file %s: ",filename);
    perror("");
    return 0;
  }

  uint32_t filesize = fileinfo.st_size - offset;

  if (filesize > n_buffer) {
    fprintf(stderr,"%s: %d > %d\\n", "binary data bigger than buffer", filesize,
            n_buffer);
    return 0;
  } else {
    FILE *file_ptr;
    file_ptr = fopen(filename,"rb");
    if (!file_ptr) {
      perror("fopen");
      return 0;
    }
    fseek(file_ptr,offset,SEEK_SET);
    copied_bytes = fread(b_buffer,sizeof(char),filesize,file_ptr);
    if (copied_bytes == 0) {
      fprintf(stderr,"%s empty\\n",filename);
    }
    fclose(file_ptr);
    return copied_bytes;
  }
}

/*
 * Load previous library state from non-volatile memory
 *
 * param[in,out]   state_buffer    buffer to hold the loaded state string
 * param[in]       n_buffer        size of the allocated state buffer
 *
 * return          number of bytes copied to state_buffer or zero on failure
 */
uint32_t state_load(uint8_t *state_buffer, uint32_t n_buffer)
{
  int32_t rslt = 0;
  rslt = binary_load(state_buffer, n_buffer, filename_state, 0);
  return rslt;
}

/*
 * Save library state to non-volatile memory
 *
 * param[in]       state_buffer    buffer holding the state to be stored
 * param[in]       length          length of the state string to be stored
 *
 * return          none
 */
void state_save(const uint8_t *state_buffer, uint32_t length)
{
  FILE *state_w_ptr;
  state_w_ptr = fopen(filename_state,"wb");
  fwrite(state_buffer,length,1,state_w_ptr);
  fclose(state_w_ptr);
}

/*
 * Load library config from non-volatile memory
 *
 * param[in,out]   config_buffer    buffer to hold the loaded state string
 * param[in]       n_buffer         size of the allocated state buffer
 *
 * return          number of bytes copied to config_buffer or zero on failure
 */
uint32_t config_load(uint8_t *config_buffer, uint32_t n_buffer)
{
  int32_t rslt = 0;
  /*
   * Provided config file is 4 bytes larger than buffer.
   * Apparently skipping the first 4 bytes works fine.
   *
   */
  rslt = binary_load(config_buffer, n_buffer, filename_config, 4);
  return rslt;
}

/* main */

/*
 * Main function which configures BSEC library and then reads and processes
 * the data from sensor based on timer ticks
 *
 * return      result of the processing
 */
int main(int argc, char *argv[])
{
  //putenv(DESTZONE); // Now taken care of in the Python controller.
  if (argc == 4)
    {
      i2c_address = atoi (argv[1]);
      if (i2c_address < 118 || i2c_address > 119)
        {
          printf("Error: '%s' is not a valid address for argument <i2c_address>.\\nValid Options: 118|119\\n", argv[1]);
          return 1;
        }
      temp_offset = strtof (argv[2], NULL);
      if (temp_offset > 10.0 || temp_offset < -10.0)
        {
          printf("Error: '%f' is outside of the valid range for argument <temperature_offset>.\\nValid Range: 10.0 to -10.0\\n", temp_offset);
          return 1;
        }
      if (strcmp(argv[3], "LP") == 0)
        {
          sample_rate_mode = BSEC_SAMPLE_RATE_LP;
        }
      else if (strcmp(argv[3], "ULP") == 0)
        {
          sample_rate_mode = BSEC_SAMPLE_RATE_ULP;
        }
      else
        {
          printf("Error: '%s' isn't a valid option for argument <sample_rate_mode>.\\nValid Options: LP|ULP\\n", argv[3]);
          return 1;
        }
    }
  else
    {
      printf("Usage:\\n");
      printf("  %s <i2c_address> <temp_offset> <sample_rate_mode>\\n", argv[0]);
      printf("       i2c_address: 118|119\\n       temp_offset: 10.0 to -10.0\\n  sample_rate_mode: LP|ULP\\n");
      return 1;
    }

  i2cOpen();
  i2cSetAddress(i2c_address);

  return_values_init ret;

  ret = bsec_iot_init(sample_rate_mode, temp_offset, bus_write, bus_read,
                      _sleep, state_load, config_load);
  if (ret.bme680_status) {
    /* Could not intialize BME680 */
    return (int)ret.bme680_status;
  } else if (ret.bsec_status) {
    /* Could not intialize BSEC library */
    return (int)ret.bsec_status;
  }

  /* Call to endless loop function which reads and processes data based on
   * sensor settings.
   * State is saved every 10.000 samples, which means every 10.000 * 3 secs
   * = 500 minutes (depending on the config).
   *
   */
  bsec_iot_loop(_sleep, get_timestamp_us, output_ready, state_save, 10000);

  i2cClose();
  return 0;
}
"""
if __name__ == "__main__":
    logging.critical("This module cannot not run standalone.")
    exit(1)
