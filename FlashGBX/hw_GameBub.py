# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/lesserkuma)

# pylint: disable=wildcard-import, unused-wildcard-import
from .LK_Device import *
from .i18n import __

class GbxDevice(LK_Device):
	DEVICE_NAME = "Game Bub"
	USB_IDS = ((0x1209, 0xB010),)
	MAX_BUFFER_READ = 1024
	MAX_BUFFER_WRITE = 512
	DEVICE_LABEL_LONG = "Game Bub"
	DEVICE_LABEL_SHORT = "Game Bub"
	FWUPDATE_ACTION = None
	DEVICE_SUPPORT_MESSAGE = "For help with your Game Bub, please see the user guide:\nhttps://docs.gamebub.net/"

	def __init__(self):
		pass

	def _write(self, data, wait=False):
		if not isinstance(data, bytearray):
			data = bytearray([data])

		# Avoid sending exact 64-byte USB packet multiples in one write.
		if len(data) > 1 and len(data) % 64 == 0:
			super()._write(data[:-1], wait=False)
			return super()._write(data[-1:], wait=wait)

		return super()._write(data, wait=wait)

	def Initialize(self, flashcarts, port=None, max_baud=2000000):
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
			if self.TryConnect(ports[i], max_baud, keep_open=True):
				self.BAUDRATE = max_baud
				dev = self.DEVICE
			else:
				continue

			if self.FW is None or self.FW == {}: continue

			dprint(f"Found a {self.DEVICE_NAME}")
			dprint("Firmware information:", self.FW)

			if self.DEVICE is None or not self.IsConnected():
				dev.close()
				self.DEVICE = None
				if self.FW is not None:
					conn_msg.append([0, __("Couldn’t communicate with the {device_name} on port {port}. Please disconnect and reconnect the device, then try again.", device_name=self.DEVICE_NAME, port=ports[i])])
				continue

			self.PORT = ports[i]
			self.DEVICE.timeout = self.DEVICE_TIMEOUT

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

				# Cartridge Power Control support, Switch Power support, and Switch Mode support
				temp = self._read(1)
				self.FW["cart_power_ctrl"] = True if temp & 1 == 1 else False
				self.FW["cart_presence_switch"] = True if (temp >> 1) & 1 == 1 else False
				self.FW["cart_mode_switch"] = True if (temp >> 2) & 1 == 1 else False

				# Reset to bootloader support
				temp = self._read(1)
				self.FW["bootloader_reset"] = bool(temp & 1)
				self.FW["device_serial"] = self.ReadDeviceSerial() if temp & 2 else None

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

	def GetFirmwareVersion(self, more=False):
		s = "{:s}{:d}".format(self.FW["cfw_id"], self.FW["fw_ver"])
		if more:
			s += " ({:s})".format(self.FW["fw_dt"])
		return s
	
	def GetFullNameExtended(self, more=False):
		if more:
			return __("{device_name} – Firmware {fw_version} ({timestamp}) on {port}", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), timestamp=self.FW["fw_dt"], port=self.GetPort())
		else:
			return __("{device_name} – Firmware {fw_version} ({port})", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), port=self.GetPort())

	def CanSetVoltageBySwitch(self):
		return False

	def CanSetVoltageByCode(self):
		return False

	def CanSetVoltageByAutoswitch(self):
		return True

	def CanPowerCycleCart(self):
		return True

	def GetSupportedModes(self):
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
