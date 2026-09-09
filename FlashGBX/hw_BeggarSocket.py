# -*- coding: utf-8 -*-
# FlashGBX

# pylint: disable=wildcard-import, unused-wildcard-import
import math, os, struct, time
from serial import SerialException
from .LK_Device import *
from .IniSettings import IniSettings
from .i18n import __


class GbxDevice(LK_Device):
	DEVICE_NAME = "Beggar Socket"
	DEVICE_LABEL_LONG = "Beggar Socket / ChisFlash GBA Burner"
	DEVICE_LABEL_SHORT = "Beggar Socket"
	DEVICE_SUPPORT_MESSAGE = "Beggar Socket support uses the USB CDC MCU firmware protocol from the chis_flash_burner example."
	PCB_VERSIONS = { 1:"" }
	BAUDRATE = 9600
	MAX_BUFFER_READ = 0x1000
	MAX_BUFFER_WRITE = 0x1000
	MAX_PACKET_PAYLOAD = 5000

	ACK_OK = 0xAA
	CMD_PROTOCOL_INFO = 0xE0
	CMD_GBA_ROM_PROGRAM_INTEL = 0xE1
	CMD_CART_POWER = 0xA0
	CMD_CART_PHI_DIV = 0xA1
	CMD_GBA_ROM_ID = 0xF0
	CMD_GBA_ROM_PROGRAM = 0xF4
	CMD_GBA_ROM_WRITE = 0xF5
	CMD_GBA_ROM_READ = 0xF6
	CMD_GBA_RAM_WRITE = 0xF7
	CMD_GBA_RAM_READ = 0xF8
	CMD_GBA_RAM_PROGRAM_FLASH = 0xF9
	CMD_GBC_WRITE = 0xFA
	CMD_GBC_READ = 0xFB
	CMD_GBC_ROM_PROGRAM = 0xFC

	CAP_GBA_ROM_PROGRAM_INTEL = 0x00000010

	def __init__(self):
		self.CART_POWERED = False
		self.VOLTAGE = 3.3
		self.PROTOCOL_MODE = "auto"
		self.USB_INFO = {}
		self.FLASH_COMMAND_SET = 0
		self._SET_FLASH_CMD_BYTES = None

	def Initialize(self, flashcarts, port=None, max_baud=2000000):
		if self.IsConnected(): self.DEVICE.close()
		conn_msg = []
		ports = []
		port_infos = {}
		if port is not None:
			ports = [ port ]
			for comport in serial.tools.list_ports.comports():
				if comport.device == port:
					port_infos[port] = self._get_usb_info(comport)
					break
		else:
			comports = serial.tools.list_ports.comports()
			for comport in comports:
				if comport.vid == 0x0483 and comport.pid == 0x0721:
					ports.append(comport.device)
					port_infos[comport.device] = self._get_usb_info(comport)
			if len(ports) == 0: return False

		for candidate in ports:
			try:
				dev = serial.Serial(candidate, self.BAUDRATE, timeout=0.1, exclusive=True)
			except (SerialException, OSError) as e:
				if "Permission" in str(e):
					conn_msg.append([3, __("The device on port {port} couldn't be accessed. Make sure your user account has permission to use it and it's not already in use by another application.", port=candidate)])
				continue

			self.DEVICE = dev
			self.PORT = candidate
			self.USB_INFO = port_infos.get(candidate, {})
			self._reset_command_buffer()
			if not self.LoadFirmwareVersion():
				dev.close()
				self.DEVICE = None
				continue

			dprint(f"Found a {self.DEVICE_NAME}")
			dprint("Firmware information:", self.FW)
			self.DEVICE.timeout = self.DEVICE_TIMEOUT
			self.UpdateFlashCarts(flashcarts)
			break

		return conn_msg

	def _get_usb_info(self, comport):
		info = {}
		for key in ("manufacturer", "product", "serial_number", "description", "hwid", "interface"):
			info[key] = getattr(comport, key, None) or ""
		return info

	def LoadFirmwareVersion(self):
		self.FW = {
			"cfw_id":"B",
			"fw_ver":1,
			"pcb_ver":1,
			"fw_ts":0,
			"fw_dt":__("MCU protocol"),
			"ofw_ver":None,
			"pcb_name":self.DEVICE_NAME,
			"cart_power_ctrl":True,
			"bootloader_reset":False,
		}
		self.PROTOCOL_CAPS = 0
		self.LEGACY_MCU_PROTOCOL = True
		self.FW["fw_dt"] = __("legacy MCU protocol")
		self.PROTOCOL_MODE = self._get_protocol_mode()
		if self.PROTOCOL_MODE == "auto":
			if self._usb_info_has_patched_marker():
				self.PROTOCOL_MODE = "patched"
				dprint("Beggar Socket patched protocol marker detected in USB descriptor.")
			else:
				self.PROTOCOL_MODE = "stock"
				dprint("Beggar Socket patched protocol marker not detected; using stock-safe protocol.")
		if self.PROTOCOL_MODE == "patched":
			info = self._packet_read(self.CMD_PROTOCOL_INFO, bytearray(), 12, timeout=0.25)
			if len(info) == 12:
				magic, protocol_version, max_packet_size, capabilities = struct.unpack("<IHHI", info)
				if magic == 0x58424742:
					self.LEGACY_MCU_PROTOCOL = False
					self.PROTOCOL_CAPS = capabilities
					self.FW["fw_ver"] = protocol_version
					self.FW["fw_dt"] = __("MCU protocol v{version}", version=protocol_version)
					self.MAX_PACKET_PAYLOAD = min(self.MAX_PACKET_PAYLOAD, max_packet_size - 4)
					dprint("Beggar Socket protocol capabilities:", "0x{:08X}".format(capabilities))
			if self.LEGACY_MCU_PROTOCOL:
				dprint("Beggar Socket patched protocol was requested, but the protocol query failed; using legacy-compatible fallback.")
		else:
			# Stock MCU firmware has no default-command recovery: an unsupported
			# command sets its busy flag and it ignores later USB packets until reset.
			# Do not probe 0xE0 unless the user explicitly opts into patched mode.
			dprint("Beggar Socket using legacy-compatible MCU protocol.")
		return True

	def _get_protocol_mode(self):
		try:
			settings = IniSettings(path=AppContext.CONFIG_PATH + os.sep + "settings.ini")
			mode = str(settings.value("BeggarSocketProtocol", default="auto")).strip().lower()
		except Exception as e:
			dprint("Beggar Socket protocol setting read failed:", str(e))
			mode = "auto"
		if mode not in ("auto", "stock", "patched"):
			mode = "auto"
		return mode

	def _usb_info_has_patched_marker(self):
		info = " ".join(str(self.USB_INFO.get(key, "")) for key in ("product", "description", "interface", "serial_number"))
		info = info.lower()
		return (
			"flashgbx" in info or
			"mcu protocol" in info or
			"beggar socket patched" in info or
			"beggar socket v" in info
		)

	def CheckActive(self):
		return self.DEVICE is not None and self.DEVICE.is_open

	def GetFirmwareVersion(self, more=False):
		return "MCU"

	def GetFullName(self):
		return self.DEVICE_NAME

	def GetFullNameExtended(self, more=False):
		return __("{device_name} - Firmware {fw_version} ({port})", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), port=self.GetPort())

	def ChangeBaudRate(self, _):
		dprint("Baudrate change is not supported.")

	def CanSetVoltageBySwitch(self):
		return False

	def CanSetVoltageByCode(self):
		return True

	def CanSetVoltageByAutoswitch(self):
		return False

	def CanPowerCycleCart(self):
		return True

	def GetSupprtedModes(self):
		return ["DMG", "AGB"]

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
		return False

	def BootloaderReset(self):
		return False

	def SupportsAudioAsWe(self):
		return False

	def _reset_command_buffer(self):
		if self.DEVICE is None: return
		self.DEVICE.rts = True
		self.DEVICE.dtr = True
		self.DEVICE.rts = False
		self.DEVICE.dtr = False
		time.sleep(0.01)

	def _packet_write(self, payload):
		if not isinstance(payload, bytearray):
			payload = bytearray(payload)
		packet_size = 2 + len(payload) + 2
		packet = bytearray(struct.pack("<H", packet_size))
		packet.extend(payload)
		packet.extend(b"\x00\x00")
		if len(packet) > 64:
			dprint("Beggar Socket packet write:", packet[:32].hex(), "...", packet[-8:].hex(), "len=0x{:X}".format(len(packet)))
		else:
			dprint("Beggar Socket packet write:", packet.hex())
		self.DEVICE.write(packet)
		self.DEVICE.flush()

	def _packet_ack(self, command, payload=None, timeout=None):
		if payload is None: payload = bytearray()
		old_timeout = self.DEVICE.timeout
		if timeout is not None: self.DEVICE.timeout = timeout
		ack = bytearray()
		try:
			self._packet_write(bytearray([command]) + bytearray(payload))
			ack = self.DEVICE.read(1)
		except (SerialException, OSError) as e:
			dprint("Beggar Socket command exception:", hex(command), str(e))
			ack = bytearray()
		if timeout is not None and self.DEVICE is not None and self.DEVICE.is_open:
			try:
				self.DEVICE.timeout = old_timeout
			except (SerialException, OSError) as e:
				dprint("Beggar Socket timeout restore exception:", str(e))
		if len(ack) != 1 or ack[0] != self.ACK_OK:
			dprint("Beggar Socket command failed:", hex(command), ack)
			self._reset_command_buffer()
			return False
		return 1

	def _packet_read(self, command, payload, length, timeout=None):
		old_timeout = self.DEVICE.timeout
		if timeout is not None: self.DEVICE.timeout = timeout
		data = bytearray()
		try:
			self._packet_write(bytearray([command]) + bytearray(payload))
			data = self.DEVICE.read(length + 2)
		except (SerialException, OSError) as e:
			dprint("Beggar Socket read exception:", hex(command), str(e))
			data = bytearray()
		if timeout is not None and self.DEVICE is not None and self.DEVICE.is_open:
			try:
				self.DEVICE.timeout = old_timeout
			except (SerialException, OSError) as e:
				dprint("Beggar Socket timeout restore exception:", str(e))
		if len(data) != length + 2:
			dprint("Beggar Socket read failed:", hex(command), len(data), "of", length + 2, data.hex())
			self._reset_command_buffer()
			return bytearray()
		return bytearray(data[2:])

	def _cart_power(self, enable=True, voltage_5v=False):
		if voltage_5v:
			self.VOLTAGE = 5
		else:
			self.VOLTAGE = 3.3
		self.CART_POWERED = enable
		# The referenced MCU firmware does not handle 0xA0 in uart_cmdHandler().
		# Sending it leaves the command buffer uncleared and breaks the next packet.
		dprint("Beggar Socket power state tracked locally:", enable, self.VOLTAGE)
		return 1

	def _set_phi_div(self, div):
		# Same as 0xA0: present in the C# helper, absent from the MCU switch.
		dprint("Ignoring unsupported Beggar Socket PHI divider command:", div)
		return 1

	def _write(self, data, wait=False):
		if not isinstance(data, bytearray):
			data = bytearray([data])
		if len(data) != 1:
			dprint("Ignoring unsupported raw Beggar Socket write:", data.hex())
			return 1 if wait else None

		command = data[0]
		if self._SET_FLASH_CMD_BYTES is not None:
			self._SET_FLASH_CMD_BYTES.append(command)
			if len(self._SET_FLASH_CMD_BYTES) == 1:
				self.FLASH_COMMAND_SET = command
				dprint("Beggar Socket FlashGBX command set:", command)
			if len(self._SET_FLASH_CMD_BYTES) >= 3:
				self._SET_FLASH_CMD_BYTES = None
			return 1 if wait else None
		if command == self.DEVICE_CMD["SET_FLASH_CMD"]:
			self._SET_FLASH_CMD_BYTES = []
			return 1 if wait else None
		if command == self.DEVICE_CMD["SET_MODE_DMG"]:
			self.MODE = "DMG"
			return 1
		if command == self.DEVICE_CMD["SET_MODE_AGB"]:
			self.MODE = "AGB"
			return 1
		if command == self.DEVICE_CMD["SET_VOLTAGE_5V"]:
			return self._cart_power(True, True)
		if command == self.DEVICE_CMD["SET_VOLTAGE_3_3V"]:
			return self._cart_power(True, False)
		if command == self.DEVICE_CMD["CART_PWR_ON"]:
			return self._cart_power(True, self.VOLTAGE == 5)
		if command == self.DEVICE_CMD["CART_PWR_OFF"]:
			return self._cart_power(False, self.VOLTAGE == 5)
		if command == self.DEVICE_CMD["QUERY_CART_PWR"]:
			self._QUERY_CART_PWR_PENDING = True
			return None
		if command in (
			self.DEVICE_CMD["DMG_MBC_RESET"],
			self.DEVICE_CMD["AGB_BOOTUP_SEQUENCE"],
			self.DEVICE_CMD["ENABLE_PULLUPS"],
			self.DEVICE_CMD["DISABLE_PULLUPS"],
			self.DEVICE_CMD["SET_ADDR_AS_INPUTS"],
		):
			return 1 if wait else None
		dprint("Ignoring unsupported Beggar Socket firmware command:", hex(command))
		return 1 if wait else None

	def _read(self, count):
		if getattr(self, "_QUERY_CART_PWR_PENDING", False):
			self._QUERY_CART_PWR_PENDING = False
			if count == 1:
				return 1 if self.CART_POWERED else 0
			return bytearray([1 if self.CART_POWERED else 0] + ([0] * (count - 1)))
		return super()._read(count)

	def _get_fw_variable(self, key):
		return self.FW_VAR.get(key, 0)

	def _set_fw_variable(self, key, value):
		self.FW_VAR[key] = value
		return 1

	def SetMode(self, mode, delay=0.1):
		if mode == "DMG":
			self.MODE = "DMG"
			self._cart_power(True, True)
		elif mode == "AGB":
			self.MODE = "AGB"
			self._cart_power(True, False)
		self._set_fw_variable("CART_MODE", 1 if mode == "DMG" else 2)
		self._set_fw_variable("ADDRESS", 0)
		time.sleep(delay)

	def CartPowerOn(self):
		return self._cart_power(True, self.VOLTAGE == 5)

	def CartPowerOff(self):
		return self._cart_power(False, self.VOLTAGE == 5)

	def CartPowerCycle(self):
		self.CartPowerOff()
		time.sleep(0.05)
		self.CartPowerOn()

	def Close(self, cartPowerOff=False):
		if self.DEVICE is not None and self.DEVICE.is_open:
			try:
				if cartPowerOff:
					self.CartPowerOff()
				self.DEVICE.close()
			except:
				self.DEVICE = None
		self.MODE = None

	def _read_gba_rom_even(self, address, length):
		read_length = length if length % 2 == 0 else length + 1
		payload = struct.pack("<IH", address, read_length)
		return self._packet_read(self.CMD_GBA_ROM_READ, payload, read_length)[:length]

	def _write_gba_rom_words(self, word_address, data):
		if len(data) % 2 != 0:
			data += b"\xFF"
		payload = bytearray(struct.pack("<I", word_address))
		payload.extend(data)
		return self._packet_ack(self.CMD_GBA_ROM_WRITE, payload)

	def _read_gba_status_word(self, address):
		data = self._read_gba_rom_even(address, 2)
		if data is False or len(data) < 2:
			return False
		return struct.unpack("<H", data)[0]

	def _wait_gba_intel_status(self, address, expected=0x80, mask=0xFFFF, timeout=5.0):
		deadline = time.time() + timeout
		last_status = None
		while time.time() < deadline:
			status = self._read_gba_status_word(address)
			if status is False:
				return False
			last_status = status
			if status & mask == expected:
				return True
			time.sleep(0.005)
		dprint("Beggar Socket Intel flash status timeout:", "address=0x{:X}".format(address), "last=0x{:X}".format(last_status if last_status is not None else 0))
		return False

	def _get_gba_intel_sector_base(self, address):
		if address >= 0x1FE0000:
			return address & ~0x7FFF
		return address & ~0x1FFFF

	def _write_gba_rom_intel_buffered(self, address, data, flash_buffer_size):
		if flash_buffer_size <= 0:
			return self._write_gba_rom_intel_single(address, data)

		if flash_buffer_size % 2 != 0:
			flash_buffer_size -= 1
		if flash_buffer_size <= 0:
			return False

		pos = 0
		while pos < len(data):
			chunk = bytearray(data[pos:pos+flash_buffer_size])
			if len(chunk) % 2 != 0:
				chunk.append(0xFF)
			if chunk == bytearray([0xFF] * len(chunk)):
				pos += len(chunk)
				continue

			write_address = address + pos
			sector_address = self._get_gba_intel_sector_base(write_address)
			word_count = len(chunk) // 2

			if self._cart_write(sector_address, 0xE8, flashcart=True) is False:
				return False
			if not self._wait_gba_intel_status(sector_address, expected=0x80, mask=0xFFFF, timeout=2.0):
				return False
			if self._cart_write(sector_address, word_count - 1, flashcart=True) is False:
				return False
			if self._write_gba_rom_words(write_address >> 1, chunk) is False:
				return False
			if self._cart_write(sector_address, 0xD0, flashcart=True) is False:
				return False
			if not self._wait_gba_intel_status(sector_address, expected=0x80, mask=0xFFFF, timeout=10.0):
				return False
			if self._cart_write(sector_address, 0xFF, flashcart=True) is False:
				return False

			pos += len(chunk)
		return 1

	def _write_gba_rom_intel_single(self, address, data):
		pos = 0
		while pos < len(data):
			chunk = bytearray(data[pos:pos+2])
			if len(chunk) < 2:
				chunk.append(0xFF)
			if chunk == bytearray([0xFF, 0xFF]):
				pos += 2
				continue

			write_address = address + pos
			value = struct.unpack("<H", chunk)[0]
			if self._cart_write(0, 0x70, flashcart=True) is False:
				return False
			if self._cart_write(0, 0x10, flashcart=True) is False:
				return False
			if self._cart_write(write_address, value, flashcart=True) is False:
				return False
			if not self._wait_gba_intel_status(0, expected=0x80, mask=0x80, timeout=1.0):
				return False
			pos += 2
		if self._cart_write(0, 0xFF, flashcart=True) is False:
			return False
		return 1

	def _write_gba_rom_stock_program(self, address, data, flash_buffer_size):
		payload = bytearray(struct.pack("<IH", address, max(0, int(flash_buffer_size))))
		payload.extend(data)
		return self._packet_ack(self.CMD_GBA_ROM_PROGRAM, payload, timeout=max(self.DEVICE_TIMEOUT, 60))

	def _write_gba_ram(self, address, data, program_flash=False):
		payload = bytearray(struct.pack("<I", address))
		payload.extend(data)
		command = self.CMD_GBA_RAM_PROGRAM_FLASH if program_flash else self.CMD_GBA_RAM_WRITE
		return self._packet_ack(command, payload)

	def _read_gba_ram(self, address, length):
		payload = struct.pack("<IH", address, length)
		return self._packet_read(self.CMD_GBA_RAM_READ, payload, length)

	def _write_gbc(self, address, data):
		payload = bytearray(struct.pack("<I", address))
		payload.extend(data)
		return self._packet_ack(self.CMD_GBC_WRITE, payload)

	def _read_gbc(self, address, length):
		payload = struct.pack("<IH", address, length)
		return self._packet_read(self.CMD_GBC_READ, payload, length)

	def _cart_read(self, address, length=0, agb_save_flash=False):
		if self.MODE == "DMG":
			if length == 0:
				length = 1
				if address < 0xA000:
					raw = self.ReadROM(address, 1, max_length=self.MAX_BUFFER_READ)
				else:
					raw = self.ReadRAM(address - 0xA000, 1, max_length=self.MAX_BUFFER_READ)
				return False if raw is False or len(raw) < 1 else raw[0]
			if address < 0xA000:
				return self.ReadROM(address, length, max_length=self.MAX_BUFFER_READ)
			return self.ReadRAM(address - 0xA000, length, max_length=self.MAX_BUFFER_READ)

		if self.MODE == "AGB":
			if agb_save_flash:
				if length == 0:
					raw = self.ReadRAM(address, 1, max_length=self.MAX_BUFFER_READ)
					return False if raw is False or len(raw) < 1 else raw[0]
				return self.ReadRAM(address, length, max_length=self.MAX_BUFFER_READ)
			if length == 0:
				raw = self.ReadROM(address, 2, max_length=self.MAX_BUFFER_READ)
				return False if raw is False or len(raw) < 2 else struct.unpack("<H", raw)[0]
			return self.ReadROM(address, length, max_length=self.MAX_BUFFER_READ)
		return False

	def _cart_write(self, address, value, flashcart=False, sram=False):
		if self.MODE == "DMG":
			if address >= 0xA000 or sram:
				return self._write_gbc(address, bytearray([value & 0xFF]))
			return self._write_gbc(address, bytearray([value & 0xFF]))

		if self.MODE == "AGB":
			if sram:
				return self._write_gba_ram(address, bytearray([value & 0xFF]))
			data = struct.pack("<H", value & 0xFFFF)
			return self._write_gba_rom_words(address >> 1, bytearray(data))
		return False

	def _cart_write_flash(self, commands, flashcart=False):
		for address, value in commands:
			if self.MODE == "AGB" and not flashcart:
				if self._write_gba_ram(address, bytearray([value & 0xFF])) is False:
					return False
			else:
				if self._cart_write(address, value, flashcart=flashcart) is False:
					return False
		return 1

	def ReadROM(self, address, length, skip_init=False, max_length=64):
		max_length = min(max_length, self.MAX_PACKET_PAYLOAD, self.MAX_BUFFER_READ)
		if self.MODE == "AGB" and max_length % 2 != 0:
			max_length -= 1
		if max_length <= 0: max_length = 2 if self.MODE == "AGB" else 1
		dprint("Reading 0x{:X} bytes from Beggar Socket ROM at 0x{:X}".format(length, address))

		buffer = bytearray()
		pos = 0
		while pos < length:
			chunk_len = min(max_length, length - pos)
			if self.MODE == "AGB":
				temp = self._read_gba_rom_even(address + pos, chunk_len)
			elif self.MODE == "DMG":
				temp = self._read_gbc(address + pos, chunk_len)
			else:
				raise NotImplementedError
			if temp is False or len(temp) != chunk_len:
				return bytearray()
			buffer += temp
			pos += chunk_len
			if self.INFO["action"] in (self.ACTIONS["ROM_READ"], self.ACTIONS["SAVE_READ"], self.ACTIONS["ROM_WRITE_VERIFY"]) and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"READ", "bytes_added":len(temp)})
		return buffer

	def ReadRAM(self, address, length, command=None, max_length=64):
		max_length = min(max_length, self.MAX_PACKET_PAYLOAD, self.MAX_BUFFER_READ)
		buffer = bytearray()
		pos = 0
		while pos < length:
			chunk_len = min(max_length, length - pos)
			if self.MODE == "AGB":
				temp = self._read_gba_ram(address + pos, chunk_len)
			elif self.MODE == "DMG":
				temp = self._read_gbc(0xA000 + address + pos, chunk_len)
			else:
				raise NotImplementedError
			if temp is False or len(temp) != chunk_len:
				return bytearray()
			buffer += temp
			pos += chunk_len
			if not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"READ", "bytes_added":len(temp)})
		return buffer

	def WriteRAM(self, address, buffer, command=None, max_length=256):
		max_length = min(max_length, self.MAX_PACKET_PAYLOAD, self.MAX_BUFFER_WRITE)
		length = len(buffer)
		num = math.ceil(length / max_length)
		program_flash = False
		if isinstance(command, bytearray) and len(command) > 0:
			program_flash = command[0] == self.DEVICE_CMD["AGB_CART_WRITE_FLASH_DATA"]
		elif command == self.DEVICE_CMD["AGB_CART_WRITE_FLASH_DATA"]:
			program_flash = True

		for i in range(0, num):
			data = bytearray(buffer[i*max_length:i*max_length+max_length])
			pos = address + (i * max_length)
			if self.MODE == "AGB":
				ret = self._write_gba_ram(pos, data, program_flash=program_flash)
			elif self.MODE == "DMG":
				ret = self._write_gbc(0xA000 + pos, data)
			else:
				raise NotImplementedError
			if ret is False:
				return False
			if self.INFO["action"] == self.ACTIONS["SAVE_WRITE"] and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":len(data)})
		return True

	def WriteROM(self, address, buffer, flash_buffer_size=False, skip_init=False, rumble_stop=False, max_length=0x400):
		max_length = min(max_length, self.MAX_PACKET_PAYLOAD, self.MAX_BUFFER_WRITE)
		if self.MODE == "AGB" and max_length % 2 != 0:
			max_length -= 1
		if max_length <= 0: max_length = 2 if self.MODE == "AGB" else 1
		if self.MODE == "AGB" and address % 2 != 0:
			return False

		length = len(buffer)
		num = math.ceil(length / max_length)
		buffer_size = 0 if flash_buffer_size is False else int(flash_buffer_size)
		pos = 0
		skip_write = False
		for i in range(0, num):
			data = bytearray(buffer[i*max_length:i*max_length+max_length])
			if self.MODE == "AGB" and len(data) % 2 != 0:
				data.append(0xFF)
			if data == bytearray([0xFF] * len(data)):
				skip_write = True
			else:
				skip_write = False
				if self.MODE == "AGB":
					if getattr(self, "PROTOCOL_CAPS", 0) & self.CAP_GBA_ROM_PROGRAM_INTEL:
						payload = bytearray(struct.pack("<IH", address + pos, buffer_size))
						payload.extend(data)
						ret = self._packet_ack(self.CMD_GBA_ROM_PROGRAM_INTEL, payload, timeout=max(self.DEVICE_TIMEOUT, 15))
					elif getattr(self, "LEGACY_MCU_PROTOCOL", False):
						if self.FLASH_COMMAND_SET == 1 and buffer_size > 0:
							ret = self._write_gba_rom_stock_program(address + pos, data, buffer_size)
						else:
							# Original MCU firmware's fast 0xF4 path implements AMD-style
							# buffered writes only. Intel/Sharp carts need patched 0xE1 for
							# speed; stock firmware can only be driven safely one word at a time.
							ret = self._write_gba_rom_intel_single(address + pos, data)
					else:
						ret = self._write_gba_rom_intel_buffered(address + pos, data, buffer_size)
				else:
					payload = bytearray(struct.pack("<IH", address + pos, buffer_size))
					payload.extend(data)
					ret = self._packet_ack(self.CMD_GBC_ROM_PROGRAM, payload, timeout=max(self.DEVICE_TIMEOUT, 60))
				if ret is False:
					self.ERROR_ARGS = { "iteration":i }
					self.SKIPPING = False
					return False
			pos += len(data)
			if self.INFO["action"] in (self.ACTIONS["ROM_WRITE"], self.ACTIONS["SAVE_WRITE"]) and not self.NO_PROG_UPDATE:
				self.SetProgress({"action":"WRITE", "bytes_added":min(len(data), max(0, length - (pos - len(data)))), "skipping":skip_write})
		self.SKIPPING = skip_write
		return True
