"""
CH347 Module
------------

The `ch347` module provides functions for interacting with the CH347 USB-UART/SPI/I2C/JTAG bridge.

Initialization:
----------------

- Use `ch347.init()` to initialize the CH347 device.

Configuration:
--------------

- Use `ch347.set_spi_config(clock: int, mode: int)` to configure the SPI parameters.

SPI Communication:
------------------

- Use `ch347.spi_write(device_index: int, chip_select: int, write_data: bytes, write_step: int)`
  to write data to the SPI bus.

- Use `ch347.spi_read(device_index: int, chip_select: int, write_data: bytes, read_length: int)`
  to read data from the SPI bus.

Closing:
--------

- Use `ch347.close()` to close the CH347 device.

Usage Example:
--------------

import ch347

# Initialize the CH347 device
ch347.init()

# Configure the SPI parameters
ch347.set_spi_config(clock=1000000, mode=0)

# Write data to the SPI bus
ch347.spi_write(device_index=0, chip_select=1, write_data=b'\x01\x02\x03', write_step=3)

# Read data from the SPI bus
data = ch347.spi_read(device_index=0, chip_select=1, write_data=b'\x00', read_length=3)

# Close the CH347 device
ch347.close()
"""

from .ch347 import *
from .bacon import *
from .command import *
from .serial import *