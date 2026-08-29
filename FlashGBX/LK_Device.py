# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import time, math, struct, traceback, zlib, copy, hashlib, os, datetime, platform, json, base64, threading
import serial, serial.tools.list_ports
from abc import ABC, abstractmethod
from serial import SerialException
from .i18n import __, ___, c__
from .RomFileDMG import RomFileDMG
from .RomFileAGB import RomFileAGB
from .Mapper import DMG_Mapper, AGB_GPIO
from .Flashcart import Flashcart, Flashcart_DMG_MMSA, Flashcart_AGB_GBAMP, Flashcart_DMG_BUNG_16M, CFI
from .Logging import ANSI, dprint
from .CartridgeTypes import AgbSaveTypes, DmgSaveTypes
from .app import AppContext, AppInfo
from .Formatter import Formatter
from .app import generate_filename
from .GBMemory import GBMemoryMap

class LK_Device(ABC):
	DEVICE_NAME = ""
	DEVICE_MIN_FW = 0
	DEVICE_MAX_FW = 0
	DEVICE_LATEST_FW_TS = {}
	PCB_VERSIONS = {}
	BAUDRATE = 1000000
	MAX_BUFFER_READ = 0x1000
	MAX_BUFFER_WRITE = 0x400

	DEVICE_CMD = {
		"NULL":0x30,
		"DEBUG":0xA0,
		"QUERY_FW_INFO":0xA1,
		"SET_MODE_AGB":0xA2,
		"SET_MODE_DMG":0xA3,
		"SET_VOLTAGE_3_3V":0xA4,
		"SET_VOLTAGE_5V":0xA5,
		"SET_VARIABLE":0xA6,
		"SET_FLASH_CMD":0xA7,
		"SET_ADDR_AS_INPUTS":0xA8,
		"CLK_TOGGLE":0xA9,
		"ENABLE_PULLUPS":0xAB,
		"DISABLE_PULLUPS":0xAC,
		"GET_VARIABLE":0xAD,
		"GET_VAR_STATE":0xAE,
		"SET_VAR_STATE":0xAF,
		"DMG_CART_READ":0xB1,
		"DMG_CART_WRITE":0xB2,
		"DMG_CART_WRITE_SRAM":0xB3,
		"DMG_MBC_RESET":0xB4,
		"DMG_MBC7_READ_EEPROM":0xB5,
		"DMG_MBC7_WRITE_EEPROM":0xB6,
		"DMG_MBC6_MMSA_WRITE_FLASH":0xB7,
		"DMG_SET_BANK_CHANGE_CMD":0xB8,
		"DMG_EEPROM_WRITE":0xB9,
		"DMG_CART_READ_MEASURE":0xBA,
		"AGB_CART_READ":0xC1,
		"AGB_CART_WRITE":0xC2,
		"AGB_CART_READ_SRAM":0xC3,
		"AGB_CART_WRITE_SRAM":0xC4,
		"AGB_CART_READ_EEPROM":0xC5,
		"AGB_CART_WRITE_EEPROM":0xC6,
		"AGB_CART_WRITE_FLASH_DATA":0xC7,
		"AGB_CART_READ_3D_MEMORY":0xC8,
		"AGB_BOOTUP_SEQUENCE":0xC9,
		"AGB_READ_GPIO_RTC":0xCA,
		"DMG_FLASH_WRITE_BYTE":0xD1,
		"AGB_FLASH_WRITE_SHORT":0xD2,
		"FLASH_PROGRAM":0xD3,
		"CART_WRITE_FLASH_CMD":0xD4,
		"CALC_CRC32":0xD5,
		"BOOTLOADER_RESET":0xF1,
		"CART_PWR_ON":0xF2,
		"CART_PWR_OFF":0xF3,
		"QUERY_CART_PWR":0xF4,
		"SET_PIN":0xF5,
		"GET_SWITCH_STATE":0xF6,
		"PING":0xFE,
	}
	# \#define VAR(\d+)_([^\t]+)\t+(.+)
	DEVICE_VAR = {
		"ADDRESS":[32, 0x00],
		"AUTO_POWEROFF_TIME":[32, 0x01],
		"TRANSFER_SIZE":[16, 0x00],
		"BUFFER_SIZE":[16, 0x01],
		"DMG_ROM_BANK":[16, 0x02],
		"STATUS_REGISTER":[16, 0x03],
		"LAST_BANK_ACCESSED":[16, 0x04],
		"STATUS_REGISTER_MASK":[16, 0x05],
		"STATUS_REGISTER_VALUE":[16, 0x06],
		"CART_MODE":[8, 0x00],
		"DMG_ACCESS_MODE":[8, 0x01],
		"FLASH_COMMAND_SET":[8, 0x02],
		"FLASH_METHOD":[8, 0x03],
		"FLASH_WE_PIN":[8, 0x04],
		"FLASH_PULSE_RESET":[8, 0x05],
		"FLASH_COMMANDS_BANK_1":[8, 0x06],
		"FLASH_SHARP_VERIFY_SR":[8, 0x07],
		"DMG_READ_CS_PULSE":[8, 0x08],
		"DMG_WRITE_CS_PULSE":[8, 0x09],
		"FLASH_DOUBLE_DIE":[8, 0x0A],
		"DMG_READ_METHOD":[8, 0x0B],
		"AGB_READ_METHOD":[8, 0x0C],
		"CART_POWERED":[8, 0x0D],
		"PULLUPS_ENABLED":[8, 0x0E],
		"AUTO_POWEROFF_ENABLED":[8, 0x0F],
		"AGB_IRQ_ENABLED":[8, 0x10],
		"DMG_AUDIO_ENABLED":[8, 0x11],
	}

	ACTIONS = {"ROM_READ":1, "SAVE_READ":2, "SAVE_WRITE":3, "ROM_WRITE":4, "ROM_WRITE_VERIFY":4, "SAVE_WRITE_VERIFY":3, "RTC_WRITE":5, "DETECT_CART":6}
	SUPPORTED_CARTS = {}

	FW = {}
	FW_UPDATE_REQ = False
	FW_VAR = {}
	MODE = None
	PORT = ''
	DEVICE = None
	WORKER = None
	INFO = { "action":None, "last_action":None, "dump_info":{} }
	ERROR = False
	ERROR_ARGS = {}
	CANCEL = False
	CANCEL_ARGS = {}
	SIGNAL = None
	POS = 0
	NO_PROG_UPDATE = False
	FAST_READ = False
	SKIPPING = False
	DEVICE_TIMEOUT = 1
	WRITE_DELAY = False
	READ_ERRORS = 0
	WRITE_ERRORS = 0
	DMG_READ_METHOD = 1
	DMG_READ_METHODS = ["RD", "A15", "SlowA15"]
	AGB_READ_METHOD = 0
	AGB_READ_METHODS = ["Single", "MemCpy", "Stream"]
	LAST_CHECK_ACTIVE = 0
	USER_ANSWER = None
	SKIP_POWERCYCLE = False
	VOLTAGE_FALLBACK_PENDING = False
	VOLTAGE_FALLBACK_TRIGGERED = False
	THREAD_AUTO_POWEROFF_TIME = None

	def __init__(self):
		pass

	@abstractmethod
	def Initialize(self, flashcarts, port=None, max_baud=2000000):
		raise NotImplementedError

	@abstractmethod
	def LoadFirmwareVersion(self):
		raise NotImplementedError

	@abstractmethod
	def GetFirmwareVersion(self, more=False):
		raise NotImplementedError

	@abstractmethod
	def ChangeBaudRate(self, baudrate):
		raise NotImplementedError

	@abstractmethod
	def CanSetVoltageBySwitch(self):
		raise NotImplementedError

	@abstractmethod
	def CanSetVoltageByCode(self):
		raise NotImplementedError

	@abstractmethod
	def CanSetVoltageByAutoswitch(self):
		raise NotImplementedError

	@abstractmethod
	def CanPowerCycleCart(self):
		raise NotImplementedError

	@abstractmethod
	def GetSupprtedModes(self):
		raise NotImplementedError

	@abstractmethod
	def IsSupported3dMemory(self):
		raise NotImplementedError

	@abstractmethod
	def IsClkConnected(self):
		raise NotImplementedError

	@abstractmethod
	def GetFullNameExtended(self, more=False):
		raise NotImplementedError

	@abstractmethod
	def SupportsFirmwareUpdates(self):
		raise NotImplementedError

	def FirmwareUpdateAction(self):
		return getattr(type(self), "FWUPDATE_ACTION", None)

	def CLIUpdaterMethod(self):
		return getattr(type(self), "CLI_UPDATER_METHOD", None)

	def GetSupportMessage(self):
		message = getattr(type(self), "DEVICE_SUPPORT_MESSAGE", None)
		if callable(message): return message()
		return message

	@abstractmethod
	def FirmwareUpdateAvailable(self):
		raise NotImplementedError

	@abstractmethod
	def GetFirmwareUpdaterClass(self):
		raise NotImplementedError
	
	@abstractmethod
	def ResetLEDs(self):
		raise NotImplementedError

	@abstractmethod
	def SupportsBootloaderReset(self):
		raise NotImplementedError

	@abstractmethod
	def BootloaderReset(self):
		raise NotImplementedError

	@abstractmethod
	def SupportsAudioAsWe(self):
		raise NotImplementedError

	#################################################################

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
			if self.FW.get("cfw_id") == "L" and self.FW.get("fw_ver", 0) >= 15:
				challenge = os.urandom(1)[0]
				self._write(bytearray([self.DEVICE_CMD["PING"], challenge]))
				response = self._read(1)
				if response is False or response != ((~challenge) & 0xFF):
					raise ConnectionError("Invalid firmware response (ping response was {response} instead of {expected})".format(response=str(response), expected=str((~challenge) & 0xFF)))
			else:
				modes = self.GetSupprtedModes()
				mode = self._get_fw_variable("CART_MODE")
				if mode > len(modes):
					raise ConnectionError("Invalid firmware response (mode={mode})".format(mode=str(mode - 1)))
			self.LAST_CHECK_ACTIVE = time.time()
			return True
		except Exception as e:
			if self.USER_ANSWER is not True: # Called from CartPowerCycleOrAskReconnect()
				print(ANSI.RED + __("Disconnecting from the device, because a critical error occurred!\n{error}", error=str(e)) + ANSI.RESET)
				dprint(__("Disconnecting from the device, because a critical error occurred!\n{error}", error=str(e)))
			try:
				if self.DEVICE.isOpen():
					self.DEVICE.reset_input_buffer()
					self.DEVICE.reset_output_buffer()
					self.DEVICE.close()
				self.DEVICE = None
			except:
				pass
			return False

	def IsSupportedMbc(self, mbc):
		return mbc in ( 0x00, 0x01, 0x02, 0x03, 0x05, 0x06, 0x08, 0x09, 0x0B, 0x0D, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x20, 0x22, 0xFC, 0xFD, 0xFE, 0xFF, 0x101, 0x103, 0x104, 0x105, 0x110, 0x201, 0x202, 0x203, 0x204, 0x205, 0x206 )

	def IsUnregistered(self):
		if "unregistered" in self.FW:
			return self.FW["unregistered"]
		else:
			return False

	def TryConnect(self, port, baudrate):
		dprint("Trying to connect to {:s} at baud rate {:d} ({:s})".format(port, baudrate, type(self).__module__))
		try:
			dev = serial.Serial(port, baudrate, timeout=0.1, exclusive=True)
		except (SerialException, OSError) as e:
			dprint(f"Couldn’t connect to port {port:s} at baudrate {baudrate:d}:", e)
			return False
		self.DEVICE = dev
		check = self.LoadFirmwareVersion()
		self.DEVICE = None
		dev.close()
		return check

	def GetBaudRate(self):
		return self.BAUDRATE

	def SetDMGReadMethod(self, method):
		if self.FW["fw_ver"] < 12: return
		if method < 0 or method >= len(self.DMG_READ_METHODS): method = 0
		self.DMG_READ_METHOD = method
		self._set_fw_variable("DMG_READ_METHOD", self.DMG_READ_METHOD)

	def SetAGBReadMethod(self, method):
		if self.FW["fw_ver"] < 12: return
		if method < 0 or method >= len(self.AGB_READ_METHODS): method = 0
		self.AGB_READ_METHOD = method
		self._set_fw_variable("AGB_READ_METHOD", self.AGB_READ_METHOD)

	def SetPin(self, pins: list, set_high):
		if self.FW["fw_ver"] < 12: return
		pin_names = [ "CART_POWER", "PIN_CLK", "PIN_WR", "PIN_RD", "PIN_CS" ]
		for i in range(0, 24):
			pin_names.append(f"PIN_A{i}")
		pin_names += [ "PIN_CS2", "PIN_AUDIO" ]
		value = 0
		p = 0
		for p in pins:
			if isinstance(p, int):
				if p > 30:
					print(__("Invalid pin index specified:"), p)
					continue
			elif isinstance(p, str):
				if p not in pin_names:
					print(__("Invalid pin index specified:"), p)
					continue
				p = pin_names.index(p)
			value |= (1 << p)

		for i in range(0, 31):
			if (value >> i & 1) == 1:
				dprint(f"Setting pin {pin_names[p]}: {set_high}")

		#dprint(f"Value: {value:031b}")
		buffer = bytearray([self.DEVICE_CMD["SET_PIN"]])
		buffer.extend(struct.pack(">I", value))
		buffer.extend(struct.pack("B", 1 if set_high else 0))
		return self._write(buffer, wait=True)

	def _GetSwitchState(self):
		if self.FW["fw_ver"] < 15: return False
		self._write(self.DEVICE_CMD["GET_SWITCH_STATE"])
		state = self._read(1)
		state_presence = state & 1
		state_mode = (state >> 1) & 1
		return state

	def GetCartModeSwitchState(self):
		if self.FW["fw_ver"] < 15: return False
		if not self.FW["cart_mode_switch"]: return False
		state = self._GetSwitchState()
		state_mode = (state >> 1) & 1
		if state_mode == 1:
			dprint("Cartridge Mode Switch: DMG")
			return 0
		else:
			dprint("Cartridge Mode Switch: AGB")
			return 1

	def GetCartPresenceSwitchState(self):
		if self.FW["fw_ver"] < 15: return False
		if not self.FW["cart_presence_switch"]: return False
		state = self._GetSwitchState()
		state_presence = state & 1
		if state_presence == 1:
			dprint("Cartridge Presence Switch: ON")
		else:
			dprint("Cartridge Presence Switch: OFF")
		return state_presence

	def UpdateFlashCarts(self, flashcarts):
		self.SUPPORTED_CARTS = { 
			"DMG":{ "Generic ROM Cartridge":"RETAIL" },
			"AGB":{ "Generic ROM Cartridge":"RETAIL" }
		}
		for mode in flashcarts.keys():
			for key in sorted(flashcarts[mode].keys(), key=str.casefold):
				self.SUPPORTED_CARTS[mode][key] = flashcarts[mode][key]

	def IsConnected(self):
		if self.DEVICE is None: return False
		if not self.DEVICE.isOpen(): return False
		try:
			while self.DEVICE.in_waiting > 0:
				dprint("Clearing input buffer... ({:d})".format(self.DEVICE.in_waiting), self.DEVICE.read(self.DEVICE.in_waiting))
				self.DEVICE.reset_input_buffer()
				time.sleep(0.05)
			self.DEVICE.reset_output_buffer()
			return self.CheckActive()
		except SerialException as e:
			print(__("Connection lost!"))
			try:
				if e.args[0].startswith("ClearCommError failed"):
					self.DEVICE.close()
					return False
			except:
				pass
			print(str(e))
			return False

	def Close(self, cartPowerOff=False):
		if self.IsConnected():
			dprint("Disconnecting from the device")
			try:
				if cartPowerOff and self.CanPowerCycleCart():
					self._set_fw_variable("AUTO_POWEROFF_TIME", 0)
					if self.FW["fw_ver"] >= 12 or "OFW_CART_PWR_OFF" not in self.DEVICE_CMD:
						self._write(self.DEVICE_CMD["CART_PWR_OFF"], wait=self.FW["fw_ver"] >= 12)
					else:
						self._write(self.DEVICE_CMD["OFW_CART_PWR_OFF"], wait=False)
				else:
					self._write(self.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=self.FW["fw_ver"] >= 12)
				self.DEVICE.close()
			except:
				self.DEVICE = None
			self.MODE = None

	def GetName(self):
		return self.DEVICE_NAME

	def GetFullNameLabel(self):
		return "{:s} – Firmware {:s}".format(self.GetFullName(), self.GetFirmwareVersion())

	def GetPCBVersion(self):
		if self.FW["pcb_ver"] in self.PCB_VERSIONS:
			return self.PCB_VERSIONS[self.FW["pcb_ver"]]
		else:
			return "(" + c__("Device Type", "unknown revision") + ")"

	def GetFullName(self):
		if len(self.GetPCBVersion()) > 0:
			return "{:s} {:s}".format(self.GetName(), self.GetPCBVersion())
		else:
			return self.GetName()

	def GetPort(self):
		return self.PORT

	def GetFWBuildDate(self):
		return self.FW["fw_dt"]

	def SetWriteDelay(self, enable=True):
		if self.WRITE_DELAY != enable:
			dprint("Setting Write Delay to", enable)
			self.WRITE_DELAY = enable

	def SetTimeout(self, seconds=1):
		if seconds < 0.1: seconds = 0.1
		self.DEVICE_TIMEOUT = seconds
		self.DEVICE.timeout = self.DEVICE_TIMEOUT

	def AbortOperation(self, from_user=True):
		self.CANCEL_ARGS["from_user"] = from_user
		self.CANCEL = True
		self.ERROR = False

	def wait_for_ack(self, values=None):
		if values is None: values = [0x01, 0x03]
		buffer = self._read(1)
		if buffer not in values:
			tb_stack = traceback.extract_stack()
			stack = tb_stack[len(tb_stack)-2] # caller only
			if stack.name == "_write": stack = tb_stack[len(tb_stack)-3]
			dprint("CANCEL_ARGS:", self.CANCEL_ARGS)
			if "from_user" in self.CANCEL_ARGS and self.CANCEL_ARGS["from_user"]:
				return False
			elif buffer is False:
				dprint("Timeout error ({:s}(), line {:d}): {:f}".format(stack.name, stack.lineno, self.DEVICE.timeout))
				dprint("Traceback:\n", ''.join(traceback.format_stack()[:-1]))
				self.CANCEL_ARGS.update({
					"info_type": "msgbox_critical",
					"info_msg": __(
						"A timeout error has occured at {function_name}() in line {line_number}. Please make sure that the cartridge contacts are clean, re-connect the device and try again from the beginning.",
						function_name=stack.name, line_number=str(stack.lineno)
					)
				})
			elif buffer == 2:
				dprint("Error reported ({:s}(), line {:d}): {:s}".format(stack.name, stack.lineno, str(buffer)))
				dprint("Traceback:\n", ''.join(traceback.format_stack()[:-1]))
				self.CANCEL_ARGS.update({
					"info_type": "msgbox_critical",
					"info_msg": __(
						"The device reported an error while running {function_name}() in line {line_number}. Please make sure that the cartridge contacts are clean, re-connect the device and try again from the beginning.",
						function_name=stack.name, line_number=str(stack.lineno)
					)
				})
			else:
				dprint("Communication error ({:s}(), line {:d}): {:s}".format(stack.name, stack.lineno, str(buffer)))
				dprint("Traceback:\n", ''.join(traceback.format_stack()[:-1]))
				self.CANCEL_ARGS.update({
					"info_type": "msgbox_critical",
					"info_msg": __(
						"A communication error has occured at {function_name}() in line {line_number}. Please make sure that the cartridge contacts are clean, re-connect the device and try again from the beginning.",
						function_name=stack.name, line_number=str(stack.lineno)
					)
				})
			self.ERROR = True
			self.CANCEL = True
			self.WRITE_ERRORS += 1
			if self.WRITE_ERRORS > 3:
				self.SetWriteDelay(enable=True)
			return False
		return buffer

	def _try_write(self, data, retries=5):
		while retries > 0:
			ack = self._write(data, wait=True)
			if "from_user" in self.CANCEL_ARGS and self.CANCEL_ARGS["from_user"]:
				return False
			if ack is not False:
				self.ERROR = False
				self.CANCEL = False
				self.CANCEL_ARGS = {}
				return ack
			retries -= 1
			dprint("Retries left:", retries)

			hp = 20
			temp = 0
			while temp not in (1, 2) and hp > 0:
				self.DEVICE.reset_output_buffer()
				self.DEVICE.reset_input_buffer()
				self.DEVICE.write(b'\x00')
				self.DEVICE.flush()
				temp = self._read(1)
				hp -= 1
				dprint("Current response:", temp, ", HP:", hp)
			#if hp == 0: break
		return False

	def _write(self, data, wait=False):
		if not isinstance(data, bytearray):
			data = bytearray([data])

		if AppContext.DEBUG:
			dprint("_write() thread_id:", threading.get_ident())
			dstr = ' '.join(format(x, '02X') for x in data)
			cmd = ""
			if len(data) < 32:
				try:
					cmd = "[{:s}] ".format((list(self.DEVICE_CMD.keys())[list(self.DEVICE_CMD.values()).index(data[0])]))
				except:
					pass
			dprint("[{:02X}] {:s}{:s}".format(int(len(dstr)/3) + 1, cmd, dstr[:96]))

		self.DEVICE.write(data)
		self.DEVICE.flush()

		# On MacOS it’s possible not all bytes are transmitted successfully,
		# even though we’re using flush() which is the tcdrain function.
		# Still looking for a better solution than delaying here.
		if self.WRITE_DELAY is True or (platform.system() == "Darwin" and (self.FW is None or "pcb_name" not in self.FW or self.FW["pcb_name"] == "GBxCart RW")):
			time.sleep(0.0014)

		if wait: return self.wait_for_ack()

	def _read(self, count):
		if AppContext.DEBUG:
			dprint("_read() thread_id:", threading.get_ident())
		
		if self.DEVICE.in_waiting > 1000: dprint("Warning: in_waiting={:d} bytes".format(self.DEVICE.in_waiting))
		buffer = self.DEVICE.read(count)

		if len(buffer) != count:
			hp = 50
			while (self.DEVICE.in_waiting != (count - len(buffer))) and hp > 0:
				time.sleep(0.01)
				hp -= 1
			if hp > 0:
				buffer += self.DEVICE.read(count - len(buffer))

		if len(buffer) != count:
			tb_stack = traceback.extract_stack()
			stack = tb_stack[len(tb_stack)-2] # caller only
			if stack.name == "_read": stack = tb_stack[len(tb_stack)-3]
			dprint("Error: Received only {:d} of {:d} byte(s) ({:s}(), line {:d})".format(len(buffer), count, stack.name, stack.lineno))
			dprint("Timeout value:", self.DEVICE.timeout)
			dprint("Traceback:\n", ''.join(traceback.format_stack()[:-1]))
			self.READ_ERRORS += 1
			while self.DEVICE.in_waiting > 0:
				self.DEVICE.reset_input_buffer()
				time.sleep(0.5)
			self.DEVICE.reset_output_buffer()
			return False

		if count == 1:
			return buffer[0]
		else:
			return bytearray(buffer)

	def _get_fw_variable(self, key):
		if self.FW.get("fw_ver", 0) < 10: return 0
		dprint("Getting firmware variable {:s}".format(key))

		size = 0
		for (k, v) in self.DEVICE_VAR.items():
			if key in k:
				if v[0] == 8: size = 1
				elif v[0] == 16: size = 2
				elif v[0] == 32: size = 4
				key = v[1]
				break
		if size == 0:
			raise KeyError("Unknown variable name specified.")

		buffer = bytearray([self.DEVICE_CMD["GET_VARIABLE"], size])
		buffer.extend(struct.pack(">I", key))
		self._write(buffer)
		temp = self._read(4)
		try:
			return struct.unpack(">I", temp)[0]
		except:
			dprint("Communication error:", temp)
			return False

	def _set_fw_variable(self, key, value):
		dprint("Setting firmware variable {:s} to 0x{:X}".format(key, value))
		self.FW_VAR[key] = value

		size = 0
		for (k, v) in self.DEVICE_VAR.items():
			if key in k:
				if v[0] == 8: size = 1
				elif v[0] == 16: size = 2
				elif v[0] == 32: size = 4
				key = v[1]
				break
		if size == 0:
			raise KeyError("Unknown variable name specified.")

		buffer = bytearray([self.DEVICE_CMD["SET_VARIABLE"], size])
		buffer.extend(struct.pack(">I", key))
		buffer.extend(struct.pack(">I", value))

		if self.FW["fw_ver"] >= 12:
			return self._try_write(buffer)
		else:
			return self._write(buffer)

	def _cart_read(self, address, length=0, agb_save_flash=False):
		if self.MODE == "DMG":
			if length == 0:
				length = 1
				if address < 0xA000:
					raw = self.ReadROM(address, 1, max_length=self.MAX_BUFFER_READ)
				else:
					raw = self.ReadRAM(address - 0xA000, 1, max_length=self.MAX_BUFFER_READ)
				if raw is False or len(raw) < 1:
					return False
				return struct.unpack("B", raw)[0]
			else:
				if address < 0xA000:
					return self.ReadROM(address, length, max_length=self.MAX_BUFFER_READ)
				else:
					return self.ReadRAM(address - 0xA000, length, max_length=self.MAX_BUFFER_READ)
		elif self.MODE == "AGB":
			if length == 0:
				if agb_save_flash:
					length = 1
					raw = self.ReadRAM(address, length, command=self.DEVICE_CMD["AGB_CART_READ_SRAM"], max_length=self.MAX_BUFFER_READ)
					if raw is False or len(raw) < 1:
						return False
					return struct.unpack("B", raw)[0]
				else:
					length = 2
					raw = self.ReadROM(address >> 1, length, max_length=self.MAX_BUFFER_READ)
					if raw is False or len(raw) < 2:
						return False
					return struct.unpack(">H", raw)[0]
			else:
				if agb_save_flash:
					return self.ReadRAM(address, length, command=self.DEVICE_CMD["AGB_CART_READ_SRAM"], max_length=self.MAX_BUFFER_READ)
				else:
					return self.ReadROM(address, length, max_length=self.MAX_BUFFER_READ)

	def _cart_write(self, address, value, flashcart=False, sram=False):
		dprint("Writing to cartridge: 0x{:X} = 0x{:X} (args: {:s}, {:s})".format(address, value & 0xFF, str(flashcart), str(sram)))
		if self.MODE == "DMG":
			if flashcart:
				buffer = bytearray([self.DEVICE_CMD["DMG_FLASH_WRITE_BYTE"]])
				buffer.extend(struct.pack(">I", address))
				buffer.extend(struct.pack("B", value & 0xFF))
			else:
				if sram:
					self._set_fw_variable("DMG_WRITE_CS_PULSE", 1)
					self._set_fw_variable("ADDRESS", address)
					self._set_fw_variable("TRANSFER_SIZE", 1)
					self._write(self.DEVICE_CMD["DMG_CART_WRITE_SRAM"])
					self._write(value, wait=True)
					return
				else:
					buffer = bytearray([self.DEVICE_CMD["DMG_CART_WRITE"]])
					buffer.extend(struct.pack(">I", address))
					buffer.extend(struct.pack("B", value & 0xFF))
		elif self.MODE == "AGB":
			if sram:
				self._set_fw_variable("TRANSFER_SIZE", 1)
				self._set_fw_variable("ADDRESS", address)
				self._write(self.DEVICE_CMD["AGB_CART_WRITE_SRAM"])
				self._write(value, wait=True)
				return
			elif flashcart:
				buffer = bytearray([self.DEVICE_CMD["AGB_FLASH_WRITE_SHORT"]])
			else:
				buffer = bytearray([self.DEVICE_CMD["AGB_CART_WRITE"]])

			buffer.extend(struct.pack(">I", address >> 1))
			buffer.extend(struct.pack(">H", value & 0xFFFF))

		if self.FW["fw_ver"] >= 12:
			self._try_write(buffer)
		else:
			self._write(buffer)

		if self.MODE == "DMG" and sram: self._set_fw_variable("DMG_WRITE_CS_PULSE", 0)

	def _cart_write_flash(self, commands, flashcart=False):
		if self.FW["fw_ver"] < 6 and not (self.MODE == "AGB" and not flashcart):
			for command in commands:
				if self._cart_write(command[0], command[1], flashcart=flashcart) is False:
					print(__("An error has occured while writing to the cartridge."))
			return

		num = len(commands)
		buffer = bytearray([self.DEVICE_CMD["CART_WRITE_FLASH_CMD"]])
		if self.FW["fw_ver"] >= 6:
			buffer.extend(struct.pack("B", 1 if flashcart else 0))
		buffer.extend(struct.pack("B", num))
		for i in range(0, num):
			dprint("Writing to cartridge: 0x{:X} = 0x{:X} ({:d} of {:d})".format(commands[i][0], commands[i][1], i+1, num))
			if self.MODE == "AGB" and flashcart:
				buffer.extend(struct.pack(">I", commands[i][0] >> 1))
			else:
				buffer.extend(struct.pack(">I", commands[i][0]))

			if self.FW["fw_ver"] < 6:
				buffer.extend(struct.pack("B", commands[i][1]))
			else:
				buffer.extend(struct.pack(">H", commands[i][1]))

		self._write(buffer)
		ret = self._read(1)
		if ret != 0x01:
			if ret is False:
				msg = __("Error: No response while trying to communicate with the device.")
				time.sleep(0.5)
				self.DEVICE.reset_input_buffer()
			else:
				msg = __("Error: Bad response “{response}” while trying to communicate with the device.", str(ret))
			print(ANSI.RED + msg + ANSI.RESET)
			return False
		return True

	def _clk_toggle(self, num=1):
		if self.FW["fw_ver"] >= 12:
			buffer = bytearray()
			buffer.extend(struct.pack("B", self.DEVICE_CMD["CLK_TOGGLE"]))
			buffer.extend(struct.pack(">I", num))
			return self._write(buffer, wait=True)
		else:
			if not self.CanPowerCycleCart(): return False
			for _ in range(0, num):
				self._write(0xA9) # CLK_HIGH
				self._write(0xAA) # CLK_LOW
			return True

	def _set_we_pin_wr(self):
		if self.MODE == "DMG":
			self._set_fw_variable("FLASH_WE_PIN", 0x01) # FLASH_WE_PIN_WR
	def _set_we_pin_audio(self):
		if self.MODE == "DMG":
			self._set_fw_variable("FLASH_WE_PIN", 0x02) # FLASH_WE_PIN_AUDIO

	def CartPowerCycleOrAskReconnect(self):
		if self.CanPowerCycleCart():
			self.CartPowerCycle()
			return

		if self.FW["fw_ver"] < 12:
			self.CANCEL_ARGS.update({
				"info_type": "msgbox_critical",
				"info_msg": __("This flashcart profile requires at least firmware version L12.")
			})
			self.CANCEL = True
			self.USER_ANSWER = None
			return False

		mode = self.GetMode()
		var_state = self.GetVarState()

		title = __("Power cycle required")
		msg = __("To continue, please re-connect the USB cable of your {device_name} on port {device_port} now.", device_name=self.GetName(), device_port=self.PORT)
		while True:
			self.USER_ANSWER = None
			self.SetProgress({"action":"USER_ACTION", "user_action":"REINSERT_CART", "msg":msg, "title":title})
			while self.USER_ANSWER is None:
				dprint("Waiting for the user to confirm the re-connecting of the device.")
				time.sleep(1)

			if self.USER_ANSWER is False:
				self.CANCEL_ARGS.update({"from_user": True})
				self.CANCEL = True
				self.USER_ANSWER = None
				return False

			if self.CheckActive(): continue
			self.USER_ANSWER = None

			dev = None
			try:
				dev = serial.Serial(self.PORT, self.BAUDRATE, timeout=0.1)
				self.DEVICE = dev
				self.LoadFirmwareVersion()
				self.SetMode(mode)
				self.SetVarState(var_state)
				time.sleep(0.5)
				break

			except SerialException as e:
				del(dev)
				dprint("An error occured while re-connecting to the device:\n", e)
				continue

	def CartPowerCycle(self):
		if self.CanPowerCycleCart():
			dprint("Power cycling cartridge")
			self.CartPowerOff()
			self.CartPowerOn()

	def CartPowerOff(self):
		dprint("Turning off the cartridge power")
		if self.CanPowerCycleCart():
			if self.FW["fw_ver"] >= 12 or "OFW_CART_PWR_OFF" not in self.DEVICE_CMD:
				self._write(self.DEVICE_CMD["CART_PWR_OFF"], wait=self.FW["fw_ver"] >= 12)
			else:
				self._write(self.DEVICE_CMD["OFW_CART_PWR_OFF"])
			# time.sleep(delay) # TODO: Move necessary delays to firmware
		else:
			self._write(self.DEVICE_CMD["SET_ADDR_AS_INPUTS"], wait=self.FW["fw_ver"] >= 12)

	def CartPowerOn(self):
		if self.CanPowerCycleCart():
			if self.FW["fw_ver"] >= 12:
				self._write(self.DEVICE_CMD["QUERY_CART_PWR"])
				if self._read(1) == 0:
					dprint("Turning on the cartridge power")
					if self.MODE == "DMG":
						self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)
					elif self.MODE == "AGB":
						self._write(self.DEVICE_CMD["SET_MODE_AGB"], wait=self.FW["fw_ver"] >= 12)

					if self.FW["pcb_name"] == "GBxCart RW": # Workaround for GBxCart RW, it sometimes glitches after cart power on?
						self._write(self.DEVICE_CMD["CART_PWR_ON"])
						time.sleep(0.2)
						hp = 10
						while hp > 0: 
							if self.DEVICE.in_waiting == 0:
								dprint("Waiting for ACK...")
								hp -= 1
								time.sleep(0.1)
								continue
							temp = self.DEVICE.read(self.DEVICE.in_waiting)
							if len(temp) >= 1: temp = temp[len(temp) - 1]
							if temp == 1: break
							self.DEVICE.timeout = 0.1
							dprint("Unexpected ACK value:", temp)
							self._write(self.DEVICE_CMD["QUERY_CART_PWR"])
							time.sleep(0.05)
							hp -= 1

						if hp == 0:
							self.DEVICE.close()
							self.DEVICE = None
							self.ERROR = True
							raise BrokenPipeError("Couldn’t power on the cartridge.")
					else:
						self._write(self.DEVICE_CMD["CART_PWR_ON"], wait=True)

					self.DEVICE.timeout = self.DEVICE_TIMEOUT

					self._write(self.DEVICE_CMD["QUERY_CART_PWR"])
					if self._read(1) != 1:
						dprint("Warning: No response from firmware on QUERY_CART_PWR.")

					if self.MODE == "DMG":
						dprint("Resetting Memory Bank Controller")
						self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True) # Sachen (and Xploder GB?) may need this
					elif self.MODE == "AGB":
						dprint("Executing AGB Bootup Sequence")
						self._write(self.DEVICE_CMD["AGB_BOOTUP_SEQUENCE"], wait=self.FW["fw_ver"] >= 12)

					if self.FW["pcb_name"] == "GBxCart RW":
						self._cart_write(0, 0xFF) # workaround for strange bootlegs

			else:
				if "OFW_QUERY_CART_PWR" in self.DEVICE_CMD and "OFW_CART_PWR_ON" in self.DEVICE_CMD:
					self._write(self.DEVICE_CMD["OFW_QUERY_CART_PWR"])
					if self._read(1) == 0:
						dprint("Turning on the cartridge power.")
						self._write(self.DEVICE_CMD["OFW_CART_PWR_ON"])
						time.sleep(1)
						self.DEVICE.reset_input_buffer() # bug workaround
				else:
					self._write(self.DEVICE_CMD["QUERY_CART_PWR"])
					if self._read(1) == 0:
						dprint("Turning on the cartridge power.")
						self._write(self.DEVICE_CMD["CART_PWR_ON"], wait=False)
						# time.sleep(delay) # TODO: Move necessary delays to firmware

		else:
			if self.MODE == "AGB":
				dprint("Executing AGB Bootup Sequence")
				self._write(self.DEVICE_CMD["AGB_BOOTUP_SEQUENCE"], wait=self.FW["fw_ver"] >= 12)

		return True

	def GetVarState(self):
		self._write(self.DEVICE_CMD["GET_VAR_STATE"])
		time.sleep(0.2)
		var_state = bytearray(self.DEVICE.read(self.DEVICE.in_waiting))
		dprint("Got the state of variables ({:d} bytes)".format(len(var_state)))
		return var_state

	def SetVarState(self, var_state):
		dprint("Sending the state of variables ({:d} bytes)".format(len(var_state)))
		self._write(self.DEVICE_CMD["SET_VAR_STATE"])
		time.sleep(0.2)
		self.DEVICE.write(var_state)
		self.DEVICE.flush()
		if self.FW["fw_ver"] >= 15: return self.wait_for_ack()

	def GetMode(self):
		if time.time() < self.LAST_CHECK_ACTIVE + 1: return self.MODE
		if self.CheckActive() is False: return None
		if self.MODE is None: return None
		if self.FW["fw_ver"] < 12: return self.MODE
		mode = self._get_fw_variable("CART_MODE")
		if mode is False:
			print(ANSI.RED + __("Error: The firmware no longer responds correctly. Please re-connect the device.") + ANSI.RESET)
			self.DEVICE.close()
			self.DEVICE = None
			self.ERROR = True
			self.CANCEL = True
			return self.MODE
		if mode == 0:
			return None
		modes = self.GetSupprtedModes()
		if mode > len(modes):
			print(ANSI.RED + __("Error: Invalid mode {mode}", mode=str(mode - 1)) + ANSI.RESET)
			return self.MODE
		self.MODE = modes[mode - 1]
		return self.MODE

	def SetMode(self, mode, delay=0.1):
		if mode == "DMG":
			self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)
			self._write(self.DEVICE_CMD["SET_VOLTAGE_5V"], wait=self.FW["fw_ver"] >= 12)
			self._set_fw_variable("DMG_READ_METHOD", self.DMG_READ_METHOD)
			self._set_fw_variable("CART_MODE", 1)
			#if self.FW["fw_ver"] >= 14: self._set_fw_variable("DMG_AUDIO_ENABLED", 0)
			self.MODE = "DMG"
		elif mode == "AGB":
			self._write(self.DEVICE_CMD["SET_MODE_AGB"], wait=self.FW["fw_ver"] >= 12)
			self._write(self.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=self.FW["fw_ver"] >= 12)
			self._set_fw_variable("AGB_READ_METHOD", self.AGB_READ_METHOD)
			self._set_fw_variable("CART_MODE", 2)
			if self.FW["fw_ver"] >= 12: self._set_fw_variable("AGB_IRQ_ENABLED", 0)
			self.MODE = "AGB"
		self._set_fw_variable(key="ADDRESS", value=0)

		if self.CanPowerCycleCart():
			self.CartPowerOn()
		else:
			if mode == "DMG":
				self.SetPin(["PIN_AUDIO"], True)
			elif mode == "AGB":
				self.SetPin(["PIN_AUDIO"], False)

	def SetAutoPowerOff(self, value):
		if not self.CanPowerCycleCart(): return
		value &= 0xFFFFFFFF
		# dprint(f"Setting automatic power off time value to {value}")
		self._set_fw_variable("AUTO_POWEROFF_ENABLED", 1 if value != 0 else 0)
		self._set_fw_variable("AUTO_POWEROFF_TIME", value)
		self.SKIP_POWERCYCLE = False if value != 0 else True

	def _thread_worker_auto_poweroff_enter(self):
		if self.FW is None or self.FW["fw_ver"] < 12: return None
		if not self.CanPowerCycleCart(): return None
		try:
			if self._get_fw_variable("AUTO_POWEROFF_ENABLED") != 1:
				return None
			auto_poweroff_time = self._get_fw_variable("AUTO_POWEROFF_TIME")
			self._set_fw_variable("AUTO_POWEROFF_TIME", 5000)
			return auto_poweroff_time
		except Exception as e:
			dprint("AUTO_POWEROFF thread enter failed:", str(e))
			return None

	def _thread_worker_auto_poweroff_leave(self, auto_poweroff_time):
		if auto_poweroff_time is None: return
		if self.FW is None or self.FW["fw_ver"] < 12: return
		if not self.CanPowerCycleCart(): return
		try:
			self._set_fw_variable("AUTO_POWEROFF_TIME", auto_poweroff_time)
		except Exception as e:
			dprint("AUTO_POWEROFF thread leave failed:", str(e))

	def _thread_worker_auto_poweroff_start(self):
		self.THREAD_AUTO_POWEROFF_TIME = self._thread_worker_auto_poweroff_enter()

	def _thread_worker_auto_poweroff_finish(self):
		auto_poweroff_time = self.THREAD_AUTO_POWEROFF_TIME
		self.THREAD_AUTO_POWEROFF_TIME = None
		self._thread_worker_auto_poweroff_leave(auto_poweroff_time)

	def GetSupportedCartridgesDMG(self):
		return (list(self.SUPPORTED_CARTS['DMG'].keys()), list(self.SUPPORTED_CARTS['DMG'].values()))

	def GetSupportedCartridgesAGB(self):
		return (list(self.SUPPORTED_CARTS['AGB'].keys()), list(self.SUPPORTED_CARTS['AGB'].values()))

	def SetProgress(self, args, signal=None):
		if self.CANCEL and args["action"] not in ("ABORT", "FINISHED", "ERROR"): return
		# Swallow hardware-triggered ABORT popups while a voltage fallback retry is queued,
		# so the silent retry isn't preceded by an error dialog. User cancels carry from_user=True
		# and must always pass through.
		if (self.VOLTAGE_FALLBACK_PENDING is True
			and args.get("action") == "ABORT"
			and args.get("from_user", False) is not True):
			self.VOLTAGE_FALLBACK_TRIGGERED = True
			return
		if "pos" in args: self.POS = args["pos"]
		if args["action"] == "UPDATE_POS": self.INFO["transferred"] = args["pos"]
		if signal is None:
			signal = self.SIGNAL

		try:
			signal.emit(args)
		except AttributeError:
			if signal is not None:
				signal(args)

		if args["action"] == "INITIALIZE":
			if self.CanPowerCycleCart(): self.CartPowerOn() # Ensure cart is powered
			self.POS = 0
		elif args["action"] == "FINISHED":
			self.POS = 0
			signal = None
			self.SIGNAL = None

	def Debug(self):
		if not self.IsConnected(): return False
		self._write(self.DEVICE_CMD["DEBUG"], wait=True) # For delay measurement on CLK line
		return True

	def ReadHeader(self, checkRtc=True):
		if not self.IsConnected(): raise ConnectionError("Couldn’t access the the device.")
		data = {}
		self.SIGNAL = None

		if self.CanPowerCycleCart():
			self.ResetLEDs()
			self.CartPowerOn()

		if self.FW["fw_ver"] >= 8: self._write(self.DEVICE_CMD["DISABLE_PULLUPS"], wait=True)
		if self.MODE == "DMG":
			self._write(self.DEVICE_CMD["SET_VOLTAGE_5V"], wait=self.FW["fw_ver"] >= 12)
			self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
			self._set_fw_variable("DMG_READ_CS_PULSE", 0)
			self._set_fw_variable("DMG_WRITE_CS_PULSE", 0)
		elif self.MODE == "AGB":
			self._write(self.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=self.FW["fw_ver"] >= 12)
			if not self.CanPowerCycleCart():
				dprint("Executing AGB Bootup Sequence")
				self._write(self.DEVICE_CMD["AGB_BOOTUP_SEQUENCE"], wait=self.FW["fw_ver"] >= 12)
		else:
			print(ANSI.RED + __("Error: No mode was set.") + ANSI.RESET)
			return False

		header = self.ReadROM(0, 0x180)

		if ".dev" in AppInfo.VERSION_PEP440 or AppContext.DEBUG:
			with open(AppContext.CONFIG_PATH + os.sep + "debug_header.bin", "wb") as f: f.write(header)

		# Parse ROM header
		if self.MODE == "DMG":
			data = RomFileDMG(header).GetHeader()
			if "game_title" in data and data["game_title"] == "TETRIS" and hashlib.sha1(header).digest() != bytearray([0x1D, 0x69, 0x2A, 0x4B, 0x31, 0x7A, 0xA5, 0xE9, 0x67, 0xEE, 0xC2, 0x2F, 0xCC, 0x32, 0x43, 0x8C, 0xCB, 0xC5, 0x78, 0x0B]): # Sachen
				header = self.ReadROM(0, 0x280)
				data = RomFileDMG(header).GetHeader()
			if "logo_correct" in data and data["logo_correct"] is False and not b"Future Console Design" in header:
				if self.FW["pcb_name"] == "GBxCart RW":
					self._cart_write(0, 0xFF) # workaround for strange bootlegs
					time.sleep(0.1)
				header = self.ReadROM(0, 0x280)
				data = RomFileDMG(header).GetHeader()
			if "mapper_raw" in data and data["mapper_raw"] == 0x203 or b"Future Console Design" in header: # Xploder GB version number
				self._cart_write(0x0006, 0)
				header[0:0x10] = self.ReadROM(0x4000, 0x10)
				header[0xD0:0xE0] = self.ReadROM(0x40D0, 0x10)
				data = RomFileDMG(header).GetHeader()
			if data == {}: return False

			data["has_rtc"] = False
			data["rtc_dict"] = {}
			data["rtc_string"] = c__("Game Data", "Not available")
			if data["logo_correct"] is True:
				_mbc = DMG_Mapper().GetInstance(args={"mbc":data["mapper_raw"]}, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
				if checkRtc:
					data["has_rtc"] = _mbc.HasRTC() is True
					if data["has_rtc"] is True:
						if _mbc.GetName() == "TAMA5": _mbc.EnableMapper()
						_mbc.LatchRTC()
						data["rtc_buffer"] = _mbc.ReadRTC()
						if _mbc.GetName() == "TAMA5": self._set_fw_variable("DMG_READ_CS_PULSE", 0)
						try:
							data["rtc_dict"] = _mbc.GetRTCDict()
							data["rtc_string"] = _mbc.GetRTCString()
						except:
							data["rtc_string"] = c__("Game Data", "Invalid RTC data")

				if _mbc.GetName() == "G-MMC1":
					try:
						temp = bytearray([0] * 0x100000)
						temp[0:0x180] = header
						_mbc.SelectBankROM(7)
						if data["game_title"] in ("NP M-MENU MENU", "GBMEM-MENU MMSA"):
							gbmem_menudata = self.ReadROM(0x4000, 0x1000)
							temp[0x1C000:0x1C000+0x1000] = gbmem_menudata
						elif data["game_title"] == "DMG MULTI MENU ":
							gbmem_menudata = self.ReadROM(0x4000, 0x4000)
							temp[0x1C000:0x1C000+0x4000] = gbmem_menudata
						elif data["game_title"] == "GBMEM-MENU 256M":
							gbmem_menudata = self.ReadROM(0x4000, 0x1000)
							temp[0x10010:0x10010+0x1000] = gbmem_menudata
						_mbc.SelectBankROM(0)
						gbmem_parsed = (GBMemoryMap()).ParseMapData(buffer_map=_mbc.ReadHiddenSector(), buffer_rom=temp)
						if gbmem_parsed:
							data["gbmem_parsed"] = gbmem_parsed
					except:
						print(traceback.format_exc())
						print(ANSI.RED + __("An error occured while trying to read the hidden sector data of the {gb_memory_cartridge}.", gb_memory_cartridge="NP GB-Memory Cartridge") + ANSI.RESET)

				elif _mbc.GetName() == "MAC-GBD":
					dprint("Reading Game Boy Camera calibration data...")
					_mbc.EnableRAM(True)
					_mbc.SelectBankRAM(2)
					temp = self.ReadRAM(address=0xFF2, length=0xE)
					if temp != bytearray(temp[0] * len(temp)):
						data["gbcamera_calibration1"] = temp
						dprint("Game Boy Camera calibration data 1:", ''.join(format(x, '02X') for x in temp))
					_mbc.SelectBankRAM(8)
					temp = self.ReadRAM(address=0x1FF2, length=0xE)
					if temp != bytearray(temp[0] * len(temp)):
						data["gbcamera_calibration2"] = temp
						dprint("Game Boy Camera calibration data 2:", ''.join(format(x, '02X') for x in temp))
					_mbc.EnableRAM(False)

		elif self.MODE == "AGB":
			# Unlock DACS carts on older firmware
			if not self.CanPowerCycleCart() or self.FW["fw_ver"] == 1:
				if header[0x04:0x04+0x9C] in (bytearray([0x00] * 0x9C), bytearray([0xFF] * 0x9C)):
					self.ReadROM(0x1FFFFE0, 20)
					header = self.ReadROM(0, 0x180)

			data = RomFileAGB(header).GetHeader()
			if data["logo_correct"] is False: # workaround for strange bootlegs
				self._cart_write(0, 0xFF)
				header = self.ReadROM(0, 0x180)
				data = RomFileAGB(header).GetHeader()

			if data["vast_fame"]: # Unlock full address space for Vast Fame protected carts
				self._cart_write(0xFFF8, 0x99, sram=True)
				self._cart_write(0xFFF9, 0x02, sram=True)
				self._cart_write(0xFFFA, 0x05, sram=True)
				self._cart_write(0xFFFB, 0x02, sram=True)
				self._cart_write(0xFFFC, 0x03, sram=True)

				self._cart_write(0xFFFD, 0x00, sram=True)

				self._cart_write(0xFFF8, 0x99, sram=True)
				self._cart_write(0xFFF9, 0x03, sram=True)
				self._cart_write(0xFFFA, 0x62, sram=True)
				self._cart_write(0xFFFB, 0x02, sram=True)
				self._cart_write(0xFFFC, 0x56, sram=True)

			if data["empty"] or data["empty_nocart"]:
				data["rom_size"] = 0x2000000
			else:
				# Check where the ROM data repeats (for unlicensed carts)
				size_check = header[0xA0:0xA0+16]
				currAddr = 0x10000
				while currAddr < 0x2000000:
					buffer = self.ReadROM(currAddr + 0xA0, 64)[:16]
					if buffer == size_check: break
					currAddr *= 2

				if data["vast_fame"]:
					if currAddr < 0x2000000:
						currAddr >>= 1 # Vast Fame carts are blank for the 1st mirror, so divide by 2
					else: # Some Vast Fame carts have no mirror, check using VF pattern behaviour instead
						currAddr = 0x200000
						while currAddr < 0x2000000:
							sentinel = self.ReadROM(currAddr + 0x2AAAA, 2)
							if int.from_bytes(sentinel) == 0xAAAA: break
							currAddr *= 2

				data["rom_size"] = currAddr

			if (self.ReadROM(0x1FFE000, 0x0C) == b"AGBFLASHDACS"):
				data["dacs_8m"] = True
				if self.FW["pcb_name"] == "GBFlash" and self.FW["pcb_ver"] < 13:
					print(ANSI.YELLOW + __("Note: This cartridge may not be fully compatible with your GBFlash hardware revision. Upgrade to v1.3 or newer for better compatibility.") + ANSI.RESET)

			data["rtc_dict"] = {}
			data["rtc_string"] = c__("Game Data", "Not available")
			if checkRtc and data["logo_correct"] is True and header[0xC5] == 0 and header[0xC7] == 0 and header[0xC9] == 0:
				_agb_gpio = AGB_GPIO(args={"rtc":True}, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
				if self.FW["fw_ver"] >= 12:
					self._write(self.DEVICE_CMD["AGB_READ_GPIO_RTC"])
					temp = self._read(8)
					data["has_rtc"] = _agb_gpio.HasRTC(temp) is True
					if data["has_rtc"] is True:
						data["rtc_buffer"] = temp[1:8]
				else:
					data["has_rtc"] = _agb_gpio.HasRTC() is True
					if data["has_rtc"] is True:
						data["rtc_buffer"] = _agb_gpio.ReadRTC()
				try:
					data["rtc_dict"] = _agb_gpio.GetRTCDict(has_rtc=data["has_rtc"])
					data["rtc_string"] = _agb_gpio.GetRTCString(has_rtc=data["has_rtc"])
				except Exception as e:
					dprint("RTC exception:", str(e.args[0]))
					data["has_rtc"] = False
			else:
				data["has_rtc"] = False
				data["no_rtc_reason"] = None

			if data["ereader"] is True:
				bank = 0
				dprint("Switching to FLASH bank {:d}".format(bank))
				cmds = [
					[ 0x5555, 0xAA ],
					[ 0x2AAA, 0x55 ],
					[ 0x5555, 0xB0 ],
					[ 0, bank ]
				]
				self._cart_write_flash(cmds)
				temp = self.ReadRAM(address=0xD000, length=0x2000, command=self.DEVICE_CMD["AGB_CART_READ_SRAM"])
				if temp[0:0x14] == b'Card-E Reader 2001\0\0':
					data["ereader_calibration"] = temp
				else:
					data["ereader_calibration"] = None
					del(data["ereader_calibration"])

		dprint("Header data:", data)
		data["raw"] = header
		self.INFO = {**self.INFO, **data}
		if "batteryless_sram" in self.INFO["dump_info"]: del(self.INFO["dump_info"]["batteryless_sram"])
		self.INFO["dump_info"]["header"] = data
		self.INFO["flash_type"] = 0
		self.INFO["last_action"] = 0

		if self.MODE == "DMG":
			self._write(self.DEVICE_CMD["SET_ADDR_AS_INPUTS"], wait=self.FW["fw_ver"] >= 12)

		return data

	def _DetectCartridge(self, args): # Wrapper for thread call
		self.SetProgress({"action":"INITIALIZE", "abortable":False, "method":"DETECT_CART"})
		signal = self.SIGNAL
		self.SIGNAL = None

		auto_poweroff_enabled = self._get_fw_variable("AUTO_POWEROFF_ENABLED")
		if auto_poweroff_enabled: self._set_fw_variable("AUTO_POWEROFF_ENABLED", 0)

		auto_poweroff_time = self._thread_worker_auto_poweroff_enter()
		try:
			ret = self._DetectCartridge_Worker(mbc=None, limitVoltage=args["limitVoltage"], checkSaveType=args["checkSaveType"], signal=signal)
			self.INFO["detect_cart"] = ret
		finally:
			self._thread_worker_auto_poweroff_leave(auto_poweroff_time)
			if auto_poweroff_enabled: self._set_fw_variable("AUTO_POWEROFF_ENABLED", auto_poweroff_enabled)

		self.INFO["detect_cart"] = ret
		self.INFO["last_action"] = self.ACTIONS["DETECT_CART"]
		self.INFO["action"] = None
		self.SIGNAL = signal
		self.SetProgress({"action":"FINISHED"})
		return True

	def _DetectCartridge_Worker(self, mbc=None, limitVoltage=False, checkSaveType=True, signal=None):
		self.SIGNAL = None
		self.CANCEL = False
		self.ERROR = False
		cart_type_id = 0
		save_type = None
		save_chip = None
		sram_unstable = None
		save_size = None
		checkBatterylessSRAM = False
		_apot = 0

		# Header
		if signal is not None: self.SetProgress({"action":"UPDATE_INFO", "text":__("Detecting ROM...")}, signal=signal)
		info = self.ReadHeader(checkRtc=True)
		if self.MODE == "DMG" and mbc is None:
			mbc = info["mapper_raw"]
			if mbc > 0x200: checkSaveType = False

		# Disable Auto Power Off
		_apoe = False
		if self.FW["fw_ver"] >= 12 and self.SKIP_POWERCYCLE is False:
			if self.CanPowerCycleCart():
				self.CartPowerCycle()
				_apoe = self._get_fw_variable("AUTO_POWEROFF_ENABLED") == 1
				if _apoe is True:
					_apot = self._get_fw_variable("AUTO_POWEROFF_TIME")
					self._set_fw_variable("AUTO_POWEROFF_TIME", 5000)

		# Detect Flash Cart
		if signal is not None: self.SetProgress({"action":"UPDATE_INFO", "text":__("Detecting Flash...")}, signal=signal)
		ret = self.DetectFlash(limitVoltage=limitVoltage)
		if ret is False: return False
		(cart_types, cart_type_id, flash_id, cfi_s, cfi, detected_size) = ret
		supported_carts = list(self.SUPPORTED_CARTS[self.MODE].values())
		cart_type = supported_carts[cart_type_id]

		# Skip DMG save type detection
		if self.MODE == "DMG" and cart_type_id == 0: checkSaveType = False

		# Preparations
		if ("command_set" in cart_type and cart_type["command_set"] in ("DMG-MBC5-32M-FLASH", "GBAMP")) or ("dmg-mbc5-32m-flash" in cart_type):
			checkSaveType = False
		elif self.MODE == "AGB" and "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] == 1:
			save_size = 65536
			save_type = 7
			checkSaveType = False
		elif self.MODE == "AGB" and "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] > 1:
			checkSaveType = False
		elif self.MODE == "DMG" and "mbc" in cart_type and cart_type["mbc"] == 0x105: # G-MMC1
			if signal is not None: self.SetProgress({"action":"UPDATE_INFO", "text":__("Detecting {gb_memory}...", gb_memory="GB-Memory")}, signal=signal)
			header = self.ReadROM(0, 0x180)
			data = RomFileDMG(header).GetHeader()
			_mbc = DMG_Mapper().GetInstance(args={"mbc":cart_type["mbc"]}, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
			temp = bytearray([0] * 0x100000)
			temp[0:0x180] = header
			if data["game_title"] in ("NP M-MENU MENU", "GBMEM-MENU MMSA"):
				_mbc.SelectBankROM(7)
				gbmem_menudata = self.ReadROM(0x4000, 0x1000)
				temp[0x1C000:0x1C000+0x1000] = gbmem_menudata
			elif data["game_title"] == "DMG MULTI MENU ":
				_mbc.SelectBankROM(7)
				gbmem_menudata = self.ReadROM(0x4000, 0x4000)
				temp[0x1C000:0x1C000+0x4000] = gbmem_menudata
			elif data["game_title"] == "GBMEM-MENU 256M":
				_mbc.SelectBankROM(4)
				gbmem_menudata = self.ReadROM(0x4010, 0x1000)
				temp[0x10010:0x10010+0x1000] = gbmem_menudata
			_mbc.SelectBankROM(0)
			info["gbmem"] = _mbc.ReadHiddenSector()
			gbmem_parsed = (GBMemoryMap()).ParseMapData(buffer_map=info["gbmem"], buffer_rom=temp)
			if gbmem_parsed:
				info["gbmem_parsed"] = gbmem_parsed

		# Save Type and Size
		if checkSaveType:
			if signal is not None: self.SetProgress({"action":"UPDATE_INFO", "text":__("Detecting save type...")}, signal=signal)
			if self.MODE == "DMG":
				save_size = 131072
				save_type = 0x04
				if mbc == 0x20: # MBC6
					save_size = 1081344
					save_type = 0x104
					return (info, save_size, save_type, save_chip, sram_unstable, cart_types, cart_type_id, cfi_s, cfi, flash_id, detected_size)
				elif mbc == 0x22: # MBC7
					save_type = 0x102
					save_size = 512
				elif mbc == 0xFD: # TAMA5
					save_size = 32
					save_type = 0x103
					return (info, save_size, save_type, save_chip, sram_unstable, cart_types, cart_type_id, cfi_s, cfi, flash_id, detected_size)
				elif mbc == 0x105: # G-MMC1
					save_size = 0x20000
					save_type = 0x04
					return (info, save_size, save_type, save_chip, sram_unstable, cart_types, cart_type_id, cfi_s, cfi, flash_id, detected_size)
				args = { 'mode':2, 'path':None, 'mbc':mbc, 'save_type':save_type, 'rtc':False, 'detect':True }
			elif self.MODE == "AGB":
				args = { 'mode':2, 'path':None, 'mbc':mbc, 'save_type':8, 'rtc':False, 'detect':True }
				if info["save_type"] is not None:
					save_type = info["save_type"]
					save_size = info["save_size"]
					if save_type == 9:
						batteryless = self.CheckBatterylessSRAM()
						if batteryless is not False:
							info["batteryless_sram"] = batteryless
							self.INFO["dump_info"]["batteryless_sram"] = batteryless
					checkSaveType = False
			else:
				return

			if checkSaveType:
				ret = self._BackupRestoreRAM(args=args)

				if ret is not False and "data" in self.INFO:
					save_size = self._find_repeating_size(self.INFO["data"], len(self.INFO["data"]))
				else:
					save_size = 0

			if checkSaveType and self.MODE == "DMG":
				try:
					save_type = DmgSaveTypes(size=save_size).GetMbc()
				except:
					save_size = 0
					save_type = 0

				if save_size > 0x20:
					if mbc == 0x22: # MBC7
						if save_size == 256:
							save_type = 0x101
						elif save_size == 512:
							save_type = 0x102
					elif save_size > 0x10000: # MBC30+RTC?
						check = True
						for i in range(0x8000, 0x10000, 0x40):
							if self.INFO["data"][i:i+3] != bytearray([self.INFO["data"][i]] * 3):
								check = False
								break

						if self.INFO["data"][0:0x8000] == self.INFO["data"][0x8000:0x10000]: # MBCX
							check = True

						if check:
							save_size = 32768
							save_type = 0x03
						else:
							check = True
							for i in range(0x1A000, 0x20000, 0x40):
								if self.INFO["data"][i:i+3] != bytearray([self.INFO["data"][i]] * 3):
									check = False
									break
							if check:
								save_size = 65536
								save_type = 0x05

			elif checkSaveType and self.MODE == "AGB":
				if info["3d_memory"] is True:
					save_type = None
					save_size = 0
				else:
					# Check for FLASH
					ret = self.ReadFlashSaveID()
					if ret is not False:
						(flash_save_id, _) = ret
						try:
							if flash_save_id != 0:
								if AgbSaveTypes().IsValidFlashChipIndex(flash_save_id) is True:
									save_size = AgbSaveTypes().GetFlashChipSize(flash_save_id)
									save_chip = AgbSaveTypes().GetFlashChipName(flash_save_id)
									if flash_save_id in (0xBF4B, 0xBF5B, 0xFFFF, 0xBF6D): # Bootlegs
										if self.INFO["data"][0:0x20000] == bytearray([0xFF] * 0x20000):
											save_type = 5
										elif self.INFO["data"][0:0x10000] == self.INFO["data"][0x10000:0x20000]:
											save_type = 4
										else:
											save_type = 5
									elif save_size == 131072:
										save_type = 5
									elif save_size == 65536:
										save_type = 4
								else: # Other bootleg chips
									save_type = 0
									save_size = 0
									save_chip = __("Unknown FLASH save chip") + f" (0x{flash_save_id:04X})"
						except Exception as e:
							print(ANSI.RED + __("Error: Couldn’t check save type with FLASH save ID {flash_save_id}", flash_save_id=f"0x{flash_save_id:04X}") + ANSI.RESET + "\n" + str(e))
							save_type = 0
							save_size = 0
							save_chip = __("Unknown FLASH save chip") + f" (0x{flash_save_id:04X})"

					if save_type is None:
						checkBatterylessSRAM = True
						if info["dacs_8m"] is True:
							save_size = 1048576
							save_type = 6
						elif save_size > 256: # SRAM
							if save_size == 131072:
								save_type = 8
								checkBatterylessSRAM = True
							elif save_size == 65536:
								save_type = 7
								checkBatterylessSRAM = True
							elif save_size == 32768:
								save_type = 3
							elif save_size in AgbSaveTypes():
								save_type = AgbSaveTypes().GetIndexFromSize(save_size)
							else:
								save_type = None
								save_size = 0
						else:
							dprint("Testing EEPROM")
							# Check for 4K EEPROM
							self._BackupRestoreRAM(args={ 'mode':2, 'path':None, 'mbc':mbc, 'save_type':1, 'rtc':False, 'detect':True })
							save_size = self._find_repeating_size(self.INFO["data"], len(self.INFO["data"]))
							eeprom_4k = self.INFO["data"]
							# Check for 64K EEPROM
							self._BackupRestoreRAM(args={ 'mode':2, 'path':None, 'mbc':mbc, 'save_type':2, 'rtc':False, 'detect':True })
							save_size = self._find_repeating_size(self.INFO["data"], len(self.INFO["data"]))
							eeprom_64k = self.INFO["data"]
							if eeprom_64k in (bytearray([0xFF] * len(eeprom_64k)), bytearray([0] * len(eeprom_64k))):
								save_size = 0
								save_type = 0
							elif (eeprom_4k == eeprom_64k[:len(eeprom_4k)]):
								save_type = 2
								save_size = 8192
								checkBatterylessSRAM = False
							else:
								save_type = 1
								save_size = 512
								checkBatterylessSRAM = False

					if checkBatterylessSRAM:
						batteryless = self.CheckBatterylessSRAM()
						if batteryless is not False:
							save_type = 9
							info["batteryless_sram"] = batteryless
							self.INFO["dump_info"]["batteryless_sram"] = batteryless

		self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
		self.INFO["last_action"] = 0
		self.INFO["action"] = None

		if self.CanPowerCycleCart() and _apoe is True and self.SKIP_POWERCYCLE is False:
			self._set_fw_variable("AUTO_POWEROFF_TIME", _apot)

		return (info, save_size, save_type, save_chip, sram_unstable, cart_types, cart_type_id, cfi_s, cfi, flash_id, detected_size)

	def CheckBatterylessSRAM(self):
		bl_size = None
		bl_offset = None
		if self.MODE == "AGB":
			buffer = self.ReadROM(0, 0x180)
			header = RomFileAGB(buffer).GetHeader()
			if header["game_code"] in ("GMBC", "PNES"):
				bl_size = 0x10000
				state_id1 = 0x57a731d7
				state_id2 = 0x57a731d8
				state_id3 = 0x57a731d9
				if struct.unpack("<I", self.ReadROM(0x400000-0x40000, 4))[0] in (state_id1, state_id2, state_id3):
					bl_offset = 0x400000-0x40000
				elif struct.unpack("<I", self.ReadROM(0x800000-0x40000, 4))[0] in (state_id1, state_id2, state_id3):
					bl_offset = 0x800000-0x40000
				elif struct.unpack("<I", self.ReadROM(0x1000000-0x40000, 4))[0] in (state_id1, state_id2, state_id3):
					bl_offset = 0x1000000-0x40000
				elif struct.unpack("<I", self.ReadROM(0x2000000-0x40000, 4))[0] in (state_id1, state_id2, state_id3):
					bl_offset = 0x2000000-0x40000
				dprint("Detected Goomba Color or PocketNES Batteryless ROM by Lesserkuma")
			else:
				boot_vector = (struct.unpack("<I", buffer[0:3] + bytearray([0]))[0] + 2) << 2
				batteryless_loader = self.ReadROM(boot_vector, 0x2000)
				try:
					if bytearray(b'<3 from Maniac') in batteryless_loader:
						payload_size = struct.unpack("<H", batteryless_loader[batteryless_loader.index(bytearray(b'<3 from Maniac')):][0x0E:0x10])[0]
						if payload_size == 0:
							payload_size = 0x414
						bl_offset = batteryless_loader.index(bytearray(b'<3 from Maniac')) + boot_vector + 0x10
						payload = self.ReadROM(bl_offset - payload_size, payload_size)
						bl_size = struct.unpack("<I", payload[0x8:0xC])[0]
						dprint("Detected Batteryless SRAM ROM made with the Automatic batteryless saving patcher for GBA by metroid-maniac")
						if bl_size not in (0x200, 0x2000, 0x8000, 0x10000, 0x20000):
							dprint("Warning: Unsupported Batteryless SRAM size value detected: 0x{:X}".format(bl_size))
					elif bytearray(b'lk_batteryless') in batteryless_loader:
						payload_size = struct.unpack("<H", batteryless_loader[batteryless_loader.index(bytearray(b'lk_batteryless')):][0x0E:0x10])[0]
						bl_offset = batteryless_loader.index(bytearray(b'lk_batteryless')) + boot_vector + 0x10
						payload = self.ReadROM(bl_offset - payload_size, payload_size)
						bl_size = struct.unpack("<I", payload[0x8:0xC])[0]
						dprint("Detected Batteryless SRAM ROM made with the GBA Save Patcher by LK")
						if bl_size not in (0x200, 0x2000, 0x8000, 0x10000, 0x20000):
							dprint("Warning: Unsupported Batteryless SRAM size value detected: 0x{:X}".format(bl_size))
					elif (bytearray([0x02, 0x13, 0xA0, 0xE3]) in batteryless_loader):
						if (
								bytearray([0x09, 0x04, 0xA0, 0xE3]) in batteryless_loader or
								bytearray([0x09, 0x14, 0xA0, 0xE3]) in batteryless_loader or
								bytearray([0x09, 0x24, 0xA0, 0xE3]) in batteryless_loader or
								bytearray([0x09, 0x34, 0xA0, 0xE3]) in batteryless_loader
						):
							bl_size = 0x20000
						else:
							bl_size = 0x10000
						base_addr = batteryless_loader.index(bytearray([0x02, 0x13, 0xA0, 0xE3]))
						addr_value = batteryless_loader[base_addr - 8]
						addr_rotate_right = batteryless_loader[base_addr - 7] * 2
						addr_shift = batteryless_loader[base_addr - 3] << 1
						address = (addr_value >> addr_rotate_right) | (addr_value << (32 - addr_rotate_right)) & 0xFFFFFFFF
						address = (address << addr_shift)
						if address < 32*1024*1024 and address > 0x1000:
							bl_offset = address
							dprint("Detected Chinese bootleg Batteryless SRAM ROM")
						else:
							dprint("Bad offset with Chinese bootleg Batteryless SRAM ROM:", hex(address))
				except Exception as e:
					dprint("An error occured while trying to determine the Batteryless SRAM method.\n", e)
					bl_offset = None
					bl_size = None
		if bl_offset is None or bl_size is None:
			dprint("No Batteryless SRAM routine detected")
			return False
		dprint("bl_offset=0x{:X}, bl_size=0x{:X}".format(bl_offset, bl_size))
		return {"bl_offset":bl_offset, "bl_size":bl_size}

	def ReadFlashSaveID(self):
		# Check if actually SRAM/FRAM
		dprint("Checking Flash ID of Save Memory")
		test_data = self._cart_read(0, 0x10, agb_save_flash=True)
		if test_data is False or len(test_data) < 5:
			return False
		test1 = test_data[4]
		self._cart_write_flash([[ 0x0004, test1 ^ 0xFF ]])
		test_data = self._cart_read(0, 0x10, agb_save_flash=True)
		if test_data is False or len(test_data) < 5:
			return False
		test2 = test_data[4]
		self._cart_write_flash([[ 0x0004, test1 ]])
		if test1 != test2:
			dprint(f"Seems to be SRAM/FRAM, not FLASH (value 0x{test1:02X} was changed to 0x{test2:02X} by SRAM access at address 0x4)", test1, test2)
			return False

		# Read Chip ID
		temp5555 = self._cart_read(0x5555, agb_save_flash=True)
		temp2AAA = self._cart_read(0x2AAA, agb_save_flash=True)
		temp0000 = self._cart_read(0x0000, agb_save_flash=True)
		if temp5555 is False or temp2AAA is False or temp0000 is False:
			return False

		cmds = [
			[ 0x5555, 0xAA ],
			[ 0x2AAA, 0x55 ],
			[ 0x5555, 0x90 ]
		]
		self._cart_write_flash(cmds)
		agb_chip_raw = self._cart_read(0, 2, agb_save_flash=True)
		if agb_chip_raw is False or len(agb_chip_raw) < 2:
			return False
		agb_flash_chip = struct.unpack(">H", agb_chip_raw)[0]
		cmds = [
			[ 0x5555, 0xAA ],
			[ 0x2AAA, 0x55 ],
			[ 0x5555, 0xF0 ]
		]
		self._cart_write_flash(cmds)
		time.sleep(0.01)
		self._cart_write_flash([ [ 0, 0xF0 ] ])
		time.sleep(0.01)

		if not AgbSaveTypes().IsValidFlashChipIndex(agb_flash_chip):
			# Restore SRAM values
			cmds = [
				[ 0x5555, temp5555 ],
				[ 0x2AAA, temp2AAA ],
				[ 0x0000, temp0000 ]
			]
			self._cart_write_flash(cmds)
			agb_flash_chip_name = __("Unknown flash chip ID") + " (0x{:04X})".format(agb_flash_chip)
		else:
			agb_flash_chip_name = AgbSaveTypes().GetFlashChipName(agb_flash_chip)

		dprint(agb_flash_chip_name)
		return (agb_flash_chip, agb_flash_chip_name)

	def ReadROM(self, address, length, skip_init=False, max_length=64):
		max_length = min(max_length, self.MAX_BUFFER_READ)
		num = math.ceil(length / max_length)
		dprint("Reading 0x{:X} bytes from cartridge ROM at 0x{:X} in {:d} iteration(s)".format(length, address, num))
		if length > max_length: length = max_length

		buffer = bytearray()
		if not skip_init:
			self._set_fw_variable("TRANSFER_SIZE", length)
			if self.MODE == "DMG":
				self._set_fw_variable("ADDRESS", address)
				self._set_fw_variable("DMG_ACCESS_MODE", 1) # MODE_ROM_READ
			elif self.MODE == "AGB":
				self._set_fw_variable("ADDRESS", address >> 1)

		if self.MODE == "DMG":
			command = "DMG_CART_READ"
		elif self.MODE == "AGB":
			command = "AGB_CART_READ"
		else:
			raise NotImplementedError

		for n in range(0, num):
			self._write(self.DEVICE_CMD[command])
			temp = self._read(length)
			if temp is not False and isinstance(temp, int): temp = bytearray([temp])
			if temp is False or len(temp) != length:
				dprint("Error while trying to read 0x{:X} bytes from cartridge ROM at 0x{:X} in iteration {:d} of {:d} (response: {:s})".format(length, address, n, num, str(temp)))
				return bytearray()
			buffer += temp
			if self.INFO["action"] in (self.ACTIONS["ROM_READ"], self.ACTIONS["SAVE_READ"], self.ACTIONS["ROM_WRITE_VERIFY"]) and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"READ", "bytes_added":len(temp)})

		return buffer

	def ReadROM_3DMemory(self, address, length, max_length=64):
		max_length = min(max_length, self.MAX_BUFFER_READ)
		buffer_size = 0x1000
		num = math.ceil(length / max_length)
		dprint("Reading 0x{:X} bytes from cartridge ROM in {:d} iteration(s)".format(length, num))
		if length > max_length: length = max_length

		self._set_fw_variable("TRANSFER_SIZE", length)
		self._set_fw_variable("BUFFER_SIZE", buffer_size)
		self._set_fw_variable("ADDRESS", address >> 1)

		buffer = bytearray()
		error = False
		for _ in range(0, int(num / (buffer_size / length))): #32
			for _ in range(0, int(buffer_size / length)): # 0x1000/0x200=8
				self._write(self.DEVICE_CMD["AGB_CART_READ_3D_MEMORY"])
				temp = self._read(length)
				if isinstance(temp, int): temp = bytearray([temp])
				if temp is False or len(temp) != length:
					error = True
					temp = bytearray(length)
				buffer += temp
				if self.INFO["action"] == self.ACTIONS["ROM_READ"] and not self.NO_PROG_UPDATE:
					self.SetProgress({"action":"READ", "bytes_added":length})
			self._write(0)

		if error: return bytearray()
		return buffer

	def ReadROM_GBAMP(self, address, length, max_length=64):
		max_length = min(max_length, self.MAX_BUFFER_READ)
		dprint("GBAMP ROM Read Mode", hex(address), hex(length), hex(max_length))
		addr = (address >> 13 << 16) | (address & 0x1FFF)
		dprint(f"0x{address:07X} → 0x{addr:07X}")
		return self.ReadROM(address=addr, length=length, max_length=max_length)

	def ReadRAM(self, address, length, command=None, max_length=64):
		max_length = min(max_length, self.MAX_BUFFER_READ)
		num = math.ceil(length / max_length)
		dprint("Reading 0x{:X} bytes from cartridge RAM in {:d} iteration(s)".format(length, num))
		if length > max_length: length = max_length
		buffer = bytearray()
		self._set_fw_variable("TRANSFER_SIZE", length)

		if self.MODE == "DMG":
			self._set_fw_variable("ADDRESS", 0xA000 + address)
			self._set_fw_variable("DMG_ACCESS_MODE", 3) # MODE_RAM_READ
			self._set_fw_variable("DMG_READ_CS_PULSE", 1)
			if command is None: command = self.DEVICE_CMD["DMG_CART_READ"]
		elif self.MODE == "AGB":
			self._set_fw_variable("ADDRESS", address)
			if command is None: command = self.DEVICE_CMD["AGB_CART_READ_SRAM"]

		for _ in range(0, num):
			self._write(command)
			temp = self._read(length)
			if isinstance(temp, int): temp = bytearray([temp])
			if temp is False or len(temp) != length: return bytearray()
			buffer += temp
			if not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"READ", "bytes_added":len(temp)})

		if self.MODE == "DMG":
			self._set_fw_variable("DMG_READ_CS_PULSE", 0)

		return buffer

	def ReadRAM_MBC7(self, address, length):
		max_length = 32
		num = math.ceil(length / max_length)
		dprint("Reading 0x{:X} bytes from cartridge EEPROM in {:d} iteration(s)".format(length, num))
		if length > max_length: length = max_length
		buffer = bytearray()
		self._set_fw_variable("TRANSFER_SIZE", length)
		self._set_fw_variable("ADDRESS", address)
		for _ in range(0, num):
			self._write(self.DEVICE_CMD["DMG_MBC7_READ_EEPROM"])
			temp = self._read(length)
			if temp is False:
				self.ERROR = True
				break
			if isinstance(temp, int): temp = bytearray([temp])
			buffer += temp
			if not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"READ", "bytes_added":len(temp)})

		return buffer

	def ReadRAM_TAMA5(self):
		dprint("Reading 0x20 bytes from cartridge RAM")
		buffer = bytearray()
		npu = self.NO_PROG_UPDATE
		self.NO_PROG_UPDATE = True
		self._set_fw_variable("DMG_READ_CS_PULSE", 1)
		self._set_fw_variable("DMG_WRITE_CS_PULSE", 1)

		# Read save state
		for i in range(0, 0x20):
			self._cart_write(0xA001, 0x06, sram=True) # register select and address (high)
			self._cart_write(0xA000, i >> 4 | 0x01 << 1, sram=True) # bit 0 = higher ram address, rest = command
			self._cart_write(0xA001, 0x07, sram=True) # address (low)
			self._cart_write(0xA000, i & 0x0F, sram=True) # bits 0-3 = lower ram address
			self._cart_write(0xA001, 0x0D, sram=True) # data out (high)
			value1, value2 = None, None
			while value1 is None or value1 != value2:
				value2 = value1
				value1 = self._cart_read(0xA000)
			data_h = value1
			self._cart_write(0xA001, 0x0C, sram=True) # data out (low)

			value1, value2 = None, None
			while value1 is None or value1 != value2:
				value2 = value1
				value1 = self._cart_read(0xA000)
			data_l = value1

			data = ((data_h & 0xF) << 4) | (data_l & 0xF)
			buffer.append(data)
			self.SetProgress({"action":"UPDATE_POS", "abortable":False, "pos":i+1})

		self._set_fw_variable("DMG_READ_CS_PULSE", 0)

		self.NO_PROG_UPDATE = npu
		return buffer

	def WriteRAM(self, address, buffer, command=None, max_length=256):
		max_length = min(max_length, self.MAX_BUFFER_WRITE)
		length = len(buffer)
		num = math.ceil(length / max_length)
		dprint("Writing 0x{:X} bytes to cartridge RAM in {:d} iteration(s)".format(length, num))
		if length > max_length: length = max_length

		self._set_fw_variable("TRANSFER_SIZE", length)
		if self.MODE == "DMG":
			self._set_fw_variable("ADDRESS", 0xA000 + address)
			self._set_fw_variable("DMG_ACCESS_MODE", 4) # MODE_RAM_WRITE
			self._set_fw_variable("DMG_WRITE_CS_PULSE", 1)
			if command is None: command = self.DEVICE_CMD["DMG_CART_WRITE_SRAM"]
		elif self.MODE == "AGB":
			self._set_fw_variable("ADDRESS", address)
			if command is None: command = self.DEVICE_CMD["AGB_CART_WRITE_SRAM"]

		for i in range(0, num):
			self._write(command)
			self._write(buffer[i*length:i*length+length], wait=True)
			#self._read(1)
			if self.INFO["action"] == self.ACTIONS["SAVE_WRITE"] and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":length})

		if self.MODE == "DMG":
			self._set_fw_variable("ADDRESS", 0)
			self._set_fw_variable("DMG_WRITE_CS_PULSE", 0)

		return True

	def WriteFlash_MBC6(self, address, buffer, mapper):
		length = len(buffer)
		max_length = 128
		num = math.ceil(length / max_length)
		if length > max_length: length = max_length
		dprint("Write 0x{:X} bytes to cartridge FLASH in {:d} iteration(s)".format(length, num))

		skip_write = False
		for i in range(0, num):
			self._set_fw_variable("TRANSFER_SIZE", length)
			self._set_fw_variable("ADDRESS", address)
			dprint("Now in iteration {:d}".format(i))

			if buffer[i*length:i*length+length] == bytearray([0xFF] * length):
				skip_write = True
				address += length
				continue

			cmds = [
				[ 0x2000, 0x01 ],
				[ 0x3000, 0x02 ],
				[ 0x7555, 0xAA ],
				[ 0x4AAA, 0x55 ],
				[ 0x7555, 0xA0 ],
			]
			self._cart_write_flash(cmds)
			mapper.SelectBankFlash(mapper.GetROMBank())
			self._write(self.DEVICE_CMD["DMG_MBC6_MMSA_WRITE_FLASH"])
			self._write(buffer[i*length:i*length+length])
			ret = self._read(1)
			if ret not in (0x01, 0x03):
				dprint("Flash write error (response = {:s}) in iteration {:d} while trying to write 0x{:X} bytes".format(str(ret), i, length))
				if "from_user" in self.CANCEL_ARGS and self.CANCEL_ARGS["from_user"]: return False
				self.CANCEL_ARGS.update({
					"info_type": "msgbox_critical",
					"info_msg": __(
						"Flash write error (response = {response}) in iteration {iteration} while trying to write {length} bytes",
						response=str(ret), iteration=i, length=length
					)
				})
				self.CANCEL = True
				self.ERROR = True
				return False
			self._cart_write(address + length - 1, 0x00)
			hp = 100
			while hp > 0:
				sr = self._cart_read(address + length - 1)
				if sr == 0x80: break
				time.sleep(0.001)
				hp -= 1

			if hp == 0:
				dprint("Flash write timeout (response = {:s}) in iteration {:d} while trying to write 0x{:X} bytes".format(str(ret), i, length))
				if "from_user" in self.CANCEL_ARGS and self.CANCEL_ARGS["from_user"]: return False
				self.CANCEL_ARGS.update({
					"info_type": "msgbox_critical",
					"info_msg": __(
						"Flash write timeout (response = {response}) in iteration {iteration} while trying to write {length} bytes",
						response=str(ret), iteration=i, length=length
					)
				})
				self.CANCEL = True
				self.ERROR = True
				return False

			address += length
			if self.INFO["action"] == self.ACTIONS["SAVE_WRITE"] and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":length})
		self._cart_write(address - 1, 0xF0)
		self.SKIPPING = skip_write

	def WriteEEPROM_MBC7(self, address, buffer):
		length = len(buffer)
		max_length = 32
		num = math.ceil(length / max_length)
		if length > max_length: length = max_length
		dprint("Write 0x{:X} bytes to cartridge EEPROM in {:d} iteration(s)".format(length, num))
		self._set_fw_variable("TRANSFER_SIZE", length)
		self._set_fw_variable("ADDRESS", address)
		for i in range(0, num):
			self._write(self.DEVICE_CMD["DMG_MBC7_WRITE_EEPROM"])
			self._write(buffer[i*length:i*length+length])
			response = self._read(1)
			dprint("Response:", response)
			if self.INFO["action"] == self.ACTIONS["SAVE_WRITE"] and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":length})

	def WriteRAM_TAMA5(self, buffer):
		npu = self.NO_PROG_UPDATE
		self.NO_PROG_UPDATE = True

		for i in range(0, 0x20):
			self._cart_write(0xA001, 0x05, sram=True) # data in (high)
			self._cart_write(0xA000, buffer[i] >> 4, sram=True)
			self._cart_write(0xA001, 0x04, sram=True) # data in (low)
			self._cart_write(0xA000, buffer[i] & 0xF, sram=True)
			self._cart_write(0xA001, 0x06, sram=True) # register select and address (high)
			self._cart_write(0xA000, i >> 4 | 0x00 << 1, sram=True) # bit 0 = higher ram address, rest = command
			self._cart_write(0xA001, 0x07, sram=True) # address (low)
			self._cart_write(0xA000, i & 0x0F, sram=True) # bits 0-3 = lower ram address
			value1, value2 = None, None
			while value1 is None or value1 != value2:
				value2 = value1
				value1 = self._cart_read(0xA000)
			self.SetProgress({"action":"UPDATE_POS", "abortable":False, "pos":i+1})

		self.NO_PROG_UPDATE = npu

	def WriteROM(self, address, buffer, flash_buffer_size=False, skip_init=False, rumble_stop=False, max_length=0x400):
		max_length = min(max_length, self.MAX_BUFFER_WRITE)
		length = len(buffer)
		num = math.ceil(length / max_length)
		dprint("Writing 0x{:X} bytes to Flash ROM in {:d} iteration(s)".format(length, num))
		if length == 0:
			dprint("Length is zero?")
			return False
		elif length > max_length:
			length = max_length

		skip_write = False
		ret = 0
		num_of_chunks = math.ceil(flash_buffer_size / length)
		pos = 0

		if not skip_init:
			self._set_fw_variable("TRANSFER_SIZE", length)
			if flash_buffer_size is not False:
				self._set_fw_variable("BUFFER_SIZE", flash_buffer_size)

		for i in range(0, num):
			data = bytearray(buffer[i*length:i*length+length])
			if (num_of_chunks == 1 or flash_buffer_size == 0) and (data == bytearray([0xFF] * len(data))):
				skip_init = False
				skip_write = True
			else:
				if skip_write:
					skip_write = False

			if not skip_write:
				if not skip_init:
					if self.MODE == "DMG":
						self._set_fw_variable("ADDRESS", address)
					elif self.MODE == "AGB":
						self._set_fw_variable("ADDRESS", address >> 1)

					skip_init = True

				if ret != 0x03: self._write(self.DEVICE_CMD["FLASH_PROGRAM"])
				ret = self._write(data, wait=True)

				if ret not in (0x01, 0x03):
					dprint("Flash error at 0x{:X} in iteration {:d} of {:d} while trying to write a total of 0x{:X} bytes (response = {:s})".format(address, i, num, len(buffer), str(ret)))
					self.ERROR_ARGS = { "iteration":i }
					self.SKIPPING = False
					return False
				pos += len(data)

				if rumble_stop and flash_buffer_size > 0 and pos % flash_buffer_size == 0:
					self._cart_write(address=0xC4, value=0x00, flashcart=True)
					self._cart_write(address=0xC6, value=0x00, flashcart=True)
					rumble_stop = False

			address += length
			if ((pos % length) * 10 == 0) and (self.INFO["action"] in (self.ACTIONS["ROM_WRITE"], self.ACTIONS["SAVE_WRITE"]) and not self.NO_PROG_UPDATE):
				self.SetProgress({"action":"WRITE", "bytes_added":length, "skipping":skip_write})

		self.SKIPPING = skip_write

	def _get_flash_write_params(self, data_length, buffer_pos, buffer_len, flash_buffer_size):
		write_len = min(buffer_len, max(0, data_length - buffer_pos))
		max_buffer_write = self.MAX_BUFFER_WRITE
		write_flash_buffer_size = flash_buffer_size
		if data_length == 0x1FFFF00 and buffer_pos < data_length and buffer_pos + buffer_len > data_length:
			max_buffer_write = 0x100
			if flash_buffer_size and flash_buffer_size > max_buffer_write:
				write_flash_buffer_size = max_buffer_write
		return (write_len, max_buffer_write, write_flash_buffer_size)

	def _ShouldApplyROMWriteBankSwitchSeparator(self, flashcart, command_set_type, bank, conflict_values):
		if self.MODE != "DMG":
			return False
		if flashcart is None or not flashcart.WEisWR():
			return False
		if command_set_type != "AMD":
			return False
		if not conflict_values:
			return False
		return (bank & 0xFF) in conflict_values

	def _SelectROMBankForFlash(self, mbc, bank, flashcart):
		audio_enabled = self.FW_VAR.get("DMG_AUDIO_ENABLED", 0)
		# On gated development carts, an MBC bank value can otherwise be
		# interpreted as a flash command while AUDIO/VIN is high.
		gate_audio = (
			self.MODE == "DMG"
			and self.FW.get("fw_ver", 0) >= 14
			and flashcart is not None
			and flashcart.AudioGatesFlashWrite()
			and audio_enabled == 1
		)
		if not gate_audio:
			return mbc.SelectBankROM(bank)

		try:
			self._set_fw_variable("DMG_AUDIO_ENABLED", 0)
			return mbc.SelectBankROM(bank)
		finally:
			self._set_fw_variable("DMG_AUDIO_ENABLED", audio_enabled)

	def _get_backup_read_length(self, pos, end_address, buffer_len):
		return min(buffer_len, max(0, end_address - pos))

	def WriteROM_GBMEMORY(self, address, buffer, bank):
		length = len(buffer)
		max_length = 128
		num = math.ceil(length / max_length)
		if length > max_length: length = max_length
		dprint("Writing 0x{:X} bytes to GB-Memory Flash ROM in {:d} iteration(s)".format(length, num))

		skip_write = False
		for i in range(0, num):
			self._set_fw_variable("TRANSFER_SIZE", length)
			self._set_fw_variable("ADDRESS", address)
			dprint("Now in iteration {:d}".format(i))

			if buffer[i*length:i*length+length] == bytearray([0xFF] * length):
				skip_write = True
				address += length
				continue

			# Enable flash chip access
			self._cart_write_flash([
				[ 0x120, 0x09 ],
				[ 0x121, 0xAA ],
				[ 0x122, 0x55 ],
				[ 0x13F, 0xA5 ],
			])
			# Re-Enable writes to MBC registers
			self._cart_write_flash([
				[ 0x120, 0x11 ],
				[ 0x13F, 0xA5 ],
			])
			# Bank 1 for commands
			self._cart_write_flash([
				[ 0x2100, 0x01 ],
			])

			# Write setup
			self._cart_write_flash([
				[ 0x120, 0x0F ],
				[ 0x125, 0x55 ],
				[ 0x126, 0x55 ],
				[ 0x127, 0xAA ],
				[ 0x13F, 0xA5 ],
			])
			self._cart_write_flash([
				[ 0x120, 0x0F ],
				[ 0x125, 0x2A ],
				[ 0x126, 0xAA ],
				[ 0x127, 0x55 ],
				[ 0x13F, 0xA5 ],
			])
			self._cart_write_flash([
				[ 0x120, 0x0F ],
				[ 0x125, 0x55 ],
				[ 0x126, 0x55 ],
				[ 0x127, 0xA0 ],
				[ 0x13F, 0xA5 ],
			])

			# Set bank back
			self._cart_write_flash([
				[ 0x2100, bank ],
			])

			# Disable writes to MBC registers
			self._cart_write_flash([
				[ 0x120, 0x10 ],
				[ 0x13F, 0xA5 ],
			])

			# Undo Wakeup
			self._cart_write_flash([
				[ 0x120, 0x08 ],
				[ 0x13F, 0xA5 ],
			])

			self._write(self.DEVICE_CMD["DMG_MBC6_MMSA_WRITE_FLASH"])
			self._write(buffer[i*length:i*length+length])
			ret = self._read(1)
			if ret not in (0x01, 0x03):
				return False

			self._cart_write(address + length - 1, 0xFF)
			while True:
				sr = self._cart_read(address + length - 1)
				if sr & 0x80 == 0x80: break
				time.sleep(0.001)

			address += length
			if self.INFO["action"] == self.ACTIONS["ROM_WRITE"] and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":length})

		self._cart_write(address - 1, 0xF0)
		self.SKIPPING = skip_write

	def WriteROM_DMG_MBC5_32M_FLASH(self, address, buffer, bank):
		length = len(buffer)
		max_length = 128
		num = math.ceil(length / max_length)
		if length > max_length: length = max_length
		dprint("Writing 0x{:X} bytes to Flash ROM in {:d} iteration(s)".format(length, num))

		skip_write = False
		for i in range(0, num):
			self._set_fw_variable("TRANSFER_SIZE", length)
			self._set_fw_variable("ADDRESS", address)
			dprint("Now in iteration {:d}".format(i))

			if buffer[i*length:i*length+length] == bytearray([0xFF] * length):
				skip_write = True
				address += length
				continue

			self._cart_write(0x4000, 0xFF)
			self._cart_write_flash([
				[ address, 0xE0 ],
				[ address, length - 1 ],
				[ address, 0x00 ],
			])
			self._write(self.DEVICE_CMD["DMG_MBC6_MMSA_WRITE_FLASH"])
			self._write(buffer[i*length:i*length+length])
			ret = self._read(1)
			if ret not in (0x01, 0x03):
				self.CANCEL_ARGS.update({
					"info_type": "msgbox_critical",
					"info_msg": __(
						"Flash write error (response = {response}) in iteration {iteration} while trying to write {length} bytes",
						response=str(ret), iteration=i, length=length
					)
				})
				self.CANCEL = True
				self.ERROR = True
				return False

			self._cart_write_flash([
				[ address, 0x0C ],
				[ address, length - 1 ],
				[ address, 0x00 ],
			])
			lives = 100
			while lives > 0:
				self._cart_write(0x4000, 0x70)
				try:
					sr = self._cart_read(address + length - 1)
					dprint("sr=0x{:X}".format(sr))
				except:
					sr = 0
					dprint("sr=Error")
				if sr & 0x80 == 0x80: break
				lives -= 1
			self._cart_write(0x4000, 0xFF)

			if lives == 0:
				self.CANCEL_ARGS.update({
					"info_type": "msgbox_critical",
					"info_msg": __(
						"Flash write error (response = {response}) in iteration {iteration} while trying to write {length} bytes",
						response=str(sr), iteration=i, length=length
					)
				})
				self.CANCEL = True
				self.ERROR = True
				return False

			address += length
			if self.INFO["action"] == self.ACTIONS["ROM_WRITE"] and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":length})

		self._cart_write(address - 1, 0xFF)
		self.SKIPPING = skip_write

	def WriteROM_DMG_DatelOrbitV2(self, address, buffer, bank):
		length = len(buffer)
		dprint("Writing 0x{:X} bytes to Datel Orbit V2 cartridge".format(length))
		for i in range(0, length):
			self._cart_write(0x7FE1, 2)
			self._cart_write(0x5555, 0xAA)
			self._cart_write(0x2AAA, 0x55)
			self._cart_write(0x5555, 0xA0)
			self._cart_write(0x7FE1, bank)
			self._cart_write(address + i, buffer[i])
			if self.INFO["action"] == self.ACTIONS["ROM_WRITE"] and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":1})
		return True

	def WriteROM_DMG_EEPROM(self, address, buffer, bank, eeprom_buffer_size=0x80):
		length = len(buffer)
		if not self.CanPowerCycleCart() or self.BAUDRATE == 1000000:
			max_length = 256
		else:
			max_length = 1024
		num = math.ceil(length / max_length)
		if length > max_length: length = max_length
		dprint("Writing 0x{:X} bytes to EEPROM in {:d} iteration(s)".format(length, num))

		for i in range(0, num):
			self._set_fw_variable("BUFFER_SIZE", eeprom_buffer_size)
			self._set_fw_variable("TRANSFER_SIZE", length)
			self._set_fw_variable("ADDRESS", address)
			dprint("Now in iteration {:d}".format(i))

			self._write(self.DEVICE_CMD["DMG_EEPROM_WRITE"])
			self._write(buffer[i*length:i*length+length])
			ret = self._read(1)
			if ret not in (0x01, 0x03):
				self.CANCEL_ARGS.update({
					"info_type": "msgbox_critical",
					"info_msg": __(
						"EEPROM write error (response = {response}) in iteration {iteration} while trying to write {length} bytes",
						response=str(ret), iteration=i, length=length
					)
				})
				self.CANCEL = True
				self.ERROR = True
				return False

			address += length
			if self.INFO["action"] == self.ACTIONS["ROM_WRITE"] and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":length})

		commands = [
			[0x0006, 0x01],
			[0x5555, 0xAA],
			[0x2AAA, 0x55],
			[0x5555, 0xF0],
			[0x0006, bank]
		]
		for command in commands:
			self._cart_write(command[0], command[1])

	def CheckROMStable(self):
		if not self.IsConnected(): raise ConnectionError("Couldn’t access the the device.")
		if self.CanPowerCycleCart():
			self.CartPowerOn()

		buffer1 = self.ReadROM(0x80, 0x40)
		time.sleep(0.1)
		buffer2 = self.ReadROM(0x80, 0x40)
		return buffer1 == buffer2

	def CompareCRC32(self, buffer, offset, length, address, flashcart=None, max_length=0x20000, reset=False, mbc=None, bank=0):
		left = length
		chunk_pos = 0
		verified = False
		while left > 0:
			chunk_len = max_length if left > max_length else left
			chunk_from = offset + chunk_pos
			chunk_to = offset + chunk_pos + chunk_len
			dprint(f"Running CRC32 verification, comparing between source 0x{chunk_from:X}~0x{chunk_to:X} and target 0x{address+chunk_pos:X}~0x{address+chunk_pos+chunk_len:X}")
			crc32_expected = zlib.crc32(buffer[chunk_from:chunk_to])

			for i in range(0, 2 if (reset is True and flashcart is not None) else 1): # for retrying with reset
				if self.MODE == "DMG":
					self._set_fw_variable("ADDRESS", address + chunk_pos)
				elif self.MODE == "AGB":
					self._set_fw_variable("ADDRESS", (address + chunk_pos) >> 1)
				self._write(self.DEVICE_CMD["CALC_CRC32"])
				self._write(bytearray(struct.pack(">I", chunk_len)))
				temp = self._read(4)
				if temp is False:
					crc32_calculated = False
				else:
					crc32_calculated = struct.unpack(">I", temp)[0]
				if crc32_expected != crc32_calculated:
					if i == 0 and flashcart is not None:
						flashcart.Reset(full_reset=True)
						if mbc is not None:
							self._SelectROMBankForFlash(mbc, bank, flashcart)
						verified = (crc32_expected, crc32_calculated)
						continue
					else:
						return (crc32_expected, crc32_calculated)
				else:
					verified = True
					break

			left -= chunk_len
			chunk_pos += chunk_len

		return verified

	def DetectFlash(self, limitVoltage=False):
		supported_carts = list(self.SUPPORTED_CARTS[self.MODE].values())
		fc_fncptr = {
			"cart_write_fncptr":self._cart_write,
			"cart_write_fast_fncptr":self._cart_write_flash,
			"cart_read_fncptr":self.ReadROM,
			"cart_powercycle_fncptr":self.CartPowerCycleOrAskReconnect,
			"progress_fncptr":self.SetProgress,
			"set_we_pin_wr":self._set_we_pin_wr,
			"set_we_pin_audio":self._set_we_pin_audio,
		}

		detected_size = 0
		cfi = False
		cfi_buffer = bytearray()
		cfi_s = ""
		flash_type_id = 0
		flash_id_s = ""
		flash_types = []
		flash_id_methods = []

		if self.MODE == "DMG":
			if limitVoltage:
				self._write(self.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=self.FW["fw_ver"] >= 12)
			else:
				self._write(self.DEVICE_CMD["SET_VOLTAGE_5V"], wait=self.FW["fw_ver"] >= 12)
			self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)

		elif self.MODE == "AGB":
			read_method = self.AGB_READ_METHOD
			self.SetAGBReadMethod(0)
			self._write(self.DEVICE_CMD["SET_MODE_AGB"], wait=self.FW["fw_ver"] >= 12)

		else:
			raise NotImplementedError

		rom = self._cart_read(0, 8)

		dprint("Resetting and unlocking all cart types")
		cmds = []
		cmds_reset = []
		cmds_unlock_read = []

		for cart_type in sorted(supported_carts, key=lambda c: 'm29w640' not in c): # m29w640 first because of corruption risk
			f = supported_carts.index(cart_type)
			if "command_set" not in cart_type: continue
			if "manual_select" in cart_type and cart_type["manual_select"] is True: continue
			if "m29w640" in cart_type:
				self._cart_write_flash(cart_type["commands"]["reset"], flashcart=self.MODE=="AGB")
				rom1 = self._cart_read(0, 8)
				self._cart_write_flash(cart_type["commands"]["read_identifier"], flashcart=self.MODE=="AGB")
				rom2 = self._cart_read(0, 8)
				if rom1 != rom2 and list(rom2[:len(cart_type["flash_ids"][0])]) == cart_type["flash_ids"][0]:
					found = True
					flash_types.append(f)
					dprint("Found a M29W640 cartridge")
					self._cart_write_flash(cart_type["commands"]["reset"], flashcart=self.MODE=="AGB")
					break
				continue
			elif self.MODE == "DMG" and cart_type["command_set"] == "BLAZE_XPLODER":
				self._cart_read(0x102, 1)
				self._cart_write(6, 1)
				self._cart_write_flash(cart_type["commands"]["reset"])
				self._cart_write(6, 0)
				rom1 = self._cart_read(0x4000, 8)
				self._cart_write(6, 1)
				self._cart_write_flash(cart_type["commands"]["read_identifier"])
				rom2 = self._cart_read(0x4000, 8)
				if rom1 != rom2 and list(rom2[:len(cart_type["flash_ids"][0])]) == cart_type["flash_ids"][0]:
					found = True
					flash_types.append(f)
					dprint("Found a BLAZE Xploder GB")
					self._cart_write_flash(cart_type["commands"]["reset"])
					break
				continue
			elif self.MODE == "DMG" and cart_type["command_set"] == "DATEL_ORBITV2":
				rom1 = self._cart_read(cart_type["read_identifier_at"], 10)
				for cmd in cart_type["commands"]["unlock_read"]: self._cart_read(cmd[0], 1)
				self._cart_write_flash(cart_type["commands"]["unlock"])
				self._cart_write_flash(cart_type["commands"]["read_identifier"])
				rom2 = self._cart_read(cart_type["read_identifier_at"], 10)
				if rom1 != rom2 and list(rom2[:len(cart_type["flash_ids"][0])]) == cart_type["flash_ids"][0]:
					found = True
					flash_types.append(f)
					dprint("Found a GameShark or Action Replay")
					self._cart_write_flash(cart_type["commands"]["reset"])
					break
				continue
			elif self.MODE == "DMG" and cart_type["command_set"] == "GBMEMORY":
				rom1 = self._cart_read(0, 8)
				self._cart_write_flash(cart_type["commands"]["unlock"])
				self._cart_write_flash(cart_type["commands"]["read_identifier"])
				rom2 = self._cart_read(0, 8)
				if rom1 != rom2 and list(rom2[:len(cart_type["flash_ids"][0])]) == cart_type["flash_ids"][0]:
					found = True
					flash_types.append(f)
					dprint("Found a GB-Memory Cartridge")
					self._cart_write_flash(cart_type["commands"]["reset"])
					break
				continue
			elif self.MODE == "DMG" and "dmg-mbc5-32m-flash" in cart_type and self.SupportsAudioAsWe():
				uses_audio_high = isinstance(cart_type["flash_ids"][0][1], list) and cart_type.get("set_audio_high") is True and self.FW.get("fw_ver", 0) >= 14
				fncptr = copy.copy(fc_fncptr)
				fncptr["cart_write_fast_fncptr"] = lambda commands, **kwargs: self._cart_write_flash(commands)
				if uses_audio_high:
					self._set_we_pin_wr()
					self._set_fw_variable("DMG_AUDIO_ENABLED", 1)
				else:
					self._set_we_pin_audio()
				found = Flashcart(config=cart_type, fncptr=fncptr).VerifyFlashID()[0]
				if uses_audio_high: self._set_fw_variable("DMG_AUDIO_ENABLED", 0)
				if found:
					flash_types.append(f)
					dprint("Found a DMG development cartridge:", cart_type["names"][0])
					self._cart_write_flash(cart_type["commands"]["reset"])
					break
				# Reset commands if not found
				self._cart_write_flash([[0, 0xFF]], True)
				self._cart_write_flash([[0, 0xF0]], True)
				self._set_we_pin_wr()
				continue
			elif self.MODE == "AGB" and cart_type["command_set"] == "GBAMP":
				rom1 = self._cart_read(0x1E8F << 1, 2) + self._cart_read(0x168F << 1, 2)
				for cmd in cart_type["commands"]["unlock_read"]: self._cart_read(cmd[0] << 1)
				self._cart_write_flash(cart_type["commands"]["read_identifier"], flashcart=True)
				rom2 = self._cart_read(0x1E8F << 1, 2) + self._cart_read(0x168F << 1, 2)
				if rom1 != rom2 and list(rom2[:len(cart_type["flash_ids"][0])]) == cart_type["flash_ids"][0]:
					found = True
					flash_types.append(f)
					dprint("Found a GBA Movie Player v2")
					self._cart_write_flash(cart_type["commands"]["reset"], flashcart=True)
					break
				continue
			elif self.MODE == "DMG" and cart_type["command_set"] == "BUNG_16M" and self.SupportsAudioAsWe():
				self._set_we_pin_audio()
				rom1 = self._cart_read(0, 4)
				self._cart_write(0x2000, 0x02, flashcart=False)
				self._cart_write(0x6AAA, 0xAA, flashcart=True)
				self._cart_write(0x2000, 0x01, flashcart=False)
				self._cart_write(0x5554, 0x55, flashcart=True)
				self._cart_write(0x2000, 0x02, flashcart=False)
				self._cart_write(0x6AAA, 0x90, flashcart=True)
				rom2 = self._cart_read(0, 4)
				if rom1 != rom2 and list(rom2[:len(cart_type["flash_ids"][0])]) == cart_type["flash_ids"][0]:
					found = True
					flash_types.append(f)
					dprint("Found a BUNG Doctor GB Card 16M")
					self._cart_write(0x2000, 0x02, flashcart=False)
					self._cart_write(0x6AAA, 0xAA, flashcart=True)
					self._cart_write(0x2000, 0x01, flashcart=False)
					self._cart_write(0x5554, 0x55, flashcart=True)
					self._cart_write(0x2000, 0x02, flashcart=False)
					self._cart_write(0x6AAA, 0xF0, flashcart=True)
					self._cart_write(0x2000, 0x00, flashcart=False)
					break
				# Reset commands if not found
				self._cart_write_flash([[0, 0xFF]], True)
				self._cart_write_flash([[0, 0xF0]], True)
				self._set_we_pin_wr()
				continue

			if "commands" in cart_type:
				c = {
					"reset":[],
					"read_identifier":[],
					"read_cfi":[],
				}
				if "reset" in cart_type["commands"]:
					c["reset"] = cart_type["commands"]["reset"]
					if cart_type["commands"]["reset"] not in cmds_reset:
						cmds_reset.append(cart_type["commands"]["reset"])
				if "unlock_read" in cart_type["commands"]:
					if cart_type["commands"]["unlock_read"] not in cmds_unlock_read:
						cmds_unlock_read.append(cart_type["commands"]["unlock_read"])
				if "unlock" in cart_type["commands"]:
					if cart_type["commands"]["unlock"] not in cmds_reset:
						cmds_reset.append(cart_type["commands"]["unlock"])
					if cart_type["commands"]["reset"] not in cmds_reset:
						cmds_reset.append(cart_type["commands"]["reset"])
				if "read_identifier" in cart_type["commands"]:
					c["read_identifier"] = cart_type["commands"]["read_identifier"]
				if "read_cfi" in cart_type["commands"]:
					c["read_cfi"] = cart_type["commands"]["read_cfi"]
				if len(c["read_identifier"]) > 0:
					if self.MODE == "DMG" and cart_type["commands"]["read_identifier"][0][0] > 0x7000: continue
					if c not in cmds:
						found = False
						for t in cmds:
							if c["read_identifier"] == t["read_identifier"]:
								found = True
						if not found:
							cmds.append(c)

		for c in cmds_reset:
			for cmd in c:
				dprint(f"Resetting by writing to 0x{cmd[0]:X}=0x{cmd[1]:X}")
				self._cart_write(cmd[0], cmd[1], flashcart=True)

		flash_id_cmds = sorted(cmds, key=lambda x: x['read_identifier'][0][0])
		read_cfi_cmds = []

		rom_s = " ".join(format(x, '02X') for x in rom)
		if self.MODE == "DMG":
			flash_id_s = "[     ROM     ] " + rom_s + "\n"
			we_pins = [ "WR", "AUDIO" ]
		else:
			flash_id_s = "[    ROM    ] " + rom_s + "\n"
			we_pins = [ None ]

		if len(flash_types) == 0:
			dprint("Trying to find the Flash ID")
			if self.SupportsAudioAsWe():
				wes = {"DMG":[1, 2], "AGB":[0]}
			else:
				wes = {"DMG":[1], "AGB":[0]}
			for we in wes[self.MODE]:
				if self.MODE == "DMG":
					self._set_fw_variable("FLASH_WE_PIN", we)
				for i in range(0, len(flash_id_cmds)):
					self._cart_write_flash(flash_id_cmds[i]["reset"], flashcart=True)
					self._cart_write_flash(flash_id_cmds[i]["read_identifier"], flashcart=True)
					cmp = self._cart_read(0, 8)
					self._cart_write_flash(flash_id_cmds[i]["reset"], flashcart=True)

					if rom != cmp:  # ROM data changed
						flash_id_methods.append([we - 1, i, list(cmp), cfi_buffer, flash_id_cmds[i]["read_identifier"]])
						if self.MODE == "DMG":
							flash_id_s += "[{:s}/{:4X}/{:2X}] {:s}\n".format(we_pins[we-1].ljust(5), flash_id_cmds[i]["read_identifier"][0][0], flash_id_cmds[i]["read_identifier"][0][1], ' '.join(format(x, '02X') for x in cmp))
						else:
							flash_id_s += "[{:6X}/{:4X}] {:s}\n".format(flash_id_cmds[i]["read_identifier"][0][0], flash_id_cmds[i]["read_identifier"][0][1], ' '.join(format(x, '02X') for x in cmp))
						flash_id_cmds[i]["read_cfi"] = [ flash_id_cmds[i]["read_identifier"][0][0], 0x98 ]
						read_cfi_cmds.append(flash_id_cmds[i]["read_cfi"])

			dprint(f"Found {len(flash_id_methods):d} result(s)")
			self._cart_write_flash([[0, 0xFF]], True)
			self._cart_write_flash([[0, 0xF0]], True)

		for f in range(1, len(supported_carts)):
			cart_type = supported_carts[f]
			flashcart = Flashcart(config=cart_type, fncptr=fc_fncptr)
			if "flash_ids" not in cart_type or len(cart_type["flash_ids"]) == 0: continue
			if isinstance(cart_type["flash_ids"][0][1], list): continue
			if "commands" not in cart_type or len(cart_type["commands"]) == 0: continue
			found = False
			if flash_id_methods not in (None, []) and len(flash_id_methods) > 0:
				for we, type, flash_id, _, cmd_rfi in flash_id_methods:
					if (cmd_rfi != cart_type["commands"]["read_identifier"]): continue
					if self.MODE == "DMG" and "write_pin" in cart_type and cart_type["write_pin"] != we_pins[we]: continue
					fcm_flash_ids = list(map(list, {tuple(sublist) for sublist in cart_type["flash_ids"]}))
					for fcm_flash_id in fcm_flash_ids:
						if fcm_flash_id == flash_id[:len(fcm_flash_id)]:
							if self.MODE == "DMG":
								dprint("“{:s}” matches with Flash ID “{:s}” ({:s}/{:X}/{:X})".format(cart_type["names"][0], " ".join(format(x, '02X') for x in fcm_flash_id), we_pins[we], flash_id_cmds[type]["read_identifier"][0][0], flash_id_cmds[type]["read_identifier"][0][1]))
							elif self.MODE == "AGB":
								dprint("“{:s}” matches with Flash ID “{:s}” ({:X})/{:X}".format(cart_type["names"][0], " ".join(format(x, '02X') for x in fcm_flash_id), flash_id_cmds[type]["read_identifier"][0][0], flash_id_cmds[type]["read_identifier"][0][1]))
							found = True
							flash_type = f
							flash_types.append(flash_type)
							if "commands" in cart_type and "reset" in cart_type["commands"]:
								self._cart_write_flash(cart_type["commands"]["reset"], flashcart=True)
							break
					if found is True: break
			if found is False: continue

		dprint("Compatible flash types:", [(index, supported_carts[index]["names"][0]) for index in flash_types])

		try:
			if len(flash_types) > 0 and "read_cfi" in supported_carts[flash_types[0]]["commands"]:
				read_cfi_cmd = supported_carts[flash_types[0]]["commands"]["read_cfi"]
				reset_cmd = supported_carts[flash_types[0]]["commands"]["reset"]
			else:
				if len(read_cfi_cmds) == 0:
					read_cfi_cmd = [ [0, 0x98] ]
				else:
					read_cfi_cmd = [ read_cfi_cmds[0] ]
				reset_cmd = flash_id_cmds[0]["reset"]
			self._cart_write_flash(read_cfi_cmd, flashcart=(self.MODE == "AGB"))
			cfi_buffer = self._cart_read(0, 0x400)
			cfi_buffer_raw = bytearray(cfi_buffer)
			self._cart_write_flash(reset_cmd, flashcart=(self.MODE == "AGB"))

			if ".dev" in AppInfo.VERSION_PEP440 or AppContext.DEBUG:
				with open(AppContext.CONFIG_PATH + os.sep + "debug_cfi.bin", "wb") as f: f.write(cfi_buffer)

			found = False
			for o in ((0x20, 2), (0x10, 1)):
				magic = "{:s}{:s}{:s}".format(chr(cfi_buffer[o[0]]), chr(cfi_buffer[o[0] + (1 * o[1])]), chr(cfi_buffer[o[0] + (2 * o[1])]))
				dprint("CFI magic:", hex(o[0]), hex(o[0] + (1 * o[1])), hex(o[0] + (2 * o[1])), "=", str(magic))
				d_swap = (0, 0)
				if magic == "QRY": # D0D1 not swapped
					found = True
				elif magic == "RQZ": # D0D1 swapped
					d_swap = [(0, 1)]
					for j2 in range(0, len(d_swap)):
						for j in range(0, len(cfi_buffer)):
							cfi_buffer[j] = CFI.swap_bits(cfi_buffer[j], d_swap[j2])
					found = True
				elif magic == "\x92\x91\x9A": # D0D1+D6D7 swapped
					d_swap = [( 0, 1 ), ( 6, 7 )]
					for j2 in range(0, len(d_swap)):
						for j in range(0, len(cfi_buffer)):
							cfi_buffer[j] = CFI.swap_bits(cfi_buffer[j], d_swap[j2])
					if ".dev" in AppInfo.VERSION_PEP440 or AppContext.DEBUG:
						with open(AppContext.CONFIG_PATH + os.sep + "debug_cfi_d0d1+d6d7.bin", "wb") as f: f.write(cfi_buffer)
					found = True
				if found: break
			if found is False:
				cfi_buffer = None
		except:
			cfi_buffer = None

		if cfi_buffer is None or len(cfi_buffer) < 0x400:
			cfi = False
		else:
			cfi = CFI().Parse(cfi_buffer_raw)
			if cfi is not False:
				cfi_s = cfi["info"]

		# Check flash size
		if len(flash_types) > 0:
			flash_type_id = flash_types[0]
			flashcart = Flashcart(config=supported_carts[flash_type_id], fncptr=fc_fncptr)
			if self.MODE == "DMG":
				supp_flash_types = self.GetSupportedCartridgesDMG()
			elif self.MODE == "AGB":
				supp_flash_types = self.GetSupportedCartridgesAGB()
			else:
				raise NotImplementedError

			if "flash_size" in supp_flash_types[1][flash_types[0]]:
				size = supp_flash_types[1][flash_types[0]]["flash_size"]
				size_undetected = False
				for i in range(0, len(flash_types)):
					if "flash_size" in supp_flash_types[1][flash_types[i]]:
						if size != supp_flash_types[1][flash_types[i]]["flash_size"]:
							size_undetected = True

				if size_undetected:
					if "flash_bank_select_type" in supp_flash_types[1][flash_types[0]] and supp_flash_types[1][flash_types[0]]["flash_bank_select_type"] == 1:
						# Check where the ROM data repeats (by bank switching)
						flashcart.SelectBankROM(0)
						size_check = self.ReadROM(0, 0x1000) + self.ReadROM(0x1FFF000, 0x1000)
						num_banks = 1
						while num_banks < (flashcart.GetFlashSize() // 0x2000000) + 1:
							dprint("Checking bank {:d}".format(num_banks))
							flashcart.SelectBankROM(num_banks)
							buffer = self.ReadROM(0, 0x1000) + self.ReadROM(0x1FFF000, 0x1000)
							if buffer == size_check: break
							num_banks <<= 1
						detected_size = 0x2000000 * num_banks
						for i in range(0, len(flash_types)):
							if detected_size == supp_flash_types[1][flash_types[i]]["flash_size"]:
								dprint("Detected {:d} flash banks".format(num_banks))
								flash_type_id = flash_types[i]
								size_undetected = False
								break
						flashcart.SelectBankROM(0)

					elif isinstance(cfi, dict) and "device_size" in cfi:
						for i in range(0, len(flash_types)):
							if "flash_size" in supp_flash_types[1][flash_types[i]] and cfi['device_size'] == supp_flash_types[1][flash_types[i]]["flash_size"]:
								flash_type_id = flash_types[i]
								size_undetected = False
								break
					else:
						if self.MODE == "AGB":
							# Check where the ROM data repeats (for unlicensed carts)
							header = self.ReadROM(0, 0x180)
							size_check = header[0xA0:0xA0+16]
							currAddr = 0x10000
							while currAddr < 0x2000000:
								buffer = self.ReadROM(currAddr + 0xA0, 64)[:16]
								if buffer == size_check: break
								currAddr *= 2
							rom_size = currAddr

							for i in range(0, len(flash_types)):
								if "flash_size" in supp_flash_types[1][flash_types[i]] and rom_size == supp_flash_types[1][flash_types[i]]["flash_size"]:
									flash_type_id = flash_types[i]
									size_undetected = False
									break

		if self.MODE == "DMG":
			self._write(self.DEVICE_CMD["SET_VOLTAGE_5V"], wait=self.FW["fw_ver"] >= 12)
			self._set_fw_variable("FLASH_WE_PIN", 1) # back to WE=WR
			# time.sleep(0.1) # TODO: Move necessary delays to firmware
		elif self.MODE == "AGB":
			self.SetAGBReadMethod(read_method)

		return (flash_types, flash_type_id, flash_id_s, cfi_s, cfi, detected_size)

	@staticmethod
	def _find_repeating_size(data, max_size, min_size=0x20):
		offset = max_size
		while offset >= min_size:
			offset = int(offset / 2)
			if data[0:offset] != data[offset:offset * 2]:
				offset = offset * 2
				break
		return offset

	def GetDumpReport(self):
		from .DumpReport import DumpReport
		return DumpReport.generate(self.INFO["dump_info"], self)

	def GetReadErrors(self):
		return self.READ_ERRORS

	#################################################################

	def DoTransfer(self, mode, fncSetProgress, args):
		from . import DataTransfer
		args['mode'] = mode
		args['port'] = self
		if self.WORKER is None:
			self.WORKER = DataTransfer.DataTransfer(args)
			if fncSetProgress not in (False, None):
				self.WORKER.updateProgress.connect(fncSetProgress)
		else:
			self.WORKER.setConfig(args)
		self.WORKER.start()

	def BackupROM(self, fncSetProgress=None, args=None):
		self.DoTransfer(1, fncSetProgress, args)

	def BackupRAM(self, fncSetProgress=None, args=None):
		if fncSetProgress is False:
			args['mode'] = 2
			args['port'] = self
			self._BackupRestoreRAM(args=args)
		else:
			self.DoTransfer(2, fncSetProgress, args)

	def RestoreRAM(self, fncSetProgress=None, args=None):
		self.DoTransfer(3, fncSetProgress, args)

	def FlashROM(self, fncSetProgress=None, args=None):
		self.DoTransfer(4, fncSetProgress, args)

	def DetectCartridge(self, fncSetProgress=None, args=None):
		self.DoTransfer(5, fncSetProgress, args)

	#################################################################

	def _BackupROM(self, args):
		self._thread_worker_auto_poweroff_start()
		try:
			return self._BackupROM_Worker(args)
		finally:
			self._thread_worker_auto_poweroff_finish()

	def _BackupROM_Worker(self, args):
		file = None
		if len(args["path"]) > 0:
			file = open(args["path"], "wb")

		self.FAST_READ = True
		agb_read_method = self.AGB_READ_METHOD
		dmg_read_method = self.DMG_READ_METHOD
		flashcart = False
		supported_carts = list(self.SUPPORTED_CARTS[self.MODE].values())
		cart_type = copy.deepcopy(supported_carts[args["cart_type"]])
		if not isinstance(cart_type, str):
			cart_type["_index"] = 0
			for i in range(0, len(list(self.SUPPORTED_CARTS[self.MODE].keys()))):
				if i == args["cart_type"]:
					try:
						cart_type["_index"] = cart_type["names"].index(list(self.SUPPORTED_CARTS[self.MODE].keys())[i])

						fc_fncptr = {
							"cart_write_fncptr":self._cart_write,
							"cart_write_fast_fncptr":self._cart_write_flash,
							"cart_read_fncptr":self.ReadROM,
							"cart_powercycle_fncptr":self.CartPowerCycleOrAskReconnect,
							"progress_fncptr":self.SetProgress,
							"set_we_pin_wr":self._set_we_pin_wr,
							"set_we_pin_audio":self._set_we_pin_audio,
						}
						flashcart = Flashcart(config=cart_type, fncptr=fc_fncptr)
					except:
						pass

		# Firmware check L8
		if self.FW["fw_ver"] < 8 and flashcart and "enable_pullups" in cart_type:
			print(ANSI.YELLOW + __("Note: This flashcart profile may not be fully compatible with your {device_name} running an old or legacy firmware version.", device_name=self.GetName()) + ANSI.RESET)
			del(cart_type["enable_pullups"])
		# Firmware check L8

		buffer_len = 0x4000

		self.INFO["dump_info"]["timestamp"] = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
		self.INFO["dump_info"]["file_name"] = args["path"]
		self.INFO["dump_info"]["file_size"] = args["rom_size"]
		self.INFO["dump_info"]["cart_type"] = args["cart_type"]
		self.INFO["dump_info"]["system"] = self.MODE

		is_3dmemory = (self.MODE == "AGB" and "command_set" in cart_type and cart_type["command_set"] == "3DMEMORY")

		if self.MODE == "DMG":
			self.INFO["dump_info"]["rom_size"] = args["rom_size"]
			self.INFO["dump_info"]["mapper_type"] = args["mbc"]
			self.INFO["dump_info"]["dmg_read_method"] = self.DMG_READ_METHODS[self.DMG_READ_METHOD]

			self.INFO["mapper_raw"] = args["mbc"]
			if not self.IsSupportedMbc(args["mbc"]):
				msg = __("This cartridge uses a mapper that is not supported by FlashGBX using your {device_name}.", device_name=self.GetFullName())
				self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":msg, "abortable":False})
				return False

			if "verify_mbc" in args and args["verify_mbc"] is not None:
				_mbc = args["verify_mbc"]
			else:
				_mbc = DMG_Mapper().GetInstance(args=args, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
			
			if self._get_fw_variable("CART_MODE") != 1:
				self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)

			self._set_fw_variable("DMG_WRITE_CS_PULSE", 0)
			self._set_fw_variable("DMG_READ_CS_PULSE", 0)
			if _mbc.GetName() == "TAMA5":
				self._set_fw_variable("DMG_WRITE_CS_PULSE", 1)
				self._set_fw_variable("DMG_READ_CS_PULSE", 1)
				_mbc.EnableMapper()
				self._set_fw_variable("DMG_READ_CS_PULSE", 0)
			elif _mbc.GetName() == "Sachen":
				start_bank = int(args["rom_size"] / 0x4000)
				_mbc.SetStartBank(start_bank)
			else:
				_mbc.EnableMapper()

			rom_size = args["rom_size"]
			rom_banks = _mbc.GetROMBanks(rom_size)
			rom_bank_size = _mbc.GetROMBankSize()
			size = _mbc.GetROMSize()

		elif self.MODE == "AGB":
			self.INFO["dump_info"]["mapper_type"] = None
			if self._get_fw_variable("CART_MODE") != 2:
				self._write(self.DEVICE_CMD["SET_MODE_AGB"], wait=self.FW["fw_ver"] >= 12)
				self.ReadROM(0, 4) # dummy read

			buffer_len = 0x10000
			size = 32 * 1024 * 1024
			if "agb_rom_size" in args: size = args["agb_rom_size"]
			self.INFO["dump_info"]["rom_size"] = size
			if is_3dmemory:
				self.INFO["dump_info"]["agb_read_method"] = "3D Memory"

			elif flashcart and "command_set" in cart_type and cart_type["command_set"] == "GBAMP":
				self.INFO["dump_info"]["agb_read_method"] = "GBA Movie Player"
				if not "verify_write" in args: self.CartPowerCycleOrAskReconnect()
				flashcart.Unlock()
				buffer_len = 0x4000

			# Initialize Vast Fame ROM (if it was not autodetected) and determine SRAM address/value bit reordering (necessary for emulation)
			elif flashcart and "command_set" in cart_type and cart_type["command_set"] == "VASTFAME":
				addr_reorder = [[-1 for i in range(16)] for j in range(4)]
				value_reorder = [[-1 for i in range(8)] for j in range(4)]
				for mode in range(0, 16):
					# Set SRAM mode
					self._cart_write(0xFFF8, 0x99, sram=True)
					self._cart_write(0xFFF9, 0x02, sram=True)
					self._cart_write(0xFFFA, 0x05, sram=True)
					self._cart_write(0xFFFB, 0x02, sram=True)
					self._cart_write(0xFFFC, 0x03, sram=True)

					self._cart_write(0xFFFD, 0x00, sram=True)
					self._cart_write(0xFFFE, mode, sram=True)

					self._cart_write(0xFFF8, 0x99, sram=True)
					self._cart_write(0xFFF9, 0x03, sram=True)
					self._cart_write(0xFFFA, 0x62, sram=True)
					self._cart_write(0xFFFB, 0x02, sram=True)
					self._cart_write(0xFFFC, 0x56, sram=True)

					# Blank SRAM
					for i in range(0, 16):
						self._cart_write(1 << i, 0, sram=True)
					self._cart_write(0x8000, 0, sram=True)

					# Get address reordering for SRAM writes (repeats every 4 modes so only check first 4)
					if mode < 4:
						for i in range(0, 16):
							self._cart_write(1 << i, 0xAA, sram=True)
							for j in range(0, 16):
								value = self._cart_read(1 << j, 1, True)[0]
								if value != 0:
									addr_reorder[mode][j] = i
									break
							self._cart_write(1 << i, 0, sram=True) # reblank SRAM
						addr_reorder[mode].reverse()

					# Get value reordering for SRAM writes/reads (assumes upper bit of address is never reordered)
					if mode % 4 == 0:
						for i in range(0, 8):
							self._cart_write(0x8000, 1 << i, sram=True)
							value = self._cart_read(0x8000, 1, True)[0]
							for j in range(0, 8):
								if (1 << j) == value:
									value_reorder[mode // 4][j] = i
									break
						value_reorder[mode // 4].reverse()

				self.INFO["dump_info"]["vf_addr_reorder"] = addr_reorder
				self.INFO["dump_info"]["vf_value_reorder"] = value_reorder
				self.INFO["dump_info"]["agb_read_method"] = self.AGB_READ_METHODS[self.AGB_READ_METHOD]

			else:
				self.INFO["dump_info"]["agb_read_method"] = self.AGB_READ_METHODS[self.AGB_READ_METHOD]

			if flashcart and "flash_bank_size" in cart_type:
				if "verify_write" in args:
					rom_banks = math.ceil(len(args["verify_write"]) / cart_type["flash_bank_size"])
				else:
					rom_banks = math.ceil(size / cart_type["flash_bank_size"])
				rom_bank_size = cart_type["flash_bank_size"]
			else:
				rom_banks = 1
				rom_bank_size = 0x2000000

		if self.ERROR: return

		if "verify_write" in args:
			size = len(args["verify_write"])
			buffer_len = min(buffer_len, size)
		else:
			if "bl_offset" in args:
				method = "SAVE_READ"
			else:
				method = "ROM_READ"
			pos = 0
			self.SetProgress({"action":"INITIALIZE", "method":method, "size":size})
			self.INFO["action"] = self.ACTIONS[method]
			if self.FW["fw_ver"] >= 8:
				if flashcart and "enable_pullups" in cart_type:
					self._write(self.DEVICE_CMD["ENABLE_PULLUPS"], wait=True)
					self.SetAGBReadMethod(0)
					dprint("Pullups enabled")
					if (self.FW["pcb_name"] == "GBFlash" and self.FW["pcb_ver"] < 13) or (self.FW["pcb_name"] == "Joey Jr"):
						print(ANSI.YELLOW + __("Note: This cartridge may not be fully compatible with your {device_name}.", device_name=self.FW["pcb_name"]) + ANSI.RESET)
				else:
					self._write(self.DEVICE_CMD["DISABLE_PULLUPS"], wait=True)
					dprint("Pullups disabled")

			if self.FW["fw_ver"] >= 12:
				if self.MODE == "DMG":
					# Joey Jr bug workaround
					enable_pullup_wr = 2 if (("enable_pullup_wr" in cart_type and cart_type["enable_pullup_wr"] is True) or ("force_wr_pullup" in args and args["force_wr_pullup"] is True)) else 0
					self._set_fw_variable("PULLUPS_ENABLED", enable_pullup_wr)

		buffer = bytearray(size)
		max_length = self.MAX_BUFFER_READ
		dprint("Max buffer size: 0x{:X}".format(max_length))
		if is_3dmemory:
			max_length = min(max_length, 0x1000)
		else:
			max_length = min(max_length, 0x2000)
		self.INFO["dump_info"]["transfer_size"] = max_length
		pos_total = 0
		start_address = 0
		end_address = size
		# dprint("ROM banks:", rom_banks)

		start_bank = 0
		if "verify_write" in args:
			buffer_pos = args["verify_from"]
			start_address = buffer_pos
			end_address = args["verify_from"] + args["verify_len"]
			start_bank = math.floor(buffer_pos / rom_bank_size)
			end_bank = math.ceil((buffer_pos + args["verify_len"]) / rom_bank_size)
			rom_banks = end_bank
		elif "bl_offset" in args:
			if "bl_layout" in args and args["bl_layout"] in (1, 2):
				args["bl_size"] <<= 1
			buffer_pos = args["bl_offset"]
			start_address = buffer_pos
			end_address = args["bl_offset"] + args["bl_size"]
			start_bank = math.floor(buffer_pos / rom_bank_size)
			end_bank = math.ceil((buffer_pos + args["bl_size"]) / rom_bank_size)
			rom_banks = end_bank

		dprint("start_address=0x{:X}, end_address=0x{:X}, start_bank=0x{:X}, rom_banks=0x{:X}, buffer_len=0x{:X}, max_length=0x{:X}".format(start_address, end_address, start_bank, rom_banks, buffer_len, max_length))
		bank = start_bank
		while bank < rom_banks:
			# ↓↓↓ Switch ROM bank
			if self.MODE == "DMG":
				if _mbc.ResetBeforeBankChange(bank) is True:
					dprint("Resetting the MBC")
					self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
				(start_address, bank_size) = _mbc.SelectBankROM(bank)
				end_address = start_address + bank_size
				buffer_len = min(buffer_len, _mbc.GetROMBankSize())
				if "verify_write" in args:
					buffer_len = min(buffer_len, bank_size, len(args["verify_write"]))
					end_address = start_address + bank_size
					start_address += (buffer_pos % rom_bank_size)
					if end_address > start_address + args["verify_len"]:
						end_address = start_address + args["verify_len"]
			elif self.MODE == "AGB":
				if "verify_write" in args:
					buffer_len = min(buffer_len, len(args["verify_write"]))
				if "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] > 0:
					flashcart.SelectBankROM(bank)
					temp = end_address - start_address
					start_address %= cart_type["flash_bank_size"]
					end_address = min(cart_type["flash_bank_size"], start_address + temp)
			# ↑↑↑ Switch ROM bank

			skip_init = False
			pos = start_address
			lives = 20

			while pos < end_address:
				temp = bytearray()
				read_len = self._get_backup_read_length(pos, end_address, buffer_len)
				if self.CANCEL:
					cancel_args = {"action":"ABORT", "abortable":False}
					cancel_args.update(self.CANCEL_ARGS)
					self.CANCEL_ARGS = {}
					self.ERROR_ARGS = {}
					self.SetProgress(cancel_args)
					try:
						if file is not None: file.close()
					except:
						pass
					if self.CanPowerCycleCart(): self.CartPowerCycle()
					return

				if is_3dmemory:
					temp = self.ReadROM_3DMemory(address=pos, length=read_len, max_length=max_length)
				elif flashcart and cart_type["command_set"] == "GBAMP":
					temp = self.ReadROM_GBAMP(address=pos, length=read_len, max_length=max_length)
				else:
					if self.FW["fw_ver"] >= 10 and "verify_write" in args:
						if self.MODE == "AGB": self.SetAGBReadMethod(0)
						if self.MODE == "DMG": self.SetDMGReadMethod(2)
						temp = self.ReadROM(address=pos, length=read_len, skip_init=skip_init, max_length=max_length)
						if self.MODE == "AGB": self.SetAGBReadMethod(agb_read_method)
						if self.MODE == "DMG": self.SetDMGReadMethod(dmg_read_method)
					else:
						# Normal read
						temp = self.ReadROM(address=pos, length=read_len, skip_init=skip_init, max_length=max_length)
					skip_init = True

				if len(temp) != read_len:
					pos_temp = pos_total
					if "verify_write" in args:
						pos_temp += args["verify_base_pos"]
						self.SetProgress({"action":"UPDATE_POS", "pos":args["verify_from"]+pos_total})
					else:
						self.SetProgress({"action":"UPDATE_POS", "pos":pos_total})

					err_text = ANSI.YELLOW + __("Note: Incomplete transfer detected. Resuming from {address}...", address="0x{:X}".format(pos_temp)) + ANSI.RESET
					if (max_length >> 1) < 64:
						dprint("Failed to receive 0x{:X} bytes from the device at position 0x{:X}.".format(read_len, pos_temp))
						max_length = 64
					elif lives >= 20 and pos_temp != 0:
						dprint("Failed to receive 0x{:X} bytes from the device at position 0x{:X}.".format(read_len, pos_temp))
					else:
						dprint("Failed to receive 0x{:X} bytes from the device at position 0x{:X}. Decreasing maximum transfer buffer size to 0x{:X}.".format(read_len, pos_temp, max_length >> 1))
						max_length >>= 1
						self.MAX_BUFFER_READ = max_length
						err_text += "\n" + __("Buffer size adjusted to {size} bytes.", size=max_length)
					if ".dev" in AppInfo.VERSION_PEP440 and not AppContext.DEBUG: print(err_text)

					self.INFO["dump_info"]["transfer_size"] = max_length
					skip_init = False
					self.DEVICE.reset_input_buffer()
					self.DEVICE.reset_output_buffer()
					lives -= 1
					if lives == 0:
						self.CANCEL_ARGS.update({
							"info_type": "msgbox_critical",
							"info_msg": __(
								"An error occured while reading from the cartridge. When connecting the device, avoid passive USB hubs and try different USB ports/cables."
							)
						})
						self.CANCEL = True
						self.ERROR = True
						if "verify_write" in args: return False
					continue
				elif lives < 20:
					lives = 20

				if file is not None:
					if "bl_layout" in args and args["bl_layout"] == 1:
						file.write(temp[0x0000:0x2000])
					elif "bl_layout" in args and args["bl_layout"] == 2:
						file.write(temp[0x2000:0x4000])
					else:
						file.write(temp)
				buffer[pos_total:pos_total+len(temp)] = temp
				pos_total += len(temp)

				if "verify_write" in args:
					check = args["verify_write"][pos_total-len(temp):pos_total]
					if temp[:len(check)] != check:
						if ".dev" in AppInfo.VERSION_PEP440 or AppContext.DEBUG:
							dprint("Writing 0x{:X} bytes to debug_verify_0x{:X}.bin".format(len(temp), pos_total-len(temp)))
							with open(AppContext.CONFIG_PATH + os.sep + "debug_verify_0x{:X}.bin".format(pos_total-len(temp)), "ab") as f: f.write(temp)

						for i in range(0, pos_total):
							if (i < len(args["verify_write"]) - 1) and (i < pos_total - 1) and args["verify_write"][i] != buffer[i]:
								if args["rtc_area"] is True and i in (0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9):
									dprint("Skipping RTC area at 0x{:X}".format(i))
								else:
									dprint("Mismatch during verification at 0x{:X}".format(i))
									return i
					else:
						dprint("Verification successful between 0x{:X} and 0x{:X}".format(pos_total-len(temp), pos_total))
					self.SetProgress({"action":"UPDATE_POS", "pos":args["verify_from"]+pos_total})
				else:
					self.SetProgress({"action":"UPDATE_POS", "pos":pos_total})

				pos += read_len

			bank += 1

		if "verify_write" in args:
			return min(pos_total, len(args["verify_write"]))

		if not "bl_offset" in args:
			# Hidden sector (GB-Memory)
			if self.MODE == "DMG" and len(args["path"]) > 0 and _mbc.HasHiddenSector():
				temp = _mbc.ReadHiddenSector()
				if temp is False:
					msg = __("An error occured while trying to read the hidden sector data of the {gb_memory_cartridge}.", gb_memory_cartridge="NP GB-Memory Cartridge")
					print(ANSI.RED + msg + ANSI.RESET)
					self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":msg, "abortable":False})
					self.CANCEL = True
					self.ERROR = True
					if file is not None: file.close()
					return False
				else:
					if file is not None: file.close()
					file = open(os.path.splitext(args["path"])[0] + ".map", "wb")
					self.INFO["hidden_sector"] = temp
					self.INFO["dump_info"]["gbmem"] = temp
					gbmem_parsed = (GBMemoryMap()).ParseMapData(buffer_map=temp, buffer_rom=buffer)
					if gbmem_parsed:
						self.INFO["dump_info"]["gbmem_parsed"] = gbmem_parsed
					file.write(temp)
					file.close()
					gbmp = self.INFO["dump_info"]["gbmem_parsed"]
					if (isinstance(gbmp, list)) and len(args["path"]) > 2:
						for i in range(1, len(gbmp)):
							if gbmp[i]["header"] == {} or gbmp[i]["header"]["logo_correct"] is False: continue
							settings = None
							if "settings" in args: settings = args["settings"]
							gbmp_n = generate_filename(mode="DMG", header=gbmp[i]["header"], settings=settings)
							gbmp_p = "{:s} - {:s}".format(os.path.splitext(args["path"])[0], gbmp_n)
							with open(gbmp_p, "wb") as f:
								f.write(buffer[gbmp[i]["rom_offset"]:gbmp[i]["rom_offset"]+gbmp[i]["rom_size"]])
			else:
				if "hidden_sector" in self.INFO: del(self.INFO["hidden_sector"])
				if "gbmem" in self.INFO["dump_info"]: del(self.INFO["dump_info"]["gbmem"])
				if "gbmem_parsed" in self.INFO["dump_info"]: del(self.INFO["dump_info"]["gbmem_parsed"])

			# Check for ROM loops
			self.INFO["loop_detected"] = False
			temp = len(buffer)
			while temp > 0x4000:
				temp = temp >> 1
				if (buffer[0:0x4000] == buffer[temp:temp+0x4000]):
					if buffer[0:temp] == buffer[temp:temp*2]:
						self.INFO["loop_detected"] = temp
				else:
					break

			# Calculate Global Checksums and Hashes
			self.SetProgress({"action":"CALC_CHECKSUMS"})
			if "header" not in self.INFO["dump_info"]: self.INFO["dump_info"]["header"] = {}
			if self.MODE == "DMG":
				if _mbc.GetName() == "MMM01":
					self.INFO["dump_info"]["header"].update(RomFileDMG(buffer[-0x8000:-0x8000+0x180]).GetHeader(unchanged=True))
				elif _mbc.GetName() in ("Sachen", "Xploder GB", "Datel Orbit V2"):
					pass
				else:
					self.INFO["dump_info"]["header"].update(RomFileDMG(buffer[:0x180]).GetHeader(unchanged=True))
				#chk = _mbc.CalcChecksum(buffer)
				self.SetProgress({"action":"CALC_CHECKSUMS", "type":__("ROM checksum")})
				self.INFO["rom_checksum_calc"] = _mbc.CalcChecksum(buffer)
			elif self.MODE == "AGB":
				self.INFO["dump_info"]["header"].update(RomFileAGB(buffer[:0x180]).GetHeader())

				temp_ver = "N/A"
				try:
					ids = [ b"SRAM_", b"EEPROM_V", b"FLASH_V", b"FLASH512_V", b"FLASH1M_V", b"AGB_8MDACS_DL_V" ]
					for id in ids:
						temp_pos = buffer.find(id)
						if temp_pos > 0:
							temp_ver = buffer[temp_pos:temp_pos+0x20]
							temp_ver = temp_ver[:temp_ver.index(0x00)].decode("ascii", "replace")
							break
				except ValueError:
					temp_ver = "N/A"
				self.INFO["dump_info"]["agb_savelib"] = temp_ver
				self.INFO["dump_info"]["agb_save_flash_id"] = None
				if "FLASH" in temp_ver:
					try:
						agb_save_flash_id = self.ReadFlashSaveID()
						if agb_save_flash_id is not False and len(agb_save_flash_id) == 2:
							self.INFO["dump_info"]["agb_save_flash_id"] = agb_save_flash_id
					except:
						print(__("Error querying the flash save chip."))
						self.DEVICE.reset_input_buffer()
						self.DEVICE.reset_output_buffer()

				if "eeprom_data" in self.INFO["dump_info"]: del(self.INFO["dump_info"]["eeprom_data"])
				if "EEPROM" in temp_ver and len(buffer) == 0x2000000:
					padding_byte = buffer[0x1FFFEFF]
					dprint("Replacing unmapped ROM data of cartridge (32 MiB ROM + EEPROM save type) with the original padding byte of 0x{:02X}.".format(padding_byte))
					self.INFO["dump_info"]["eeprom_data"] = buffer[0x1FFFF00:0x2000000]
					buffer[0x1FFFF00:0x2000000] = bytearray([padding_byte] * 0x100)
					file.seek(0x1FFFF00)
					file.write(buffer[0x1FFFF00:0x2000000])

			self.SetProgress({"action":"CALC_CHECKSUMS", "type":__("MD5 hash")})
			self.INFO["file_md5"] = hashlib.md5(buffer).hexdigest()
			self.SetProgress({"action":"CALC_CHECKSUMS", "type":__("SHA-1 hash")})
			self.INFO["file_sha1"] = hashlib.sha1(buffer).hexdigest()
			self.SetProgress({"action":"CALC_CHECKSUMS", "type":__("SHA-256 hash")})
			self.INFO["file_sha256"] = hashlib.sha256(buffer).hexdigest()
			self.SetProgress({"action":"CALC_CHECKSUMS", "type":__("CRC32 checksum")})
			self.INFO["file_crc32"] = zlib.crc32(buffer) & 0xFFFFFFFF
			self.INFO["dump_info"]["hash_md5"] = self.INFO["file_md5"]
			self.INFO["dump_info"]["hash_sha1"] = self.INFO["file_sha1"]
			self.INFO["dump_info"]["hash_sha256"] = self.INFO["file_sha256"]
			self.INFO["dump_info"]["hash_crc32"] = self.INFO["file_crc32"]

		if file is not None: file.close()

		# ↓↓↓ Switch to first ROM bank
		if self.MODE == "DMG":
			if _mbc.ResetBeforeBankChange(0) is True:
				dprint("Resetting the MBC")
				self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
			_mbc.SelectBankROM(0)
			self.SetDMGReadMethod(dmg_read_method)
		elif self.MODE == "AGB":
			if "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] > 0:
				flashcart.SelectBankROM(0)
			self.SetAGBReadMethod(agb_read_method)
		# ↑↑↑ Switch to first ROM bank

		# Clean up
		self.INFO["last_action"] = self.INFO["action"]
		self.INFO["action"] = None
		self.INFO["last_path"] = args["path"]
		self._thread_worker_auto_poweroff_finish()
		self.SetProgress({"action":"FINISHED"})
		return True

	def WriteRTC(self, args):
		if self.CanPowerCycleCart():
			self.CartPowerOn()

		if self.MODE == "DMG":
			_mbc = DMG_Mapper().GetInstance(args=args, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
			if not _mbc.HasRTC(): return False
			ret = _mbc.WriteRTCDict(args["rtc_dict"])
		elif self.MODE == "AGB":
			_agb_gpio = AGB_GPIO(args={"rtc":True}, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
			if _agb_gpio.HasRTC() is not True: return False
			ret = _agb_gpio.WriteRTCDict(args["rtc_dict"])
		else:
			raise NotImplementedError
		return ret

	def _BackupRestoreRAM(self, args):
		self._thread_worker_auto_poweroff_start()
		try:
			return self._BackupRestoreRAM_Worker(args)
		finally:
			self._thread_worker_auto_poweroff_finish()

	def _BackupRestoreRAM_Worker(self, args):
		self.FAST_READ = False
		if "rtc" not in args: args["rtc"] = False

		# Prepare some stuff
		command = None
		empty_data_byte = 0x00
		extra_size = 0
		audio_low = False

		# Initialization
		ram_banks = 0
		buffer_len = 0
		sram_5 = 0
		temp = None

		cart_type = None
		if "cart_type" in args and args["cart_type"] and args["cart_type"] >= 0:
			supported_carts = list(self.SUPPORTED_CARTS[self.MODE].values())
			cart_type = copy.deepcopy(supported_carts[args["cart_type"]])

			if self.FW["fw_ver"] >= 12:
				if self.MODE == "DMG":
					# Joey Jr bug workaround
					enable_pullup_wr = 2 if (("enable_pullup_wr" in cart_type and cart_type["enable_pullup_wr"] is True) or ("force_wr_pullup" in args and args["force_wr_pullup"] is True)) else 0
					self._set_fw_variable("PULLUPS_ENABLED", enable_pullup_wr)

		self._set_fw_variable("STATUS_REGISTER_MASK", 0x80)
		self._set_fw_variable("STATUS_REGISTER_VALUE", 0x80)

		if self.MODE == "DMG":
			self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True) # fixes Taobao FRAM cart save data
			_mbc = DMG_Mapper().GetInstance(args=args, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
			if not self.IsSupportedMbc(args["mbc"]):
				msg = __("This cartridge uses a mapper that is not supported by FlashGBX using your {device_name}.", device_name=self.GetFullName())
				self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":msg, "abortable":False})
				return False
			if "save_size" in args:
				save_size = args["save_size"]
			else:
				save_size = DmgSaveTypes(mbc=args["save_type"]).GetSize()

			ram_banks = _mbc.GetRAMBanks(save_size)

			buffer_len = min(0x200, _mbc.GetRAMBankSize())
			self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)
			self._set_fw_variable("DMG_WRITE_CS_PULSE", 0)
			self._set_fw_variable("DMG_READ_CS_PULSE", 0)

			# Enable mappers
			if _mbc.GetName() == "TAMA5":
				self._set_fw_variable("DMG_WRITE_CS_PULSE", 1)
				self._set_fw_variable("DMG_READ_CS_PULSE", 1)
				_mbc.EnableMapper()
				self._set_fw_variable("DMG_READ_CS_PULSE", 0)
				buffer_len = 0x20
			elif _mbc.GetName() == "MBC7":
				buffer_len = save_size
			elif _mbc.GetName() == "MBC6":
				empty_data_byte = 0xFF
				audio_low = True
				self._set_fw_variable("FLASH_METHOD", 0x04) # FLASH_METHOD_DMG_MBC6
				self._set_fw_variable("FLASH_WE_PIN", 0x01) # WR
				_mbc.EnableFlash(enable=True, enable_write=True if (args["mode"] == 3) else False)
			elif _mbc.GetName() == "Xploder GB":
				empty_data_byte = 0xFF
				self._set_fw_variable("FLASH_PULSE_RESET", 0)
				self._set_fw_variable("FLASH_DOUBLE_DIE", 0)
				self._write(self.DEVICE_CMD["SET_FLASH_CMD"])
				self._write(0x00) # FLASH_COMMAND_SET_NONE
				self._write(0x01) # FLASH_METHOD_UNBUFFERED
				self._write(0x01) # FLASH_WE_PIN_WR
				commands = [
					[ 0x5555, 0xAA ],
					[ 0x2AAA, 0x55 ],
					[ 0x5555, 0xA0 ],
				]
				for i in range(0, 6):
					if i >= len(commands):
						self._write(bytearray(struct.pack(">I", 0)) + bytearray(struct.pack(">H", 0)))
					else:
						self._write(bytearray(struct.pack(">I", commands[i][0])) + bytearray(struct.pack(">H", commands[i][1])))
				if self.FW["fw_ver"] >= 12: self.wait_for_ack()
				self._set_fw_variable("FLASH_COMMANDS_BANK_1", 1)
				self._write(self.DEVICE_CMD["DMG_SET_BANK_CHANGE_CMD"])
				self._write(1) # number of commands
				self._write(bytearray(struct.pack(">I", 0x0006))) # address/value
				self._write(0) # type = address
				ret = self._read(1)
				if ret != 0x01:
					print("Error in DMG_SET_BANK_CHANGE_CMD:", ret)
			else:
				_mbc.EnableMapper()

			if args["rtc"] is True:
				extra_size = _mbc.GetRTCBufferSize()

			# Check for DMG-MBC5-32M-FLASH
			self._cart_write(0x2000, 0x00)
			self._cart_write(0x4000, 0x90)
			flash_id = self._cart_read(0x4000, 2)
			if flash_id in (bytearray([0xB0, 0x88]), bytearray([0xB0, 0xB0])): audio_low = True
			self._cart_write(0x4000, 0xF0)
			self._cart_write(0x4000, 0xFF)
			self._cart_write(0x2000, 0x01)
			if audio_low:
				dprint("DMG-MBC5-32M-FLASH Development Cartridge detected")
				self._set_fw_variable("FLASH_WE_PIN", 0x01)
				self.SetPin(["PIN_AUDIO"], False)
			self._cart_write(0x4000, 0x00)

			_mbc.EnableRAM(enable=True)

		elif self.MODE == "AGB":
			self._write(self.DEVICE_CMD["SET_MODE_AGB"], wait=self.FW["fw_ver"] >= 12)
			self._write(self.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=self.FW["fw_ver"] >= 12)
			buffer_len = 0x2000
			if "save_size" in args:
				save_size = args["save_size"]
			else:
				save_size = AgbSaveTypes().GetSize(args["save_type"])
			ram_banks = math.ceil(save_size / 0x10000)
			agb_flash_chip = 0

			if args["save_type"] in (1, 2): # EEPROM
				if args["mode"] == 3:
					buffer_len = 0x40
				else:
					buffer_len = 0x100
			elif args["save_type"] in (4, 5): # FLASH
				empty_data_byte = 0xFF
				ret = self.ReadFlashSaveID()
				if ret is False:
					if not args.get("detect"):
						self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("Couldn’t detect the save data flash chip type."), "abortable":False})
					return False
				buffer_len = 0x1000
				(agb_flash_chip, _) = ret
				if agb_flash_chip in (0xBF4B, 0xBF5B, 0xFFFF): # Bootlegs
					buffer_len = 0x800
				elif agb_flash_chip == 0xBF6D:
					buffer_len = 0x8000
			elif args["save_type"] == 6: # DACS
				# self._write(self.DEVICE_CMD["AGB_BOOTUP_SEQUENCE"], wait=self.FW["fw_ver"] >= 12)
				empty_data_byte = 0xFF
				# Read Chip ID
				ram_banks = 1
				self._cart_write(0, 0x90)
				flash_id = self._cart_read(0, 4)
				self._cart_write(0, 0x50)
				self._cart_write(0, 0xFF)
				if flash_id != bytearray([ 0xB0, 0x00, 0x9F, 0x00 ]):
					dprint("Warning: Unknown DACS flash chip ID ({:s})".format(' '.join(format(x, '02X') for x in flash_id)))
					if not args.get("detect"):
						self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("Couldn’t detect the DACS flash chip.\nUnknown Flash ID: {flash_id}", flash_id=' '.join(format(x, '02X') for x in flash_id)), "abortable":False})
					return False
				buffer_len = 0x2000

				# ↓↓↓ Load commands into firmware
				flash_cmds = [
					[ "PA", 0x70 ],
					[ "PA", 0x10 ],
					[ "PA", "PD" ]
				]
				self._set_fw_variable("FLASH_SHARP_VERIFY_SR", 1)
				self._write(self.DEVICE_CMD["SET_FLASH_CMD"])
				self._write(0x02) # FLASH_COMMAND_SET_INTEL
				self._write(0x01) # FLASH_METHOD_UNBUFFERED
				self._write(0x00) # unset
				for i in range(0, 6):
					if i > len(flash_cmds) - 1: # skip
						self._write(bytearray(struct.pack(">I", 0)) + bytearray(struct.pack(">H", 0)))
					else:
						address = flash_cmds[i][0]
						value = flash_cmds[i][1]
						if not isinstance(address, int): address = 0
						if not isinstance(value, int): value = 0
						address >>= 1
						dprint("Setting command #{:d} to 0x{:X}=0x{:X}".format(i, address, value))
						self._write(bytearray(struct.pack(">I", address)) + bytearray(struct.pack(">H", value)))
				if self.FW["fw_ver"] >= 12: self.wait_for_ack()
				# ↑↑↑ Load commands into firmware

			# Bootleg mapper
			if cart_type is not None and "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] == 1:
				sram_5 = struct.unpack("B", bytes(self._cart_read(address=5, length=1, agb_save_flash=True)))[0]
				self._cart_write(address=5, value=1, sram=True)

			commands = [ # save type commands
				[ [None], [None] ], # No save
				[ bytearray([ self.DEVICE_CMD["AGB_CART_READ_EEPROM"], 1]), bytearray([ self.DEVICE_CMD["AGB_CART_WRITE_EEPROM"], 1]) ], # 4K EEPROM
				[ bytearray([ self.DEVICE_CMD["AGB_CART_READ_EEPROM"], 2]), bytearray([ self.DEVICE_CMD["AGB_CART_WRITE_EEPROM"], 2]) ], # 64K EEPROM
				[ self.DEVICE_CMD["AGB_CART_READ_SRAM"], self.DEVICE_CMD["AGB_CART_WRITE_SRAM"] ], # 256K SRAM
				[ self.DEVICE_CMD["AGB_CART_READ_SRAM"], bytearray([ self.DEVICE_CMD["AGB_CART_WRITE_FLASH_DATA"], 2 if agb_flash_chip == 0x1F3D else 1]) ], # 512K FLASH
				[ self.DEVICE_CMD["AGB_CART_READ_SRAM"], bytearray([ self.DEVICE_CMD["AGB_CART_WRITE_FLASH_DATA"], 1]) ], # 1M FLASH
				[ False, False ], # 8M DACS
				[ self.DEVICE_CMD["AGB_CART_READ_SRAM"], self.DEVICE_CMD["AGB_CART_WRITE_SRAM"] ], # 512K SRAM
				[ self.DEVICE_CMD["AGB_CART_READ_SRAM"], self.DEVICE_CMD["AGB_CART_WRITE_SRAM"] ], # 1M SRAM
			]
			command = commands[args["save_type"]][args["mode"] - 2]

			if args["rtc"] is True:
				extra_size = 0x10

		action = None
		if args["mode"] == 2: # Backup
			action = "SAVE_READ"
			buffer = bytearray()
			if self.MODE == "DMG" and args["save_type"] == 0x204: # Unlicensed PHOTO!
				ram_banks = 16

		elif args["mode"] == 3: # Restore
			action = "SAVE_WRITE"
			self.INFO["save_erase"] = args["erase"]
			if args["erase"] == True:
				buffer = bytearray([ empty_data_byte ] * save_size)
				if self.MODE == "DMG" and _mbc.GetName() == "Xploder GB":
					buffer[0] = 0x00
				elif self.MODE == "DMG" and _mbc.GetName() == "MAC-GBD":
					buffer[0x11B2:0x11D7] = bytearray.fromhex("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF4D616769631115")
					buffer[0x11D7:0x11FC] = buffer[0x11B2:0x11D7]
			else:
				if args["path"] is None:
					if "buffer" in args:
						buffer = args["buffer"]
					else:
						buffer = self.INFO["data"]
				else:
					with open(args["path"], "rb") as f:
						buffer = bytearray(f.read())

				if self.MODE == "DMG" and args["save_type"] == 0x204: # Unlicensed PHOTO!
					ram_banks = 16
					if len(buffer) <= 0x20000:
						save_size = len(buffer)
						args["save_type"] = 0x04

				# Fill too small file
				if not (self.MODE == "AGB" and args["save_type"] == 6): # Not DACS
					if args["mode"] == 3:
						while len(buffer) < save_size:
							buffer += bytearray(buffer)

		# Main loop
		if not (args["mode"] == 2 and "verify_write" in args and args["verify_write"]):
			self.INFO["action"] = self.ACTIONS[action]
			self.SetProgress({"action":"INITIALIZE", "method":action, "size":save_size+extra_size})

		buffer_offset = 0
		max_length = 64 if self.FW["pcb_name"] in ("GBxCart RW", "") else self.MAX_BUFFER_READ
		for bank in range(0, ram_banks):
			if self.MODE == "DMG":
				if _mbc.GetName() == "MBC6" and bank > 7:
					self._set_fw_variable("DMG_ROM_BANK", bank - 8)
					(start_address, bank_size) = _mbc.SelectBankFlash(bank - 8)
					end_address = start_address + bank_size
					buffer_len = 0x2000
					if args["mode"] == 3: # Restore
						if ((buffer_offset - 0x8000) % 0x20000) == 0:
							dprint("Erasing flash sector at position 0x{:X}".format(buffer_offset))
							_mbc.EraseFlashSector()
				elif _mbc.GetName() == "Xploder GB":
					self._set_fw_variable("DMG_ROM_BANK", bank + 8)
					(start_address, bank_size) = _mbc.SelectBankRAM(bank)
					end_address = min(save_size, start_address + bank_size)
				else:
					self._set_fw_variable("DMG_WRITE_CS_PULSE", 1 if _mbc.WriteWithCSPulse() else 0)
					(start_address, bank_size) = _mbc.SelectBankRAM(bank)
					end_address = min(save_size, start_address + bank_size)
			elif self.MODE == "AGB":
				start_address = 0
				bank_size = 0x10000
				if args["save_type"] == 6: # DACS
					bank_size = min(save_size, 0x100000)
					buffer_len = 0x2000

				end_address = min(save_size, bank_size)

				if save_size > bank_size:
					if args["save_type"] == 8 or agb_flash_chip in (0xBF4B, 0xBF5B, 0xFFFF, 0xBF6D): # Bootleg 1M
						dprint("Switching to bootleg save bank {:d}".format(bank))
						self._cart_write(0x1000000, bank)
					elif args["save_type"] == 5: # FLASH 1M
						dprint("Switching to FLASH bank {:d}".format(bank))
						cmds = [
							[ 0x5555, 0xAA ],
							[ 0x2AAA, 0x55 ],
							[ 0x5555, 0xB0 ],
							[ 0, bank ]
						]
						self._cart_write_flash(cmds)
					else:
						dprint("Unknown bank switching method")
					time.sleep(0.05)

			dprint("start_address=0x{:X}, end_address=0x{:X}, buffer_len=0x{:X}, buffer_offset=0x{:X}".format(start_address, end_address, buffer_len, buffer_offset))
			pos = start_address
			while pos < end_address:
				if self.CANCEL:
					cancel_args = {"action":"ABORT", "abortable":False}
					cancel_args.update(self.CANCEL_ARGS)
					self.CANCEL_ARGS = {}
					self.ERROR_ARGS = {}
					self.SetProgress(cancel_args)
					if self.CanPowerCycleCart(): self.CartPowerCycle()
					return

				if args["mode"] == 2: # Backup
					in_temp = [None] * 2
					if "verify_read" in args and args["verify_read"]: # Read twice for detecting instabilities
						xe = 2
					else:
						xe = 1
					_read_failed = False
					for x in range(0, xe):
						if x == 1:
							self.NO_PROG_UPDATE = True
						else:
							self.NO_PROG_UPDATE = False

						if self.MODE == "DMG" and _mbc.GetName() == "MBC7":
							in_temp[x] = self.ReadRAM_MBC7(address=pos, length=buffer_len)
						elif self.MODE == "DMG" and _mbc.GetName() == "MBC6" and bank > 7: # MBC6 flash save memory
							in_temp[x] = self.ReadROM(address=pos, length=buffer_len, skip_init=False, max_length=max_length)
						elif self.MODE == "DMG" and _mbc.GetName() == "TAMA5":
							in_temp[x] = self.ReadRAM_TAMA5()
						elif self.MODE == "DMG" and _mbc.GetName() == "Xploder GB":
							in_temp[x] = self.ReadROM(address=0x20000+pos, length=buffer_len, skip_init=False, max_length=max_length)
						elif self.MODE == "AGB" and args["save_type"] in (1, 2): # EEPROM
							in_temp[x] = self.ReadRAM(address=int(pos/8), length=buffer_len, command=command, max_length=max_length)
						elif self.MODE == "AGB" and args["save_type"] == 6: # DACS
							in_temp[x] = self.ReadROM(address=0x1F00000+pos, length=buffer_len, skip_init=False, max_length=max_length)
						elif self.MODE == "DMG" and _mbc.GetName() == "MBC2":
							in_temp[x] = self.ReadRAM(address=pos, length=buffer_len, command=command, max_length=max_length)
							for i in range(0, len(in_temp[x])):
								in_temp[x][i] = in_temp[x][i] & 0x0F
						else:
							in_temp[x] = self.ReadRAM(address=pos, length=buffer_len, command=command, max_length=max_length)

						if len(in_temp[x]) != buffer_len:
							if (max_length >> 1) < 64:
								dprint("Received 0x{:X} bytes instead of 0x{:X} bytes from the device at position 0x{:X}!".format(len(in_temp[x]), buffer_len, len(buffer)))
								max_length = 64
							else:
								dprint("Received 0x{:X} bytes instead of 0x{:X} bytes from the device at position 0x{:X}! Decreasing maximum transfer buffer length to 0x{:X}.".format(len(in_temp[x]), buffer_len, len(buffer), max_length >> 1))
								max_length >>= 1
								_read_failed = True
							self.DEVICE.reset_input_buffer()
							self.DEVICE.reset_output_buffer()
							if _read_failed:
								break

					if _read_failed:
						continue

					if xe == 2 and in_temp[0] != in_temp[1]:
						print(ANSI.RED + __("Error: Inconsistent reads detected.") + ANSI.RESET)
						print(f"- Read #1: {in_temp[0].hex()}")
						print(f"- Read #2: {in_temp[1].hex()}")
						if not args.get("detect"):
							self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("Failed to read save data consistently. Please ensure that the cartridge contacts are clean."), "abortable":False})
						return False

					temp = in_temp[0]
					buffer += temp
					self.SetProgress({"action":"UPDATE_POS", "pos":len(buffer)})

				elif args["mode"] == 3: # Restore
					if self.MODE == "DMG" and _mbc.GetName() == "MBC7":
						self.WriteEEPROM_MBC7(address=pos, buffer=buffer[buffer_offset:buffer_offset+buffer_len])
					elif self.MODE == "DMG" and _mbc.GetName() == "MBC6" and bank > 7: # MBC6 flash save memory
						if self.FW["fw_ver"] > 1:
							self.WriteROM(address=pos, buffer=buffer[buffer_offset:buffer_offset+buffer_len])
							self._cart_write(pos + buffer_len - 1, 0xF0)
						else:
							self.WriteFlash_MBC6(address=pos, buffer=buffer[buffer_offset:buffer_offset+buffer_len], mapper=_mbc)
					elif self.MODE == "DMG" and _mbc.GetName() == "TAMA5":
						self.WriteRAM_TAMA5(buffer=buffer[buffer_offset:buffer_offset+buffer_len])
					elif self.MODE == "DMG" and _mbc.GetName() == "Xploder GB":
						self.WriteROM_DMG_EEPROM(address=pos, buffer=buffer[buffer_offset:buffer_offset+buffer_len], bank=bank+8)
					elif self.MODE == "AGB" and args["save_type"] in (1, 2): # EEPROM
						self.WriteRAM(address=int(pos/8), buffer=buffer[buffer_offset:buffer_offset+buffer_len], command=command)
					elif self.MODE == "AGB" and args["save_type"] in (4, 5): # FLASH
						sector_address = pos % 0x10000
						if agb_flash_chip == 0x1F3D: # Atmel AT29LV512
							self.WriteRAM(address=int(pos/128), buffer=buffer[buffer_offset:buffer_offset+buffer_len], command=command)
						else:
							dprint("Erasing flash save sector; pos=0x{:X}, sector_address=0x{:X}".format(pos, sector_address))
							cmds = [
								[ 0x5555, 0xAA ],
								[ 0x2AAA, 0x55 ],
								[ 0x5555, 0x80 ],
								[ 0x5555, 0xAA ],
								[ 0x2AAA, 0x55 ],
								[ sector_address, 0x30 ]
							]
							self._cart_write_flash(cmds)
							sr = 0
							lives = 50
							while True:
								time.sleep(0.01)
								sr = self._cart_read(sector_address, 2, agb_save_flash=True)
								try:
									sr = struct.unpack(">H", sr)[0]
								except:
									sr = str(sr)
								dprint("Data Check: 0x{:X} == 0xFFFF? {:s}".format(sr, str(sr == 0xFFFF)))
								if sr == 0xFFFF: break
								lives -= 1
								if lives == 0:
									errmsg = __("Error: Save data flash sector at {address} didn’t erase successfully (SR={status_register}).", address="0x{:X}".format(bank*0x10000 + pos), status_register="0x{:04X}".format(sr))
									print(ANSI.RED + errmsg + ANSI.RESET)
									# dprint(errmsg)
									break
							if buffer[buffer_offset:buffer_offset+buffer_len] != bytearray([0xFF] * buffer_len):
								if ("ereader" in self.INFO and self.INFO["ereader"] is True and sector_address == 0xF000):
									self.WriteRAM(address=pos, buffer=buffer[buffer_offset:buffer_offset+0xF80], command=command, max_length=0x80)
								else:
									self.WriteRAM(address=pos, buffer=buffer[buffer_offset:buffer_offset+buffer_len], command=command)
					elif self.MODE == "AGB" and args["save_type"] == 6: # DACS
						sector_address = pos + 0x1F00000
						if sector_address in (0x1F00000, 0x1F10000, 0x1F20000, 0x1F30000, 0x1F40000, 0x1F50000, 0x1F60000, 0x1F70000, 0x1F80000, 0x1F90000, 0x1FA0000, 0x1FB0000, 0x1FC0000, 0x1FD0000, 0x1FE0000, 0x1FF0000, 0x1FF2000, 0x1FF4000, 0x1FF6000, 0x1FF8000, 0x1FFA000, 0x1FFC000):
							dprint("DACS: Now at sector 0x{:X}".format(sector_address))
							cmds = [
								[ # Erase Sector
									[ 0, 0x50 ],
									[ sector_address, 0x20 ],
									[ sector_address, 0xD0 ],
								]
							]
							if sector_address == 0x1F00000: # First write
								temp = [
									[ # Unlock
										[ 0, 0x50 ],
										[ 0, 0x60 ],
										[ 0, 0xD0 ],
									]
								]
								temp.extend(cmds)
								cmds = temp
							elif sector_address == 0x1FFC000: # Boot sector
								temp = [
									[ # Unlock 1
										[ 0, 0x50 ],
										[ 0, 0x60 ],
										[ 0, 0xD0 ],
									],
									[ # Unlock 2
										[ 0, 0x50 ],
										[ sector_address, 0x60 ],
										[ sector_address, 0xDC ],
									]
								]
								temp.extend(cmds)
								cmds = temp

							for cmd in cmds:
								dprint("Executing DACS commands:", cmd)
								self._cart_write_flash(commands=cmd, flashcart=True)
								sr = 0
								lives = 20
								while True:
									time.sleep(0.1)
									raw_sr = self._cart_read(sector_address, 2)
									if raw_sr is False or len(raw_sr) < 2:
										lives -= 1
										if lives == 0:
											self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("An error occured while writing to the DACS cartridge. Please make sure that the cartridge contacts are clean, re-connect the device and try again from the beginning."), "abortable":False})
											return False
										continue
									sr = struct.unpack("<H", raw_sr)[0]
									dprint("DACS: Status Register Check: 0x{:X} == 0x80? {:s}".format(sr, str(sr & 0xE0 == 0x80)))
									if sr & 0xE0 == 0x80: break
									lives -= 1
									if lives == 0:
										self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("An error occured while writing to the DACS cartridge. Please make sure that the cartridge contacts are clean, re-connect the device and try again from the beginning."), "abortable":False})
										return False
						if sector_address < 0x1FFE000:
							dprint("DACS: Writing to area 0x{:X}–0x{:X}".format(0x1F00000+pos, 0x1F00000+pos+buffer_len-1))
							self.WriteROM(address=0x1F00000+pos, buffer=buffer[buffer_offset:buffer_offset+buffer_len])
						else:
							dprint("DACS: Skipping read-only area 0x{:X}–0x{:X}".format(0x1F00000+pos, 0x1F00000+pos+buffer_len-1))
					else:
						self.WriteRAM(address=pos, buffer=buffer[buffer_offset:buffer_offset+buffer_len], command=command)
					self.SetProgress({"action":"UPDATE_POS", "pos":buffer_offset+buffer_len})

				pos += buffer_len
				buffer_offset += buffer_len

		verified = False
		if args["mode"] == 2: # Backup
			self.INFO["transferred"] = len(buffer)
			rtc_buffer = None
			# Real Time Clock
			if args["rtc"] is True:
				self.NO_PROG_UPDATE = True
				if self.MODE == "DMG" and args["rtc"] is True:
					if _mbc.HasRTC():
						_mbc.LatchRTC()
						rtc_buffer = _mbc.ReadRTC()
				elif self.MODE == "AGB":
					_agb_gpio = AGB_GPIO(args={"rtc":True}, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
					rtc_buffer = None
					if self.FW["fw_ver"] >= 12:
						self._write(self.DEVICE_CMD["AGB_READ_GPIO_RTC"])
						rtc_buffer = self._read(8)
						if len(rtc_buffer) == 8 and _agb_gpio.HasRTC(rtc_buffer) is True:
							rtc_buffer = rtc_buffer[1:]
							rtc_buffer.append(_agb_gpio.RTCReadStatus()) # 24h mode = 0x40, reset flag = 0x80
							rtc_buffer.extend(struct.pack("<Q", int(time.time())))
						else:
							rtc_buffer = None
					else:
						if _agb_gpio.HasRTC() is True:
							rtc_buffer = _agb_gpio.ReadRTC(buffer=rtc_buffer)
				self.NO_PROG_UPDATE = False
				if rtc_buffer in (False, None): rtc_buffer = bytearray()
				self.SetProgress({"action":"UPDATE_POS", "pos":len(buffer)+len(rtc_buffer)})

			# Bootleg mapper
			if self.MODE == "AGB" and cart_type is not None and "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] == 1:
				buffer[5] = sram_5

			# PHOTO! rolls
			if self.MODE == "DMG" and args["save_type"] == 0x204:
				for i in range(8, 64):
					_mbc.SelectBankROM(i)
					buffer += self.ReadROM(0x4000, 0x4000)
					self.SetProgress({"action":"UPDATE_POS", "pos":len(buffer)})

			if args["path"] is not None:
				if self.MODE == "DMG" and _mbc.GetName() == "MBC2":
					for i in range(0, len(buffer)):
						buffer[i] = buffer[i] & 0x0F
				file = open(args["path"], "wb")
				file.write(buffer)
				if rtc_buffer is not None:
					file.write(rtc_buffer)
				file.close()
			else:
				self.INFO["data"] = buffer

			self.INFO["file_crc32"] = zlib.crc32(buffer) & 0xFFFFFFFF
			self.INFO["file_sha1"] = hashlib.sha1(buffer).hexdigest()

			if "verify_write" in args and args["verify_write"] not in (None, False):
				return True
			elif "verify_write" not in args or args["verify_write"] is False:
				verified = True

		elif args["mode"] == 3: # Restore
			self.INFO["transferred"] = len(buffer)
			if args["rtc"] is True:
				advance = "rtc_advance" in args and args["rtc_advance"]
				self.SetProgress({"action":"UPDATE_RTC", "method":"write"})
				if self.MODE == "DMG" and args["rtc"] is True:
					if "erase" in args and args["erase"] is True:
						buffer += bytearray([0] * _mbc.GetRTCBufferSize())
					_mbc.WriteRTC(buffer[-_mbc.GetRTCBufferSize():], advance=advance)
				elif self.MODE == "AGB":
					if "erase" in args and args["erase"] is True:
						buffer += bytearray([0xFF] * 0x10)
					_agb_gpio = AGB_GPIO(args={"rtc":True}, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)
					_agb_gpio.WriteRTC(buffer[-0x10:], advance=advance)

			# PHOTO! rolls
			if self.MODE == "DMG" and args["save_type"] == 0x204 and "cart_type" in args and args["cart_type"] != -1:
				if len(buffer) > 0x20000 and args["cart_type"] is not None:
					self._FlashROM({'buffer': buffer[0x20000:0x100000], 'path':"", 'cart_type': args["cart_type"], 'override_voltage': False, 'prefer_chip_erase': False, 'fast_read_mode': True, 'verify_write': False, 'fix_header': False, 'fix_bootlogo': False, 'mbc': 252, 'bl_offset': 0x20000, 'bl_size': 0xE0000, 'bl_layout': 0, 'bl_save': True, 'flash_offset': 0x20000, 'flash_size': 0xE0000, 'mode': 4, 'photo_mode': True})
					args["verify_write"] = False

			self.SetProgress({"action":"UPDATE_POS", "pos":len(buffer), "force_update":True})

			# ↓↓↓ Write verify
			if "verify_write" in args and args["verify_write"] is True and args["erase"] is not True:
				if self.MODE == "DMG": _mbc.SelectBankRAM(0)
				self.SetProgress({"action":"INITIALIZE", "method":"SAVE_WRITE_VERIFY", "size":buffer_offset})

				verify_args = copy.copy(args)
				start_address = 0
				end_address = buffer_offset
				if self.MODE == "AGB" and args["save_type"] == 6: # DACS
					end_address = min(len(buffer), 0xFE000)

				path = args["path"] # backup path
				verify_args.update({"mode":2, "verify_write":buffer, "path":None})
				self.ReadROM(0, 4) # dummy read
				self.INFO["data"] = None
				if not self._BackupRestoreRAM(verify_args): return

				if self.MODE == "DMG" and _mbc.GetName() == "MBC2":
					for i in range(0, len(self.INFO["data"])):
						self.INFO["data"][i] &= 0x0F
						buffer[i] &= 0x0F

				args["path"] = path # restore path
				if self.CANCEL is True:
					pass

				if self.MODE == "AGB" and "ereader" in self.INFO and self.INFO["ereader"] is True: # e-Reader
					buffer[0xFF80:0x10000] = self.INFO["data"][0xFF80:0x10000]
					buffer[0x1FF80:0x20000] = self.INFO["data"][0xFF80:0x10000]

				if self.INFO["data"] is None:
					return False
				if (self.INFO["data"][:end_address] != buffer[:end_address]):
					msg = ""
					count = 0
					time_start = time.time()
					for i in range(0, len(self.INFO["data"])):
						if i >= len(buffer): break
						if time.time() > time_start + 10:
							self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("The save data was written completely, but didn’t pass the verification check."), "abortable":False})
							return False
						data1 = self.INFO["data"][i]
						data2 = buffer[:end_address][i]
						if data1 != data2:
							count += 1
							if len(msg.split("\n")) <= 10:
								msg += "- 0x{:06X}: {:02X}≠{:02X}\n".format(i, data1, data2)
							elif len(msg.split("\n")) == 11:
								msg += "(" + __("more than 10 differences found") + ")\n"
							else:
								pass
					self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":___(
						"The save data was written completely, but {count} byte ({percent}%) didn’t pass the verification check.",
						"The save data was written completely, but {count} bytes ({percent}%) didn’t pass the verification check.",
						n=count,
						count=count,
						percent="{:.2f}".format(count / len(self.INFO["data"]) * 100)
						) + "\n\n" + msg[:-1],
						"abortable":False
					})
					return False
				else:
					verified = True
			else:
				verified = True
			# ↑↑↑ Write verify

		if self.MODE == "DMG":
			_mbc.SelectBankRAM(0)
			_mbc.EnableRAM(enable=False)
			self._set_fw_variable("DMG_READ_CS_PULSE", 0)
			if audio_low:
				self._set_fw_variable("FLASH_WE_PIN", 0x02)
				self.SetPin(["PIN_AUDIO"], True)
			self._write(self.DEVICE_CMD["SET_ADDR_AS_INPUTS"], wait=self.FW["fw_ver"] >= 12) # Prevent hotplugging corruptions on rare occasions
		elif self.MODE == "AGB":
			# Bootleg mapper
			if cart_type is not None and "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] == 1:
				self._cart_write(address=5, value=0, sram=True)
				self._cart_write(address=5, value=buffer[5], sram=True)

		# Clean up
		self.INFO["last_action"] = self.INFO["action"]
		self.INFO["action"] = None
		self.INFO["last_path"] = args["path"]
		self._thread_worker_auto_poweroff_finish()
		self.SetProgress({"action":"FINISHED", "verified":verified})
		return True

	def _FlashROM(self, args):
		self._thread_worker_auto_poweroff_start()
		try:
			return self._FlashROM_Worker(args)
		finally:
			try:
				if self.MODE == "DMG" and self.FW.get("fw_ver", 0) >= 14 and self.FW_VAR.get("DMG_AUDIO_ENABLED", 0) == 1:
					self._set_fw_variable("DMG_AUDIO_ENABLED", 0)
			finally:
				self._thread_worker_auto_poweroff_finish()

	def _FlashROM_Worker(self, args):
		# Initialization
		self.FAST_READ = True
		temp = None
		rom_bank_size = 0
		end_bank = 0
		pos_from = 0
		verify_len = 0
		enable_pullup_wr = False

		if "buffer" in args:
			data_import = args["buffer"]
		else:
			with open(args["path"], "rb") as file: data_import = bytearray(file.read())

		flash_offset = 0 # Batteryless SRAM or Transfer Resume
		if "flash_offset" in args:
			flash_offset = args["flash_offset"]
		if "start_addr" in args and args["start_addr"] > 0:
			data_import = bytearray(b'\xFF' * args["start_addr"]) + data_import

		# Batteryless SRAM
		if "bl_layout" in args and args["bl_layout"] in (1, 2):
			args["bl_size"] <<= 1
			args["flash_size"] <<= 1
			bl_data_import = bytearray(b'\xFF' * args["bl_size"])

			if args["bl_layout"] == 1:
				for i in range(0, args["bl_size"] // 0x4000):
					bl_data_import[i*0x4000:i*0x4000+0x2000] = data_import[i*0x2000:i*0x2000+0x2000]
			elif args["bl_layout"] == 2:
				for i in range(0, args["bl_size"] // 0x4000):
					bl_data_import[i*0x4000+0x2000:i*0x4000+0x2000+0x2000] = data_import[i*0x2000:i*0x2000+0x2000]
			data_import = bl_data_import

		# Pad data
		if len(data_import) > 0:
			if len(data_import) < 0x400:
				data_import += bytearray([0xFF] * (0x400 - len(data_import)))
			if len(data_import) % 0x4000 > 0:
				data_import += bytearray([0xFF] * (0x4000 - len(data_import) % 0x4000))

			# Skip writing the last 256 bytes of 32 MiB ROMs with EEPROM save type
			if self.MODE == "AGB" and len(data_import) == 0x2000000:
				temp_ver = "N/A"
				try:
					ids = [ b"SRAM_", b"EEPROM_V", b"FLASH_V", b"FLASH512_V", b"FLASH1M_V", b"AGB_8MDACS_DL_V" ]
					for id in ids:
						temp_pos = data_import.find(id)
						if temp_pos > 0:
							temp_ver = data_import[temp_pos:temp_pos+0x20]
							temp_ver = temp_ver[:temp_ver.index(0x00)].decode("ascii", "replace")
							break
				except ValueError:
					temp_ver = "N/A"
				if "EEPROM" in temp_ver:
					print(ANSI.YELLOW + __("Note: The last 256 bytes of this 32 MiB ROM will not be written as this area is reserved by the EEPROM save type.") + ANSI.RESET)
					data_import = data_import[:0x1FFFF00]

		# Fix bootlogo and header
		if "fix_bootlogo" in args and isinstance(args["fix_bootlogo"], bytearray):
			dstr = ''.join(format(x, '02X') for x in args["fix_bootlogo"])
			dprint("Replacing bootlogo data with", dstr)
			if self.MODE == "DMG":
				data_import[0x104:0x134] = args["fix_bootlogo"]
			elif self.MODE == "AGB":
				data_import[0x04:0xA0] = args["fix_bootlogo"]
		if "fix_header" in args and args["fix_header"]:
			dprint("Fixing header checksums")
			if self.MODE == "DMG":
				temp = RomFileDMG(data_import[0:0x200]).FixHeader()
			elif self.MODE == "AGB":
				temp = RomFileAGB(data_import[0:0x200]).FixHeader()
			data_import[0:0x200] = temp

		supported_carts = list(self.SUPPORTED_CARTS[self.MODE].values())
		cart_type = copy.deepcopy(supported_carts[args["cart_type"]])
		try:
			cart_name = cart_type["names"][0]
		except:
			cart_name = c__("Flashcart Profile", "Unknown")

		if cart_type == "RETAIL": return False # Generic ROM Cartridge is not flashable

		# Firmware check L2
		if (cart_type["type"] == "DMG" and "write_pin" in cart_type and cart_type["write_pin"] == "WR+RESET" and self.FW["fw_ver"] < 2) or (self.FW["fw_ver"] < 2 and ("pulse_reset_after_write" in cart_type and cart_type["pulse_reset_after_write"] is True)):
			self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("This flashcart profile requires at least firmware version L2."), "abortable":False})
			return False
		# Firmware check L2
		# Firmware check L3
		if (self.FW["fw_ver"] < 3 and ("command_set" in cart_type and cart_type["command_set"] == "SHARP") and ("buffer_write" in cart_type["commands"])):
			print(ANSI.YELLOW + __("Note: Update your {device_name} firmware to version L3 or higher for a better transfer rate with this flashcart profile.", device_name=self.DEVICE_NAME) + ANSI.RESET)
			del(cart_type["commands"]["buffer_write"])
		# Firmware check L3
		# Firmware check L5
		if (self.FW["fw_ver"] < 5 and ("flash_commands_on_bank_1" in cart_type and cart_type["flash_commands_on_bank_1"] is True)):
			self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("This flashcart profile requires at least firmware version L5."), "abortable":False})
			return False
		if (self.FW["fw_ver"] < 5 and ("double_die" in cart_type and cart_type["double_die"] is True)):
			print(ANSI.YELLOW + __("Note: Update your {device_name} firmware to version L5 or higher for a better transfer rate with this flashcart profile.", device_name=self.DEVICE_NAME) + ANSI.RESET)
			del(cart_type["commands"]["buffer_write"])
		# Firmware check L5
		# Firmware check L8
		if (self.FW["fw_ver"] < 8 and "enable_pullups" in cart_type and cart_type["enable_pullups"] is True):
			print(ANSI.YELLOW + __("Note: This flashcart profile may not be fully compatible with your {device_name} running an old or legacy firmware version.", device_name=self.GetName()) + ANSI.RESET)
			del(cart_type["enable_pullups"])
		# Firmware check L8
		# Firmware check L12
		if (self.FW["fw_ver"] < 12 and "set_irq_high" in cart_type and cart_type["set_irq_high"] is True):
			print(ANSI.YELLOW + __("Note: This flashcart profile may not be fully compatible with your {device_name} until updated to a newer firmware version.", device_name=self.GetName()) + ANSI.RESET)
			del(cart_type["set_irq_high"])
		if (self.FW["fw_ver"] < 12 and "status_register_mask" in cart_type):
			if self.FW["pcb_name"] in ("GBxCart RW", ""):
				self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("This flashcart profile requires a different firmware version. Please update your GBxCart RW firmware using the older FlashGBX v4.3 and try again."), "abortable":False})
			else:
				self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("This flashcart profile requires at least firmware version L12."), "abortable":False})
			return False
		# Firmware check L12
		# Firmware check L14
		if (self.FW["fw_ver"] < 14 and "set_audio_high" in cart_type and cart_type["set_audio_high"] is True):
			self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("This flashcart profile requires at least firmware version L14."), "abortable":False})
			return False
		# Firmware check L14

		# Ensure cart is powered
		if self.CanPowerCycleCart(): self.CartPowerOn()

		cart_type["_index"] = 0
		for i in range(0, len(list(self.SUPPORTED_CARTS[self.MODE].keys()))):
			if i == args["cart_type"]:
				try:
					cart_type["_index"] = cart_type["names"].index(list(self.SUPPORTED_CARTS[self.MODE].keys())[i])
				except:
					pass

		fc_fncptr = {
			"cart_write_fncptr":self._cart_write,
			"cart_write_fast_fncptr":self._cart_write_flash,
			"cart_read_fncptr":self.ReadROM,
			"cart_powercycle_fncptr":self.CartPowerCycleOrAskReconnect,
			"progress_fncptr":self.SetProgress,
			"set_we_pin_wr":self._set_we_pin_wr,
			"set_we_pin_audio":self._set_we_pin_audio,
		}
		if cart_type["command_set"] == "GBMEMORY":
			flashcart = Flashcart_DMG_MMSA(config=cart_type, fncptr=fc_fncptr)
		elif cart_type["command_set"] == "GBAMP":
			flashcart = Flashcart_AGB_GBAMP(config=cart_type, fncptr=fc_fncptr)
		elif cart_type["command_set"] == "BUNG_16M":
			flashcart = Flashcart_DMG_BUNG_16M(config=cart_type, fncptr=fc_fncptr)
		else:
			flashcart = Flashcart(config=cart_type, fncptr=fc_fncptr)

		rumble = "rumble" in flashcart.CONFIG and flashcart.CONFIG["rumble"] is True

		# ↓↓↓ Set Voltage
		if args["override_voltage"] is not False:
			active_voltage = args["override_voltage"]
			if args["override_voltage"] == 5:
				self._write(self.DEVICE_CMD["SET_VOLTAGE_5V"], wait=self.FW["fw_ver"] >= 12)
			else:
				self._write(self.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=self.FW["fw_ver"] >= 12)
		elif flashcart.GetVoltage() == 3.3:
			active_voltage = 3.3
			self._write(self.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=self.FW["fw_ver"] >= 12)
		elif flashcart.GetVoltage() == 5:
			active_voltage = 5
			self._write(self.DEVICE_CMD["SET_VOLTAGE_5V"], wait=self.FW["fw_ver"] >= 12)
		else:
			active_voltage = flashcart.GetVoltage()
		# Voltage-locked devices ignore the SET_VOLTAGE_* writes above; their
		# slot voltage is determined by the platform mode.
		if self.CanSetVoltageByAutoswitch() and not self.CanSetVoltageByCode():
			active_voltage = 5 if self.MODE == "DMG" else 3.3
		# ↑↑↑ Set Voltage

		# ↓↓↓ Pad data for full chip erase on sector erase mode
		if not flashcart.SupportsChipErase() and flashcart.SupportsSectorErase() and args["prefer_chip_erase"]:
			print(ANSI.YELLOW + __("Note: Chip erase mode is not supported for this flashcart profile. Sector erase mode will be used.") + "\n" + ANSI.RESET)
			# Pad data if the user wants to erase the entire cartridge
			if data_import == bytearray([0xFF] * len(data_import)):
				flash_size = flashcart.GetFlashSize()
				if flash_size is not False and len(data_import) < flash_size:
					# Pad with FF till the end (with MemoryError fix)
					pad_len = flash_size - len(data_import)
					while pad_len > 0x2000000:
						data_import += bytearray([0xFF] * 0x2000000)
						pad_len -= 0x2000000
					data_import += bytearray([0xFF] * (flash_size - len(data_import)))
		# ↑↑↑ Pad data for full chip erase on sector erase mode

		# ↓↓↓ Flashcart configuration
		if self.FW["fw_ver"] >= 8:
			if "enable_pullups" in cart_type:
				if cart_type["enable_pullups"] is True:
					self._write(self.DEVICE_CMD["ENABLE_PULLUPS"], wait=True)
					dprint("Pullups enabled")
				else:
					self._write(self.DEVICE_CMD["DISABLE_PULLUPS"], wait=True)
					dprint("Pullups disabled")
		if self.FW["fw_ver"] >= 12:
			if self.MODE == "DMG":
				# Joey Jr bug workaround
				enable_pullup_wr = 2 if (("enable_pullup_wr" in cart_type and cart_type["enable_pullup_wr"] is True) or ("force_wr_pullup" in args and args["force_wr_pullup"] is True)) else 0
				self._set_fw_variable("PULLUPS_ENABLED", enable_pullup_wr)
			elif self.MODE == "AGB":
				self._set_fw_variable("AGB_IRQ_ENABLED", 1 if "set_irq_high" in cart_type else 0)

		_mbc = None
		errmsg_mbc_selection = ""
		if self.MODE == "DMG":
			self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)
			mbc = flashcart.GetMBC()
			if mbc is not False and isinstance(mbc, int):
				args["mbc"] = mbc
				dprint("Using forced mapper type 0x{:02X} for flashing".format(mbc))
			elif mbc == "manual":
				dprint("Using manually selected mapper type 0x{:02X} for flashing".format(args["mbc"]))
			else:
				args["mbc"] = 0
				dprint("Using default mapper type 0x{:02X} for flashing".format(args["mbc"]))
			if args["mbc"] == 0: args["mbc"] = 0x19 # MBC5 default

			if not self.IsSupportedMbc(args["mbc"]):
				msg = __("This cartridge uses a mapper that is not supported by FlashGBX using your {device_name}.", device_name=self.GetFullName())
				self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":msg, "abortable":False})
				return False

			_mbc = DMG_Mapper().GetInstance(args=args, cart_write_fncptr=self._cart_write, cart_read_fncptr=self._cart_read, cart_powercycle_fncptr=self.CartPowerCycleOrAskReconnect, clk_toggle_fncptr=self._clk_toggle)

			self._set_fw_variable("FLASH_PULSE_RESET", 1 if flashcart.PulseResetAfterWrite() else 0)

			end_bank = math.ceil(len(data_import) / _mbc.GetROMBankSize())
			rom_bank_size = _mbc.GetROMBankSize()

			_mbc.EnableMapper()

			if flashcart.GetMBC() == "manual":
				errmsg_mbc_selection += "\n" + __("- Check mapper type used:") + " " + _mbc.GetName() + " (" + c__("Mapper Type", "manual selection") + ")"
			else:
				errmsg_mbc_selection += "\n" + __("- Check mapper type used:") + " " + _mbc.GetName() + " (" + c__("Mapper Type", "forced by selected flashcart profile") + ")"
			if len(data_import) > _mbc.GetMaxROMSize():
				errmsg_mbc_selection += "\n" + __("- Check mapper type ROM size limit: likely up to {max_size}", max_size=Formatter.file_size(_mbc.GetMaxROMSize()))

		elif self.MODE == "AGB":
			self._write(self.DEVICE_CMD["SET_MODE_AGB"], wait=self.FW["fw_ver"] >= 12)
			if flashcart and "flash_bank_size" in cart_type:
				end_bank = math.ceil(len(data_import) / cart_type["flash_bank_size"])
			else:
				end_bank = 1
			if flashcart and "flash_bank_size" in cart_type:
				rom_bank_size = cart_type["flash_bank_size"]
			else:
				rom_bank_size = 0x2000000

		flash_buffer_size = flashcart.GetBufferSize()
		# ↑↑↑ Flashcart configuration

		# ↓↓↓ DMG-MMSA-JPN hidden sector
		if self.MODE == "DMG" and _mbc.GetName() == "G-MMC1":
			if "buffer_map" not in args:
				if os.path.exists(os.path.splitext(args["path"])[0] + ".map"):
					with open(os.path.splitext(args["path"])[0] + ".map", "rb") as file: args["buffer_map"] = file.read()
				else:
					temp = data_import
					if len(temp) == 0: temp = bytearray([0xFF] * 0x180)
					try:
						gbmem = GBMemoryMap(rom=temp, oldmap=_mbc.ReadHiddenSector())
						args["buffer_map"] = gbmem.GetMapData()
					except Exception:
						print(traceback.format_exc())
						print(ANSI.RED + __("An error occured while trying to generate the hidden sector data for the {gb_memory_cartridge}.", gb_memory_cartridge="NP GB-Memory cartridge") + ANSI.RESET)
						args["buffer_map"] = False

					if args["buffer_map"] is False:
						self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("The {gb_memory_cartridge} requires extra hidden sector data. As it couldn’t be auto-generated, please provide your own at the following path:", gb_memory_cartridge="NP GB-Memory cartridge") + " " + os.path.splitext(args["path"])[0] + ".map", "abortable":False})
						return False
					else:
						dprint("Hidden sector data:", args["buffer_map"])
						if ".dev" in AppInfo.VERSION_PEP440 or AppContext.DEBUG:
							with open(AppContext.CONFIG_PATH + os.sep + "debug_mmsa_map.bin", "wb") as f: f.write(args["buffer_map"])
			data_map_import = copy.copy(args["buffer_map"])
			data_map_import = bytearray(data_map_import)
			dprint("Hidden sector data loaded")
		# ↑↑↑ DMG-MMSA-JPN hidden sector

		# ↓↓↓ Load commands into firmware
		flash_cmds = []
		command_set_type = flashcart.GetCommandSetType()
		temp = 0
		if command_set_type == "AMD":
			temp = 0x01
			dprint("Using AMD command set")
		elif command_set_type == "INTEL":
			temp = 0x02
			self._set_fw_variable("FLASH_SHARP_VERIFY_SR", 0)
			dprint("Using Intel command set")
		elif command_set_type == "SHARP":
			temp = 0x02
			self._set_fw_variable("FLASH_SHARP_VERIFY_SR", 1)
			dprint("Using Sharp/Intel command set")
		elif command_set_type in ("GBMEMORY", "DMG-MBC5-32M-FLASH"):
			temp = 0x00
			dprint("Using GB-Memory command set")
		elif command_set_type in ("BLAZE_XPLODER", "DATEL_ORBITV2", "EEPROM", "GBAMP", "BUNG_16M"):
			temp = 0x00
		else:
			self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("This flashcart profile is currently not supported for ROM writing."), "abortable":False})
			return False

		if flashcart.HasDoubleDie() and self.FW["fw_ver"] >= 5:
			self._set_fw_variable("FLASH_DOUBLE_DIE", 1)
		else:
			self._set_fw_variable("FLASH_DOUBLE_DIE", 0)

		if command_set_type == "GBMEMORY" and self.FW["fw_ver"] < 2:
			self._set_fw_variable("FLASH_WE_PIN", 0x01)
			dprint("Using legacy GB-Memory mode")
		elif command_set_type == "DMG-MBC5-32M-FLASH" and self.FW["fw_ver"] < 12:
			self._set_fw_variable("FLASH_WE_PIN", 0x02)
		else:
			self._write(self.DEVICE_CMD["SET_FLASH_CMD"])
			self._write(temp)

			if flashcart.IsF2A():
				self._write(0x05) # FLASH_METHOD_AGB_FLASH2ADVANCE
				flash_cmds = [
					[ "SA", 0xE8 ],
					[ "SA", "BS" ],
					[ "PA", "PD" ],
					[ "SA", 0xD0 ],
					[ "SA", 0xFF ]
				]
				dprint("Using Flash2Advance mode with a buffer of {:d} bytes".format(flash_buffer_size))
			elif command_set_type == "GBMEMORY" and self.FW["fw_ver"] >= 2:
				self._write(0x03) # FLASH_METHOD_DMG_MMSA
				dprint("Using GB-Memory mode")
			elif command_set_type == "DATEL_ORBITV2" and self.FW["fw_ver"] >= 12:
				self._write(0x09) # FLASH_METHOD_DMG_DATEL_ORBITV2
				dprint("Using Datel Orbit V2 mode")
			elif command_set_type == "DMG-MBC5-32M-FLASH" and self.FW["fw_ver"] >= 12:
				self._write(0x0A) # FLASH_METHOD_DMG_E201264
				dprint("Using E201264 mode")
			elif command_set_type == "GBAMP" and self.FW["fw_ver"] >= 12:
				self._write(0x0B) # FLASH_METHOD_AGB_GBAMP
				dprint("Using GBAMP mode")
			elif command_set_type == "BUNG_16M" and self.FW["fw_ver"] >= 12:
				self._write(0x0C) # FLASH_METHOD_DMG_BUNG_16M
				dprint("Using BUNG Doctor GB Card 16M mode")
			elif flashcart.SupportsBufferWrite() and flash_buffer_size > 0:
				self._write(0x02) # FLASH_METHOD_BUFFERED
				flash_cmds = flashcart.GetCommands("buffer_write")
				dprint("Using buffered writing with a buffer of {:d} bytes".format(flash_buffer_size))
			elif flashcart.SupportsPageWrite() and flash_buffer_size > 0 and self.FW["fw_ver"] >= 12:
				self._write(0x08) # FLASH_METHOD_PAGED
				flash_cmds = flashcart.GetCommands("page_write")
				dprint("Using paged writing with a buffer of {:d} bytes".format(flash_buffer_size))
			elif flashcart.SupportsSingleWrite():
				self._write(0x01) # FLASH_METHOD_UNBUFFERED
				flash_cmds = flashcart.GetCommands("single_write")
				dprint("Using single writing")
			else:
				self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("This flashcart profile is currently not supported for ROM writing."), "abortable":False})
				return False

			we = 0x00
			if flashcart.WEisWR():
				we = 0x01 # FLASH_WE_PIN_WR
				self._write(we)
				dprint("Using WR as WE")
			elif flashcart.WEisAUDIO():
				we = 0x02 # FLASH_WE_PIN_AUDIO
				self._write(we)
				dprint("Using AUDIO as WE")
			elif flashcart.WEisWR_RESET():
				we = 0x03 # FLASH_WE_PIN_WR_RESET
				self._write(we) # FLASH_WE_PIN_WR_RESET
				dprint("Using WR+RESET as WE")
			else:
				self._write(we) # unset

			for i in range(0, 6):
				if i > len(flash_cmds) - 1: # skip
					self._write(bytearray(struct.pack(">I", 0)) + bytearray(struct.pack(">H", 0)))
				else:
					address = flash_cmds[i][0]
					value = flash_cmds[i][1]
					if not isinstance(address, int): address = 0
					if not isinstance(value, int): value = 0
					if self.MODE == "AGB": address >>= 1
					dprint("Setting command #{:d} to 0x{:X}=0x{:X}".format(i, address, value))
					self._write(bytearray(struct.pack(">I", address)) + bytearray(struct.pack(">H", value)))
			if self.FW["fw_ver"] >= 12: self.wait_for_ack()

			if self.FW["fw_ver"] >= 6:
				if "flash_commands_on_bank_1" in cart_type and cart_type["flash_commands_on_bank_1"] is True:
					self._set_fw_variable("FLASH_COMMANDS_BANK_1", 1)
					self._write(self.DEVICE_CMD["DMG_SET_BANK_CHANGE_CMD"])
					if "bank_switch" in cart_type["commands"]:
						self._write(len(cart_type["commands"]["bank_switch"])) # number of commands
						for command in cart_type["commands"]["bank_switch"]:
							address = command[0]
							value = command[1]
							if value == "ID":
								self._write(bytearray(struct.pack(">I", address))) # address
								self._write(0) # type = address
							else:
								self._write(bytearray(struct.pack(">I", value))) # value
								self._write(1) # type = value
						ret = self._read(1)
						if ret != 0x01:
							print("Error in DMG_SET_BANK_CHANGE_CMD:", ret)
					else:
						self._write(0, wait=True)
				else:
					self._set_fw_variable("FLASH_COMMANDS_BANK_1", 0)
					self._write(self.DEVICE_CMD["DMG_SET_BANK_CHANGE_CMD"])
					self._write(0, wait=True)
			else:
				if "flash_commands_on_bank_1" in cart_type and cart_type["flash_commands_on_bank_1"] is True:
					self._set_fw_variable("FLASH_COMMANDS_BANK_1", 1)
				else:
					self._set_fw_variable("FLASH_COMMANDS_BANK_1", 0)

			if self.FW["fw_ver"] >= 12:
				if "status_register_mask" in cart_type:
					self._set_fw_variable("STATUS_REGISTER_MASK", cart_type["status_register_mask"])
					self._set_fw_variable("STATUS_REGISTER_VALUE", cart_type["status_register_value"])
				else:
					self._set_fw_variable("STATUS_REGISTER_MASK", 0x80)
					self._set_fw_variable("STATUS_REGISTER_VALUE", 0x80)

		rom_write_bank_switch_conflict_values = set()
		if self.MODE == "DMG" and flashcart.WEisWR() and command_set_type == "AMD":
			rom_write_bank_switch_conflict_values = flashcart.GetROMWriteBankSwitchConflictValues()
			if len(rom_write_bank_switch_conflict_values) > 0:
				dprint("ROM write bank switch separator values:", sorted(rom_write_bank_switch_conflict_values))

		if self.FW["fw_ver"] >= 12: self._set_fw_variable("AGB_IRQ_ENABLED", 1 if "set_irq_high" in cart_type else 0)
		# ↑↑↑ Load commands into firmware

		# ↓↓↓ Preparations
		if self.MODE == "DMG" and "flash_commands_on_bank_1" in cart_type and cart_type["flash_commands_on_bank_1"] is True:
			dprint("Setting ROM bank 1")
			_mbc.SelectBankROM(1)
		if we != 0x00:
			self._set_fw_variable("FLASH_WE_PIN", we)
		if self.FW["fw_ver"] >= 14 and "set_audio_high" in cart_type:
			self._set_fw_variable("DMG_AUDIO_ENABLED", 1 if cart_type.get("set_audio_high") is True else 0)
		# ↑↑↑ Preparations

		# ↓↓↓ Read Flash ID
		if "flash_ids" in cart_type:
			(verified, flash_id) = flashcart.VerifyFlashID()
			if not verified and not command_set_type == "BLAZE_XPLODER":
				if self.VOLTAGE_FALLBACK_PENDING:
					# Silent 3.3V trial: a Flash ID mismatch (typically all-0x00 when the chip
					# isn't powered at this voltage) is a strong sign 3.3V is wrong for this PCB.
					# Skip the warning and bail out so the 5V fallback runs immediately.
					self.VOLTAGE_FALLBACK_TRIGGERED = True
					self.ERROR = True
					self.CANCEL = True
					return False
				print(ANSI.YELLOW + __("Note: This cartridge’s Flash ID ({flash_id}) doesn’t match the flashcart profile selection.", flash_id=' '.join(format(x, '02X') for x in flash_id)) + ANSI.RESET)
		else:
			if flashcart.Unlock() is False: return False
		# ↑↑↑ Read Flash ID

		# ↓↓↓ Read Sector Map
		sector_map = flashcart.GetSectorMap()
		smallest_sector_size = 0x2000
		sector_offsets = []
		write_sectors = []
		verify_sectors = []
		sector_pos = 0
		delta_state_new = None
		flash_capacity = len(data_import)
		if sector_map is not None and sector_map is not False:
			smallest_sector_size = flashcart.GetSmallestSectorSize()
			sector_offsets = flashcart.GetSectorOffsets(rom_size=flashcart.GetFlashSize(default=len(data_import)), rom_bank_size=rom_bank_size)
			if len(sector_offsets) > 0:
				flash_capacity = sector_offsets[-1][0] + sector_offsets[-1][1]
				if flash_capacity < len(data_import) and not (flashcart.SupportsChipErase() and args["prefer_chip_erase"]):
					sector_offsets = flashcart.GetSectorOffsets(rom_size=len(data_import), rom_bank_size=rom_bank_size)

			sector_offsets_hash = base64.urlsafe_b64encode(hashlib.sha1(str(sector_offsets).encode("UTF-8")).digest()).decode("ASCII", "ignore")[:4]

			# Delta flashing
			if len(sector_offsets) > 1:
				splitext = os.path.splitext(args["path"])
				if splitext[0].endswith(".delta") and os.path.exists(splitext[0][:-6] + splitext[1]):
					delta_state_new = []
					with open(splitext[0][:-6] + splitext[1], "rb") as f:
						for i in range(0, len(sector_offsets)):
							s_from = sector_offsets[i][0]
							s_size = sector_offsets[i][1]
							s_to = s_from + s_size
							if data_import[s_from:s_to] != f.read(s_to - s_from):
								x = [ s_from, s_size, zlib.crc32(data_import[s_from:s_to]) & 0xFFFFFFFF ]
								delta_state_new.append(x)
								dprint("Sector differs:", x)
					write_sectors = copy.copy(delta_state_new)
					json_file = "{:s}_{:s}.json".format(splitext[0], sector_offsets_hash)
					if os.path.exists(json_file):
						with open(json_file, "rb") as f:
							try:
								delta_state_old = json.loads(f.read().decode("UTF-8-SIG"))
							except:
								delta_state_old = []
							if len(delta_state_old) > 0:
								for x in delta_state_old:
									if x in write_sectors:
										del(write_sectors[write_sectors.index(x)])
										dprint("Skipping sector:", x)
									else:
										write_sectors2 = []
										for y in write_sectors: write_sectors2.append(y[:-1])
										if x[:-1] not in write_sectors2:
											write_sectors.append(x)
											dprint("Forcing sector:", x)

					if len(write_sectors) == 0:
						self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("No flash sectors were found that would need to be updated for delta flashing."), "abortable":False})
						return False

				elif "flash_sectors" in args and len(args["flash_sectors"]) > 0:
					write_sectors = args["flash_sectors"]

				elif flash_offset > 0: # Batteryless SRAM
					if "flash_size" not in args:
						flash_size = len(data_import) - flash_offset
					else:
						flash_size = args["flash_size"]
						data_import = data_import[:flash_size]
					bl_sectors = []
					for sector in sector_offsets:
						if flash_offset > sector[0]: continue
						if (flash_offset + flash_size) < sector[0]: break
						bl_sectors.append(sector)
					write_sectors = bl_sectors
					if "bl_save" in args:
						data_import = bytearray([0] * bl_sectors[0][0]) + data_import
				else:
					write_sectors = []
					for item in sector_offsets:
						if item[0] < len(data_import):
							write_sectors.append(item)

			dprint("Sectors to update:", write_sectors)
		# ↑↑↑ Read Sector Map

		# ↓↓↓ Set window title before chip erase so it appears during erase phase
		if not "photo_mode" in args:
			self.SetProgress({"action":"INITIALIZE", "method":"ROM_WRITE", "size":len(data_import), "flash_offset":flash_offset, "sector_count":max(1, len(write_sectors)), "voltage":active_voltage})
			self.INFO["action"] = self.ACTIONS["ROM_WRITE"]
		# ↑↑↑ Set window title before chip erase

		# ↓↓↓ Chip erase
		chip_erase = False
		if flashcart.SupportsChipErase() and not flash_offset > 0:
			if flashcart.SupportsSectorErase() and args["prefer_chip_erase"] is False and sector_map is not False:
				chip_erase = False
			else:
				chip_erase = True
				dprint("Erasing the entire flash chip")
				if flashcart.ChipErase() is False:
					return False
		elif flashcart.SupportsSectorErase() is False:
			self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("No erase method available."), "abortable":False})
			return False
		# ↑↑↑ Chip erase

		# ↓↓↓ Flash Write
		if chip_erase:
			write_sectors = [[ 0, len(data_import) ]]
			for i in range(0, len(data_import), 0x20000):
				verify_sectors.append([i, 0x20000])
		elif len(write_sectors) == 0:
			write_sectors = sector_offsets

		if not "photo_mode" in args:
			self.SetProgress({"action":"INITIALIZE", "method":"ROM_WRITE", "size":len(data_import), "flash_offset":flash_offset, "sector_count":len(write_sectors), "voltage":active_voltage})
			self.INFO["action"] = self.ACTIONS["ROM_WRITE"]
		self.SetProgress({"action":"UPDATE_POS", "pos":flash_offset})

		if smallest_sector_size is not False:
			buffer_len = smallest_sector_size
		elif self.MODE == "DMG":
			buffer_len = _mbc.GetROMBankSize()
			if _mbc.HasFlashBanks(): _mbc.SelectBankFlash(0)
		else:
			buffer_len = 0x2000
		dprint("Transfer buffer length is 0x{:X}".format(buffer_len))

		current_bank = 0
		start_bank = 0
		start_address = 0
		buffer_pos = 0
		retry_hp = 0
		first_sector_written = False
		end_address = len(data_import)
		dprint("ROM banks:", end_bank)

		if len(write_sectors) == 0:
			self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("Couldn’t start writing ROM because the flash cart couldn’t be detected properly."), "abortable":False})
			return False

		for sector in write_sectors:
			if chip_erase is False:
				if not first_sector_written:
					retry_hp = 15
				else:
					retry_hp = 100

				if self.MODE == "AGB":
					dprint("Writing sector:", hex(sector[0]), hex(sector[1]))
					buffer_pos = sector[0]
					start_address = buffer_pos
					end_address = sector[0] + sector[1]
					if sector[:2] not in sector_offsets:
						dprint("Sector not found for delta writing:", sector)
						continue
					sector_pos = sector_offsets.index(sector[:2])
					start_bank = math.floor(buffer_pos / rom_bank_size)
					end_bank = math.ceil((buffer_pos + sector[1]) / rom_bank_size)
				elif self.MODE == "DMG":
					dprint("Writing sector:", hex(sector[0]), hex(sector[1]))
					buffer_pos = sector[0]
					#end_address = sector[0] + sector[1]
					if sector[:2] not in sector_offsets:
						print("Sector not found for delta writing:", sector)
						continue
					sector_pos = sector_offsets.index(sector[:2])
					start_bank = math.floor(buffer_pos / rom_bank_size)
					end_bank = math.ceil((buffer_pos + sector[1]) / rom_bank_size)

			bank = start_bank

			# ↓↓↓ Check if data matches already
			if not chip_erase and self.FW["fw_ver"] >= 12 and "compare_sectors" in args and args["compare_sectors"] is True and not (flashcart and cart_type["command_set"] == "GBAMP"):
				buffer_pos_matchcheck = buffer_pos
				verified = False
				ts_se_start = time.time()
				while bank < end_bank:
					status = None
					# ↓↓↓ Switch ROM bank
					if self.MODE == "DMG":
						if _mbc.ResetBeforeBankChange(bank) is True:
							dprint("Resetting the MBC")
							self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
						(start_address, bank_size) = self._SelectROMBankForFlash(_mbc, bank, flashcart)
						if flashcart.PulseResetAfterWrite():
							if bank == 0:
								if self.FW["fw_ver"] < 2 and "OFW_GB_CART_MODE" in self.DEVICE_CMD:
									self._write(self.DEVICE_CMD["OFW_GB_CART_MODE"])
								else:
									self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)
								self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
						self._set_fw_variable("DMG_ROM_BANK", bank)

						buffer_len = min(buffer_len, bank_size)
						if "start_addr" in flashcart.CONFIG and bank == 0: start_address = flashcart.CONFIG["start_addr"]
						end_address = start_address + bank_size
						start_address += (buffer_pos % rom_bank_size)
						if end_address > start_address + sector[1]:
							end_address = start_address + sector[1]

					elif self.MODE == "AGB":
						if "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] > 0:
							if bank != current_bank:
								flashcart.Reset(full_reset=True)
								flashcart.SelectBankROM(bank)
								temp = end_address - start_address
								start_address %= cart_type["flash_bank_size"]
								end_address = min(cart_type["flash_bank_size"], start_address + temp)
								current_bank = bank
					# ↑↑↑ Switch ROM bank

					pos = start_address
					#dprint("pos=0x{:X}, buffer_pos=0x{:X}, start_address=0x{:X}, end_address=0x{:X}".format(pos, buffer_pos_matchcheck, start_address, end_address))
					compare_len = min(end_address - pos, len(data_import) - buffer_pos_matchcheck)
					if compare_len <= 0: break
					verified = self.CompareCRC32(buffer=data_import, offset=buffer_pos_matchcheck, length=compare_len, address=pos, flashcart=flashcart, reset=True, mbc=_mbc, bank=bank)
					self.SetProgress({"action":"UPDATE_POS", "pos":buffer_pos_matchcheck})
					if verified is not True:
						break
					buffer_pos_matchcheck += compare_len
					bank += 1

				if verified is True:
					dprint("Skipping sector #{:d}, because the CRC32 matched".format(sector_pos))
					if self.MODE == "DMG" and flashcart.FlashCommandsOnBank1(): self._SelectROMBankForFlash(_mbc, bank, flashcart)
					self.NO_PROG_UPDATE = True
					se_ret = flashcart.SectorErase(pos=pos, buffer_pos=buffer_pos, skip=verified)
					self.NO_PROG_UPDATE = False

					if self.CANCEL:
						cancel_args = {"action":"ABORT", "abortable":False}
						cancel_args.update(self.CANCEL_ARGS)
						self.CANCEL_ARGS = {}
						self.ERROR_ARGS = {}
						self.SetProgress(cancel_args)
						if self.CanPowerCycleCart(): self.CartPowerCycle()
						if self.FW["fw_ver"] >= 12: self._set_fw_variable("AGB_IRQ_ENABLED", 0)
						return

					ts_se_elapsed = time.time() - ts_se_start
					if se_ret:
						sector_size = se_ret
						dprint("Next sector size: 0x{:X}".format(sector_size))
					buffer_pos += sector_size
					continue
				else:
					verified = False
					bank = start_bank
			# ↑↑↑ Check if data matches already

			while bank < end_bank:
				if self.CANCEL:
					cancel_args = {"action":"ABORT", "abortable":False}
					cancel_args.update(self.CANCEL_ARGS)
					self.CANCEL_ARGS = {}
					self.ERROR_ARGS = {}
					self.SetProgress(cancel_args)
					if self.CanPowerCycleCart(): self.CartPowerCycle()
					if self.FW["fw_ver"] >= 12: self._set_fw_variable("AGB_IRQ_ENABLED", 0)
					return

				status = None
				# ↓↓↓ Switch ROM bank
				if self.MODE == "DMG":
					if _mbc.ResetBeforeBankChange(bank) is True:
						dprint("Resetting the MBC")
						self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
					(start_address, bank_size) = self._SelectROMBankForFlash(_mbc, bank, flashcart)
					if flashcart.PulseResetAfterWrite():
						if bank == 0:
							if self.FW["fw_ver"] < 2 and "OFW_GB_CART_MODE" in self.DEVICE_CMD:
								self._write(self.DEVICE_CMD["OFW_GB_CART_MODE"])
							else:
								self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)
							self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
					self._set_fw_variable("DMG_ROM_BANK", bank)

					buffer_len = min(buffer_len, bank_size)
					if "start_addr" in flashcart.CONFIG and bank == 0: start_address = flashcart.CONFIG["start_addr"]
					end_address = start_address + bank_size
					start_address += (buffer_pos % rom_bank_size)
					if end_address > start_address + sector[1]:
						end_address = start_address + sector[1]
					if self._ShouldApplyROMWriteBankSwitchSeparator(flashcart, command_set_type, bank, rom_write_bank_switch_conflict_values):
						_mbc.ApplyROMWriteBankSwitchSeparator(bank)

				elif self.MODE == "AGB":
					if "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] > 0:
						if bank != current_bank:
							flashcart.Reset(full_reset=True)
							flashcart.SelectBankROM(bank)
							temp = end_address - start_address
							start_address %= cart_type["flash_bank_size"]
							end_address = min(cart_type["flash_bank_size"], start_address + temp)
							current_bank = bank
				# ↑↑↑ Switch ROM bank

				skip_init = False
				pos = start_address
				dprint("buffer_pos=0x{:X}, start_address=0x{:X}, end_address=0x{:X}".format(buffer_pos, start_address, end_address))

				while pos < end_address:
					if self.CANCEL:
						cancel_args = {"action":"ABORT", "abortable":False}
						cancel_args.update(self.CANCEL_ARGS)
						self.CANCEL_ARGS = {}
						self.ERROR_ARGS = {}
						self.SetProgress(cancel_args)
						if self.CanPowerCycleCart(): self.CartPowerCycle()
						if self.FW["fw_ver"] >= 12: self._set_fw_variable("AGB_IRQ_ENABLED", 0)
						return

					if buffer_pos >= len(data_import): break
					write_len = buffer_len

					# ↓↓↓ Sector erase
					se_ret = None
					if chip_erase is False:
						if sector_pos < len(sector_offsets) and buffer_pos == sector_offsets[sector_pos][0]:
							ts_se_start = time.time()
							dprint("Erasing sector #{:d} at position 0x{:X} (0x{:X})".format(sector_pos, buffer_pos, pos))
							self.SetProgress({"action":"UPDATE_POS", "pos":buffer_pos, "force_update":True})
							if self.CanPowerCycleCart(): self.CartPowerOn()

							sector_pos += 1
							if self.MODE == "DMG" and flashcart.FlashCommandsOnBank1():
								self._SelectROMBankForFlash(_mbc, bank, flashcart)
								if self._ShouldApplyROMWriteBankSwitchSeparator(flashcart, command_set_type, bank, rom_write_bank_switch_conflict_values):
									_mbc.ApplyROMWriteBankSwitchSeparator(bank)
							self.NO_PROG_UPDATE = True
							se_ret = flashcart.SectorErase(pos=pos, buffer_pos=buffer_pos, skip=False)
							self.NO_PROG_UPDATE = False
							if "from_user" in self.CANCEL_ARGS and self.CANCEL_ARGS["from_user"]:
								continue
							if sector not in verify_sectors:
								verify_sectors.append(sector)

							ts_se_elapsed = time.time() - ts_se_start
							if se_ret:
								self.SetProgress({"action":"UPDATE_POS", "pos":buffer_pos, "sector_pos":sector_pos, "sector_erase_time":ts_se_elapsed, "force_update":True})
								sector_size = se_ret
								dprint("Next sector size: 0x{:X}".format(sector_size))
							skip_init = False
					# ↑↑↑ Sector erase

					if se_ret is not False:
						if command_set_type == "GBMEMORY" and self.FW["fw_ver"] < 2:
							status = self.WriteROM_GBMEMORY(address=pos, buffer=data_import[buffer_pos:buffer_pos+buffer_len], bank=bank)
						elif command_set_type == "GBMEMORY" and self.FW["fw_ver"] >= 2:
							status = self.WriteROM(address=pos, buffer=data_import[buffer_pos:buffer_pos+buffer_len], flash_buffer_size=flash_buffer_size, skip_init=(skip_init and not self.SKIPPING))
						elif command_set_type == "DMG-MBC5-32M-FLASH" and self.FW["fw_ver"] < 12:
							status = self.WriteROM_DMG_MBC5_32M_FLASH(address=pos, buffer=data_import[buffer_pos:buffer_pos+buffer_len], bank=bank)
						elif command_set_type == "EEPROM":
							status = self.WriteROM_DMG_EEPROM(address=pos, buffer=data_import[buffer_pos:buffer_pos+buffer_len], bank=bank, eeprom_buffer_size=256)
						elif command_set_type == "BLAZE_XPLODER":
							status = self.WriteROM_DMG_EEPROM(address=pos, buffer=data_import[buffer_pos:buffer_pos+buffer_len], bank=bank)
						elif command_set_type == "DATEL_ORBITV2" and self.FW["fw_ver"] >= 12:
							status = self.WriteROM(address=(pos | (bank << 24)), buffer=data_import[buffer_pos:buffer_pos+buffer_len], flash_buffer_size=flash_buffer_size, skip_init=(skip_init and not self.SKIPPING))
						elif command_set_type == "DATEL_ORBITV2" and self.FW["fw_ver"] < 12:
							status = self.WriteROM_DMG_DatelOrbitV2(address=pos, buffer=data_import[buffer_pos:buffer_pos+buffer_len], bank=bank)
						else:
							(write_len, max_buffer_write, write_flash_buffer_size) = self._get_flash_write_params(len(data_import), buffer_pos, buffer_len, flash_buffer_size)
							status = self.WriteROM(address=pos, buffer=data_import[buffer_pos:buffer_pos+write_len], flash_buffer_size=write_flash_buffer_size, skip_init=(skip_init and not self.SKIPPING), rumble_stop=rumble, max_length=max_buffer_write)

					if status is False or se_ret is False:
						self.CANCEL = True
						self.ERROR = True
						sr = c__("Status Register", "Unknown")
						if self.FW["fw_ver"] >= 12:
							if se_ret is False:
								sr = flashcart.LAST_SR
								if isinstance(sr, int):
									if sr < 0x100:
										sr = f"0x{sr:02X} ({sr>>4:04b} {sr&0xF:04b})"
									else:
										sr = f"0x{sr:04X} ({sr>>8:08b} {sr&0xFF:08b})"
							else:
								lives = 3
								while lives > 0:
									dprint("Retrieving last status register value...")
									self.DEVICE.reset_input_buffer()
									self.DEVICE.reset_output_buffer()
									sr = self._get_fw_variable("STATUS_REGISTER")
									if sr not in (False, None):
										if sr < 0x100:
											sr = f"0x{sr:02X} ({sr>>4:04b} {sr&0xF:04b})"
										else:
											sr = f"0x{sr:04X} ({sr>>8:08b} {sr&0xFF:08b})"
										break
									dprint("Erroneous response:", sr)
									lives -= 1
								if lives == 0:
									sr = c__("Status Register", "Timeout")
						dprint("Last status register value:", sr)

						if "from_user" in self.CANCEL_ARGS and self.CANCEL_ARGS["from_user"]:
							break
						elif not self.DEVICE.is_open or self.DEVICE is None:
							self.CANCEL_ARGS.update({
								"info_type": "msgbox_critical",
								"info_msg": \
									__(
										"An error occured while writing {buffer_len} bytes at position {buffer_pos} ({file_size}). Please re-connect the device and try again from the beginning.",
										buffer_len=f"0x{buffer_len:X}", buffer_pos=f"0x{buffer_pos:X}", file_size=Formatter.file_size(buffer_pos, as_int=False)
									)
									+ "\n\n"
									+ __(
										"Troubleshooting advice:\n"
										"- Clean cartridge contacts\n"
										"- Check soldering if it’s a DIY cartridge\n"
										"- Avoid passive USB hubs and try different USB ports/cables\n"
										"- Check flashcart profile selection"
									)
									+ errmsg_mbc_selection + "\n\n"
									+ __("Status Register:") + " " + sr
							})
							break
						else:
							if chip_erase: retry_hp = 0
							if "iteration" in self.ERROR_ARGS and self.ERROR_ARGS["iteration"] > 0:
								retry_hp -= 5
								if retry_hp <= 0:
									self.CANCEL_ARGS.update({
										"info_type": "msgbox_critical",
										"info_msg": \
											__(
												"Unstable connection detected while writing {buffer_len} bytes in iteration {iteration} at position {buffer_pos} ({file_size}). Please re-connect the device and try again from the beginning.",
												buffer_len="0x{:X}".format(buffer_len), iteration=self.ERROR_ARGS["iteration"], buffer_pos="0x{:X}".format(buffer_pos), file_size=Formatter.file_size(buffer_pos, as_int=False)
											)
											+ "\n\n"
											+ __(
												"Troubleshooting advice:\n"
												"- Clean cartridge contacts\n"
												"- Check soldering if it’s a DIY cartridge\n"
												"- Avoid passive USB hubs and try different USB ports/cables"
											)
											+ "\n\n"
											+ __("Status Register:") + " " + sr
									})
									continue
							else:
								retry_hp -= 10
								if retry_hp <= 0:
									enable_pullup_wr_str = " (+ WR pullup)" if enable_pullup_wr == 2 else ""
									self.CANCEL_ARGS.update({
										"info_type": "msgbox_critical",
										"info_msg": \
											__(
												"An error occured while writing {buffer_len} bytes at position {buffer_pos} ({file_size}). Please re-connect the device and try again from the beginning.",
												buffer_len=f"0x{buffer_len:X}", buffer_pos=f"0x{buffer_pos:X}", file_size=Formatter.file_size(buffer_pos, as_int=False)
											)
											+ "\n\n"
											+ __(
												"Troubleshooting advice:\n"
												"- Clean cartridge contacts\n"
												"- Check soldering if it’s a DIY cartridge\n"
												"- Avoid passive USB hubs and try different USB ports/cables\n"
												"- Check cartridge ROM storage size (at least {rom_size} is required){errmsg}\n"
												"- Check flashcart profile used: {cart_name}{enable_pullup_wr_str}\n"
												"- The cartridge may also be incompatible with your {device_name} device",
												rom_size=Formatter.file_size(len(data_import), as_int=False), errmsg=errmsg_mbc_selection, cart_name=cart_name, enable_pullup_wr_str=enable_pullup_wr_str, device_name=self.GetFullNameLabel()
											)
											+ "\n\n"
											+ __("Status Register:") + " " + sr,
										"abortable": False
									})
									continue

							rev_buffer_pos = sector_offsets[sector_pos - 1][0]
							buffer_pos = rev_buffer_pos
							bank = start_bank
							sector_pos -= 1
							err_text = __("Write error! Retrying from {address}...", address="0x{:X}".format(rev_buffer_pos))
							print(ANSI.YELLOW + err_text + ANSI.RESET)
							dprint("Bank {:d} | HP: {:d}/100".format(bank, retry_hp))
							pos = end_address
							status = False

							self.SetProgress({"action":"ERROR", "abortable":True, "pos":buffer_pos, "text":err_text})
							delay = 0.5 # + (100-retry_hp)/100
							if self.CanPowerCycleCart():
								self.CartPowerOff()
								time.sleep(delay)
								self.CartPowerOn()
								if self.MODE == "DMG" and _mbc.HasFlashBanks(): _mbc.SelectBankFlash(bank)
							time.sleep(delay)
							if self.DEVICE is None:
								raise ConnectionAbortedError(__(
									"A critical connection error occured while writing {buffer_len} bytes at position {buffer_pos} ({file_size}). Please re-connect the device and try again from the beginning.",
									buffer_len="0x{:X}".format(buffer_len),
									buffer_pos="0x{:X}".format(buffer_pos),
									size="0x{:X}".format(buffer_len),
									pos="0x{:X}".format(buffer_pos),
									file_size=Formatter.file_size(buffer_pos, as_int=False)
								))

							self.ERROR = False
							if "from_user" in self.CANCEL_ARGS and self.CANCEL_ARGS["from_user"]:
								self.CANCEL_ARGS.update({
									"info_type": "msgbox_warning",
									"info_msg": __("The erroneous process has been stopped."),
									"abortable": False
								})
								break
							self.CANCEL = False
							self.CANCEL_ARGS = {}
							self.DEVICE.reset_input_buffer()
							self.DEVICE.reset_output_buffer()
							self._cart_write(pos, 0xF0)
							self._cart_write(pos, 0xFF)
							if flashcart.Unlock() is False: return False
							continue

					skip_init = True

					buffer_pos += write_len
					pos += write_len
					self.SetProgress({"action":"UPDATE_POS", "pos":buffer_pos})

				if status is not False:
					bank += 1
			first_sector_written = True

		self.SetProgress({"action":"UPDATE_POS", "pos":len(data_import), "force_update":True})
		# ↑↑↑ Flash write

		# ↓↓↓ GB-Memory Hidden Sector
		if command_set_type == "GBMEMORY":
			if flashcart.EraseHiddenSector(buffer=data_map_import) is False:
				return False
			status = self.WriteROM_GBMEMORY(address=0, buffer=data_map_import[0:128], bank=1)
			if status is False:
				self.SetProgress({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":__("An error occured while writing the hidden sector. Please make sure that the cartridge contacts are clean, re-connect the device and try again from the beginning."), "abortable":False})
				return False
		# ↑↑↑ GB-Memory Hidden Sector

		# ↓↓↓ Reset flash
		flashcart.Reset(full_reset=True)
		if self.FW["fw_ver"] >= 14 and "set_audio_high" in cart_type:
			self._set_fw_variable("DMG_AUDIO_ENABLED", 0)
		# ↑↑↑ Reset flash

		# ↓↓↓ Flash verify
		verified = False
		crc32_errors = 0
		if "broken_sectors" in self.INFO: del(self.INFO["broken_sectors"])
		if "verify_write" in args and args["verify_write"] is True:
			self.SetProgress({"action":"INITIALIZE", "method":"ROM_WRITE_VERIFY", "size":len(data_import), "flash_offset":flash_offset, "voltage":active_voltage})
			if ".dev" in AppInfo.VERSION_PEP440 or AppContext.DEBUG:
				with open(AppContext.CONFIG_PATH + os.sep + "debug_verify.bin", "wb") as f: pass

			current_bank = None
			broken_sectors = []

			for sector in verify_sectors:
				if self.CANCEL:
					cancel_args = {"action":"ABORT", "abortable":False}
					cancel_args.update(self.CANCEL_ARGS)
					self.CANCEL_ARGS = {}
					self.ERROR_ARGS = {}
					self.SetProgress(cancel_args)
					if self.CanPowerCycleCart(): self.CartPowerCycle()
					if self.FW["fw_ver"] >= 12: self._set_fw_variable("AGB_IRQ_ENABLED", 0)
					return

				if sector[0] >= len(data_import): break

				verified = False
				if self.FW["fw_ver"] >= 10 and not (flashcart and cart_type["command_set"] == "GBAMP"):
					if self.MODE == "AGB":
						dprint("Verifying sector:", hex(sector[0]), hex(sector[1]))
						buffer_pos = sector[0]
						start_address = buffer_pos
						end_address = sector[0] + sector[1]
						if not chip_erase:
							sector_pos = sector_offsets.index(sector[:2])
						else:
							sector_pos = 0
						start_bank = math.floor(buffer_pos / rom_bank_size)
						end_bank = math.ceil((buffer_pos + sector[1]) / rom_bank_size)
					elif self.MODE == "DMG":
						dprint("Verifying sector:", hex(sector[0]), hex(sector[1]))
						buffer_pos = sector[0]
						if not chip_erase:
							sector_pos = sector_offsets.index(sector[:2])
						else:
							sector_pos = 0
						start_bank = math.floor(buffer_pos / rom_bank_size)
						end_bank = math.ceil((buffer_pos + sector[1]) / rom_bank_size)

					bank = start_bank
					while bank < end_bank:
						# ↓↓↓ Switch ROM bank
						if self.MODE == "DMG":
							if _mbc.ResetBeforeBankChange(bank) is True:
								dprint("Resetting the MBC")
								self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
							(start_address, bank_size) = _mbc.SelectBankROM(bank)
							verify_len = bank_size
							if flashcart.PulseResetAfterWrite():
								if bank == 0:
									if self.FW["fw_ver"] < 2 and "OFW_GB_CART_MODE" in self.DEVICE_CMD:
										self._write(self.DEVICE_CMD["OFW_GB_CART_MODE"])
									else:
										self._write(self.DEVICE_CMD["SET_MODE_DMG"], wait=self.FW["fw_ver"] >= 12)
									self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
							self._set_fw_variable("DMG_ROM_BANK", bank)

							buffer_len = min(buffer_len, bank_size)
							if "start_addr" in flashcart.CONFIG and bank == 0: start_address = flashcart.CONFIG["start_addr"]
							end_address = start_address + bank_size
							start_address += (buffer_pos % rom_bank_size)
							if end_address > start_address + sector[1]:
								end_address = start_address + sector[1]
							pos_from = (bank * start_address)

						elif self.MODE == "AGB":
							if "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] > 0:
								if bank != current_bank:
									flashcart.Reset(full_reset=True)
									flashcart.SelectBankROM(bank)
									temp = end_address - start_address
									start_address %= cart_type["flash_bank_size"]
									end_address = min(cart_type["flash_bank_size"], start_address + temp)
									current_bank = bank
							pos_from = sector[0]
							verify_len = min(sector[1], max(0, len(data_import) - pos_from))
						# ↑↑↑ Switch ROM bank

						dprint(f"Verifying ROM bank #{bank} at 0x{pos_from:x} (physical 0x{start_address:X}, 0x{verify_len:X} bytes)")

						verified = False
						if self.FW["fw_ver"] >= 12 and sector[1] >= verify_len and crc32_errors < 5:
							verified = self.CompareCRC32(buffer=data_import, offset=pos_from, length=verify_len, address=start_address, flashcart=flashcart, reset=False, mbc=_mbc, bank=bank)
							if verified is True:
								dprint("CRC32 verification successful between 0x{:X} and 0x{:X}".format(pos_from, verify_len))
								self.SetProgress({"action":"UPDATE_POS", "pos":pos_from + verify_len})
							elif verified is not True and len(verified) == 2:
								crc32_errors += 1
								dprint("Mismatch during CRC32 verification at 0x{:X}".format(pos_from), "Errors:", crc32_errors)
								verified = False
								break

							if verified is False: break

						else:
							self.SetProgress({"action":"UPDATE_POS", "pos":buffer_pos})

						bank += 1

				if not verified:
					verify_args = copy.copy(args)
					verify_args.update({"verify_write":data_import[sector[0]:sector[0]+sector[1]], "rom_size":len(data_import), "verify_from":sector[0], "path":"", "rtc_area":flashcart.HasRTC(), "verify_mbc":_mbc})
					verify_args["verify_base_pos"] = sector[0]
					verify_args["verify_len"] = len(verify_args["verify_write"])
					verify_args["rom_size"] = len(verify_args["verify_write"])

					self.NO_PROG_UPDATE = True
					self.ReadROM(0, 4) # dummy read
					self.NO_PROG_UPDATE = False
					start_address = 0
					end_address = buffer_pos

					verified_size = self._BackupROM(verify_args)
					if isinstance(verified_size, int): dprint("args[\"verify_len\"]=0x{:X}, verified_size=0x{:X}".format(verify_args["verify_len"], verified_size))
					if self.CANCEL or self.ERROR:
						cancel_args = {"action":"ABORT", "abortable":False}
						cancel_args.update(self.CANCEL_ARGS)
						self.CANCEL_ARGS = {}
						self.ERROR_ARGS = {}
						self.SetProgress(cancel_args)
						if self.CanPowerCycleCart(): self.CartPowerCycle()
						if self.FW["fw_ver"] >= 12: self._set_fw_variable("AGB_IRQ_ENABLED", 0)
						verified = False
						return
					elif (verified_size is not True) and (verify_args["verify_len"] != verified_size):
						if verified_size is None:
							dprint("Verification failed! Sector: {sector}", sector=str(sector))
						else:
							dprint("Verification failed at {address}! Sector: {sector}", address="0x{:X}".format(sector[0]+verified_size), sector=str(sector))
						if sector not in broken_sectors:
							broken_sectors.append(sector)
						continue
					else:
						dprint("Verification between 0x{:X} and 0x{:X} successful by normal reading.".format(sector[0], sector[0]+sector[1]))
						verified = True

			self.SetProgress({"action":"UPDATE_POS", "pos":len(data_import), "force_update":True, "skipping":self.POS < len(data_import)})
			if len(broken_sectors) > 0:
				self.INFO["broken_sectors"] = broken_sectors
				self.INFO["verify_error_params"] = {}
				self.INFO["verify_error_params"]["rom_size"] = len(data_import)
				if self.MODE == "DMG":
					self.INFO["verify_error_params"]["mapper_name"] = _mbc.GetName()
					if flashcart.GetMBC() == "manual":
						self.INFO["verify_error_params"]["mapper_selection_type"] = 1 # manual
					else:
						self.INFO["verify_error_params"]["mapper_selection_type"] = 2 # forced by cart type
					self.INFO["verify_error_params"]["mapper_max_size"] = _mbc.GetMaxROMSize()
				verified = False
		# ↑↑↑ Flash verify

		if delta_state_new is not None and not chip_erase and not "broken_sectors" in self.INFO:
			try:
				with open(json_file, "wb") as f:
					f.write(json.dumps(delta_state_new).encode("UTF-8-SIG"))
			except PermissionError:
				print(__("Error: Couldn’t update write-protected file “{file}”", file=json_file))

		# ↓↓↓ Switch to first ROM bank
		if self.MODE == "DMG":
			if _mbc.ResetBeforeBankChange(0) is True:
				dprint("Resetting the MBC")
				self._write(self.DEVICE_CMD["DMG_MBC_RESET"], wait=True)
			_mbc.SelectBankROM(0)
			self._set_fw_variable("DMG_ROM_BANK", 0)
		elif self.MODE == "AGB":
			if "flash_bank_select_type" in cart_type and cart_type["flash_bank_select_type"] > 0:
				flashcart.SelectBankROM(0)
		# ↑↑↑ Switch to first ROM bank

		self.SetMode(self.MODE)

		if not "photo_mode" in args:
			self.INFO["last_action"] = self.INFO["action"]
			self.INFO["action"] = None
			self._thread_worker_auto_poweroff_finish()
			self.SetProgress({"action":"FINISHED", "verified":verified})
		return True

	#################################################################

	def TransferData(self, args, signal):
		self.ERROR = False
		self.CANCEL = False
		self.CANCEL_ARGS = {}
		self.READ_ERRORS = 0
		self.WRITE_ERRORS = 0

		if self.IsConnected():
			if self.CanPowerCycleCart():
				self.CartPowerOn()

			ret = False
			self.SIGNAL = signal
			try:
				temp = copy.copy(args)
				if "buffer" in temp: temp["buffer"] = "(0x{:x} bytes of data)".format(len(temp["buffer"]))
				dprint("args:", temp)
				del(temp)
				self.NO_PROG_UPDATE = False
				if args['mode'] == 1: ret = self._BackupROM(args)
				elif args['mode'] == 2: ret = self._BackupRestoreRAM(args)
				elif args['mode'] == 3: ret = self._BackupRestoreRAM(args)
				elif args['mode'] == 4:
					voltage_fallback = args.get("voltage_fallback", False)
					ask_voltage_fallback = args.get("ask_voltage_fallback", False)
					if voltage_fallback:
						self.VOLTAGE_FALLBACK_PENDING = True
						self.VOLTAGE_FALLBACK_TRIGGERED = False
					try:
						ret = self._FlashROM(args)
					finally:
						self.VOLTAGE_FALLBACK_PENDING = False
					if voltage_fallback and self.VOLTAGE_FALLBACK_TRIGGERED:
						self.VOLTAGE_FALLBACK_TRIGGERED = False
						self.CANCEL = False
						self.ERROR = False
						self.CANCEL_ARGS = {}
						self.ERROR_ARGS = {}
						if ask_voltage_fallback:
							self.USER_ANSWER = None
							self.SetProgress({
								"action":"USER_ACTION",
								"user_action":"RETRY_5V",
								"title":__("Retry at 5V?"),
								"msg":__("Writing at 3.3V failed. Do you want to retry at 5V? Some cartridges of the same kind require 5V for successful writing, but please note that 5V can be unsafe for some flash chips.")
							})
							while self.USER_ANSWER is None:
								dprint("Waiting for the user to confirm retrying the ROM write at 5V.")
								time.sleep(1)
							if self.USER_ANSWER is not True:
								self.USER_ANSWER = None
								self.SetProgress({"action":"ABORT", "abortable":False})
								ret = False
							else:
								self.USER_ANSWER = None
								args["override_voltage"] = voltage_fallback
								args["voltage_fallback"] = False
								print(ANSI.YELLOW + __("Note: Writing at 3.3V failed. Retrying at 5V...") + ANSI.RESET)
								self.SetProgress({"action":"UPDATE_INFO", "abortable":False, "text":__("Switching voltage..."), "pos":0, "size":0})
								#if self.CanPowerCycleCart(): self.CartPowerCycle()
								ret = self._FlashROM(args)
						else:
							args["override_voltage"] = voltage_fallback
							args["voltage_fallback"] = False
							print(ANSI.YELLOW + __("Note: Writing at 3.3V failed. Retrying at 5V...") + ANSI.RESET)
							self.SetProgress({"action":"UPDATE_INFO", "abortable":False, "text":__("Switching voltage..."), "pos":0, "size":0})
							#if self.CanPowerCycleCart(): self.CartPowerCycle()
							ret = self._FlashROM(args)
				elif args['mode'] == 5: ret = self._DetectCartridge(args)
				elif args['mode'] == 0xFF: self.Debug()
				self.USER_ANSWER = None
				if self.FW is None: return False
				if self.FW["fw_ver"] >= 2 and self.FW["pcb_name"] == "GBxCart RW":
					if ret is True and "OFW_DONE_LED_ON" in self.DEVICE_CMD:
						self._write(self.DEVICE_CMD["OFW_DONE_LED_ON"])
					elif self.ERROR is True and "OFW_ERROR_LED_ON" in self.DEVICE_CMD:
						self._write(self.DEVICE_CMD["OFW_ERROR_LED_ON"])

			except serial.serialutil.SerialTimeoutException as _:
				self.VOLTAGE_FALLBACK_PENDING = False
				print(__("Connection timed out. Please reconnect the device."))
				return False
			except serial.serialutil.PortNotOpenError as _:
				self.VOLTAGE_FALLBACK_PENDING = False
				print(__("Connection closed."))
				return False

			return True
