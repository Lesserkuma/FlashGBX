# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/lesserkuma)

# pylint: disable=wildcard-import, unused-wildcard-import
from .LK_Device import *

class GbxDevice(LK_Device):
	DEVICE_NAME = "Game Bub"
	MAX_BUFFER_READ = 0x400
	MAX_BUFFER_WRITE = 0x400

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
				if comports[i].vid == 0x1209 and comports[i].pid == 0xB010:
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

			if self.DEVICE is None or not self.IsConnected():
				self.DEVICE = None
				if self.FW is not None:
					conn_msg.append([0, "Couldn’t communicate with the " + self.DEVICE_NAME + " device on port " + ports[i] + ". Please disconnect and reconnect the device, then try again."])
				continue

			self.PORT = ports[i]
			self.DEVICE.timeout = self.DEVICE_TIMEOUT

			conn_msg.append([0, "For help with your Game Bub, please see the user guide: https://docs.gamebub.net/"])

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
			self.FW["ofw_ver"] = None
			self.FW["pcb_name"] = ""
			self.FW["cart_power_ctrl"] = False
			self.FW["bootloader_reset"] = False
			if self.FW["cfw_id"] in ["L", "E"] and self.FW["fw_ver"] >= 12:
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
		if more:
			s += " ({:s})".format(self.FW["fw_dt"])
		return s

	def GetFullNameExtended(self, more=False):
		if more:
			return "{:s} – Firmware {:s} on {:s}".format(self.GetFullName(), self.GetFirmwareVersion(), self.GetPort())
		else:
			return "{:s} – Firmware {:s} ({:s})".format(self.GetFullName(), self.GetFirmwareVersion(), self.GetPort())

	def CanSetVoltageManually(self):
		return False

	def CanSetVoltageAutomatically(self):
		return True

	def CanPowerCycleCart(self):
		return True

	def GetSupprtedModes(self):
		return ["DMG", "AGB"]

	def IsSupported3dMemory(self):
		return True

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
		return False

	def BootloaderReset(self):
		return False

	def SupportsAudioAsWe(self):
		return True

	def GetFullName(self):
		return self.DEVICE_NAME
