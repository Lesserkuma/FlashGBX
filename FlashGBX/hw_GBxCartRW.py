# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

# pylint: disable=wildcard-import, unused-wildcard-import
import datetime, hashlib, math, os, random, re, struct, time, zipfile, zlib
from serial import SerialException
from serial.serialutil import Timeout
from .app import AppInfo
from .LK_Device import *
from .i18n import __, c__, format_decimal
from .IniSettings import IniSettings

class GbxDevice(LK_Device):
	DEVICE_NAME = "GBxCart RW"
	USB_IDS = ((0x1A86, 0x7523),)
	DEVICE_MIN_FW = 1
	DEVICE_MAX_FW = 1
	DEVICE_LATEST_FW_TS = { 4:1709317610, 5:1793184971, 6:1793184971, 2:0, 90:0, 100:0 }
	PCB_VERSIONS = { 5:'v1.4', 6:'v1.4a/b/c', 2:'v1.1/v1.2', 4:'v1.3', 90:'XMAS v1.0', 100:'Mini v1.0' }
	DEVICE_LABEL_LONG = "GBxCart RW v1.4 or v1.4a/b/c"
	DEVICE_LABEL_SHORT = "GBxCart RW v1.4"
	FWUPDATE_ACTION = "fwupdate-gbxcartrw"
	CLI_UPDATER_METHOD = "UpdateFirmwareGBxCartRW"
	DEVICE_SUPPORT_MESSAGE = "For help with your GBxCart RW, please visit the insideGadgets Discord:\nhttps://gbxcart.com/discord"

	BAUDRATE = 1000000
	FLOW_CONTROL = False
	MAX_BUFFER_READ = 0x1000
	MAX_BUFFER_WRITE = 0x400
	DEVICE_CMD = LK_Device.DEVICE_CMD.copy()
	DEVICE_CMD.update({
		"OFW_RESET_AVR":0x2A,
		"OFW_CART_MODE":0x43,
		"OFW_FW_VER":0x56,
		"OFW_PCB_VER":0x68,
		"OFW_USART_1_0M_SPEED":0x3C,
		"OFW_USART_1_5M_SPEED":0x3E,
		"OFW_CART_PWR_ON":0x2F,
		"OFW_CART_PWR_OFF":0x2E,
		"OFW_QUERY_CART_PWR":0x5D,
		"OFW_DONE_LED_ON":0x3D,
		"OFW_ERROR_LED_ON":0x3F,
		"OFW_GB_CART_MODE":0x47,
		"OFW_GB_FLASH_BANK_1_COMMAND_WRITES":0x4E,
		"OFW_LNL_QUERY":0x25,
	})

	def _OpenSerial(self, *args, **kwargs):
		return GBxCartSerial(*args, **kwargs)

	def _ConfigureACKTransport(self):
		if not isinstance(self.DEVICE, GBxCartSerial) or not self.FW: return
		if self.FW.get("pcb_ver") not in (5, 6) or self.FW.get("cfw_id") != "L" or self.FW.get("fw_ver", 0) < 16: return
		self.FW["uart_ack"] = self.DEVICE.ConfigureACK(self.FLOW_CONTROL)
		self.FW["uart_rle"] = self.DEVICE.COMPRESSION_SUPPORTED
		if self.DEVICE.ACK_ENABLED:
			self.MAX_BUFFER_READ = 0x2000
		elif self.BAUDRATE == 1000000:
			self.MAX_BUFFER_READ = 0x100
		else:
			self.MAX_BUFFER_READ = 0x1000
		self.MAX_BUFFER_WRITE = 0x100 if self.DEVICE.ACK_ENABLED or self.BAUDRATE == 1000000 else 0x400
		dprint("GBxCart RW Flow Control Mode:", self.DEVICE.ACK_ENABLED)

	def SetFlowControl(self, enabled):
		self.FLOW_CONTROL = bool(enabled)
		if self.DEVICE is not None and self.DEVICE.is_open:
			self._ConfigureACKTransport()

	def _DisableACKTransport(self):
		if isinstance(self.DEVICE, GBxCartSerial) and self.DEVICE.ACK_ENABLED:
			self.DEVICE.SetACKMode(False)

	def Initialize(self, flashcarts=None, port=None, max_baud=1500000):
		if self.DEVICE is not None: self.DEVICE.close()
		self.DEVICE = None
		self.FW = None

		conn_msg = []
		ports = []
		if port is not None:
			ports = [ port ]
		else:
			ports = self.GetCandidatePorts()
			if len(ports) == 0: return False

		for i in range(0, len(ports)):
			for baudrate in (1000000, 1500000):
				try:
					if self.TryConnect(ports[i], baudrate, keep_open=True):
						self.BAUDRATE = baudrate
						break
				except SerialException as e:
					if "Permission" in str(e):
						conn_msg.append([3, __("The device on port {port} couldn’t be accessed. Make sure your user account has permission to use it and it’s not already in use by another application.", port=ports[i])])
					elif "FileNotFoundError" in str(e):
						continue
					else:
						conn_msg.append([3, __("A critical error occured while trying to access the device on port {port}.", port=ports[i]) + "\n\n" + str(e)])
					continue

			if self.FW is None or self.FW == {}: continue
			dev = self.DEVICE
			if self.FW.get("pcb_ver") in (5, 6, 101):
				self.PORT = ports[i]
				baudrate = 1500000 if max_baud >= 1500000 else 1000000
				if self.BAUDRATE != baudrate:
					self.ChangeBaudRate(baudrate=baudrate, keep_open=True)

			dprint(f"Found a {self.DEVICE_NAME}")
			dprint("Firmware information:", self.FW)
			dprint("Baud rate:", self.BAUDRATE)

			if self.DEVICE is None or not self.IsConnected() or self.FW is None or self.FW["pcb_ver"] not in self.DEVICE_LATEST_FW_TS:
				dev.close()
				self.DEVICE = None
				if self.FW is not None:
					conn_msg.append([0, __("Couldn’t communicate with the {device_name} on port {port}. Please disconnect and reconnect the device, then try again.", device_name=self.DEVICE_NAME, port=ports[i])])
				continue
			elif self.FW["fw_ts"] > self.DEVICE_LATEST_FW_TS[self.FW["pcb_ver"]]:
				conn_msg.append([1, __("Note: The {device_name} on port {port} is running a firmware version that is newer than what this version of FlashGBX was developed to work with, so errors may occur.", device_name=self.DEVICE_NAME, port=ports[i])])
			elif self.FW["pcb_ver"] in (5, 6, 101) and self.BAUDRATE > 1000000:
				self.MAX_BUFFER_READ = 0x1000
				self.MAX_BUFFER_WRITE = 0x400
			else:
				self.MAX_BUFFER_READ = 0x1000
				self.MAX_BUFFER_WRITE = 0x100

			if self.MAX_BUFFER_READ == 0x1000 and self.BAUDRATE == 1000000:
				self.MAX_BUFFER_READ = 0x100

			self.PORT = ports[i]
			self.DEVICE.timeout = self.DEVICE_TIMEOUT
			self._ConfigureACKTransport()
			self.FirmwareUpdateAvailable()

			# Load Flash Cartridge Handlers
			if flashcarts is not None:
				self.UpdateFlashCarts(flashcarts)

			# Stop after first found device
			break

		return conn_msg

	def LoadFirmwareVersion(self):
		dprint("Querying firmware version")
		try:
			self.DEVICE.timeout = 0.075
			self.DEVICE.reset_input_buffer()
			self.DEVICE.reset_output_buffer()
			self._write(self.DEVICE_CMD["OFW_PCB_VER"])
			temp = self.DEVICE.read(1)
			self.DEVICE.timeout = self.DEVICE_TIMEOUT
			if len(temp) == 0:
				dprint("No response")
				self.FW = None
				return False
			pcb = temp[0]
			if self.DEVICE.baudrate > 1000000 and pcb not in (5, 6, 101):
				self.FW = None
				return False
			self._write(self.DEVICE_CMD["OFW_FW_VER"])
			ofw = self._read(1)
			if (pcb == 2 and ofw == 2):
				dprint(f"Not a {self.DEVICE_NAME}")
				self.FW = None
				return False
			if (pcb >= 5 and ofw == 0):
				dprint(f"Not a {self.DEVICE_NAME}")
				self.FW = None
				return False
			if (pcb < 5 and ofw > 0):
				self.FW = {
					"ofw_ver":ofw,
					"pcb_ver":pcb,
					"pcb_name":"GBxCart RW",
					"cfw_id":"",
					"fw_ver":0,
					"fw_ts":0,
					"fw_dt":"",
				}
				return True

			self._write(self.DEVICE_CMD["QUERY_FW_INFO"])
			size = self._read(1)
			if size != 8: return False
			data = self._read(size)
			info = data[:8]
			keys = ["cfw_id", "fw_ver", "pcb_ver", "fw_ts"]
			values = struct.unpack(">cHBI", bytearray(info))
			self.FW = dict(zip(keys, values))
			self.FW["cfw_id"] = self.FW["cfw_id"].decode('ascii')
			self.FW["fw_dt"] = datetime.datetime.fromtimestamp(self.FW["fw_ts"]).astimezone().replace(microsecond=0).isoformat()
			self.FW["ofw_ver"] = ofw
			self.FW["pcb_name"] = ""
			self.FW["cart_power_ctrl"] = False
			self.FW["bootloader_reset"] = False
			if self.FW["cfw_id"] == "L" and self.FW["fw_ver"] >= 12:
				size = self._read(1)
				name = self._read(size)
				if len(name) > 0:
					try:
						self.FW["pcb_name"] = name.decode("UTF-8").replace("\x00", "").strip()
					except:
						self.FW["pcb_name"] = "Unnamed Device"
					self.DEVICE_NAME = self.FW["pcb_name"]

				# Cartridge Power Control support
				temp = self._read(1)
				self.FW["cart_power_ctrl"] = True if temp & 1 == 1 else False
				self.FW["cart_presence_switch"] = True if (temp >> 1) & 1 == 1 else False
				self.FW["cart_mode_switch"] = True if (temp >> 2) & 1 == 1 else False

				# Reset to bootloader support
				temp = self._read(1)
				self.FW["bootloader_reset"] = bool(temp & 1)
				self.FW["device_serial"] = self.ReadDeviceSerial() if temp & 2 else None

			self._ConfigureACKTransport()
			return True

		except Exception as e:
			dprint("Disconnecting due to an error", e, sep="\n")
			try:
				if self.DEVICE.isOpen():
					self.DEVICE.reset_input_buffer()
					self.DEVICE.reset_output_buffer()
					self.DEVICE.close()
				self.DEVICE = None
			except:
				pass
			return False

	def ChangeBaudRate(self, baudrate, keep_open=False):
		if baudrate == 1000000:
			if self.DEVICE is None or not self.DEVICE.isOpen():
				if not self.PORT: return
				self.DEVICE = self._OpenSerial(self.PORT, self.BAUDRATE, timeout=0.1)
		elif not self.IsConnected():
			return
		dprint("Changing baud rate to", baudrate)
		close_port = True
		try:
			self._DisableACKTransport()
			if baudrate == 1500000:
				self._write(self.DEVICE_CMD["OFW_USART_1_5M_SPEED"])
			elif baudrate == 1000000:
				self._write(self.DEVICE_CMD["OFW_USART_1_0M_SPEED"])
			self.BAUDRATE = baudrate
			self.LAST_CHECK_ACTIVE = 0
			if keep_open:
				self.DEVICE.baudrate = baudrate
				close_port = False
		finally:
			if close_port: self.DEVICE.close()

	def CheckActive(self):
		if self.LAST_CHECK_ACTIVE and time.monotonic() < self.LAST_CHECK_ACTIVE + 1: return True
		dprint("Checking if device is active (GBxCart RW specific)")
		if self.DEVICE is None: return False
		if self.FW["pcb_name"] is None:
			if self.LoadFirmwareVersion():
				self.LAST_CHECK_ACTIVE = time.monotonic()
				return True
			return False
		try:
			if self.FW["fw_ver"] == 0: # legacy GBxCart RW firmware
				self.LAST_CHECK_ACTIVE = time.monotonic()
				return True
			elif self.FW["fw_ver"] < 12:
				self._write(bytearray([self.DEVICE_CMD["OFW_FW_VER"]]))
				self._read(1)
				self.LAST_CHECK_ACTIVE = time.monotonic()
				return True
			else:
				return super().CheckActive()
		except Exception as e:
			dprint("Disconnecting...", e)
			try:
				if self.DEVICE.isOpen():
					self.DEVICE.reset_input_buffer()
					self.DEVICE.reset_output_buffer()
					self.DEVICE.close()
				self.DEVICE = None
			except:
				pass
			return False

	def GetFirmwareVersion(self, more=False):
		if self.FW["fw_ver"] == 0: # old GBxCart RW
			return "R{:d}".format(self.FW["ofw_ver"])

		if self.FW["pcb_ver"] in (5, 6, 101):
			s = "R{:d}+{:s}{:d}".format(self.FW["ofw_ver"], self.FW["cfw_id"], self.FW["fw_ver"])
		else:
			s = "{:s}{:d}".format(self.FW["cfw_id"], self.FW["fw_ver"])
		if more:
			s += " ({:s})".format(self.FW["fw_dt"])
		return s

	def GetFullNameExtended(self, more=False):
		if self.FW["fw_ver"] == 0:  # old GBxCart RW
			return __("{device_name} – Firmware {fw_version} ({port})", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), port=self.GetPort())

		if more:
			return __("{device_name} – Firmware {fw_version} ({timestamp}) on {port} at {baudrate}M baud", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), timestamp=self.FW["fw_dt"], port=self.GetPort(), baudrate=format_decimal(self.BAUDRATE/1000/1000, precision=1))
		else:
			return __("{device_name} – Firmware {fw_version} ({port})", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), port=self.GetPort())

	def CanSetVoltageBySwitch(self):
		return False

	def CanSetVoltageByCode(self):
		return True

	def CanSetVoltageByAutoswitch(self):
		return False

	def CanPowerCycleCart(self):
		if self.FW is None or self.DEVICE is None: return False
		if not self.DEVICE.is_open: return False
		if self.FW["fw_ver"] >= 12:
			return self.FW["cart_power_ctrl"]
		else:
			return self.FW["pcb_ver"] in (5, 6)

	def CartPowerOn(self):
		# Restart the ACK window after handling stray bytes during cartridge power-on.
		ack_enabled = isinstance(self.DEVICE, GBxCartSerial) and self.DEVICE.ACK_ENABLED
		if ack_enabled: self.DEVICE.SetACKMode(False)
		try:
			return super().CartPowerOn()
		finally:
			if ack_enabled and self.DEVICE is not None and self.DEVICE.is_open:
				self.DEVICE.SetACKMode(True)

	def GetSupportedModes(self):
		if self.FW["pcb_ver"] == 101:
			return ["DMG"]
		else:
			return ["DMG", "AGB"]

	def IsSupported3dMemory(self):
		return True

	def IsClkConnected(self):
		return self.FW["pcb_ver"] in (5, 6, 101)

	def SupportsFirmwareUpdates(self):
		if not isinstance(getattr(self, "FW", None), dict):
			return True
		if "pcb_ver" not in self.FW:
			return True
		if "ofw_ver" not in self.FW:
			return self.FW["pcb_ver"] in (2, 4, 5, 6, 90, 100, 101)

		if self.FW["ofw_ver"] == 30:
			if self.DEVICE is not None:
				self._write(self.DEVICE_CMD["OFW_LNL_QUERY"])
				old_timeout = self.DEVICE.timeout
				self.DEVICE.timeout = 0.15
				is_lnl = self._read(1) == 0x31
				self.DEVICE.timeout = old_timeout
				dprint("LinkNLoad detected:", is_lnl)
				if is_lnl: return False
		return self.FW["pcb_ver"] in (2, 4, 5, 6, 90, 100, 101)

	def FirmwareUpdateAvailable(self):
		self.FW_UPDATE_REQ = False
		if self.FW["pcb_ver"] in (2, 4, 90, 100) or (self.FW["fw_ver"] == 0 and self.FW["pcb_ver"] == 101):
			self.FW_UPDATE_REQ = 2
			return True
		if self.FW["pcb_ver"] not in (5, 6): return False
		if self.FW.get("uart_ack") is False: return True
		if self.FW.get("uart_rle") is False: return True
		if self.FW["fw_ts"] != self.DEVICE_LATEST_FW_TS[self.FW["pcb_ver"]]:
			return True

	def GetLastSupportedVersion(self):
		return "3.37"

	def GetFirmwareUpdaterClass(self):
		if self is None or self.FW["pcb_ver"] in (5, 6): # v1.4 / v1.4a/b/c
			try:
				return (FirmwareUpdater, FirmwareUpdaterWindow)
			except:
				return None
		elif self.FW["pcb_ver"] in (2, 4, 90, 100, 101): # v1.3
			try:
				return (None, FirmwareUpdaterWindowV13)
			except:
				return None
		else:
			return None

	def ResetLEDs(self):
		if self.DEVICE in (None, False): return
		self._write(self.DEVICE_CMD["OFW_CART_MODE"]) # Reset LEDs
		self._read(1)

	def SupportsBootloaderReset(self):
		return bool(self.FW and self.FW.get("fw_ver", 0) >= 16 and self.FW.get("bootloader_reset", False))

	def BootloaderReset(self):
		if not self.SupportsBootloaderReset(): return False
		dprint("Resetting to bootloader...")
		try:
			self._DisableACKTransport()
			if self._write(self.DEVICE_CMD["BOOTLOADER_RESET"], wait=True) != 1: return False
			self._write(1)
			self.DEVICE.close()
			time.sleep(0.1)
			return True
		except (OSError, SerialException) as e:
			dprint("Bootloader reset failed:", e)
			return False

	def SupportsAudioAsWe(self):
		return True

	def Close(self, cartPowerOff=False):
		dev = self.DEVICE
		try:
			try:
				self._DisableACKTransport()
				self.ResetLEDs()
			except SerialException:
				pass
			return super().Close(cartPowerOff)
		finally:
			if dev is not None and dev.is_open:
				dev.close()

	def SetTimeout(self, seconds=1):
		if seconds < 1: seconds = 1
		self.DEVICE_TIMEOUT = seconds
		self.DEVICE.timeout = self.DEVICE_TIMEOUT

	def _read(self, count):
		result = super()._read(count)
		if result is False and isinstance(self.DEVICE, GBxCartSerial) and self.DEVICE.ACK_ENABLED:
			self.DEVICE.Synchronize(enable_ack=True)
		return result

	def GetVarState(self):
		if not isinstance(self.DEVICE, GBxCartSerial) or not self.DEVICE.ACK_ENABLED:
			return super().GetVarState()
		self._write(self.DEVICE_CMD["GET_VAR_STATE"])
		old_timeout = self.DEVICE.timeout
		self.DEVICE.timeout = 0.1
		buffer = bytearray()
		try:
			while True:
				part = self.DEVICE.read(64)
				buffer.extend(part)
				if len(part) < 64: return buffer
		finally:
			self.DEVICE.timeout = old_timeout


class GBxCartSerial(serial.Serial):
	ACK_WINDOW = 64
	MODE_COMMAND = b"~"
	FRAME_SIZE = 4096

	def __init__(self, *args, **kwargs):
		self.ACK_ENABLED = False
		self.ACK_SUPPORTED = None
		self.ACK_COUNT = 0
		self.ACK_SEQUENCE = 0
		self.COMPRESSION = True
		self.COMPRESSION_SUPPORTED = None
		self.COMPRESSION_ENABLED = False
		self.FRAME_SEQUENCE = 0
		self.FRAME_INPUT = bytearray()
		self.FRAME_OUTPUT = bytearray()

		super().__init__(*args, **kwargs)
		if self.is_open:
			try:
				self.Synchronize()
			except (OSError, serial.SerialException):
				super().close()
				raise

	def _WriteRaw(self, data):
		if super().write(data) != len(data):
			raise serial.SerialTimeoutException("Incomplete GBxCart RW serial write")

	def Synchronize(self, enable_ack=False):
		self.ACK_ENABLED = False
		self.ACK_COUNT = self.ACK_SEQUENCE = 0
		self.COMPRESSION_ENABLED = False
		self.FRAME_SEQUENCE = 0
		self.FRAME_INPUT.clear()
		self.FRAME_OUTPUT.clear()
		super().reset_output_buffer()
		self._WriteRaw(b"\xFF\x18" * 3)
		self.flush()
		time.sleep(0.2)
		super().reset_input_buffer()
		if enable_ack:
			self.SetACKMode(True)

	def ConfigureACK(self, enabled):
		if self.ACK_SUPPORTED is None:
			self._WriteRaw(self.MODE_COMMAND + b"\x00")
			reply = super().read(1)
			self.ACK_SUPPORTED = reply == b"\x06"
			if not self.ACK_SUPPORTED:
				if reply:
					super().read(1)
				super().reset_input_buffer()
		if self.ACK_SUPPORTED and self.COMPRESSION_SUPPORTED is None:
			self.write(self.MODE_COMMAND + b"\x03")
			self.COMPRESSION_SUPPORTED = self.read(1) == b"\xD3"
		if self.ACK_SUPPORTED:
			self.SetACKMode(enabled)
		return self.ACK_SUPPORTED

	def SetACKMode(self, enabled):
		compressed = bool(enabled and self.COMPRESSION_SUPPORTED and self.COMPRESSION)
		if self.ACK_ENABLED == enabled and self.COMPRESSION_ENABLED == compressed: return
		self.write(self.MODE_COMMAND + bytes((7 if compressed else int(enabled),)))
		if self.read(1) != b"\x06":
			raise serial.SerialException("GBxCart RW ACK mode negotiation failed")
		self.ACK_ENABLED = enabled
		self.ACK_COUNT = self.ACK_SEQUENCE = 0
		self.COMPRESSION_ENABLED = compressed
		self.FRAME_SEQUENCE = 0
		self.FRAME_INPUT.clear()
		self.FRAME_OUTPUT.clear()

	def write(self, data):
		if not self.ACK_ENABLED:
			return super().write(data)
		data = bytes(data)
		self._WriteRaw(data.replace(b"\xFF", b"\xFF\xFF"))
		return len(data)

	def flush(self):
		if self.write_timeout is None:
			return super().flush()
		deadline = Timeout(self.write_timeout)
		while self.out_waiting:
			if deadline.expired():
				raise serial.SerialTimeoutException("GBxCart RW serial flush timed out")
			time.sleep(0.001)

	def _ReadACK(self, size):
		if not self.ACK_ENABLED:
			return super().read(size)
		buffer = bytearray()
		deadline = Timeout(self.timeout)
		while len(buffer) < size:
			count = min(size - len(buffer), self.ACK_WINDOW - self.ACK_COUNT)
			part = super().read(count)
			buffer.extend(part)
			self.ACK_COUNT += len(part)
			if self.ACK_COUNT == self.ACK_WINDOW:
				self._WriteRaw(b"\xFF\x06" + bytes((self.ACK_SEQUENCE,)))
				self.ACK_SEQUENCE = (self.ACK_SEQUENCE + 1) & 255
				self.ACK_COUNT = 0
			if len(part) != count or (not deadline.is_non_blocking and deadline.expired()):
				break
		return bytes(buffer)

	def _ReadFrameBytes(self, size):
		if len(self.FRAME_INPUT) < size:
			self.FRAME_INPUT.extend(self._ReadACK(size - len(self.FRAME_INPUT)))
		return len(self.FRAME_INPUT) >= size

	def _ReadFrame(self):
		if not self._ReadFrameBytes(4): return False
		try:
			size, field = struct.unpack_from("<HH", self.FRAME_INPUT)
			compressed = bool(field & 0x4000)
			repeated = field == 0x8001
			if not 1 <= size <= self.FRAME_SIZE or not (field == size or repeated or 0x4000 < field < 0x4000 + size) or (repeated and size < 2):
				raise ValueError("Invalid compressed frame length or flags")
			length = field & 0x3FFF if compressed else 1 if repeated else size
			if not self._ReadFrameBytes(length + 8): return False
			checksum = struct.unpack_from("<I", self.FRAME_INPUT, length + 4)[0]
			if zlib.crc32(self.FRAME_INPUT[:length + 4], self.FRAME_SEQUENCE) != checksum:
				raise ValueError("Compressed frame checksum or sequence mismatch")
			payload = self.FRAME_INPUT[4:length + 4]
			buffer = bytearray()
			if compressed:
				position = 0
				while position < len(payload):
					token = payload[position]
					position += 1
					count = (token & 0x7F) + (3 if token & 0x80 else 1)
					take = 1 if token & 0x80 else count
					if position + take > len(payload) or len(buffer) + count > size:
						raise ValueError("Invalid RLE group length")
					data = payload[position:position + take]
					buffer.extend(data * count if token & 0x80 else data)
					position += take
				if len(buffer) != size: raise ValueError("Incomplete RLE frame")
			else:
				buffer = payload * size if repeated else payload
			self.FRAME_OUTPUT.extend(buffer)
			del self.FRAME_INPUT[:length + 8]
			self.FRAME_SEQUENCE = (self.FRAME_SEQUENCE + 1) & 0xFFFFFFFF
			return True
		except ValueError as e:
			self.Synchronize()
			raise serial.SerialException("GBxCart RW compressed transfer failed: " + str(e)) from e

	def read(self, size=1):
		if not self.COMPRESSION_ENABLED: return self._ReadACK(size)
		buffer = bytearray()
		deadline = Timeout(self.timeout)
		while len(buffer) < size:
			if not self.FRAME_OUTPUT and not self._ReadFrame(): break
			count = min(size - len(buffer), len(self.FRAME_OUTPUT))
			buffer.extend(self.FRAME_OUTPUT[:count])
			del self.FRAME_OUTPUT[:count]
			if not deadline.is_non_blocking and deadline.expired(): break
		return bytes(buffer)

	def _GetInWaiting(self):
		return len(self.FRAME_OUTPUT) + len(self.FRAME_INPUT) + super().in_waiting
	in_waiting = property(_GetInWaiting)

	def reset_input_buffer(self):
		if self.ACK_ENABLED:
			self.Synchronize(enable_ack=True)
		else:
			super().reset_input_buffer()

	def reset_output_buffer(self):
		if self.ACK_ENABLED and self.out_waiting:
			self.flush()
		super().reset_output_buffer()

	def close(self):
		try:
			if self.is_open and self.ACK_ENABLED:
				if self.in_waiting or self.FRAME_INPUT:
					self.Synchronize()
				else:
					self.SetACKMode(False)
		except (OSError, serial.SerialException):
			try:
				self.Synchronize()
			except (OSError, serial.SerialException):
				pass
		finally:
			self.ACK_ENABLED = False
			self.COMPRESSION_ENABLED = False
			super().close()


class FirmwareUpdater():
	PORT = ""

	def __init__(self, app_path=".", port=None):
		self.APP_PATH = app_path
		self.PORT = port

	def WriteFirmware(self, zipfn, fncSetStatus):
		try:
			with zipfile.ZipFile(zipfn) as archive:
				with archive.open("fw.ini") as f: buffer1 = bytearray(f.read())
				with archive.open("fw.bin") as f: buffer2 = bytearray(f.read())
		except (zipfile.BadZipFile, KeyError):
			fncSetStatus(__("The firmware update file is corrupted."))
			return 3
		if len(buffer2) < 0x20:
			fncSetStatus(__("The firmware update file is corrupted."))
			return 3
		while len(buffer1) < len(buffer2): buffer1 = buffer1 + buffer1
		random.seed(struct.unpack("<I", buffer2[-0x18:-0x14])[0])
		chk = buffer2[-0x14:]
		buffer = bytearray()
		for i in range(0, len(buffer2[0:-0x18])):
			r = int(random.random()*256) % 256
			buffer.append(buffer2[0:-0x18][len(buffer2[0:-0x18]) - i - 1] ^ r ^ buffer1[len(buffer1) - i - 1])
		if (chk != hashlib.sha1(buffer).digest()):
			fncSetStatus(__("The firmware update file is corrupted."))
			return 3

		if self.PORT is None:
			ports = []
			comports = serial.tools.list_ports.comports()
			for i in range(0, len(comports)):
				if comports[i].vid == 0x1A86 and comports[i].pid == 0x7523:
					ports.append(comports[i].device)
			if len(ports) == 0:
				fncSetStatus(__("No device found."))
				return 2
			port = ports[0]
		else:
			port = self.PORT
		data = buffer
		buffer = bytearray()

		fncSetStatus(text=__("Connecting..."))
		try:
			dev = serial.Serial(port=port, baudrate=57600, timeout=1)
		except:
			fncSetStatus(text=__("Device not accessible."), enableUI=True)
			return 2
		dev.reset_input_buffer()

		# Write firmware
		fncSetStatus(__("Updating firmware..."), setProgress=0)

		size = len(data)
		counter = 0
		while counter < size:
			byte = data[counter:counter+1]
			dev.write(byte)
			tmp_byte = dev.read(1)
			if (tmp_byte != byte):
				try:
					tmp_byte = int.from_bytes(tmp_byte, byteorder="little")
				except:
					tmp_byte = 0
				byte = int.from_bytes(byte, byteorder="little")
				if counter == 0:
					fncSetStatus(text=__("Update failed!"), enableUI=True)
				else:
					fncSetStatus(text=__("Update failed at offset {offset}!", offset="0x{:04X}".format(counter)), enableUI=True)
				return 2

			counter += 1
			percent = float(counter)/size*100
			fncSetStatus(text=__("Updating firmware... Do not unplug the device!"), setProgress=percent)

		dev.close()
		time.sleep(0.8)
		fncSetStatus(__("Done!"))
		time.sleep(0.2)
		return 1


try:
	from .pyside import QtCore, QtWidgets, QtGui, QDesktopWidget

	class FirmwareUpdaterWindow(QtWidgets.QDialog):
		APP = None
		DEVICE = None
		FWUPD = None
		DEV_NAME = "GBxCart RW"
		FW_VER = ""
		PCB_VER = ""

		def __init__(self, app, app_path, file=None, icon=None, device=None):
			QtWidgets.QDialog.__init__(self, app)
			if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
			self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
			self.setWindowTitle(AppInfo.NAME + " – " + __("Firmware Updater for {device_name}", device_name="GBxCart RW"))
			self.setWindowFlags((self.windowFlags() | QtCore.Qt.MSWindowsFixedSizeDialogHint) & ~QtCore.Qt.WindowContextHelpButtonHint)

			self.APP = app
			if device is not None:
				self.FWUPD = FirmwareUpdater(app_path, device.GetPort())
				self.DEV_NAME = device.GetName()
				self.FW_VER = device.GetFirmwareVersion(more=True)
				self.PCB_VER = device.GetPCBVersion()
				self.DEVICE = device
			else:
				self.APP.QT_APP.processEvents()
				self.FWUPD = FirmwareUpdater(app_path, None)

			self.layout = QtWidgets.QGridLayout()
			self.layout.setContentsMargins(-1, 8, -1, 8)
			self.layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
			self.layout_device = QtWidgets.QVBoxLayout()

			# ↓↓↓ Current Device Information
			self.grpDeviceInfo = QtWidgets.QGroupBox(__("Current Firmware"))
			self.grpDeviceInfo.setMinimumWidth(420)
			self.grpDeviceInfoLayout = QtWidgets.QVBoxLayout()
			self.grpDeviceInfoLayout.setContentsMargins(-1, 3, -1, -1)
			rowDeviceInfo1 = QtWidgets.QHBoxLayout()
			self.lblDeviceName = QtWidgets.QLabel(__("Device:"))
			self.lblDeviceName.setMinimumWidth(120)
			self.lblDeviceNameResult = QtWidgets.QLabel("GBxCart RW")
			rowDeviceInfo1.addWidget(self.lblDeviceName)
			rowDeviceInfo1.addWidget(self.lblDeviceNameResult)
			rowDeviceInfo1.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo1)
			rowDeviceInfo3 = QtWidgets.QHBoxLayout()
			self.lblDeviceFWVer = QtWidgets.QLabel(__("Firmware version:"))
			self.lblDeviceFWVer.setMinimumWidth(120)
			self.lblDeviceFWVerResult = QtWidgets.QLabel("")
			rowDeviceInfo3.addWidget(self.lblDeviceFWVer)
			rowDeviceInfo3.addWidget(self.lblDeviceFWVerResult)
			rowDeviceInfo3.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo3)
			rowDeviceInfo2 = QtWidgets.QHBoxLayout()
			self.lblDevicePCBVer = QtWidgets.QLabel(__("PCB version:"))
			self.lblDevicePCBVer.setMinimumWidth(120)
			self.optDevicePCBVer14 = QtWidgets.QRadioButton("v1.4")
			self.connect(self.optDevicePCBVer14, QtCore.SIGNAL("clicked()"), self.SetPCBVersion)
			self.optDevicePCBVer14a = QtWidgets.QRadioButton("v1.4a/b/c")
			self.connect(self.optDevicePCBVer14a, QtCore.SIGNAL("clicked()"), self.SetPCBVersion)
			rowDeviceInfo2.addWidget(self.lblDevicePCBVer)
			rowDeviceInfo2.addWidget(self.optDevicePCBVer14)
			rowDeviceInfo2.addWidget(self.optDevicePCBVer14a)
			rowDeviceInfo2.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo2)
			self.grpDeviceInfo.setLayout(self.grpDeviceInfoLayout)
			self.layout_device.addWidget(self.grpDeviceInfo)
			# ↑↑↑ Current Device Information

			# ↓↓↓ Available Firmware Updates
			self.grpAvailableFwUpdates = QtWidgets.QGroupBox(__("Available Firmware"))
			self.grpAvailableFwUpdates.setMinimumWidth(400)
			self.grpAvailableFwUpdatesLayout = QtWidgets.QVBoxLayout()
			self.grpAvailableFwUpdatesLayout.setContentsMargins(-1, 3, -1, -1)

			rowDeviceInfo4 = QtWidgets.QHBoxLayout()
			self.lblDeviceFWVer2 = QtWidgets.QLabel(__("Firmware version:"))
			self.lblDeviceFWVer2.setMinimumWidth(120)
			self.lblDeviceFWVer2Result = QtWidgets.QLabel("(" + __("Please choose the PCB version") + ")")
			rowDeviceInfo4.addWidget(self.lblDeviceFWVer2)
			rowDeviceInfo4.addWidget(self.lblDeviceFWVer2Result)
			rowDeviceInfo4.addStretch(1)
			self.grpAvailableFwUpdatesLayout.addLayout(rowDeviceInfo4)

			self.rowUpdate = QtWidgets.QHBoxLayout()
			self.btnUpdate = QtWidgets.QPushButton(__("Install Firmware Update"))
			self.btnUpdate.setMinimumWidth(200)
			self.btnUpdate.setContentsMargins(20, 20, 20, 20)
			self.connect(self.btnUpdate, QtCore.SIGNAL("clicked()"), lambda: [ self.UpdateFirmware() ])
			self.rowUpdate.addStretch()
			self.rowUpdate.addWidget(self.btnUpdate)
			self.rowUpdate.addStretch()

			self.grpAvailableFwUpdatesLayout.addSpacing(3)
			self.grpAvailableFwUpdatesLayout.addItem(self.rowUpdate)
			self.grpAvailableFwUpdates.setLayout(self.grpAvailableFwUpdatesLayout)
			self.layout_device.addWidget(self.grpAvailableFwUpdates)
			# ↑↑↑ Available Firmware Updates

			self.grpStatus = QtWidgets.QGroupBox("")
			self.grpStatusLayout = QtWidgets.QGridLayout()
			self.prgStatus = QtWidgets.QProgressBar()
			self.prgStatus.setMinimum(0)
			self.prgStatus.setMaximum(1000)
			self.prgStatus.setValue(0)
			self.lblStatus = QtWidgets.QLabel(__("Status: Ready."))

			self.grpStatusLayout.addWidget(self.prgStatus, 1, 0)
			self.grpStatusLayout.addWidget(self.lblStatus, 2, 0)

			self.grpStatus.setLayout(self.grpStatusLayout)
			self.layout_device.addWidget(self.grpStatus)

			self.grpFooterLayout = QtWidgets.QHBoxLayout()
			self.btnClose = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Close"))
			self.connect(self.btnClose, QtCore.SIGNAL("clicked()"), lambda: [ self.reject() ])
			self.grpFooterLayout.addStretch()
			self.grpFooterLayout.addWidget(self.btnClose)
			self.layout_device.addItem(self.grpFooterLayout)

			self.layout.addLayout(self.layout_device, 0, 0)
			self.setLayout(self.layout)

			self.lblDeviceNameResult.setText(self.DEV_NAME)
			self.lblDeviceFWVerResult.setText(self.FW_VER)
			if self.PCB_VER == "v1.4":
				self.optDevicePCBVer14.setChecked(True)
				self.optDevicePCBVer14a.setEnabled(False)
			elif self.PCB_VER == "v1.4a/b/c":
				self.optDevicePCBVer14a.setChecked(True)
				self.optDevicePCBVer14.setEnabled(False)
			self.SetPCBVersion()

		def SetPCBVersion(self):
			if self.optDevicePCBVer14.isChecked():
				file_name = self.FWUPD.APP_PATH + os.sep + os.path.join("res", "fw_GBxCart_RW_v1_4.zip")
			elif self.optDevicePCBVer14a.isChecked():
				file_name = self.FWUPD.APP_PATH + os.sep + os.path.join("res", "fw_GBxCart_RW_v1_4a.zip")
			else:
				return

			with zipfile.ZipFile(file_name) as zip:
				with zip.open("fw.ini") as f: ini_file = f.read()
				ini_file = ini_file.decode(encoding="utf-8")
				self.INI = IniSettings(ini=ini_file, main_section="Firmware")
				self.OFW_VER = self.INI.GetValue("fw_ver")
				self.OFW_BUILDTS = self.INI.GetValue("fw_buildts")
				self.OFW_TEXT = self.INI.GetValue("fw_text")

			self.lblDeviceFWVer2Result.setText("{:s} ({:s})".format(self.OFW_VER, datetime.datetime.fromtimestamp(int(self.OFW_BUILDTS)).astimezone().replace(microsecond=0).isoformat()))

		def run(self):
			try:
				self.layout.update()
				self.layout.activate()
				screenGeometry = QDesktopWidget().screenGeometry(self)
				x = (screenGeometry.width() - self.width()) / 2
				y = (screenGeometry.height() - self.height()) / 2
				self.move(x, y)
				self.show()
			except:
				return

		def hideEvent(self, event):
			if self.DEVICE is None:
				self.APP.ConnectDevice()
			self.APP.activateWindow()

		def reject(self):
			if self.CloseDialog():
				super().reject()

		def CloseDialog(self):
			if self.btnClose.isEnabled() is False:
				text = __("<b>Warning:</b> If you close this window while a firmware update is still running, it might leave the device in an unbootable state.") + " " + __("You can still recover it by running the Firmware Updater again later.") + "<br><br>" + __("Are you sure you want to close this window?")
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.No)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.No: return False
			return True

		def UpdateFirmware(self):
			if self.optDevicePCBVer14.isChecked():
				device_version = "v1.4"
				pcb_version = 5
				file_name = self.FWUPD.APP_PATH + os.sep + os.path.join("res", "fw_GBxCart_RW_v1_4.zip")
				led = "Done"
			elif self.optDevicePCBVer14a.isChecked():
				device_version = "v1.4a/b/c"
				pcb_version = 6
				file_name = self.FWUPD.APP_PATH + os.sep + os.path.join("res", "fw_GBxCart_RW_v1_4a.zip")
				led = "Status"
			else:
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=__("Please select the PCB version of your GBxCart RW device."), standardButtons=QtWidgets.QMessageBox.Ok)
				answer = msgbox.exec()
				return False

			bootloader_entered = bool(self.DEVICE is not None and self.DEVICE.FW and self.DEVICE.FW.get("pcb_ver") == pcb_version and self.DEVICE.BootloaderReset())
			self.APP.DisconnectDevice()

			if not bootloader_entered:
				text = __("Please follow these steps to proceed with the firmware update:")
				text += "\n\n" + __(
					"- Disconnect the USB cable of your GBxCart RW {device_version}.\n"
					"- On the circuit board of your GBxCart RW {device_version}, press and hold down the small button while connecting the USB cable again.\n"
					"- Keep the small button held for at least 2 seconds, then let go of it.\n"
					"- If done right, the green LED labeled “{led}” should remain lit.",
					device_version=device_version,
					led=led
				)
				text += "\n" + __("- Click OK to continue.")
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.Ok)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.Cancel: return
			self.btnUpdate.setEnabled(False)
			self.btnClose.setEnabled(False)
			self.optDevicePCBVer14.setEnabled(False)
			self.optDevicePCBVer14a.setEnabled(False)

			while True:
				ret = self.FWUPD.WriteFirmware(file_name, self.SetStatus)
				if ret == 1:
					text = __("The firmware update is complete!")
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					self.optDevicePCBVer14.setEnabled(True)
					self.optDevicePCBVer14a.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					self.DEVICE = None
					self.reject()
					return True
				elif ret == 2:
					text = __("The firmware update has failed. Please try again.")
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					self.optDevicePCBVer14.setEnabled(True)
					self.optDevicePCBVer14a.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return False
				elif ret == 3:
					text = __("The firmware update file is corrupted. Please re-install the application.")
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					self.optDevicePCBVer14.setEnabled(True)
					self.optDevicePCBVer14a.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return False

		def SetStatus(self, text, enableUI=False, setProgress=None):
			self.lblStatus.setText(__("Status: {text}", text=text))
			if setProgress is not None:
				self.prgStatus.setValue(setProgress * 10)
			if enableUI:
				self.btnUpdate.setEnabled(True)
				self.btnClose.setEnabled(True)
				self.optDevicePCBVer14.setEnabled(True)
				self.optDevicePCBVer14a.setEnabled(True)
			self.APP.QT_APP.processEvents()
except ImportError:
	pass


try:
	from .pyside import QtCore, QtWidgets, QtGui, QDesktopWidget

	class FirmwareUpdaterWindowV13(QtWidgets.QDialog):
		APP = None
		DEVICE = None
		PORT = ""
		FW_FILES = {"v1.1/v1.2":"fw_GBxCart_RW_v1_1_v1_2.zip", "v1.3":"fw_GBxCart_RW_v1_3.zip", "XMAS v1.0":"fw_GBxCart_RW_XMAS_v1_0.zip", "Mini v1.0":"fw_GBxCart_RW_Mini_v1_0.zip"}

		def __init__(self, app, app_path, file=None, icon=None, device=None):
			QtWidgets.QDialog.__init__(self, app)
			if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
			self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
			self.APP = app
			self.APP_PATH = app_path
			self.DEVICE = device
			self.PCB_VER = device.GetPCBVersion()
			self.FW_VER = device.GetFirmwareVersion()
			self.PORT = device.GetPort()

			self.setWindowTitle(AppInfo.NAME + " – " + __("Firmware Updater for {device_name}", device_name="GBxCart RW"))
			self.setWindowFlags((self.windowFlags() | QtCore.Qt.MSWindowsFixedSizeDialogHint) & ~QtCore.Qt.WindowContextHelpButtonHint)

			with zipfile.ZipFile(self.APP_PATH + os.sep + os.path.join("res", "{:s}".format(self.FW_FILES[self.PCB_VER]))) as zip:
				with zip.open("fw.ini") as f: ini_file = f.read()
				ini_file = ini_file.decode(encoding="utf-8")
				self.INI = IniSettings(ini=ini_file, main_section="Firmware")
				self.CFW_VER = self.INI.GetValue("cfw_ver")
				self.CFW_TEXT = self.INI.GetValue("cfw_text")
				self.OFW_VER = self.INI.GetValue("ofw_ver")
				self.OFW_TEXT = self.INI.GetValue("ofw_text")

			self.layout = QtWidgets.QGridLayout()
			self.layout.setContentsMargins(-1, 8, -1, 8)
			self.layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
			self.layout_device = QtWidgets.QVBoxLayout()

			# ↓↓↓ Current Device Information
			self.grpDeviceInfo = QtWidgets.QGroupBox(__("Current Device Information"))
			self.grpDeviceInfo.setMinimumWidth(420)
			self.grpDeviceInfoLayout = QtWidgets.QVBoxLayout()
			self.grpDeviceInfoLayout.setContentsMargins(-1, 3, -1, -1)
			rowDeviceInfo1 = QtWidgets.QHBoxLayout()
			self.lblDeviceName = QtWidgets.QLabel(__("Device Name:"))
			self.lblDeviceName.setMinimumWidth(120)
			self.lblDeviceNameResult = QtWidgets.QLabel("GBxCart RW")
			rowDeviceInfo1.addWidget(self.lblDeviceName)
			rowDeviceInfo1.addWidget(self.lblDeviceNameResult)
			rowDeviceInfo1.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo1)
			rowDeviceInfo2 = QtWidgets.QHBoxLayout()
			self.lblDevicePCBVer = QtWidgets.QLabel(__("PCB version:"))
			self.lblDevicePCBVer.setMinimumWidth(120)
			self.lblDevicePCBVerResult = QtWidgets.QLabel("1.3")
			rowDeviceInfo2.addWidget(self.lblDevicePCBVer)
			rowDeviceInfo2.addWidget(self.lblDevicePCBVerResult)
			rowDeviceInfo2.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo2)
			rowDeviceInfo3 = QtWidgets.QHBoxLayout()
			self.lblDeviceFWVer = QtWidgets.QLabel(__("Firmware version:"))
			self.lblDeviceFWVer.setMinimumWidth(120)
			self.lblDeviceFWVerResult = QtWidgets.QLabel("R26")
			rowDeviceInfo3.addWidget(self.lblDeviceFWVer)
			rowDeviceInfo3.addWidget(self.lblDeviceFWVerResult)
			rowDeviceInfo3.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo3)
			self.grpDeviceInfo.setLayout(self.grpDeviceInfoLayout)
			self.layout_device.addWidget(self.grpDeviceInfo)
			# ↑↑↑ Current Device Information

			# ↓↓↓ Available Firmware Updates
			self.grpAvailableFwUpdates = QtWidgets.QGroupBox(__("Firmware Update Options"))
			self.grpAvailableFwUpdates.setMinimumWidth(400)
			self.grpAvailableFwUpdatesLayout = QtWidgets.QVBoxLayout()
			self.grpAvailableFwUpdatesLayout.setContentsMargins(-1, 3, -1, -1)

			self.optCFW = QtWidgets.QRadioButton("{:s}".format(self.CFW_VER))
			self.lblCFW_Info = QtWidgets.QLabel("{:s}".format(self.CFW_TEXT))
			self.lblCFW_Info.setWordWrap(True)
			self.lblCFW_Info.mousePressEvent = lambda x: [ self.optCFW.setChecked(True) ]
			self.optOFW = QtWidgets.QRadioButton("{:s}".format(self.OFW_VER))
			self.lblOFW_Info = QtWidgets.QLabel("{:s}".format(self.OFW_TEXT))
			self.lblOFW_Info.setWordWrap(True)
			self.lblOFW_Info.mousePressEvent = lambda x: [ self.optOFW.setChecked(True) ]
			self.optExternal = QtWidgets.QRadioButton(__("External firmware file"))

			self.rowUpdate = QtWidgets.QHBoxLayout()
			self.btnUpdate = QtWidgets.QPushButton(__("Install Firmware Update"))
			self.btnUpdate.setMinimumWidth(200)
			self.btnUpdate.setContentsMargins(20, 20, 20, 20)
			self.connect(self.btnUpdate, QtCore.SIGNAL("clicked()"), lambda: [ self.UpdateFirmware() ])
			self.rowUpdate.addStretch()
			self.rowUpdate.addWidget(self.btnUpdate)
			self.rowUpdate.addStretch()

			if self.PCB_VER == "v1.3":
				self.grpAvailableFwUpdatesLayout.addWidget(self.optCFW)
				self.grpAvailableFwUpdatesLayout.addWidget(self.lblCFW_Info)
				self.optCFW.setChecked(True)
			else:
				self.optOFW.setChecked(True)
			self.grpAvailableFwUpdatesLayout.addWidget(self.optOFW)
			self.grpAvailableFwUpdatesLayout.addWidget(self.lblOFW_Info)
			self.grpAvailableFwUpdatesLayout.addWidget(self.optExternal)
			self.grpAvailableFwUpdatesLayout.addSpacing(3)
			self.grpAvailableFwUpdatesLayout.addItem(self.rowUpdate)
			self.grpAvailableFwUpdates.setLayout(self.grpAvailableFwUpdatesLayout)
			self.layout_device.addWidget(self.grpAvailableFwUpdates)
			# ↑↑↑ Available Firmware Updates

			self.grpStatus = QtWidgets.QGroupBox("")
			self.grpStatusLayout = QtWidgets.QGridLayout()
			self.prgStatus = QtWidgets.QProgressBar()
			self.prgStatus.setMinimum(0)
			self.prgStatus.setMaximum(100)
			self.prgStatus.setValue(0)
			self.lblStatus = QtWidgets.QLabel(__("Ready."))

			self.grpStatusLayout.addWidget(self.prgStatus, 1, 0)
			self.grpStatusLayout.addWidget(self.lblStatus, 2, 0)

			self.grpStatus.setLayout(self.grpStatusLayout)
			self.layout_device.addWidget(self.grpStatus)

			self.grpFooterLayout = QtWidgets.QHBoxLayout()
			self.btnClose = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Close"))
			self.connect(self.btnClose, QtCore.SIGNAL("clicked()"), lambda: [ self.reject() ])
			self.grpFooterLayout.addStretch()
			self.grpFooterLayout.addWidget(self.btnClose)
			self.layout_device.addItem(self.grpFooterLayout)

			self.layout.addLayout(self.layout_device, 0, 0)
			self.setLayout(self.layout)

			self.ReadDeviceInfo()

		def run(self):
			self.layout.update()
			self.layout.activate()
			screenGeometry = QDesktopWidget().screenGeometry(self)
			x = (screenGeometry.width() - self.width()) / 2
			y = (screenGeometry.height() - self.height()) / 2
			self.move(x, y)
			self.show()

		def hideEvent(self, event):
			if self.DEVICE is None:
				self.APP.ConnectDevice()
			self.APP.activateWindow()

		def reject(self):
			if self.CloseDialog():
				super().reject()

		def CloseDialog(self):
			if self.btnClose.isEnabled() is False:
				text = __("<b>Warning:</b> If you close this window while a firmware update is still running, it might leave the device in an unbootable state.") + "<br><br>" + __("Are you sure you want to close this window?")
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.No)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.No: return False
			return True

		def ReadDeviceInfo(self):
			self.lblDeviceNameResult.setText(self.DEVICE.GetName())
			self.lblDeviceFWVerResult.setText(self.DEVICE.GetFirmwareVersion(more=True))
			self.lblDevicePCBVerResult.setText(self.DEVICE.GetPCBVersion())

		def ResetAVR(self, delay=0.1):
			port = self.PORT
			try:
				dev = serial.Serial(port, 1000000, timeout=1)
			except serial.SerialException:
				return False
			dev.write(b'0')
			dev.flush()
			time.sleep(0.00125)
			dev.write(struct.pack(">BIBB", 0x2A, 0x37653565, 0x31, 0))
			dev.flush()
			time.sleep(0.00125)
			self.APP.QT_APP.processEvents()
			time.sleep(0.3 + delay)
			dev.reset_input_buffer()
			dev.reset_output_buffer()
			dev.close()
			return True

		def UpdateFirmware(self):
			fw = ""
			path = ""
			if self.optCFW.isChecked():
				fw = self.CFW_VER
				fn = "cfw.hex"
			elif self.optOFW.isChecked():
				fw = self.OFW_VER
				fn = "ofw.hex"
			else:
				path = self.APP.SETTINGS.value("LastDirFirmwareUpdate")
				path = QtWidgets.QFileDialog.getOpenFileName(self, __("Choose GBxCart RW Firmware File"), path, __("Firmware Update") + " (*.hex);;" + __("All Files") + " (*.*)")[0]
				if path == "": return
				temp = re.search(r"^(gbx(?:cart|mas)_rw_.+_pcb_r.+\.hex)$", os.path.basename(path))
				if temp is None:
					msg = __("The expected filename for a valid firmware file is <b>{filename_pattern}</b>. Please visit {url} for the latest official firmware updates.", filename_pattern="gbx*_rw_*_pcb_r*.hex", url="<a href=\"https://www.gbxcart.com/\">https://www.gbxcart.com</a>")
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=msg, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return
				self.APP.SETTINGS.setValue("LastDirFirmwareUpdate", os.path.dirname(path))
				fw = "{:s}\n\n".format(path) + __("Please double check that this is a valid firmware file for your GBxCart RW. If it is invalid or an update for a different device, it may render your device unusable.")
				fn = None

			text = __("The following firmware will now be written to your GBxCart RW device:") + "\n- {fw}".format(fw=fw)
			text += "\n\n" + __("Do you want to continue?")
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
			msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
			answer = msgbox.exec()
			if answer == QtWidgets.QMessageBox.No: return
			self.btnUpdate.setEnabled(False)
			self.btnClose.setEnabled(False)
			self.grpAvailableFwUpdates.setEnabled(False)

			if path == "":
				with zipfile.ZipFile(self.APP_PATH + os.sep + os.path.join("res", "{:s}".format(self.FW_FILES[self.PCB_VER]))) as archive:
					with archive.open(fn) as f: ihex = f.read().decode("ascii")
			else:
				with open(path, "rb") as f: ihex = f.read().decode("ascii")

			ihex = ihex.splitlines()
			buffer = bytearray()
			for line in ihex:
				keys = ["colon", "raw", "bytecount", "address", "type", "data", "checksum"]
				values = re.search(r"^(\:)((.{2})(.{4})(.{2})(.*))(.{2})$", line)
				if values == None: continue
				values = values.groups()
				data = dict(zip(keys, values))
				for (k, v) in data.items():
					if k in ("bytecount", "type", "checksum"):
						data[k] = struct.unpack("B", bytes.fromhex(v))[0]
					elif k == "address":
						data[k] = struct.unpack("H", bytes.fromhex(v))[0]
					elif k != "colon":
						data[k] = bytes.fromhex(v)

				# Calculate checksum
				chk = 0
				for i in range(0, len(data["raw"])):
					chk += data["raw"][i]
				chk = chk & 0xFF
				chk = (~chk + 1) & 0xFF
				if (chk != data["checksum"]):
					self.SetStatus(__("Firmware checksum error."))
					self.prgStatus.setValue(0)
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					self.grpAvailableFwUpdates.setEnabled(True)
					return False

				else:
					buffer += bytearray(data["data"])

			if len(buffer) >= 7168:
				self.SetStatus(__("Firmware file is too large."))
				self.prgStatus.setValue(0)
				self.btnUpdate.setEnabled(True)
				self.btnClose.setEnabled(True)
				self.grpAvailableFwUpdates.setEnabled(True)
				return False

			self.APP.DisconnectDevice()

			while True:
				ret = self.WriteFirmware(buffer, self.SetStatus)
				if ret == 1: return True
				elif ret == 2: return False
				elif ret == 3: continue

		def SetStatus(self, text, enableUI=False, setProgress=None):
			self.lblStatus.setText(__("Status: {text}", text=text))
			if setProgress is not None:
				self.prgStatus.setValue(setProgress)
			if enableUI:
				self.btnUpdate.setEnabled(True)
				self.btnClose.setEnabled(True)
				self.grpAvailableFwUpdates.setEnabled(True)

		def WriteFirmware(self, data, fncSetStatus):
			fw_buffer = data
			port = self.PORT

			delay = 0
			lives = 10
			buffer = bytearray()

			msgWarnBadResponse = __(
				"Failed to update your GBxCart RW {pcb_version} ({fw_version})!\n\n"
				"The firmware update failed as the device is not responding correctly. Please ensure you use a genuine GBxCart RW, re-connect using a different USB cable and try again.\n\n"
				"⚠️ Please note that FlashGBX does not work with the “{flashboy}” series devices.",
				pcb_version=self.PCB_VER,
				fw_version=self.FW_VER,
				flashboy="FLASH BOY"
			)

			fncSetStatus(text=__("Waiting for bootloader..."), setProgress=0)
			if self.ResetAVR(delay) is False:
				fncSetStatus(text=__("Bootloader error."), enableUI=True)
				self.prgStatus.setValue(0)
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME + " – " + __("Firmware Updater for {device_name}", device_name="GBxCart RW " + self.PCB_VER), text=msgWarnBadResponse, standardButtons=QtWidgets.QMessageBox.Ok)
				answer = msgbox.exec()
				return 2

			while True:
				try:
					dev = serial.Serial(port=port, baudrate=9600*4, timeout=1)
				except:
					fncSetStatus(text=__("Device access error."), enableUI=True)
					return 2
				dev.reset_input_buffer()
				dev.reset_output_buffer()
				dev.write(b"@@@")
				dev.flush()
				time.sleep(0.00125)
				buffer = dev.read(0x11)
				if (len(buffer) < 0x11) or (buffer[0:3] != b'TSB'):
					dev.write(b"?")
					dev.flush()
					time.sleep(0.00125)
					dev.close()
					self.APP.QT_APP.processEvents()
					time.sleep(1)
					if len(buffer) != 0x11:
						delay += 0.05
					fncSetStatus(__("Waiting for bootloader... (+{milliseconds}ms)", milliseconds=math.ceil(delay * 1000)))
					if self.ResetAVR(delay) is False:
						fncSetStatus(text=__("Bootloader error."), enableUI=True)
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME + " – " + __("Firmware Updater for {device_name}", device_name="GBxCart RW " + self.PCB_VER), text=msgWarnBadResponse, standardButtons=QtWidgets.QMessageBox.Ok)
						answer = msgbox.exec()
						return 2
					lives -= 1
					if lives < 0:
						fncSetStatus(text=__("Bootloader timeout."), enableUI=True)
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME + " – " + __("Firmware Updater for {device_name}", device_name="GBxCart RW " + self.PCB_VER), text=msgWarnBadResponse, standardButtons=QtWidgets.QMessageBox.Ok)
						answer = msgbox.exec()
						return 2
					continue
				break

			fncSetStatus(__("Reading bootloader information..."))
			info = {}
			keys = ["magic", "tsb_version", "tsb_status", "signature", "page_size", "flash_size", "eeprom_size", "unknown", "avr_jmp_identifier"]
			values = struct.unpack("<3sHB3sBHHBB", bytearray(buffer[:-1]))
			info = dict(zip(keys, values))
			info["page_size"] *= 2
			info["flash_size"] *= 2
			info["eeprom_size"] += 1
			if info["avr_jmp_identifier"] == 0x00:
				info["jmp_mode"] = "relative"
				info["device_type"] = "attiny"
			elif info["avr_jmp_identifier"] == 0x0C:
				info["jmp_mode"] = "absolute"
				info["device_type"] = "attiny"
			elif info["avr_jmp_identifier"] == 0xAA:
				info["jmp_mode"] = "relative"
				info["device_type"] = "atmega"

			if info["page_size"] != 64 or info["flash_size"] != 7616 or info["eeprom_size"] != 512 or info["jmp_mode"] != "relative" or info["device_type"] != "atmega" or info["signature"] != b'\x1E\x93\x06':
				fncSetStatus(text="Wrong device detected.", enableUI=True)
				return 2

			if (info["tsb_version"] < 32768):
				info["tsb_version"] = int((info["tsb_version"] & 31) + ((info["tsb_version"] & 480) / 32) * 100 + ((info["tsb_version"] & 65024 ) / 512) * 10000 + 20000000)
			else:
				fncSetStatus(text="Wrong device detected.", enableUI=True)
				return 2

			#################

			# Read user data
			fncSetStatus(__("Reading user data..."))
			dev.write(b"c")
			user_data = bytearray(dev.read(0x41))
			info["tsb_timeout"] = user_data[2]

			# Change timeout to 6s
			fncSetStatus(__("Writing user data..."))
			user_data[2] = 254
			dev.write(b"C")
			dev.read(1)
			dev.write(b"!")
			dev.write(user_data)
			dev.flush()
			time.sleep(0.00125)
			dev.read(0x41)

			# Write firmware
			fncSetStatus(__("Updating firmware... Do not unplug the device!"))
			iterations = math.ceil(len(fw_buffer) / 0x40)
			if len(fw_buffer) < iterations * 0x40:
				fw_buffer = fw_buffer + bytearray([0xFF] * ((iterations * 0x40) - len(fw_buffer)))

			lives = 10
			dev.write(b"F")
			dev.flush()
			time.sleep(0.00125)
			ret = dev.read(1)
			while ret != b"?":
				dev.write(b"F")
				dev.flush()
				time.sleep(0.00125)
				ret = dev.read(1)
				lives -= 1
				if lives == 0:
					dev.write(b"?")
					dev.flush()
					time.sleep(0.00125)
					dev.close()
					fncSetStatus(text=__("Protocol Error. Please try again."), enableUI=True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text="The firmware update was not successful (Protocol Error). Do you want to try again?\n\nIf it doesn’t work even after multiple retries, please use the insideGadgets standalone firmware updater instead.", standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
					answer = msgbox.exec()
					if answer == QtWidgets.QMessageBox.Yes:
						time.sleep(1)
						return 3
					return 2

			for i in range(0, iterations):
				self.APP.QT_APP.processEvents()
				dev.write(b"!")
				dev.write(fw_buffer[i*0x40:i*0x40+0x40])
				fncSetStatus(text=__("Updating firmware... Do not unplug the device!"), setProgress=(i*0x40+0x40) / len(fw_buffer) * 100)
				ret = dev.read(1)
				if (ret != b"?"):
					dev.write(b"?")
					dev.flush()
					time.sleep(0.00125)
					dev.close()
					fncSetStatus(text=__("Write Error ({error_value}). Please try again.", error_value=str(ret)), enableUI=True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=__("The firmware update was not successful (Write Error, {error_value}). Do you want to try again?\n\nIf it doesn’t work even after multiple retries, please use the insideGadgets standalone firmware updater instead.", error_value=str(ret)), standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
					answer = msgbox.exec()
					if answer == QtWidgets.QMessageBox.Yes:
						time.sleep(1)
						return 3
					return 2
			dev.write(b"?")
			dev.flush()
			time.sleep(0.00125)
			dev.read(1)

			# verify flash
			fncSetStatus(__("Verifying update..."))
			buffer2 = bytearray()
			dev.write(b"f")
			dev.flush()
			time.sleep(0.00125)
			for i in range(0, 0x1DC0, 0x40):
				self.APP.QT_APP.processEvents()
				dev.write(b"!")
				dev.flush()
				time.sleep(0.00125)
				while dev.in_waiting == 0: time.sleep(0.01)
				ret = bytearray(dev.read(0x40))
				buffer2 += ret
				self.prgStatus.setValue(len(buffer2) / 0x1DC0 * 100)
			dev.read(1)

			buffer2 = buffer2[:len(fw_buffer)]

			if fw_buffer == buffer2:
				fncSetStatus(__("Verification OK."))
				self.APP.QT_APP.processEvents()
				time.sleep(0.2)
			else:
				fncSetStatus(text=__("Verification Error."), enableUI=True)
				dev.write(b"?")
				dev.flush()
				time.sleep(0.00125)
				dev.close()
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=__("The firmware update was not successful (Verification Error). Do you want to try again?\n\nIf it doesn’t work even after multiple retries, please use the insideGadgets standalone firmware updater instead."), standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.Yes:
					time.sleep(1)
					return 3
				return 2

			# Change timeout to 1s
			fncSetStatus(__("Writing user data..."))
			user_data[2] = 42
			dev.write(b"C")
			dev.flush()
			time.sleep(0.00125)
			ret = dev.read(1)
			while ret != b"?":
				dev.write(b"C")
				dev.flush()
				time.sleep(0.00125)
				ret = dev.read(1)
				lives -= 1
				if lives == 0:
					dev.write(b"?")
					dev.flush()
					time.sleep(0.00125)
					dev.close()
					fncSetStatus(text=__("User data update error. Please try again."), enableUI=True)
					return 2
			dev.write(b"!")
			dev.write(user_data)
			dev.flush()
			time.sleep(0.00125)
			dev.read(0x41)

			# Restart
			self.APP.QT_APP.processEvents()
			time.sleep(0.1)
			fncSetStatus(__("Restarting the device..."))
			dev.write(b"?")
			dev.flush()
			time.sleep(0.00125)
			dev.close()
			self.APP.QT_APP.processEvents()
			time.sleep(0.8)
			fncSetStatus(__("Done!"))
			self.APP.QT_APP.processEvents()
			time.sleep(0.2)
			self.DEVICE = None
			self.btnUpdate.setEnabled(True)
			self.btnClose.setEnabled(True)
			self.grpAvailableFwUpdates.setEnabled(True)
			text = __("The firmware update is complete!")
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
			answer = msgbox.exec()
			self.reject()
			return 1
except ImportError:
	pass
