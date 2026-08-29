# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import time, datetime, struct, math, hashlib
from dateutil.relativedelta import relativedelta
from .RomFileDMG import RomFileDMG
from .Logging import dprint, ANSI
from .i18n import __, c__, ___, c___

class BCD:
	@classmethod
	def encode(cls, value: int) -> int:
		return math.floor(value / 10) << 4 | value % 10

	@classmethod
	def decode(cls, value: int) -> int:
		return ((value & 0x0F) + ((value >> 4) * 10))

def ConvertMapperToMapperType(mapper_raw):
	i = 0
	retval = None
	for (mapper_type, (ids, _)) in DMG_Mapper.MAPPER_MAP.items():
		if i == 0:
			retval = (mapper_type, ids, i)
		if mapper_raw in ids:
			retval = (mapper_type, ids, i)
			break
		i += 1
	return retval

def ConvertMapperTypeToMapper(mapper_type):
	i = 0
	for (_, (ids, _)) in DMG_Mapper.MAPPER_MAP.items():
		if mapper_type == i:
			return ids[0]
		i += 1
	return 0

def compare_mbc(a, b):
	for (_, (ids, _)) in DMG_Mapper.MAPPER_MAP.items():
		if a in ids and b in ids:
			return True
	return False

def get_mbc_name(id):
	for (mapper_type, (ids, _)) in DMG_Mapper.MAPPER_MAP.items():
		if id in ids:
			return mapper_type
	return __("Unknown mapper type {id}", id=f"0x{id:02X}")

def save_size_includes_rtc(mode, mbc, save_size, save_type):
	from .CartridgeTypes import DmgSaveTypes, AgbSaveTypes
	rtc_size = 0x10
	if mode == "DMG":
		save_type = DmgSaveTypes(mbc=save_type).GetIndex()
		if get_mbc_name(mbc) in ("MBC3", "MBC30"): rtc_size = 0x30
		elif get_mbc_name(mbc) == "HuC-3": rtc_size = 0x0C
		elif get_mbc_name(mbc) == "TAMA5": rtc_size = 0x28
		return (((DmgSaveTypes(index=save_type).GetSize() + rtc_size) % save_size) == 0)
	elif mode == "AGB":
		rtc_size = 0x10
		return (((AgbSaveTypes().GetSize(save_type) + rtc_size) % save_size) == 0)
	return False


class DMG_Mapper:
	MBC_ID = 0
	CART_WRITE_FNCPTR = None
	CART_READ_FNCPTR = None
	CART_POWERCYCLE_FNCPTR = None
	CLK_TOGGLE_FNCPTR = None
	ROM_BANK_SIZE = 0x4000
	RAM_BANK_SIZE = 0x2000
	ROM_BANK_NUM = 0
	CURRENT_ROM_BANK = 0
	CURRENT_FLASH_BANK = -1
	START_BANK = 0
	RTC_BUFFER = None

	# Mapper type definitions (class-level constants)
	MAPPER_TYPES = {
		0x00: "None", # ROM
		0x01: "MBC1",
		0x02: "MBC1+SRAM",
		0x03: "MBC1+SRAM+BATTERY",
		0x05: "MBC2",
		0x06: "MBC2+SRAM+BATTERY",
		0x08: "None", # ROM+RAM
		0x09: "None", # ROM+RAM+BATTERY
		0x0B: "MMM01",
		0x0D: "MMM01+SRAM+BATTERY",
		0x0F: "MBC3+RTC+BATTERY",
		0x10: "MBC3+RTC+SRAM+BATTERY",
		0x11: "MBC3",
		0x12: "MBC3+SRAM",
		0x13: "MBC3+SRAM+BATTERY",
		0x19: "MBC5",
		0x1A: "MBC5+SRAM",
		0x1B: "MBC5+SRAM+BATTERY",
		0x1C: "MBC5+RUMBLE",
		0x1D: "MBC5+RUMBLE+SRAM",
		0x1E: "MBC5+RUMBLE+SRAM+BATTERY",
		0x20: "MBC6+SRAM+FLASH+BATTERY",
		0x22: "MBC7+ACCELEROMETER+EEPROM",
		0xFC: "MAC-GBD+SRAM+BATTERY",
		0xFD: "TAMA5+RTC+EEPROM",
		0xFE: "HuC-3+RTC+SRAM+BATTERY",
		0xFF: "HuC-1+IR+SRAM+BATTERY",
		0x101: "MBC1M",
		0x103: "MBC1M+SRAM+BATTERY",
		0x104: "M161",
		0x105: "G-MMC1+SRAM+BATTERY",
		0x110: "MBC30+RTC+SRAM+BATTERY",
		0x201: "Unlicensed 256M Mapper",
		0x202: "Unlicensed Wisdom Tree Mapper",
		0x203: "Unlicensed Xploder GB Mapper",
		0x204: "Unlicensed Sachen Mapper",
		0x205: "Unlicensed Datel Orbit V2 Mapper",
		0x206: "Unlicensed MBCX Mapper"
	}

	# Mapper type to IDs mapping (class names as strings to avoid forward reference issues)
	MAPPER_MAP = {
		"None": ([0x00, 0x08, 0x09], None),
		"MBC1": ([0x01, 0x02, 0x03], "DMG_MBC1"),
		"MBC2": ([0x05, 0x06], "DMG_MBC2"),
		"MBC3": ([0x0F, 0x10, 0x11, 0x12, 0x13], "DMG_MBC3"),
		"MBC30": ([0x110], "DMG_MBC3"),
		"MBC5": ([0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E], "DMG_MBC5"),
		"MBC6": ([0x20], "DMG_MBC6"),
		"MBC7": ([0x22], "DMG_MBC7"),
		"MBC1M": ([0x101, 0x103], "DMG_MBC1M"),
		"MMM01": ([0x0B, 0x0D], "DMG_MMM01"),
		"MAC-GBD": ([0xFC], "DMG_GBD"),
		"G-MMC1": ([0x105], "DMG_GMMC1"),
		"M161": ([0x104], "DMG_M161"),
		"HuC-1": ([0xFF], "DMG_HuC1"),
		"HuC-3": ([0xFE], "DMG_HuC3"),
		"TAMA5": ([0xFD], "DMG_TAMA5"),
		"Unlicensed 256M Multi Cart Mapper": ([0x201], "DMG_Unlicensed_256M"),
		"Unlicensed Wisdom Tree Mapper": ([0x202], "DMG_Unlicensed_WisdomTree"),
		"Unlicensed Xploder GB Mapper": ([0x203], "DMG_Unlicensed_XploderGB"),
		"Unlicensed Sachen Mapper": ([0x204], "DMG_Unlicensed_Sachen"),
		"Unlicensed Datel Orbit V2 Mapper": ([0x205], "DMG_Unlicensed_DatelOrbitV2"),
		"Unlicensed MBCX Mapper": ([0x206], "DMG_Unlicensed_MBCX"),
	}

	SGB_MAP = {
		0x00:'No support', 0x03:'Supported'
	}
	CGB_MAP = {
		0x00:'No support', 0x80:'Supported', 0xC0:'Required'
	}

	def __init__(self, args=None, cart_write_fncptr=None, cart_read_fncptr=None, cart_powercycle_fncptr=None, clk_toggle_fncptr=None):
		if args is None: args = {}
		if "mbc" in args: self.MBC_ID = args["mbc"]
		if "rom_banks" in args:
			self.ROM_BANK_NUM = args["rom_banks"]
		elif "rom_size" in args:
			self.ROM_BANK_NUM = math.ceil(args["rom_size"] / self.ROM_BANK_SIZE)
		self.CART_WRITE_FNCPTR = cart_write_fncptr
		self.CART_READ_FNCPTR = cart_read_fncptr
		self.CART_POWERCYCLE_FNCPTR = cart_powercycle_fncptr
		self.CLK_TOGGLE_FNCPTR = clk_toggle_fncptr

	def GetInstance(self, args=None, cart_write_fncptr=None, cart_read_fncptr=None, cart_powercycle_fncptr=None, clk_toggle_fncptr=None):
		if args is None: args = {}
		mbc_id = args["mbc"]

		mapper_type = self.GetMapperType(mbc_id)

		# Get the appropriate class from MAPPER_MAP
		mapper_info = self.MAPPER_MAP.get(mapper_type)
		mapper_class_name = mapper_info[1] if mapper_info else None

		# Resolve class name to actual class object
		if mapper_class_name:
			mapper_class = globals().get(mapper_class_name)
			if mapper_class:
				return mapper_class(
					args=args,
					cart_write_fncptr=cart_write_fncptr,
					cart_read_fncptr=cart_read_fncptr,
					cart_powercycle_fncptr=cart_powercycle_fncptr,
					clk_toggle_fncptr=clk_toggle_fncptr
				)

		# Default: return base class instance
		self.__init__(
			args=args,
			cart_write_fncptr=cart_write_fncptr,
			cart_read_fncptr=cart_read_fncptr,
			cart_powercycle_fncptr=cart_powercycle_fncptr,
			clk_toggle_fncptr=clk_toggle_fncptr
		)
		return self

	@classmethod
	def GetMapperName(cls, mapper_id):
		return cls.MAPPER_TYPES.get(mapper_id, "Unknown")

	@classmethod
	def GetMapperType(cls, mapper_id):
		for mapper_type, (ids, _) in cls.MAPPER_MAP.items():
			if mapper_id in ids:
				return mapper_type
		return "Unknown"

	@classmethod
	def GetMapperIdsByType(cls, mapper_type):
		mapper_info = cls.MAPPER_MAP.get(mapper_type)
		return mapper_info[0] if mapper_info else []

	@classmethod
	def IsValidMapperId(cls, mapper_id):
		return mapper_id in cls.MAPPER_TYPES

	@classmethod
	def HasFeature(cls, feature, mapper_id):
		name = cls.GetMapperName(mapper_id)
		return feature.upper() in name.upper()

	@classmethod
	def GetAllMapperTypes(cls):
		return list(cls.MAPPER_MAP.keys())

	@classmethod
	def GetAllMapperIds(cls):
		return list(cls.MAPPER_TYPES.keys())

	def CartRead(self, address, length=0):
		if length == 0: # auto size:
			return self.CART_READ_FNCPTR(address)
		else:
			return self.CART_READ_FNCPTR(address, length)

	def CartWrite(self, commands, delay=False, sram=False):
		for command in commands:
			address = command[0]
			value = command[1]
			self.CART_WRITE_FNCPTR(address, value, sram=sram)
			if delay is not False: time.sleep(delay)

	def GetID(self):
		return self.MBC_ID

	def GetName(self):
		# Get the base mapper type name (e.g. "MBC1", "MBC5")
		mapper_type = self.GetMapperType(self.MBC_ID)
		if mapper_type != "Unknown":
			return mapper_type
		return "Unknown MBC {:d}".format(self.MBC_ID)

	def GetFullName(self):
		# Get the full mapper name with all features (e.g. "MBC1+SRAM+BATTERY")
		full_name = self.GetMapperName(self.MBC_ID)
		if full_name != "Unknown":
			return full_name
		return "Unknown MBC {:d}".format(self.MBC_ID)

	def GetROMBank(self):
		return self.CURRENT_ROM_BANK

	def GetFlashBank(self):
		return self.CURRENT_FLASH_BANK

	def GetROMBanks(self, rom_size):
		return math.ceil(rom_size / self.ROM_BANK_SIZE)

	def GetROMBankSize(self):
		return self.ROM_BANK_SIZE

	def GetRAMBanks(self, ram_size):
		return math.ceil(ram_size / self.RAM_BANK_SIZE)

	def GetRAMBankSize(self):
		return self.RAM_BANK_SIZE

	def GetROMSize(self):
		return self.ROM_BANK_SIZE * self.ROM_BANK_NUM

	def GetMaxROMSize(self):
		return 32*1024

	def CalcChecksum(self, buffer):
		chk = 0
		for i in range(0, len(buffer), 2):
			if i != 0x14E:
				chk = chk + buffer[i + 1]
				chk = chk + buffer[i]
		return chk & 0xFFFF

	def EnableMapper(self):
		return True

	def EnableRAM(self, enable=True):
		dprint(self.GetName(), "|", enable)
		commands = [
			[ 0x0000, 0x0A if enable else 0x00 ]
		]
		self.CartWrite(commands)

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0x2100, index & 0xFF ],
		]

		start_address = 0 if index == 0 else 0x4000

		self.CartWrite(commands)
		return (start_address, self.ROM_BANK_SIZE)

	def ApplyROMWriteBankSwitchSeparator(self, index):
		return False

	def SelectBankRAM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0x4000, index & 0xFF ]
		]
		start_address = 0
		self.CartWrite(commands)
		return (start_address, self.RAM_BANK_SIZE)

	def SetStartBank(self, index):
		self.START_BANK = index

	def SelectBankFlash(self, index):
		return

	def HasFlashBanks(self):
		return False

	def HasHiddenSector(self):
		return False

	def HasRTC(self):
		return self.HasFeature("RTC", self.MBC_ID)

	def GetRTCBufferSize(self):
		return 0

	def LatchRTC(self):
		return 0

	def ReadRTC(self):
		return False

	def WriteRTC(self, buffer, advance=False):
		pass

	def GetRTCDict(self):
		return {}

	def WriteRTCDict(self, rtc_dict):
		pass

	def GetRTCString(self):
		return c__("Real Time Clock Feature", "Not available")

	def ResetBeforeBankChange(self, index):
		return False

	def ReadWithCSPulse(self):
		return False

	def WriteWithCSPulse(self):
		return False

##################

class DMG_MBC1(DMG_Mapper):
	def GetName(self):
		return "MBC1"

	def EnableRAM(self, enable=True):
		dprint(self.GetName(), "|", enable)
		if enable:
			commands = [
				[ 0x6000, 0x01 ],
				[ 0x0000, 0x0A ],
			]
		else:
			commands = [
				[ 0x0000, 0x00 ],
				[ 0x6000, 0x00 ],
			]
		self.CartWrite(commands)

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index, hex(index >> 5), hex(index & 0x1F))
		commands = [
			[ 0x6000, 1 ],
			[ 0x2000, index ],
			[ 0x4000, index >> 5 ],
		]
		start_address = 0x4000 if index & 0x1F else 0

		self.CartWrite(commands)
		return (start_address, self.ROM_BANK_SIZE)

	def GetMaxROMSize(self):
		return 2*1024*1024

class DMG_MBC2(DMG_Mapper):
	def GetName(self):
		return "MBC2"

	def SelectBankRAM(self, index):
		return (0, self.RAM_BANK_SIZE)

	def GetMaxROMSize(self):
		return 256*1024

class DMG_MBC3(DMG_Mapper):
	def GetName(self):
		return "MBC3"

	def HasRTC(self):
		dprint("Checking for RTC")
		if self.MBC_ID not in (0x0F, 0x10, 0x110, 0x206):
			dprint("No RTC because mapper value is not used for RTC:", self.MBC_ID)
			return False
		self.EnableRAM(enable=False)
		self.EnableRAM(enable=True)
		self.LatchRTC()

		skipped = True
		for i in range(0x08, 0x0D):
			self.CLK_TOGGLE_FNCPTR(60)
			self.CartWrite([ [0x4000, i] ])
			data = self.CartRead(0xA880, 0x100)
			if len(data) == 0: return False
			if data[0] in (0, 0xFF): continue
			skipped = False
			if data != bytearray([data[0]] * 0x100):
				dprint("No RTC because whole bank is not the same value:", data[0])
				skipped = True
				break

		self.EnableRAM(enable=False)
		self.CartWrite([ [0x4000, 0] ])
		return skipped is False

	def GetRTCBufferSize(self):
		return 0x30

	def LatchRTC(self):
		dprint("Latching RTC")
		self.CLK_TOGGLE_FNCPTR(60)
		self.CartWrite([ [ 0x0000, 0x0A ] ])
		self.CLK_TOGGLE_FNCPTR(60)
		self.CartWrite([ [ 0x6000, 0x00 ] ])
		self.CLK_TOGGLE_FNCPTR(60)
		self.CartWrite([ [ 0x6000, 0x01 ] ])

	def ReadRTC(self):
		dprint("Reading RTC")
		self.EnableRAM(enable=True)

		buffer = bytearray()
		for i in range(0x08, 0x0D):
			self.CLK_TOGGLE_FNCPTR(60)
			self.CartWrite([ [0x4000, i] ])
			buffer.extend(struct.pack("<I", self.CartRead(0xA000)))
		buffer.extend(buffer) # copy

		# Add timestamp of backup time
		ts = int(time.time())
		buffer.extend(struct.pack("<Q", ts))

		self.EnableRAM(enable=False)
		self.CartWrite([ [0x4000, 0] ])
		self.RTC_BUFFER = buffer
		return buffer

	def WriteRTCDict(self, rtc_dict):
		dprint("Writing RTC:", rtc_dict)
		self.EnableRAM(enable=True)

		buffer = bytearray(5)
		buffer[0] = rtc_dict["rtc_s"] % 60
		buffer[1] = rtc_dict["rtc_m"] % 60
		buffer[2] = rtc_dict["rtc_h"] % 24
		buffer[3] = rtc_dict["rtc_d"] & 0xFF
		buffer[4] = rtc_dict["rtc_d"] >> 8 & 1

		dprint("New values: RTC_S=0x{:02X}, RTC_M=0x{:02X}, RTC_H=0x{:02X}, RTC_DL=0x{:02X}, RTC_DH=0x{:02X}".format(buffer[0], buffer[1], buffer[2], buffer[3], buffer[4]))

		# Unlock and latch RTC
		self.CLK_TOGGLE_FNCPTR(50)
		self.CartWrite([ [ 0x0000, 0x0A ] ])
		self.CLK_TOGGLE_FNCPTR(50)
		self.CartWrite([ [ 0x6000, 0x00 ] ])
		self.CLK_TOGGLE_FNCPTR(50)
		self.CartWrite([ [ 0x6000, 0x01 ] ])

		# Halt RTC
		self.CLK_TOGGLE_FNCPTR(50)
		self.CartWrite([ [ 0x4000, 0x0C ] ])
		self.CLK_TOGGLE_FNCPTR(50)
		self.CartWrite([ [ 0xA000, 0x40 ] ], sram=True)

		# Write to registers
		for i in range(0x08, 0x0D):
			self.CLK_TOGGLE_FNCPTR(50)
			self.CartWrite([ [ 0x4000, i ] ])
			self.CLK_TOGGLE_FNCPTR(50)
			data = buffer[i-8]
			self.CartWrite([ [ 0xA000, data ] ], sram=True)

		# Latch RTC
		self.CLK_TOGGLE_FNCPTR(50)
		self.CartWrite([ [ 0x6000, 0x00 ] ])
		self.CLK_TOGGLE_FNCPTR(50)
		self.CartWrite([ [ 0x6000, 0x01 ] ])

		self.CartWrite([ [0x4000, 0] ])
		self.EnableRAM(enable=False)

		return True

	def WriteRTC(self, buffer, advance=False):
		dprint("Writing RTC:", buffer)
		self.EnableRAM(enable=True)
		# Pre-initialize from buffer so advance=False path always has defined variables
		seconds = buffer[0x00]
		minutes = buffer[0x04]
		hours = buffer[0x08]
		days = buffer[0x0C] | buffer[0x10] << 8
		days = days & 0x1FF
		carry = ((buffer[0x10] & 0x80) != 0)
		if advance:
			try:
				dt_now = datetime.datetime.fromtimestamp(time.time())
				if buffer == bytearray([0x00] * len(buffer)): # Reset
					seconds = 0
					minutes = 0
					hours = 0
					days = 0
					carry = 0
				else:
					seconds = buffer[0x00]
					minutes = buffer[0x04]
					hours = buffer[0x08]
					days = buffer[0x0C] | buffer[0x10] << 8
					carry = ((buffer[0x10] & 0x80) != 0)
					days = days & 0x1FF
					timestamp_then = struct.unpack("<Q", buffer[-8:])[0]
					timestamp_now = int(time.time())
					dprint(seconds, minutes, hours, days, carry)
					if timestamp_then < timestamp_now:
						dt_then = datetime.datetime.fromtimestamp(timestamp_then)
						dt_buffer1 = datetime.datetime.strptime("{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(2000, 1, 1, 0, 0, 0), "%Y-%m-%d %H:%M:%S")
						dt_buffer2 = datetime.datetime.strptime("{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(2000, 1, 1, hours % 24, minutes % 60, seconds % 60), "%Y-%m-%d %H:%M:%S")
						dt_buffer2 += datetime.timedelta(days=days)
						rd = relativedelta(dt_now, dt_then)
						dt_new = dt_buffer2 + rd
						dprint(dt_then, dt_now, dt_buffer1, dt_buffer2, dt_new, sep="\n")
						seconds = dt_new.second
						minutes = dt_new.minute
						hours = dt_new.hour
						temp = datetime.date.fromtimestamp(timestamp_now) - datetime.date.fromtimestamp(timestamp_then)
						days = temp.days + days
						if days >= 512:
							carry = True
							days = days % 512
						dprint(seconds, minutes, hours, days, carry)

			except Exception as e:
				print(__("Error: Couldn’t update the RTC register values.") + "\n" + str(e))

		d = {
			"rtc_s":seconds % 60,
			"rtc_m":minutes % 60,
			"rtc_h":hours % 24,
			"rtc_d":days % 512,
		}
		self.WriteRTCDict(d)
		self.EnableRAM(enable=False)

	def GetRTCDict(self):
		if self.RTC_BUFFER is None:
			self.ReadRTC()
		rtc_buffer = self.RTC_BUFFER

		rtc_s = rtc_buffer[0x00]
		rtc_m = rtc_buffer[0x04]
		rtc_h = rtc_buffer[0x08]
		rtc_d = (rtc_buffer[0x0C] | rtc_buffer[0x10] << 8) & 0x1FF
		rtc_carry = ((rtc_buffer[0x10] & 0x80) != 0)
		d = {
			"rtc_d":rtc_d,
			"rtc_h":rtc_h,
			"rtc_m":rtc_m,
			"rtc_s":rtc_s,
			"rtc_carry":rtc_carry
		}

		#if rtc_carry: rtc_d += 256
		if rtc_h > 24 or rtc_m > 60 or rtc_s > 60:
			try:
				dprint("Invalid RTC state: {:d} days, {:02d}:{:02d}:{:02d}".format(rtc_d, rtc_h, rtc_m, rtc_s))
			except:
				pass
			s = __("Invalid RTC state")
			d["rtc_valid"] = False
		elif rtc_h == 0 and rtc_m == 0 and rtc_s == 0 and rtc_d == 0 and rtc_carry == 0:
			s = __("Not available")
			d["rtc_valid"] = False
		else:
			s = ___("{days} day, {hours}:{minutes}:{seconds}", "{days} days, {hours}:{minutes}:{seconds}", n=rtc_d, days=rtc_d, hours="{:02d}".format(rtc_h), minutes="{:02d}".format(rtc_m), seconds="{:02d}".format(rtc_s))
			d["rtc_valid"] = True

		d["string"] = s
		return d

	def GetRTCString(self):
		return self.GetRTCDict()["string"]

	def GetMaxROMSize(self):
		return 4*1024*1024

class DMG_MBC5(DMG_Mapper):
	def GetName(self):
		return "MBC5"

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)

		self.CURRENT_ROM_BANK = index
		commands = [
			[ 0x3000, ((index >> 8) & 0xFF) ],
			[ 0x2100, index & 0xFF ],
		]

		start_address = 0 if index == 0 else 0x4000

		self.CartWrite(commands)
		return (start_address, self.ROM_BANK_SIZE)

	def ApplyROMWriteBankSwitchSeparator(self, index):
		dprint(self.GetName(), "| ROM write bank switch separator |", index)
		self.CartWrite([[ 0x4000, 0x00 ]])
		return True

	def GetMaxROMSize(self):
		return 8*1024*1024

class DMG_MBC6(DMG_Mapper):
	def __init__(self, args=None, cart_write_fncptr=None, cart_read_fncptr=None, cart_powercycle_fncptr=None, clk_toggle_fncptr=None):
		if args is None: args = {}
		super().__init__(args=args, cart_write_fncptr=cart_write_fncptr, cart_read_fncptr=cart_read_fncptr, cart_powercycle_fncptr=cart_powercycle_fncptr, clk_toggle_fncptr=None)
		self.ROM_BANK_SIZE = 0x2000
		self.RAM_BANK_SIZE = 0x1000
		self.ROM_BANK_NUM = 128

	def GetName(self):
		return "MBC6"

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		self.CURRENT_ROM_BANK = index
		#index = index * 2
		commands = [
			[ 0x2800, 0 ],
			[ 0x3800, 0 ],
			[ 0x2000, index ],	# ROM Bank A (0x4000–0x5FFF)
			[ 0x3000, index ],	# ROM Bank B (0x6000–0x7FFF)
		]
		self.CartWrite(commands)
		start_address = 0 if index == 0 else 0x4000
		return (start_address, self.ROM_BANK_SIZE)

	def HasFlashBanks(self):
		return True

	def SelectBankFlash(self, index):
		dprint(self.GetName(), "|", index)
		self.CURRENT_ROM_BANK = index
		#index = index * 2
		commands = [
			[ 0x2800, 8 ],
			[ 0x3800, 8 ],
			[ 0x2000, index ],	# ROM Bank A (0x4000–0x5FFF)
			[ 0x3000, index ],	# ROM Bank B (0x6000–0x7FFF)
		]
		self.CartWrite(commands)
		start_address = 0x4000
		return (start_address, self.ROM_BANK_SIZE)

	def GetRAMBanks(self, ram_size): # 0x108000
		return 8 + 128

	def SelectBankRAM(self, index):
		dprint(self.GetName(), "|", index)
		#index = index * 2
		commands = [
			[ 0x0400, index ],	# RAM Bank A (0xA000-0xAFFF)
			[ 0x0800, index ],	# RAM Bank B (0xB000-0xBFFF)
		]
		self.CartWrite(commands)
		start_address = 0
		return (start_address, self.RAM_BANK_SIZE)

	def EnableFlash(self, enable=True, enable_write=False):
		if enable:
			self.CartWrite([
				[ 0x1000, 0x01 ],		# Enable flash write
				[ 0x0C00, 0x01 ],		# Enable flash output
				[ 0x1000, 0x01 if enable_write else 0x00 ],		# Disable flash write?
				[ 0x2800, 0x08 ],		# Map flash memory into ROM Bank A
				[ 0x3800, 0x08 ]		# Map flash memory into ROM Bank B
			])
		else:
			self.CartWrite([
				[ 0x1000, 0x01 ],		# Enable flash write
				[ 0x0C00, 0x00 ],		# Disable flash output
				[ 0x1000, 0x00 ],		# Disable flash write
				[ 0x2800, 0x00 ],		# Map ROM memory into ROM Bank A
				[ 0x3800, 0x00 ]		# Map ROM memory into ROM Bank B
			])

	def EraseFlashSector(self):
		cmds = [
			[ 0x2000, 0x01 ],
			[ 0x3000, 0x02 ],
			[ 0x7555, 0xAA ],
			[ 0x4AAA, 0x55 ],
			[ 0x7555, 0x80 ],
			[ 0x7555, 0xAA ],
			[ 0x4AAA, 0x55 ],
		]
		self.CartWrite(cmds)
		self.SelectBankFlash(self.GetROMBank())
		self.CartWrite([[ 0x4000, 0x30 ]])
		while True:
			sr = self.CartRead(0x4000)
			dprint("Status Register Check: 0x{:X} == 0x80? {:s}".format(sr, str(sr == 0x80)))
			if sr == 0x80: break
			time.sleep(0.01)

	def GetFlashID(self):
		self.EnableFlash(enable=True)
		# Query Flash ID
		self.CartWrite([
			[ 0x2000, 0x01 ],
			[ 0x3000, 0x02 ],
			[ 0x7555, 0xAA ],
			[ 0x4AAA, 0x55 ],
			[ 0x7555, 0x90 ],
		])
		flash_id = self.CartRead(0x6000, 8)
		# Reset to Read Array Mode
		self.CartWrite([
			[ 0x4000, 0xF0 ],
		])
		self.SelectBankROM(self.CURRENT_ROM_BANK)
		return flash_id

	def GetMaxROMSize(self):
		return 1*1024*1024

class DMG_MBC7(DMG_Mapper):
	def GetName(self):
		return "MBC7"

	def SelectBankRAM(self, index):
		return (0, 0x200)

	def EnableRAM(self, enable=True):
		dprint(self.GetName(), "|", enable)
		commands = [
			[ 0x0000, 0x0A if enable else 0x00 ],
			[ 0x4000, 0x40 ]
		]
		self.CartWrite(commands)

	def GetMaxROMSize(self):
		return 4*1024*1024

class DMG_MBC1M(DMG_MBC1):
	def GetName(self):
		return "MBC1M"

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0x6000, 1 ],
			[ 0x2000, index ],
			[ 0x4000, index >> 4 ],
		]
		start_address = 0x4000 if index & 0x0F else 0

		self.CartWrite(commands)
		return (start_address, self.ROM_BANK_SIZE)

	def GetMaxROMSize(self):
		return 1*1024*1024

class DMG_MMM01(DMG_Mapper):
	def GetName(self):
		return "MMM01"

	def CalcChecksum(self, buffer):
		chk = 0
		temp_data = buffer[0:-0x8000]
		temp_menu = buffer[-0x8000:]
		temp_dump = temp_menu + temp_data
		for i in range(0, len(temp_dump), 2):
			if i != 0x14E:
				chk = chk + temp_dump[i + 1]
				chk = chk + temp_dump[i]
		return chk & 0xFFFF

	def ResetBeforeBankChange(self, index):
		return ((index % 0x20) == 0)

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)

		start_address = 0 if index == 0 else 0x4000

		if (index % 0x20) == 0:
			commands = [
				[ 0x2000, index & 0xFF ],	# start from this ROM bank
				[ 0x6000, 0x00 ],			# 0x00 = 512 KB, 0x04 = 32 KB, 0x08 = 64 KB, 0x10 = 128 KB, 0x20 = 256 KB
				[ 0x4000, 0x40 ],			# RAM bank?
				[ 0x0000, 0x00 ],
				[ 0x0000, 0x40 ],			# Enable mapping
				[ 0x2100, ((index % 0x20) & 0xFF)],
			]
			start_address = 0
		else:
			commands = [
				[ 0x2100, ((index % 0x20) & 0xFF)],
			]

		self.CartWrite(commands)
		return (start_address, self.ROM_BANK_SIZE)

	def GetMaxROMSize(self):
		return 1*1024*1024

class DMG_GBD(DMG_MBC5):
	def GetName(self):
		return "MAC-GBD"

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0x2000, index & 0xFF ],
		]

		start_address = 0 if index == 0 else 0x4000

		self.CartWrite(commands)
		return (start_address, self.ROM_BANK_SIZE)

	def GetMaxROMSize(self):
		return 1*1024*1024

class DMG_GMMC1(DMG_MBC5):
	def GetName(self):
		return "G-MMC1"

	def lk_dmg_mmsa_flash_command(self, addr, data):
		commands = [
			[0x120, 0x0F],
			[0x125, addr >> 8],
			[0x126, addr & 0xFF],
			[0x127, data],
			[0x13F, 0xA5]
		]
		return commands
	def lk_dmg_mmsa_access_mapper(self):
		commands = [
			[0x120, 0x09],
			[0x121, 0xAA],
			[0x122, 0x55],
			[0x13F, 0xA5]
		]
		return commands
	def lk_dmg_mmsa_access_rom(self):
		commands = [
			[0x120, 0x08],
			[0x13F, 0xA5]
		]
		return commands
	def lk_dmg_mmsa_access_mbc(self, enable):
		if enable:
			commands = [
				[0x120, 0x11],
				[0x13F, 0xA5]
			]
		else:
			commands = [
				[0x120, 0x10],
				[0x13F, 0xA5]
			]
		return commands
	def lk_dmg_mmsa_disable_flash_write_protect(self):
		commands = [
			[0x120, 0x0A],
			[0x125, 0x62],
			[0x126, 0x04],
			[0x13F, 0xA5],

			[0x120, 0x02],
			[0x13F, 0xA5]
		]
		return commands
	def lk_dmg_mmsa_map_full(self):
		commands = [
			[0x120, 0x04],
			[0x13F, 0xA5]
		]
		return commands
	def lk_dmg_mmsa_map_menu(self):
		commands = [
			[0x120, 0x05],
			[0x13F, 0xA5]
		]
		return commands

	def EnableMapper(self):
		dprint(self.GetName())
		self.CartWrite(self.lk_dmg_mmsa_access_mapper())
		self.CartWrite(self.lk_dmg_mmsa_access_mbc(enable=True))
		self.CartWrite(self.lk_dmg_mmsa_map_full())
		self.CartWrite(self.lk_dmg_mmsa_flash_command(0x0, 0xF0))
		self.CartWrite(self.lk_dmg_mmsa_access_rom())
		return True

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0x2000, index & 0xFF ],
		]

		start_address = 0 if index == 0 else 0x4000

		self.CartWrite(commands)
		return (start_address, self.ROM_BANK_SIZE)

	def HasHiddenSector(self):
		return True

	def ReadHiddenSector(self):
		hp = 5
		while hp > 0:
			self.EnableMapper()
			rom = self.CartRead(0, 128)
			self.CartWrite(self.lk_dmg_mmsa_access_mapper())
			self.CartWrite(self.lk_dmg_mmsa_access_mbc(enable=True))
			self.CartWrite([[0x2100, 0x1]])
			self.CartWrite(self.lk_dmg_mmsa_flash_command(0x5555, 0xAA))
			self.CartWrite(self.lk_dmg_mmsa_flash_command(0x2AAA, 0x55))
			self.CartWrite(self.lk_dmg_mmsa_flash_command(0x5555, 0x77))
			self.CartWrite(self.lk_dmg_mmsa_flash_command(0x5555, 0xAA))
			self.CartWrite(self.lk_dmg_mmsa_flash_command(0x2AAA, 0x55))
			self.CartWrite(self.lk_dmg_mmsa_flash_command(0x5555, 0x77))
			self.CartWrite([[0x2100, 0x0]])
			hs = self.CartRead(0, 128)
			self.CartWrite(self.lk_dmg_mmsa_access_rom())
			if hs != rom: break
			hp -= 1
			dprint("HP:", hp, hs)

		if hp > 0:
			return hs
		else:
			print(ANSI.RED + __("Failed to read the hidden sector data of the {gb_memory_cartridge}.", gb_memory_cartridge="NP GB-Memory Cartridge") + ANSI.RESET)
			return False

	def CalcChecksum(self, buffer):
		header = RomFileDMG(buffer[:0x180]).GetHeader()
		target_chk_value = 0
		target_sha1_value = 0
		if header["game_title"] == "NP M-MENU MENU":
			target_sha1_value = "15f5d445c0b2fdf4221cf2a986a4a5cb8dfda131"
			target_chk_value = 0x19E8
		elif header["game_title"] == "DMG MULTI MENU ":
			target_sha1_value = "b8949fb9c4343b2c04ad59064e9d1dd78a131366"
			target_chk_value = 0xC297

		if target_chk_value != 0:
			if hashlib.sha1(buffer[0:0x18000]).hexdigest() != target_sha1_value:
				return 0
			elif buffer[0:0x180] == buffer[0x20000:0x20180]:
				return 1
			else:
				return target_chk_value
		else:
			return super().CalcChecksum(buffer=buffer)

	def GetMaxROMSize(self):
		return 1*1024*1024

class DMG_M161(DMG_Mapper):
	def GetName(self):
		return "M161"

	def __init__(self, args=None, cart_write_fncptr=None, cart_read_fncptr=None, cart_powercycle_fncptr=None, clk_toggle_fncptr=None):
		if args is None: args = {}
		self.ROM_BANK_SIZE = 0x8000
		super().__init__(args=args, cart_write_fncptr=cart_write_fncptr, cart_read_fncptr=cart_read_fncptr, cart_powercycle_fncptr=cart_powercycle_fncptr, clk_toggle_fncptr=None)

	def ResetBeforeBankChange(self, index):
		return True

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0x4000, (index & 0x7) ]
		]
		self.CartWrite(commands)
		return (0, 0x8000)

	def GetMaxROMSize(self):
		return 256*1024

class DMG_HuC1(DMG_MBC5):
	def GetName(self):
		return "HuC-1"

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0x2100, index & 0xFF ],
		]

		start_address = 0 if index == 0 else 0x4000

		self.CartWrite(commands)
		return (start_address, self.ROM_BANK_SIZE)

	def EnableRAM(self, enable=True):
		dprint(self.GetName(), "|", enable)
		commands = [
			[ 0x0000, 0x0A if enable else 0x0E ]
		]
		self.CartWrite(commands)

	def GetMaxROMSize(self):
		return 1*1024*1024

class DMG_HuC3(DMG_Mapper):
	def GetName(self):
		return "HuC-3"

	def HasRTC(self):
		return True

	def GetRTCBufferSize(self):
		return 0x0C

	def ReadRTC(self):
		buffer = bytearray()
		commands = [
			[ 0x0000, 0x0B ],
			[ 0xA000, 0x60 ],
			[ 0x0000, 0x0D ],
			[ 0xA000, 0xFE ],
		]
		self.CartWrite(commands)
		time.sleep(0.01)
		commands = [
			[ 0x0000, 0x0C ],
			[ 0x0000, 0x00 ],

			[ 0x0000, 0x0B ],
			[ 0xA000, 0x40 ],
			[ 0x0000, 0x0D ],
			[ 0xA000, 0xFE ],
		]
		self.CartWrite(commands)
		time.sleep(0.01)
		commands = [
			[ 0x0000, 0x0C ],
			[ 0x0000, 0x00 ]
		]
		self.CartWrite(commands)

		rtc = 0
		for i in range(0, 6):
			commands = [
				[ 0x0000, 0x0B ],
				[ 0xA000, 0x10 ],
				[ 0x0000, 0x0D ],
				[ 0xA000, 0xFE ],
			]
			self.CartWrite(commands)
			time.sleep(0.01)
			commands = [
				[ 0x0000, 0x0C ]
			]
			self.CartWrite(commands)
			rtc |= (self.CartRead(0xA000) & 0x0F) << (i * 4)
			self.CartWrite([[ 0x0000, 0x00 ]], delay=0.01)

		buffer.extend(struct.pack("<L", rtc))

		# Add timestamp of backup time
		ts = int(time.time())
		buffer.extend(struct.pack("<Q", ts))

		dstr = ' '.join(format(x, '02X') for x in buffer)
		dprint("RTC: [{:02X}] {:s}".format(int(len(dstr)/3) + 1, dstr))

		self.RTC_BUFFER = buffer
		return buffer

	def WriteRTCDict(self, rtc_dict):
		dprint("Writing RTC:", rtc_dict)
		self.EnableRAM(enable=True)

		total_minutes = 60 * rtc_dict["rtc_h"] + rtc_dict["rtc_m"]
		data = (total_minutes & 0xFFF) | ((rtc_dict["rtc_d"] & 0xFFF) << 12)
		buffer = bytearray(4)
		buffer[0:4] = struct.pack("<I", data)

		commands = [
			[ 0x0000, 0x0B ],
			[ 0xA000, 0x60 ],
			[ 0x0000, 0x0D ],
			[ 0xA000, 0xFE ],
			[ 0x0000, 0x0C ],
			[ 0x0000, 0x00 ],

			[ 0x0000, 0x0B ],
			[ 0xA000, 0x40 ],
			[ 0x0000, 0x0D ],
			[ 0xA000, 0xFE ],
			[ 0x0000, 0x0C ],
			[ 0x0000, 0x00 ]
		]
		self.CartWrite(commands, delay=0.01)

		for i in range(0, 3):
			commands = [
				[ 0x0000, 0x0B ],
				[ 0xA000, 0x30 | (buffer[i] & 0x0F) ],
				[ 0x0000, 0x0D ],
				[ 0xA000, 0xFE ],
				[ 0x0000, 0x00 ],
				[ 0x0000, 0x0D ],

				[ 0x0000, 0x0B ],
				[ 0xA000, 0x30 | ((buffer[i] >> 4) & 0x0F) ],
				[ 0x0000, 0x0D ],
				[ 0xA000, 0xFE ],
				[ 0x0000, 0x00 ],
				[ 0x0000, 0x0D ]
			]
			self.CartWrite(commands, delay=0.03)

		commands = [
			[ 0x0000, 0x0B ],
			[ 0xA000, 0x31 ],
			[ 0x0000, 0x0D ],
			[ 0xA000, 0xFE ],
			[ 0x0000, 0x00 ],
			[ 0x0000, 0x0D ],

			[ 0x0000, 0x0B ],
			[ 0xA000, 0x61 ],
			[ 0x0000, 0x0D ],
			[ 0xA000, 0xFE ],
			[ 0x0000, 0x00 ]
		]
		self.CartWrite(commands, delay=0.03)
		dstr = ' '.join(format(x, '02X') for x in buffer)
		dprint("[{:02X}] {:s}".format(int(len(dstr)/3) + 1, dstr))
		return True

	def WriteRTC(self, buffer, advance=False):
		if advance:
			try:
				dt_now = datetime.datetime.fromtimestamp(time.time())
				dprint(buffer)
				if buffer == bytearray([0x00] * len(buffer)): # Reset
					hours = 0
					minutes = 0
					days = 0
				else:
					data = struct.unpack("<I", buffer[0:4])[0]
					hours = math.floor((data & 0xFFF) / 60)
					minutes = (data & 0xFFF) % 60
					days = (data >> 12) & 0xFFF

					timestamp_then = struct.unpack("<Q", buffer[-8:])[0]
					timestamp_now = int(time.time())
					dprint(hours, minutes, days)
					if timestamp_then < timestamp_now:
						dt_then = datetime.datetime.fromtimestamp(timestamp_then)
						dt_buffer1 = datetime.datetime.strptime("{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(1, 1, 1, 0, 0, 0), "%Y-%m-%d %H:%M:%S")
						dt_buffer2 = datetime.datetime.strptime("{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(1, 1, 1, hours, minutes, 0), "%Y-%m-%d %H:%M:%S")
						dt_buffer2 += datetime.timedelta(days=days)
						rd = relativedelta(dt_now, dt_then)
						dt_new = dt_buffer2 + rd
						dprint(dt_then, dt_now, dt_buffer1, dt_buffer2, dt_new, sep="\n")
						minutes = dt_new.minute
						hours = dt_new.hour
						temp = datetime.date.fromtimestamp(timestamp_now) - datetime.date.fromtimestamp(timestamp_then)
						days = temp.days + days
						dprint(minutes, hours, days)

				d = {
					"rtc_h":hours,
					"rtc_m":minutes,
					"rtc_d":days
				}
				self.WriteRTCDict(d)

			except Exception as e:
				print(__("Error: Couldn’t update the RTC register values.") + "\n" + str(e))

	def GetRTCDict(self):
		if self.RTC_BUFFER is None:
			self.ReadRTC()
		rtc_buffer = struct.unpack("<I", self.RTC_BUFFER[0:4])[0]
		rtc_h = math.floor((rtc_buffer & 0xFFF) / 60)
		rtc_m = (rtc_buffer & 0xFFF) % 60
		rtc_d = (rtc_buffer >> 12) & 0xFFF

		d = {
			"rtc_h":rtc_h,
			"rtc_m":rtc_m,
			"rtc_d":rtc_d,
			"rtc_valid":True
		}

		d["string"] = ___("{days} day, {hours}:{minutes}", "{days} days, {hours}:{minutes}", n=rtc_d, days=rtc_d, hours="{:02d}".format(rtc_h), minutes="{:02d}".format(rtc_m))

		return d

	def GetRTCString(self):
		return self.GetRTCDict()["string"]

	def GetMaxROMSize(self):
		return 2*1024*1024

class DMG_TAMA5(DMG_Mapper):
	def GetName(self):
		return "TAMA5"

	def EnableMapper(self):
		tama5_check = self.CartRead(0xA000)
		lives = 20
		while (tama5_check & 3) != 1:
			dprint("- Current value is 0x{:X}, now writing 0xA001=0x{:X}".format(tama5_check, 0x0A))
			self.CartWrite([[0xA001, 0x0A]], sram=True)
			tama5_check = self.CartRead(0xA000)
			lives -= 1
			if lives < 0:
				print(__("Error: Couldn’t enable the {mapper_name} mapper.", mapper_name="TAMA5"))
				return False
		dprint("Enabled TAMA5 successfully")
		return True

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0xA001, 0x00 ],	# ROM bank (low)
			[ 0xA000, index & 0x0F ],
			[ 0xA001, 0x01 ],	# ROM bank (high)
			[ 0xA000, (index >> 4) & 0x0F ],
		]
		start_address = 0 if index == 0 else 0x4000

		self.CartWrite(commands, sram=True)
		return (start_address, self.ROM_BANK_SIZE)

	def HasRTC(self):
		return True

	def GetRTCBufferSize(self):
		return 0x28

	def ReadRTC(self):
		buffer = bytearray()
		for page in range(0, 4):
			page_buffer = bytearray(8)
			for reg in range(0, 0x10):
				commands = [
					# Select RTC
					[ 0xA001, 0x06 ],
					[ 0xA000, 0x08 ],
					# Select RTC register
					[ 0xA001, 0x04 ],
					[ 0xA000, reg ],
					# Select RTC operation
					[ 0xA001, 0x07 ],
					[ 0xA000, (page << 1) + 1 ],
					# Read data
					[ 0xA001, 0x0C ]
				]
				self.CartWrite(commands, sram=True)
				value1, value2 = None, None
				while value1 is None or value1 != value2:
					value2 = value1
					value1 = self.CartRead(0xA000)
				data = self.CartRead(0xA000) & 0x0F
				if reg % 2 == 0:
					page_buffer[reg>>1] = data
				else:
					page_buffer[reg>>1] |= data << 4
			buffer += page_buffer

		# Add timestamp of backup time
		ts = int(time.time())
		buffer.extend(struct.pack("<Q", ts))

		#dstr = ' '.join(format(x, '02X') for x in buffer)
		#print("[{:02X}] {:s}".format(int(len(dstr)/3) + 1, dstr))

		commands = [
			# Select RTC
			[ 0xA001, 0x00 ]
		]
		self.CartWrite(commands, sram=True)
		self.SelectBankROM(0)

		self.RTC_BUFFER = buffer
		return buffer

	def WriteRTCDict(self, rtc_dict):
		buffer = rtc_dict["rtc_buffer"]
		buffer[0x00] = BCD.encode(rtc_dict["rtc_s"])
		buffer[0x01] = BCD.encode(rtc_dict["rtc_i"])
		buffer[0x02] = BCD.encode(rtc_dict["rtc_h"])
		buffer[0x03] = ((BCD.encode(rtc_dict["rtc_d"]) & 0xF) << 4) | 6 #weekday?
		buffer[0x04] = (BCD.encode(rtc_dict["rtc_d"]) >> 4) | ((BCD.encode(rtc_dict["rtc_m"]) & 0xF) << 4)
		buffer[0x05] = (BCD.encode(rtc_dict["rtc_m"]) >> 4) | ((BCD.encode(rtc_dict["rtc_y"]) & 0xF) << 4)
		buffer[0x06] = (BCD.encode(rtc_dict["rtc_y"]) >> 4)
		buffer[0x0D] = rtc_dict["rtc_leap_year_state"] << 4 | 1 #24h flag

		for page in range(0, 5):
			if page == 0:
				commands = [
					# Select TAMA6
					[ 0xA001, 0x06 ],
					[ 0xA000, 0x04 ],
					# Stop timer
					[ 0xA001, 0x06 ],
					[ 0xA000, 0x04 ],
					[ 0xA001, 0x07 ],
					[ 0xA000, 0x00 ],
				]
				commands = [
					# Select TAMA6
					[ 0xA001, 0x06 ],
					[ 0xA000, 0x04 ],
					# Reset timer
					[ 0xA001, 0x06 ],
					[ 0xA000, 0x04 ],
					[ 0xA001, 0x07 ],
					[ 0xA000, 0x01 ],
				]
				self.CartWrite(commands, sram=True)

			page_buffer = buffer[page*8:page*8+8]
			for reg in range(0, 0x0D):
				commands = [
					# Select RTC
					[ 0xA001, 0x06 ],
					[ 0xA000, 0x08 ],
					# Select RTC register
					[ 0xA001, 0x04 ],
					[ 0xA000, reg ],
					# Set data
					[ 0xA001, 0x05 ]
				]
				self.CartWrite(commands, sram=True)
				if reg % 2 == 0:
					self.CartWrite([[ 0xA000, page_buffer[reg>>1] & 0xF ]], sram=True)
				else:
					self.CartWrite([[ 0xA000, page_buffer[reg>>1] >> 4 ]], sram=True)
				commands = [
					# Select RTC operation
					[ 0xA001, 0x07 ],
					[ 0xA000, (page << 1) ],
					# Read data
					[ 0xA001, 0x0C ]
				]
				self.CartWrite(commands, sram=True)
				value1, value2 = None, None
				while value1 is None or value1 != value2:
					value2 = value1
					value1 = self.CartRead(0xA000)

		return True

	def WriteRTC(self, buffer, advance=False):
		if advance:
			try:
				dt_now = datetime.datetime.fromtimestamp(time.time())
				if buffer == bytearray([0x00] * len(buffer)): # Reset
					seconds = 0
					minutes = 0
					hours = 0
					weekday = 0
					days = 1
					months = 1
					years = 0
					leap_year_state = 0
					#z24h_flag = 1
				else:
					#dstr = ' '.join(format(x, '02X') for x in buffer)
					#print("[{:02X}] {:s}".format(int(len(dstr)/3) + 1, dstr))

					seconds = BCD.decode(buffer[0x00])
					minutes = BCD.decode(buffer[0x01])
					hours = BCD.decode(buffer[0x02])
					weekday = buffer[0x03] & 0xF
					days = BCD.decode(buffer[0x03] >> 4 | (buffer[0x04] & 0xF) << 4)
					months = BCD.decode(buffer[0x04] >> 4 | (buffer[0x05] & 0xF) << 4)
					years = BCD.decode(buffer[0x05] >> 4 | (buffer[0x06] & 0xF) << 4)
					leap_year_state = BCD.decode(buffer[0x0D] >> 4)
					#z24h_flag = BCD.decode(buffer[0x0D] & 0xF)
					#print("Old:", seconds, minutes, hours, day_of_week, days, months, years, leap_year_state, z24h_flag)

					timestamp_then = struct.unpack("<Q", buffer[-8:])[0]
					timestamp_now = int(time.time())
					if timestamp_then < timestamp_now:
						dt_then = datetime.datetime.fromtimestamp(timestamp_then)
						dt_buffer = datetime.datetime.strptime("{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(2000 + leap_year_state, months, days, hours % 24, minutes % 60, seconds % 60), "%Y-%m-%d %H:%M:%S")
						rd = relativedelta(dt_now, dt_then)
						dt_new = dt_buffer + rd

						# Weird cases
						year_new = (dt_new.year - 2000 - leap_year_state) 
						years += year_new
						if years >= 160:
							years -= 140
						elif years >= 140:
							years -= 100
						elif years >= 120:
							years -= 60
						elif years >= 100 and (years - year_new) < 100:
							years -= 100

						months = dt_new.month
						days = dt_new.day
						hours = dt_new.hour
						minutes = dt_new.minute
						seconds = dt_new.second
						dt_buffer_notime = dt_buffer.replace(hour=0, minute=0, second=0)
						dt_new_notime = dt_new.replace(hour=0, minute=0, second=0)
						days_passed = int((dt_new_notime.timestamp() - dt_buffer_notime.timestamp()) / 60 / 60 / 24)
						weekday += days_passed % 7
						leap_year_state = (leap_year_state + year_new) % 4

			except Exception as e:
				print(__("Error: Couldn’t update the RTC register values.") + "\n" + str(e))
				return

			d = {
				"rtc_y":years,
				"rtc_m":months,
				"rtc_d":days,
				"rtc_h":hours,
				"rtc_i":minutes,
				"rtc_s":seconds,
				"rtc_leap_year_state":leap_year_state,
				"rtc_buffer":buffer,
				"rtc_valid":True
			}
			self.WriteRTCDict(d)
			return

		# advance=False: write raw nibbles directly to preserve all bit fields
		# (bypasses WriteRTCDict which hardcodes weekday=6 in BCD encode)
		for page in range(0, 4):
			page_buffer = buffer[page*8:page*8+8]
			for reg in range(0, 0x0D):
				commands = [
					[ 0xA001, 0x06 ], [ 0xA000, 0x08 ],
					[ 0xA001, 0x04 ], [ 0xA000, reg ],
					[ 0xA001, 0x05 ]
				]
				self.CartWrite(commands, sram=True)
				if reg % 2 == 0:
					self.CartWrite([ [ 0xA000, page_buffer[reg>>1] & 0xF ] ], sram=True)
				else:
					self.CartWrite([ [ 0xA000, page_buffer[reg>>1] >> 4 ] ], sram=True)
				commands2 = [
					[ 0xA001, 0x07 ], [ 0xA000, page << 1 ],
					[ 0xA001, 0x0C ]
				]
				self.CartWrite(commands2, sram=True)
				value1, value2 = None, None
				while value1 is None or value1 != value2:
					value2 = value1
					value1 = self.CartRead(0xA000)

	def GetRTCDict(self):
		if self.RTC_BUFFER is None:
			self.ReadRTC()
		rtc_buffer = self.RTC_BUFFER
		seconds = BCD.decode(rtc_buffer[0x00])
		minutes = BCD.decode(rtc_buffer[0x01])
		hours = BCD.decode(rtc_buffer[0x02])
		#weekday = rtc_buffer[0x03] & 0xF
		days = BCD.decode(rtc_buffer[0x03] >> 4 | (rtc_buffer[0x04] & 0xF) << 4)
		months = BCD.decode(rtc_buffer[0x04] >> 4 | (rtc_buffer[0x05] & 0xF) << 4)
		years = BCD.decode(rtc_buffer[0x05] >> 4 | (rtc_buffer[0x06] & 0xF) << 4)
		leap_year_state = BCD.decode(rtc_buffer[0x0D] >> 4)

		d = {
			"rtc_y":years,
			"rtc_m":months,
			"rtc_d":days,
			#"rtc_w":weekday,
			"rtc_h":hours,
			"rtc_i":minutes,
			"rtc_s":seconds,
			"rtc_leap_year_state":leap_year_state,
			"rtc_buffer":rtc_buffer,
			"rtc_valid":True
		}

		year_count = years - 19
		if leap_year_state == 0:
			years_label = c___("ᴸ means leap year", "{years} yearᴸ", "{years} yearsᴸ", n=year_count, years=year_count)
		else:
			years_label = ___("{years} year", "{years} years", n=year_count, years=year_count)
		d["string"] = __("{years_label}, {month}-{day}, {hours}:{minutes}:{seconds}", years_label=years_label, month=months, day=days, hours="{:02d}".format(hours), minutes="{:02d}".format(minutes), seconds="{:02d}".format(seconds))
		return d

	def GetRTCString(self):
		return self.GetRTCDict()["string"]

	def ReadWithCSPulse(self):
		return False

	def WriteWithCSPulse(self):
		return True

	def GetMaxROMSize(self):
		return 512*1024

class DMG_Unlicensed_256M(DMG_MBC5):
	def GetName(self):
		return "256M Multi Cart"

	def HasFlashBanks(self):
		return True

	def SelectBankFlash(self, index):
		flash_bank = math.floor(index / 512)
		dprint(self.GetName(), "|SelectBankFlash()|", index, "->", flash_bank)

		if self.CURRENT_FLASH_BANK != flash_bank:
			dprint("Power cycling now")
			self.CART_POWERCYCLE_FNCPTR()
			self.CURRENT_FLASH_BANK = flash_bank

		commands = [
			[ 0x7000, 0x00 ],
			[ 0x7001, 0x00 ],
			[ 0x7002, 0x80 + flash_bank ]
		]
		self.CURRENT_FLASH_BANK = flash_bank
		self.CartWrite(commands, delay=0.1)

	def SelectBankROM(self, index):
		dprint(self.GetName(), index)

		if (index % 512 == 0) or (self.CURRENT_FLASH_BANK != math.floor(index / 512)):
			self.SelectBankFlash(index)
		self.CURRENT_ROM_BANK = index
		index = index % 512

		commands = [
			[ 0x3000, ((index >> 8) & 0xFF) ],
			[ 0x2100, index & 0xFF ],
		]

		start_address = 0 if index == 0 else 0x4000
		self.CartWrite(commands)

		return (start_address, self.ROM_BANK_SIZE)

	def SelectBankRAM(self, index):
		dprint(self.GetName(), "|", index)

		flash_bank = math.floor(index / 0x10)

		if index % 4 == 0:
			self.EnableRAM(enable=False)
			#self.CART_POWERCYCLE_FNCPTR()
			self.CURRENT_FLASH_BANK = flash_bank

			commands = [
				[ 0x7000, (0x40 * math.floor(index / 4)) & 0xFF ],
				[ 0x7001, 0xC0 ],
				[ 0x7002, 0x00 + flash_bank ]
			]
			self.CartWrite(commands, delay=0.01)
			self.EnableRAM(enable=True)
			dprint(hex(index), hex(0x10 + flash_bank), hex((0x40 * math.floor(index / 4)) & 0xFF))

		commands = [
			[ 0x4000, index % 4 ]
		]
		start_address = 0
		self.CartWrite(commands)

		return (start_address, self.RAM_BANK_SIZE)

	def GetMaxROMSize(self):
		return 32*1024*1024

class DMG_Unlicensed_WisdomTree(DMG_Mapper):
	def GetName(self):
		return "Wisdom Tree"

	def __init__(self, args=None, cart_write_fncptr=None, cart_read_fncptr=None, cart_powercycle_fncptr=None, clk_toggle_fncptr=None):
		if args is None: args = {}
		self.ROM_BANK_SIZE = 0x8000
		super().__init__(args=args, cart_write_fncptr=cart_write_fncptr, cart_read_fncptr=cart_read_fncptr, cart_powercycle_fncptr=cart_powercycle_fncptr, clk_toggle_fncptr=None)

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ index, 0 ]
		]
		self.CartWrite(commands)
		return (0, 0x8000)

	def GetMaxROMSize(self):
		return 2*1024*1024

class DMG_Unlicensed_XploderGB(DMG_Mapper):
	def GetName(self):
		return "Xploder GB"

	def __init__(self, args=None, cart_write_fncptr=None, cart_read_fncptr=None, cart_powercycle_fncptr=None, clk_toggle_fncptr=None):
		if args is None: args = {}
		super().__init__(args=args, cart_write_fncptr=cart_write_fncptr, cart_read_fncptr=cart_read_fncptr, cart_powercycle_fncptr=cart_powercycle_fncptr, clk_toggle_fncptr=None)
		self.RAM_BANK_SIZE = 0x4000

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		if index == 0:
			self.CartRead(0x0102, 1)
			self.CART_POWERCYCLE_FNCPTR()
			self.CartRead(0x0102, 1)
		self.CartWrite([[ 0x0006, index & 0xFF ]])
		self.CURRENT_ROM_BANK = index
		start_address = 0x4000
		return (start_address, self.ROM_BANK_SIZE)

	def SelectBankRAM(self, index):
		dprint(self.GetName(), "|", index)
		if index == 0:
			self.CartRead(0x0102, 1)
			self.CART_POWERCYCLE_FNCPTR()
			self.CartRead(0x0102, 1)
		return self.SelectBankROM(index + 8)

	def GetMaxROMSize(self):
		return 128*1024

class DMG_Unlicensed_Sachen(DMG_Mapper):
	def GetName(self):
		return "Sachen"

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		commands = [
			[ 0x2000, index + self.START_BANK ]
		]
		self.CartWrite(commands)
		start_address = 0x4000
		return (start_address, self.ROM_BANK_SIZE)

	def GetMaxROMSize(self):
		return 2*1024*1024

class DMG_Unlicensed_DatelOrbitV2(DMG_Mapper):
	def GetName(self):
		return "Datel Orbit V2"

	def __init__(self, args=None, cart_write_fncptr=None, cart_read_fncptr=None, cart_powercycle_fncptr=None, clk_toggle_fncptr=None):
		if args is None: args = {}
		self.ROM_BANK_SIZE = 0x2000
		super().__init__(args=args, cart_write_fncptr=cart_write_fncptr, cart_read_fncptr=cart_read_fncptr, cart_powercycle_fncptr=cart_powercycle_fncptr, clk_toggle_fncptr=None)

	def SelectBankROM(self, index):
		dprint(self.GetName(), "|", index)
		if index == 0:
			self.CartRead(0x0101, 1)
			self.CartRead(0x0108, 1)
			self.CartRead(0x0101, 1)
		self.CartWrite([[ 0x7FE1, index & 0xFF ]])
		start_address = 0x4000
		return (start_address, self.ROM_BANK_SIZE)

	def GetMaxROMSize(self):
		return 128*1024

class DMG_Unlicensed_MBCX(DMG_MBC3):
	def GetName(self):
		return "MBCX"

	def HasFlashBanks(self):
		return True

	def SelectBankFlash(self, index):
		dprint(self.GetName(), "|SelectBankFlash()|", index)

		commands = [
			[ 0x0000, 0x05 ],
			[ 0x4000, 0x82 ],
			[ 0xA000, index ],
			[ 0x0000, 0x00 ]
		]
		self.CURRENT_FLASH_BANK = index
		self.CartWrite(commands, delay=0.1)

	def SelectBankROM(self, index):
		dprint(self.GetName(), index)

		if (index % 512 == 0) or (self.CURRENT_FLASH_BANK != math.floor(index / 512)):
			self.SelectBankFlash(math.floor(index / 512))
		self.CURRENT_ROM_BANK = index
		index = index % 512

		commands = [
			[ 0x3000, ((index >> 8) & 0xFF) ],
			[ 0x2100, index & 0xFF ],
		]

		self.CartWrite(commands)
		return (0x4000, self.ROM_BANK_SIZE)

	def ApplyROMWriteBankSwitchSeparator(self, index):
		dprint(self.GetName(), "| ROM write bank switch separator |", index)
		self.CartWrite([[ 0x4000, 0x00 ]])
		return True

	def GetMaxROMSize(self):
		return 32*1024*1024


class AGB_GPIO:
	CART_WRITE_FNCPTR = None
	CART_READ_FNCPTR = None
	CLK_TOGGLE_FNCPTR = None
	RTC = False
	RTC_BUFFER = None

	# Addresses
	GPIO_REG_DAT = 0xC4 # Data
	GPIO_REG_CNT = 0xC6 # IO Select
	GPIO_REG_RE = 0xC8 # Read Enable Flag Register

	# Commands
	RTC_RESET = 0x60
	RTC_WRITE_STATUS = 0x62
	RTC_READ_STATUS = 0x63
	RTC_WRITE_DATE = 0x64
	RTC_READ_DATE = 0x65
	RTC_WRITE_TIME = 0x66
	RTC_READ_TIME = 0x67
	RTC_WRITE_ALARM = 0x68
	RTC_READ_ALARM = 0x69

	def __init__(self, args=None, cart_write_fncptr=None, cart_read_fncptr=None, cart_powercycle_fncptr=None, clk_toggle_fncptr=None):
		if args is None: args = {}
		self.CART_WRITE_FNCPTR = cart_write_fncptr
		self.CART_READ_FNCPTR = cart_read_fncptr
		self.CART_POWERCYCLE_FNCPTR = cart_powercycle_fncptr
		self.CLK_TOGGLE_FNCPTR = clk_toggle_fncptr
		if "rtc" in args: self.RTC = args["rtc"]

	def CartRead(self, address, length=0):
		if length == 0: # auto size:
			address = address * 2
			data = self.CART_READ_FNCPTR(address)
			data = struct.pack(">H", data)
			data = struct.unpack("<H", data)[0]
			#dprint("0x{:X} is 0x{:X}".format(address, data))
		else:
			data = self.CART_READ_FNCPTR(address, length)
			#dprint("0x{:X} is".format(address), data)

		return data

	def CartWrite(self, commands, delay=False):
		for command in commands:
			address = command[0]
			value = command[1]
			# dprint("0x{:X} = 0x{:X}".format(address, value))
			self.CART_WRITE_FNCPTR(address, value)
			if delay is not False: time.sleep(delay)

	def RTCCommand(self, command):
		for i in range(0, 8):
			bit = (command >> (7 - i)) & 0x01
			self.CartWrite([
				[ self.GPIO_REG_DAT, 4 | (bit << 1) ],
				[ self.GPIO_REG_DAT, 4 | (bit << 1) ],
				[ self.GPIO_REG_DAT, 4 | (bit << 1) ],
				[ self.GPIO_REG_DAT, 5 | (bit << 1) ]
			])

	def RTCReadData(self):
		data = 0
		for _ in range(0, 8):
			self.CartWrite([
				[ self.GPIO_REG_DAT, 4 ],
				[ self.GPIO_REG_DAT, 4 ],
				[ self.GPIO_REG_DAT, 4 ],
				[ self.GPIO_REG_DAT, 4 ],
				[ self.GPIO_REG_DAT, 4 ],
				[ self.GPIO_REG_DAT, 5 ]
			])
			temp = self.CartRead(self.GPIO_REG_DAT) & 0xFF
			bit = (temp & 2) >> 1
			data = (data >> 1) | (bit << 7)
			# dprint("RTCReadData(): i={:d}/temp={:X}/bit={:x}/data={:x}".format(i, temp, bit, data))
		return data

	def RTCWriteData(self, data):
		for i in range(0, 8):
			bit = (data >> i) & 0x01
			self.CartWrite([
				[ self.GPIO_REG_DAT, 4 | (bit << 1) ],
				[ self.GPIO_REG_DAT, 4 | (bit << 1) ],
				[ self.GPIO_REG_DAT, 4 | (bit << 1) ],
				[ self.GPIO_REG_DAT, 5 | (bit << 1) ]
			])

	def RTCReadStatus(self):
		self.CartWrite([
			[ self.GPIO_REG_RE, 1 ], # Enable RTC Mapping
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_DAT, 5 ],
			[ self.GPIO_REG_CNT, 7 ], # Write Enable
		])
		self.RTCCommand(self.RTC_READ_STATUS)
		self.CartWrite([
			[ self.GPIO_REG_CNT, 5 ], # Read Enable
		])
		data = self.RTCReadData()
		self.CartWrite([
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_RE, 0 ], # Disable RTC Mapping
		])
		return data

	def RTCWriteStatus(self, value):
		self.CartWrite([
			[ self.GPIO_REG_RE, 1 ], # Enable RTC Mapping
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_DAT, 5 ],
			[ self.GPIO_REG_CNT, 7 ], # Write Enable
		])
		self.RTCCommand(self.RTC_WRITE_STATUS)
		self.RTCWriteData(value)

		self.CartWrite([
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_RE, 0 ], # Disable RTC Mapping
		])

	def HasRTC(self, buffer=None):
		if not self.RTC: return False
		if buffer is not None: self.RTC_BUFFER = buffer[1:]

		if buffer is None:
			status = self.RTCReadStatus()
		else:
			status = buffer[0]

		dprint("Status:", bin(status))
		if (status >> 7) == 1:
			dprint("No RTC because of set RTC Status Register Power Flag:", status >> 7 & 1)
			return 1
		if (status >> 6) != 1:
			dprint("Unexpected RTC Status Register 24h Flag:", status >> 6 & 1)
			#return 2

		rom1 = self.CartRead(self.GPIO_REG_DAT, 6)
		if buffer is None:
			self.CartWrite([
				[ self.GPIO_REG_RE, 1 ], # Enable RTC Mapping
			])
			rom2 = self.CartRead(self.GPIO_REG_DAT, 6)
			self.CartWrite([
				[ self.GPIO_REG_RE, 0 ], # Disable RTC Mapping
			])
		else:
			rom2 = buffer[1:7]

		dprint("RTC Data:", ' '.join(format(x, '02X') for x in rom1), "/", ' '.join(format(x, '02X') for x in rom2))
		if (rom1 == rom2):
			dprint("No RTC because ROM data didn’t change:", rom1, rom2)
			return 3

		return True

	def ReadRTC(self, buffer=None):
		if not self.RTC: return False
		if buffer is None:
			self.CartWrite([
				[ self.GPIO_REG_RE, 1 ], # Enable RTC Mapping
				[ self.GPIO_REG_DAT, 1 ],
				[ self.GPIO_REG_DAT, 5 ],
				[ self.GPIO_REG_CNT, 7 ], # Write Enable
			])
			self.RTCCommand(self.RTC_READ_DATE)
			self.CartWrite([
				[ self.GPIO_REG_CNT, 5 ], # Read Enable
			])
			buffer = bytearray()
			for _ in range(0, 7):
				buffer.append(self.RTCReadData())

			self.CartWrite([
				[ self.GPIO_REG_DAT, 1 ],
				[ self.GPIO_REG_DAT, 1 ],
				[ self.GPIO_REG_RE, 0 ], # Disable RTC Mapping
			])

		# Add timestamp of backup time
		buffer.append(self.RTCReadStatus()) # 24h mode = 0x40, reset flag = 0x80
		buffer.extend(struct.pack("<Q", int(time.time())))

		dprint(' '.join(format(x, '02X') for x in buffer))

		# Digits are BCD (Binary Coded Decimal)
		#[07] 00 01 27 05 06 30 20
		#[07] 00 01 27 05 06 30 28
		# "27 days, 06:51:55"
		#[07] 00 01 27 05 06 52 18
		#     YY MM DD WW HH MM SS
		self.RTC_BUFFER = buffer
		return buffer

	def WriteRTCDict(self, rtc_dict):
		buffer = bytearray(7)
		try:
			buffer[0] = BCD.encode(rtc_dict["rtc_y"])
			buffer[1] = BCD.encode(rtc_dict["rtc_m"])
			buffer[2] = BCD.encode(rtc_dict["rtc_d"])
			buffer[3] = BCD.encode(rtc_dict["rtc_w"] % 7)
			buffer[4] = BCD.encode(rtc_dict["rtc_h"])
			if buffer[4] >= 12: buffer[4] |= 0x80
			buffer[5] = BCD.encode(rtc_dict["rtc_i"])
			buffer[6] = BCD.encode(rtc_dict["rtc_s"])
			dprint("New values: RTC_Y=0x{:02X}, RTC_M=0x{:02X}, RTC_D=0x{:02X}, RTC_W=0x{:02X}, RTC_H=0x{:02X}, RTC_I=0x{:02X}, RTC_S=0x{:02X}".format(buffer[0], buffer[1], buffer[2], buffer[3], buffer[4], buffer[5], buffer[6]))
		except ValueError as e:
			print(__("Error: Couldn’t update the RTC register values.") + "\n" + str(e))

		self.CartWrite([
			[ self.GPIO_REG_RE, 1 ], # Enable RTC Mapping
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_DAT, 5 ],
			[ self.GPIO_REG_CNT, 7 ], # Write Enable
		])
		self.RTCCommand(self.RTC_WRITE_DATE)
		for i in range(0, 7):
			self.RTCWriteData(buffer[i])

		self.CartWrite([
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_DAT, 1 ],
			[ self.GPIO_REG_RE, 0 ], # Disable RTC Mapping
		])
		return True

	def WriteRTC(self, buffer, advance=False):
		rtc_status = None
		if buffer == bytearray([0xFF] * len(buffer)): # Reset
			years = 0
			months = 1
			days = 1
			weekday = 6 # 2000-01-01 was Saturday; GBA RTC uses Sunday=0
			hours = 0
			minutes = 0
			seconds = 0
			# rtc_status = 0x40 | 0x80 # 24h mode + reset flag
			rtc_status = 0x40 # 24h mode (reset flag causes issues on some flash cartridges)
		else:
			years = BCD.decode(buffer[0x00])
			months = BCD.decode(buffer[0x01])
			days = BCD.decode(buffer[0x02])
			weekday = BCD.decode(buffer[0x03]) % 7
			hours = BCD.decode(buffer[0x04] & 0x7F)
			minutes = BCD.decode(buffer[0x05])
			seconds = BCD.decode(buffer[0x06])
			rtc_status = buffer[0x07]
			if rtc_status == 0x01: rtc_status = 0x40 # old dumps had this value

		if advance:
			try:
				dt_now = datetime.datetime.fromtimestamp(time.time())
				timestamp_then = struct.unpack("<Q", buffer[-8:])[0]
				timestamp_now = int(time.time())
				if timestamp_then < timestamp_now:
					dt_then = datetime.datetime.fromtimestamp(timestamp_then)
					dt_buffer = datetime.datetime.strptime("{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(years + 2000, months % 13, days % 32, hours % 60, minutes % 60, seconds % 60), "%Y-%m-%d %H:%M:%S")
					rd = relativedelta(dt_now, dt_then)
					dt_new = dt_buffer + rd
					years = dt_new.year - 2000
					months = dt_new.month
					days = dt_new.day
					dt_buffer_notime = dt_buffer.replace(hour=0, minute=0, second=0)
					dt_new_notime = dt_new.replace(hour=0, minute=0, second=0)
					days_passed = int((dt_new_notime.timestamp() - dt_buffer_notime.timestamp()) / 60 / 60 / 24)
					weekday = (weekday + days_passed) % 7
					hours = dt_new.hour
					minutes = dt_new.minute
					seconds = dt_new.second

				#dprint(years, months, days, weekday, hours, minutes, seconds)
				buffer[0x00] = BCD.encode(years)
				buffer[0x01] = BCD.encode(months)
				buffer[0x02] = BCD.encode(days)
				buffer[0x03] = BCD.encode(weekday % 7)
				buffer[0x04] = BCD.encode(hours)
				if hours >= 12: buffer[0x04] |= 0x80
				buffer[0x05] = BCD.encode(minutes)
				buffer[0x06] = BCD.encode(seconds)

				dstr = ' '.join(format(x, '02X') for x in buffer)
				dprint("[{:02X}] {:s}".format(int(len(dstr)/3) + 1, dstr))

			except Exception as e:
				print(__("Error: Couldn’t update the RTC register values.") + "\n" + str(e))

		d = {
			"rtc_y":years,
			"rtc_m":months,
			"rtc_d":days,
			"rtc_w":weekday % 7,
			"rtc_h":hours,
			"rtc_i":minutes,
			"rtc_s":seconds,
		}
		dprint(d)
		self.WriteRTCDict(d)

		if rtc_status is not None:
			self.RTCWriteStatus(rtc_status)

	def GetRTCDict(self, has_rtc=None):
		if has_rtc is None:
			has_rtc = self.HasRTC()
		if has_rtc is not True:
			if has_rtc is False or has_rtc in (2, 3):
				return {"string":__("Not available")}
			elif has_rtc == 1:
				return {"string":__("Not available / Battery dry")}

		if self.RTC_BUFFER is None:
			self.ReadRTC()
		rtc_buffer = self.RTC_BUFFER

		#weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
		rtc_y = (rtc_buffer[0] & 0x0F) + ((rtc_buffer[0] >> 4) * 10)
		rtc_m = (rtc_buffer[1] & 0x0F) + ((rtc_buffer[1] >> 4) * 10)
		rtc_d = (rtc_buffer[2] & 0x0F) + ((rtc_buffer[2] >> 4) * 10)
		rtc_w = ((rtc_buffer[3] & 0x0F) + ((rtc_buffer[3] >> 4) * 10)) % 7
		rtc_h = ((rtc_buffer[4] & 0x0F) + (((rtc_buffer[4] >> 4) & 0x7) * 10))
		rtc_i = (rtc_buffer[5] & 0x0F) + ((rtc_buffer[5] >> 4) * 10)
		rtc_s = (rtc_buffer[6] & 0x0F) + ((rtc_buffer[6] >> 4) * 10)

		d = {
			"rtc_y":rtc_y,
			"rtc_m":rtc_m,
			"rtc_d":rtc_d,
			"rtc_w":rtc_w,
			"rtc_h":rtc_h,
			"rtc_i":rtc_i,
			"rtc_s":rtc_s,
			"rtc_24h":rtc_buffer[0] >> 6 & 1
		}

		if rtc_y == 0 and rtc_m == 0 and rtc_d == 0 and rtc_h == 0 and rtc_i == 0 and rtc_s == 0:
			d["string"] = __("Invalid RTC data")
			d["rtc_valid"] = False
		else:
			d["string"] = __("20{year}-{month}-{day} {hours}:{minutes}:{seconds}", year="{:02d}".format(rtc_y), month="{:02d}".format(rtc_m), day="{:02d}".format(rtc_d), hours="{:02d}".format(rtc_h), minutes="{:02d}".format(rtc_i), seconds="{:02d}".format(rtc_s))
			d["rtc_valid"] = True

		return d

	def GetRTCString(self, has_rtc=None):
		return self.GetRTCDict(has_rtc=has_rtc)["string"]
