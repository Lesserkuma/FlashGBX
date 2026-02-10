# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/lesserkuma)

# pylint: disable=wildcard-import, unused-wildcard-import
from .LK_Device import *

from .bacon import BaconFakeSerialDevice, SetDebug, SetDeviceCMD

class GbxDevice(LK_Device):
	DEVICE_NAME = "Bacon"
	DEVICE_MIN_FW = 1
	DEVICE_MAX_FW = 12
	DEVICE_LATEST_FW_TS = { 5:1730731680, 10:1730731680, 11:1730731680, 12:1730731680, 13:1730731680 }
	PCB_VERSIONS = { 5:'', 12:'v1.2', 13:'v1.3' }
	
	def __init__(self):
		SetDebug(Util.DEBUG)
		SetDeviceCMD(LK_Device.DEVICE_CMD, LK_Device.DEVICE_VAR)
		pass
	
	def Initialize(self, flashcarts, port=None, max_baud=2000000):
		conn_msg = []
		try:
			self.DEVICE = BaconFakeSerialDevice()
			self.LoadFirmwareVersion()
		except Exception as e:
			dprint("Failed to initialize BaconFakeSerialDevice:", e)
			return False
		dprint(f"Found a {self.DEVICE_NAME}")
		dprint("Firmware information:", "?")
	
		self.MAX_BUFFER_READ = 0x1000
		self.MAX_BUFFER_WRITE = 0x800
		
		self.PORT = "Dummy"
		self.DEVICE.timeout = 1

		conn_msg.append([0, "Welcome to use " + self.DEVICE_NAME + "."])

		# Load Flash Cartridge Handlers
		self.UpdateFlashCarts(flashcarts)
		return conn_msg

	def LoadFirmwareVersion(self):
		dprint("Querying firmware version")
		try:
			self.DEVICE.timeout = 0.075
			self.DEVICE.reset_input_buffer()
			self.DEVICE.reset_output_buffer()
			self.DEVICE.timeout = 1
			self.FW = {}
			self.FW["fw_ts"] = 1730731680
			self.FW["cfw_id"] = "L"
			self.FW["fw_ver"] = 13
			self.FW["fw_dt"] = datetime.datetime.fromtimestamp(self.FW["fw_ts"]).astimezone().replace(microsecond=0).isoformat()
			self.FW["ofw_ver"] = None
			self.FW["pcb_ver"] = 13
			self.FW["pcb_name"] = "Bacon"
			# Cartridge Power Control support
			self.FW["cart_power_ctrl"] = True
			# Reset to bootloader support
			self.FW["bootloader_reset"] = False #True if temp & 1 == 1 else False
			self.FW["unregistered"] = False #True if temp >> 7 == 1 else False
			return True
		except Exception as e:
			traceback.print_exc()
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
		if self.DEVICE is None: 
			dprint("Device is None")
			return False
		if self.LoadFirmwareVersion():
			dprint("Device is active")
			self.LAST_CHECK_ACTIVE = time.time()
			return True
		return False

	def GetFirmwareVersion(self, more=False):
		s = "{:s}{:d}".format(self.FW["cfw_id"], self.FW["fw_ver"])
		if self.FW["pcb_name"] == None:
			s += " <unverified>"
		if more:
			s += " ({:s})".format(self.FW["fw_dt"])
		return s

	def GetFullNameExtended(self, more=False):
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
		return ["DMG", "AGB"]
	
	def IsSupported3dMemory(self):
		return True
	
	def IsClkConnected(self):
		return True

	def SupportsFirmwareUpdates(self):
		return True
	
	def FirmwareUpdateAvailable(self):
		return False
	
	def GetFirmwareUpdaterClass(self):
		return None

	def ResetLEDs(self):
		pass
	
	def SupportsBootloaderReset(self):
		return self.FW["bootloader_reset"]

	def BootloaderReset(self):
		return False

	def SupportsAudioAsWe(self):
		return not (self.FW["pcb_ver"] < 13 and self.CanPowerCycleCart())

	def GetMode(self):
		return super().GetMode()

	def SetAutoPowerOff(self, value):
		value &= 0xFFFFFFFF
		#if value == 0 or value > 5000: value = 1500
		return super().SetAutoPowerOff(value)

	def GetFullName(self):
		if self.FW["pcb_ver"] < 13 and self.CanPowerCycleCart():
			s = "{:s} {:s} + PLUGIN 01".format(self.GetName(), self.GetPCBVersion())
		else:
			s = "{:s} {:s}".format(self.GetName(), self.GetPCBVersion())
		if self.IsUnregistered():
			s += " (unregistered)"
		return s

	def GetRegisterInformation(self):
		text = "hahaha, no"
		return text
