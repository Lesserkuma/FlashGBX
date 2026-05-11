# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

# pylint: disable=wildcard-import, unused-wildcard-import
from .LK_Device import *

class GbxDevice(LK_Device):
	DEVICE_NAME = "Chromatic"
	DEVICE_LATEST_FW_TS = 1778072716
	MAX_BUFFER_READ = 0x4000

	def __init__(self):
		pass

	def Initialize(self, flashcarts, port=None, max_baud=2000000):
		if self.IsConnected(): self.DEVICE.close()
		conn_msg = []
		ports = []
		if port is not None:
			ports = [ port ]
		else:
			comports = serial.tools.list_ports.comports()
			for i in range(0, len(comports)):
				if comports[i].vid == 0x374E and comports[i].pid == 0x0101:
					ports.append(comports[i].device)
			if len(ports) == 0: return False

		for i in range(0, len(ports)):
			if self.TryConnect(ports[i], max_baud):
				self.BAUDRATE = max_baud
				dev = serial.Serial(ports[i], self.BAUDRATE, timeout=0.1)
				self.DEVICE = dev
			else:
				continue

			if self.FW is None or self.FW == {}: continue

			dprint(f"Found a {self.DEVICE_NAME}")
			dprint("Firmware information:", self.FW)
			# dprint("Baud rate:", self.BAUDRATE)

			if self.DEVICE is None or not self.IsConnected():
				self.DEVICE = None
				if self.FW is not None:
					conn_msg.append([0, "Couldn’t communicate with the " + self.DEVICE_NAME + " device on port " + ports[i] + ". Please disconnect and reconnect the device, then try again."])
				continue
			elif self.FW is None:
				dev.close()
				self.DEVICE = None
				continue
			elif "cfw_id" not in self.FW or self.FW["cfw_id"] != 'L': # Not a CFW by FredEmmott
				dprint("Incompatible firmware:", self.FW)
				dev.close()
				self.DEVICE = None
				continue
			elif self.FW["fw_ts"] > self.DEVICE_LATEST_FW_TS:
				conn_msg.append([0, "Note: The " + self.DEVICE_NAME + " device on port " + ports[i] + " is running a firmware version that is newer than what this version of FlashGBX was developed to work with, so errors may occur."])

			self.PORT = ports[i]
			self.DEVICE.timeout = self.DEVICE_TIMEOUT

			conn_msg.append([0, "No help is currently available when using a ModRetro Chromatic device"])

			# Load Flash Cartridge Handlers
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

			self._write(bytearray(b'\x55\xAA'))
			time.sleep(0.01)
			device_id = self.DEVICE.read(self.DEVICE.in_waiting)

			if b"Chromatic" not in device_id:
				dprint("Not a Chromatic")
				self.FW = None
				return False

			if b"FW L" not in device_id:
				dprint("Not running LK firmware")
				return False

			if device_id[0] == 0:
				self._write(bytearray(b'LK')) # Enable LK firmware
				if self.DEVICE.read(1) != b'\xFF':
					dprint("LK firmware was not enabled successfully")
					self.FW = None
					return False

			self._write(self.DEVICE_CMD["QUERY_FW_INFO"])
			size = self.DEVICE.read(1)
			self.DEVICE.timeout = self.DEVICE_TIMEOUT
			if len(size) == 0:
				print("No response")
				self.FW = None
				return False
			size = struct.unpack("B", size)[0]
			if size != 8:
				print(size)
				return False
			data = self._read(size)
			info = data[:8]
			keys = ["cfw_id", "fw_ver", "pcb_ver", "fw_ts"]
			values = struct.unpack(">cHBI", bytearray(info))
			self.FW = dict(zip(keys, values))
			self.FW["cfw_id"] = self.FW["cfw_id"].decode('ascii')
			self.FW["fw_dt"] = datetime.datetime.fromtimestamp(self.FW["fw_ts"]).astimezone().replace(microsecond=0).isoformat()
			self.FW["ofw_ver"] = None
			self.FW["pcb_name"] = None
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
				self.FW["cart_power_ctrl"] = True if self._read(1) == 1 else False

				# Reset to bootloader support
				self.FW["bootloader_reset"] = True if self._read(1) == 1 else False
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

	def ChangeBaudRate(self, _):
		dprint("Baudrate change is not supported.")

	def CheckActive(self):
		if time.time() < self.LAST_CHECK_ACTIVE + 1: return True
		dprint("Checking if device is active")
		if self.DEVICE is None: return False
		if self.FW["pcb_name"] is None:
			if self.LoadFirmwareVersion():
				self.LAST_CHECK_ACTIVE = time.time()
				return True
			else:
				return False
		try:
			self._get_fw_variable("CART_MODE")
			self.LAST_CHECK_ACTIVE = time.time()
			return True
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
		s = "{:s}{:d}".format(self.FW["cfw_id"], self.FW["fw_ver"])
		if self.FW["pcb_name"] == None:
			s += " <unverified>"
		if more:
			s += " ({:s})".format(self.FW["fw_dt"])
		return s

	def GetFullNameLabel(self):
		if self.FW["pcb_ver"] == -1:
			return self.FW["pcb_name"]
		return super().GetFullNameLabel()

	def GetFullName(self):
		return self.GetName()

	def GetFullNameExtended(self, more=False):
		if self.FW["pcb_ver"] == -1:
			return self.FW["pcb_name"]

		if more:
			return "{:s} – Firmware {:s} ({:s}) on {:s}".format(self.GetFullName(), self.GetFirmwareVersion(), self.FW["fw_dt"], self.GetPort())
		else:
			return "{:s} – Firmware {:s} ({:s})".format(self.GetFullName(), self.GetFirmwareVersion(), self.GetPort())

	def CanSetVoltageManually(self):
		return False

	def CanSetVoltageAutomatically(self):
		return True

	def CanPowerCycleCart(self):
		return self.FW["cart_power_ctrl"]

	def GetSupprtedModes(self):
		return ["DMG"]

	def IsSupported3dMemory(self):
		return False

	def IsClkConnected(self):
		return True

	def SupportsFirmwareUpdates(self):
		return False

	def FirmwareUpdateAvailable(self):
		return False

	def GetFirmwareUpdaterClass(self):
		return None

	def ResetLEDs(self):
		pass

	def SupportsBootloaderReset(self):
		return self.FW["bootloader_reset"]

	def BootloaderReset(self):
		if not self.SupportsBootloaderReset(): return False
		dprint("Resetting to bootloader...")
		try:
			self._write(self.DEVICE_CMD["BOOTLOADER_RESET"], wait=True)
			self._write(1)
			self.Close()
			return True
		except Exception as e:
			print("Disconnecting...", e)
			return False

	def SupportsAudioAsWe(self):
		return True

	def Close(self, cartPowerOff=False):
		if self.FW["cfw_id"] == "G":
			self.DEVICE.close()

		if self.IsConnected():
			dprint("Disconnecting from the device")
			try:
				self.DEVICE.write(b'KL') # Disable LK firmware
				self.DEVICE.read(1)
				self.DEVICE.close()
			except:
				self.DEVICE = None
			self.MODE = None
