# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import math, time, datetime, copy, configparser, threading, os, platform, traceback, io, struct, re, statistics, random, sys
from io import StringIO
from enum import Enum

# Common constants
APPNAME = "FlashGBX"
VERSION_PEP440 = "4.6"
VERSION = "v{:s}".format(VERSION_PEP440)
VERSION_TIMESTAMP = 1769513530
DEBUG = False
DEBUG_LOG = []
APP_PATH = ""
CONFIG_PATH = ""

AGB_Header_ROM_Sizes = [ "32 KiB", "64 KiB", "128 KiB", "256 KiB", "512 KiB", "1 MiB", "2 MiB", "4 MiB", "8 MiB", "16 MiB", "32 MiB", "64 MiB", "128 MiB", "256 MiB", "512 MiB" ]
AGB_Header_ROM_Sizes_Map = [ 0x8000, 0x10000, 0x20000, 0x40000, 0x80000, 0x100000, 0x200000, 0x400000, 0x800000, 0x1000000, 0x2000000, 0x4000000, 0x8000000, 0x10000000, 0x20000000 ]
AGB_Header_Save_Types = [ "None", "4K EEPROM (512 Bytes)", "64K EEPROM (8 KiB)", "256K SRAM/FRAM (32 KiB)", "512K FLASH (64 KiB)", "1M FLASH (128 KiB)", "8M DACS (1 MiB)", "Unlicensed 512K SRAM (64 KiB)", "Unlicensed 1M SRAM (128 KiB)", "Unlicensed Batteryless SRAM" ]
AGB_Header_Save_Sizes = [ 0, 512, 8192, 32768, 65536, 131072, 1048576, 65536, 131072, 0 ]
AGB_Flash_Save_Chips = { 0xBFD4:"SST 39VF512", 0x1F3D:"Atmel AT29LV512", 0xC21C:"Macronix MX29L512", 0x321B:"Panasonic MN63F805MNP", 0xC209:"Macronix MX29L010", 0x6213:"SANYO LE26FV10N1TS", 0xBF4B:"Unlicensed SST25VF064C", 0xBF5B:"Unlicensed SST49LF080A", 0xBF6D:"Unlicensed SST39VF6401B", 0xFFFF:"Unlicensed 0xFFFF" }
AGB_Flash_Save_Chips_Sizes = [ 0x10000, 0x10000, 0x10000, 0x10000, 0x20000, 0x20000, 0x20000, 0x20000, 0x20000, 0x20000 ]

DMG_Header_Mapper = { 0x00:'None', 0x01:'MBC1', 0x02:'MBC1+SRAM', 0x03:'MBC1+SRAM+BATTERY', 0x06:'MBC2+SRAM+BATTERY', 0x0F:'MBC3+RTC+BATTERY', 0x10:'MBC3+RTC+SRAM+BATTERY', 0x110:'MBC30+RTC+SRAM+BATTERY', 0x12:'MBC3+SRAM', 0x13:'MBC3+SRAM+BATTERY', 0x19:'MBC5', 0x1A:'MBC5+SRAM', 0x1B:'MBC5+SRAM+BATTERY', 0x1C:'MBC5+RUMBLE', 0x1E:'MBC5+RUMBLE+SRAM+BATTERY', 0x20:'MBC6+SRAM+FLASH+BATTERY', 0x22:'MBC7+ACCELEROMETER+EEPROM', 0x101:'MBC1M', 0x103:'MBC1M+SRAM+BATTERY', 0x0B:'MMM01',  0x0D:'MMM01+SRAM+BATTERY', 0xFC:'MAC-GBD+SRAM+BATTERY', 0x105:'G-MMC1+SRAM+BATTERY', 0x104:'M161', 0xFF:'HuC-1+IR+SRAM+BATTERY', 0xFE:'HuC-3+RTC+SRAM+BATTERY', 0xFD:'TAMA5+RTC+EEPROM', 0x201:'Unlicensed 256M Mapper', 0x202:'Unlicensed Wisdom Tree Mapper', 0x203:'Unlicensed Xploder GB Mapper', 0x204:'Unlicensed Sachen Mapper', 0x205:'Unlicensed Datel Orbit V2 Mapper', 0x206:'Unlicensed MBCX Mapper' }
DMG_Mapper_Types = { "None":[ 0x00, 0x08, 0x09 ], "MBC1":[ 0x01, 0x02, 0x03 ], "MBC2":[ 0x05, 0x06 ], "MBC3":[ 0x0F, 0x10, 0x11, 0x12, 0x13 ], "MBC30":[ 0x110 ], "MBC5":[ 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E ], "MBC6":[ 0x20 ], "MBC7":[ 0x22 ], "MBC1M":[ 0x101, 0x103 ], "MMM01":[ 0x0B, 0x0D ], "MAC-GBD":[ 0xFC ], "G-MMC1":[ 0x105 ], "M161":[ 0x104 ], "HuC-1":[ 0xFF ], "HuC-3":[ 0xFE ], "TAMA5":[ 0xFD ], "Unlicensed 256M Multi Cart Mapper":[ 0x201 ], "Unlicensed Wisdom Tree Mapper":[ 0x202 ], "Unlicensed Xploder GB Mapper":[ 0x203 ], "Unlicensed Sachen Mapper":[ 0x204 ], "Unlicensed Datel Orbit V2 Mapper":[ 0x205 ], "Unlicensed MBCX Mapper":[ 0x206 ] }
DMG_Header_ROM_Sizes = [ "32 KiB", "64 KiB", "128 KiB", "256 KiB", "512 KiB", "1 MiB", "2 MiB", "4 MiB", "8 MiB", "16 MiB", "32 MiB", "64 MiB", "128 MiB" ]
DMG_Header_ROM_Sizes_Map = [ 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C ]
DMG_Header_ROM_Sizes_Flasher_Map = [ 0x8000, 0x10000, 0x20000, 0x40000, 0x80000, 0x100000, 0x200000, 0x400000, 0x800000, 0x1000000, 0x2000000, 0x4000000, 0x8000000 ]
DMG_Header_RAM_Sizes = [ "None", "4K SRAM (512 Bytes)", "16K SRAM (2 KiB)", "64K SRAM (8 KiB)", "256K SRAM (32 KiB)", "512K SRAM (64 KiB)", "1M SRAM (128 KiB)", "MBC6 SRAM+FLASH (1.03 MiB)", "MBC7 2K EEPROM (256 Bytes)", "MBC7 4K EEPROM (512 Bytes)", "TAMA5 EEPROM (32 Bytes)", "Unlicensed 4M SRAM (512 KiB)", "Unlicensed 1M EEPROM (128 KiB)", "Unlicensed Photo! Directory (1 MiB)", "Unlicensed Batteryless SRAM" ]
DMG_Header_RAM_Sizes_Map = [ 0x00, 0x100, 0x01, 0x02, 0x03, 0x05, 0x04, 0x104, 0x101, 0x102, 0x103, 0x201, 0x203, 0x204, 0x205 ]
DMG_Header_RAM_Sizes_Flasher_Map = [ 0, 0x200, 0x800, 0x2000, 0x8000, 0x10000, 0x20000, 0x108000, 0x100, 0x200, 0x20, 0x80000, 0x20000, 0x100000, 0x80000 ] # RAM size in bytes
DMG_Header_SGB = { 0x00:'No support', 0x03:'Supported' }
DMG_Header_CGB = { 0x00:'No support', 0x80:'Supported', 0xC0:'Required' }

class ANSI:
	BOLD = '\033[1m'
	RED = '\033[91m'
	GREEN = '\033[92m'
	YELLOW = '\033[33m'
	DARK_GRAY = '\033[90m'
	RESET = '\033[0m'
	CLEAR_LINE = '\033[2K'

class IniSettings():
	FILENAME = ""
	SETTINGS = None
	MAIN_SECTION = "General"
	def __init__(self, path="", ini="", main_section="General"):
		if path != "":
			try:
				if not os.path.isdir(os.path.dirname(path)):
					os.makedirs(os.path.dirname(path))
				if os.path.exists(path):
					with open(path, "a+", encoding="UTF-8") as f: f.close()
				else:
					with open(path, "w+", encoding="UTF-8") as f: f.close()
			except:
				print("Can’t access the configuration directory or settings file.")
				return
			self.FILENAME = path
			self.SETTINGS = configparser.RawConfigParser()
			self.SETTINGS.optionxform = str
			try:
				self.Reload()
			except configparser.MissingSectionHeaderError:
				print("Resetting invalid configuration file...")
				with open(path, "w+", encoding="UTF-8") as f: f.close()
				path = ""
		
		if path == "":
			self.FILENAME = False
			self.SETTINGS = configparser.RawConfigParser()
			self.SETTINGS.read_string(ini)
			self.SETTINGS.optionxform = str
		
		self.MAIN_SECTION = main_section
	
	def Reload(self):
		if self.SETTINGS is None: return
		if self.FILENAME is not False:
			with open(self.FILENAME, "r", encoding="UTF-8") as f:
				self.SETTINGS.read_file(f)
		if len(self.SETTINGS.sections()) == 0:
			self.SETTINGS.add_section(self.MAIN_SECTION)
	
	def value(self, key, default=None): return self.GetValue(key, default)
	def GetValue(self, key, default=None):
		if self.SETTINGS is None: return None
		self.Reload()
		if key not in self.SETTINGS[self.MAIN_SECTION]:
			if default is not None: self.SetValue(key, default)
			return default
		return (self.SETTINGS[self.MAIN_SECTION][key])
	
	def setValue(self, key, value): self.SetValue(key, value)
	def SetValue(self, key, value):
		if self.SETTINGS is None: return None
		self.Reload()
		self.SETTINGS[self.MAIN_SECTION][key] = value
		dprint("Updating settings:", key, "=", value)
		if self.FILENAME is not False:
			with open(self.FILENAME, "w", encoding="UTF-8") as f:
				self.SETTINGS.write(f)
	
	def clear(self): self.Clear()
	def Clear(self):
		if self.SETTINGS is None: return None
		self.SETTINGS.clear()
		if self.FILENAME is not False:
			with open(self.FILENAME, "w", encoding="UTF-8") as f:
				self.SETTINGS.write(f)
	
	def GetString(self):
		output = StringIO()
		self.SETTINGS.write(output)
		return(output.getvalue())

class Progress():
	MUTEX = threading.Lock()
	PROGRESS = {}
	UPDATER = None
	WAITER = None
	
	def __init__(self, updater, waiter):
		self.UPDATER = updater
		self.WAITER = waiter
	
	def IsOutlier(self, speeds, new_number, threshold):
		if not speeds: return False
		mean = sum(speeds) / len(speeds)
		std_deviation = (sum((x - mean) ** 2 for x in speeds) / len(speeds)) ** 0.5
		lower_bound = mean - threshold * std_deviation
		upper_bound = mean + threshold * std_deviation
		if new_number < lower_bound or new_number > upper_bound:
			return True
		else:
			return False

	def SetProgress(self, args):
		self.MUTEX.acquire(1)
		try:
			if not "method" in self.PROGRESS: self.PROGRESS = {}
			now = time.time()
			if args["action"] == "USER_ACTION":
				self.WAITER(args)

			elif args["action"] == "INITIALIZE":
				self.PROGRESS["action"] = args["action"]
				self.PROGRESS["method"] = args["method"]
				if "flash_offset" in args:
					self.PROGRESS["flash_offset"] = args["flash_offset"]
				else:
					self.PROGRESS["flash_offset"] = 0
				if "size" in args:
					self.PROGRESS["size"] = args["size"] - self.PROGRESS["flash_offset"]
				else:
					self.PROGRESS["size"] = 0
				if "pos" in args:
					self.PROGRESS["pos"] = args["pos"] - self.PROGRESS["flash_offset"]
				else:
					self.PROGRESS["pos"] = 0
				if "sector_count" in args:
					self.PROGRESS["sector_count"] = args["sector_count"]
				else:
					self.PROGRESS["sector_count"] = 1
				if "time_start" in args:
					self.PROGRESS["time_start"] = args["time_start"]
				else:
					self.PROGRESS["time_start"] = now
				if "abortable" in args:
					self.PROGRESS["abortable"] = args["abortable"]
				else:
					self.PROGRESS["abortable"] = True
				self.PROGRESS["time_last_emit"] = now
				self.PROGRESS["time_last_update_speed"] = now
				self.PROGRESS["time_left"] = 0
				self.PROGRESS["speed"] = 0
				self.PROGRESS["speeds"] = []
				self.PROGRESS["bytes_last_update_speed"] = 0
				self.PROGRESS["sector_erase_time"] = 0
				self.UPDATER(self.PROGRESS)
			
			if args["action"] == "ABORT":
				self.UPDATER(args)
				self.PROGRESS = {}
			
			elif args["action"] in ("ERASE", "SECTOR_ERASE", "UNLOCK", "UPDATE_RTC", "ERROR"):
				if "time_start" in self.PROGRESS:
					args["time_elapsed"] = now - self.PROGRESS["time_start"]
				elif "time_start" in args:
					args["time_elapsed"] = now - args["time_start"]
				args["pos"] = 1
				args["size"] = 0
				self.UPDATER(args)
			
			elif self.PROGRESS == {}:
				return

			elif args["action"] in ("READ", "WRITE", "UPDATE_POS"):
				if "method" not in self.PROGRESS: return
				elif args["action"] == "READ" and self.PROGRESS["method"] in ("SAVE_WRITE", "ROM_WRITE"): return
				elif args["action"] == "WRITE" and self.PROGRESS["method"] in ("SAVE_READ", "ROM_READ", "ROM_WRITE_VERIFY"): return
				if self.PROGRESS["pos"] > self.PROGRESS["size"]: return
				skip_speed = False
				self.PROGRESS["action"] = "PROGRESS"
				if args["action"] in ("READ", "WRITE"):
					self.PROGRESS["pos"] += args["bytes_added"]
				elif args["action"] == "UPDATE_POS":
					# print(self.PROGRESS["pos"], args["pos"] - self.PROGRESS["flash_offset"])
					if self.PROGRESS["pos"] == args["pos"] - self.PROGRESS["flash_offset"]:
						skip_speed = True
					self.PROGRESS["pos"] = args["pos"] - self.PROGRESS["flash_offset"]
					if "sector_erase_time" in args:
						if "sector_erase_time" in self.PROGRESS:
							self.PROGRESS["sector_erase_time"] = (self.PROGRESS["sector_erase_time"] + args["sector_erase_time"]) / 2
						else:
							self.PROGRESS["sector_erase_time"] = args["sector_erase_time"]
					if "sector_pos" in args:
						if "sector_erase_time" not in args: self.PROGRESS["sector_erase_time"] = 0
						self.PROGRESS["sector_pos"] = args["sector_pos"]
					if "abortable" in args:
						self.PROGRESS["abortable"] = args["abortable"]

				if ((now - self.PROGRESS["time_last_emit"]) > 0.06) or "force_update" in args and args["force_update"] is True:
					self.PROGRESS["time_elapsed"] = now - self.PROGRESS["time_start"]
					time_delta = now - self.PROGRESS["time_last_update_speed"]
					pos_delta = self.PROGRESS["pos"] - self.PROGRESS["bytes_last_update_speed"]
					if time_delta > 0 and (time.time() - self.PROGRESS["time_start"] > 2) and "sector_erase_time" not in args:
						speed = (pos_delta / time_delta) / 1024
						if speed > 0 and not skip_speed:
							if len(self.PROGRESS["speeds"]) < 40 or not self.IsOutlier(speeds=self.PROGRESS["speeds"], new_number=speed, threshold=25):
								self.PROGRESS["speeds"].append(speed)
							if len(self.PROGRESS["speeds"]) > 50: self.PROGRESS["speeds"].pop(0)
							if len(self.PROGRESS["speeds"]) > 1 and random.randint(0, 10) == 0: self.PROGRESS["speeds"].pop(0)
							# print(len(self.PROGRESS["speeds"]), pos_delta, end="  \r", flush=True)
						if len(self.PROGRESS["speeds"]) > 0:
							# print(self.PROGRESS["speeds"])
							self.PROGRESS["speed"] = statistics.mean(self.PROGRESS["speeds"])
						else:
							self.PROGRESS["speed"] = 0
					self.PROGRESS["time_last_update_speed"] = now
					self.PROGRESS["bytes_last_update_speed"] = self.PROGRESS["pos"]
					
					if "skipping" in args and args["skipping"] is True:
						self.PROGRESS["speed"] = 0
						self.PROGRESS["skipping"] = True
					else:
						self.PROGRESS["skipping"] = False
					
					if self.PROGRESS["speed"] > 0 and len(self.PROGRESS["speeds"]) > 0:
						total_speed = self.PROGRESS["speed"] #statistics.mean(self.PROGRESS["speeds"])
						self.PROGRESS["time_left"] = (self.PROGRESS["size"] - self.PROGRESS["pos"]) / 1024 / total_speed
						if self.PROGRESS["sector_erase_time"] > 0:
							self.PROGRESS["time_left"] += self.PROGRESS["sector_erase_time"] * (self.PROGRESS["sector_count"] - self.PROGRESS["sector_pos"])
					
					self.UPDATER(self.PROGRESS)
					self.PROGRESS["time_last_emit"] = now
			
			elif args["action"] == "UPDATE_INFO":
				self.PROGRESS["text"] = args["text"]
				self.PROGRESS["action"] = args["action"]
				self.UPDATER(self.PROGRESS)

			elif args["action"] == "FINISHED":
				self.PROGRESS["pos"] = self.PROGRESS["size"]
				self.UPDATER(self.PROGRESS)
				self.PROGRESS["action"] = args["action"]
				self.PROGRESS["bytes_last_update_speed"] = self.PROGRESS["size"]
				self.PROGRESS["time_elapsed"] = now - self.PROGRESS["time_start"]
				self.PROGRESS["time_last_emit"] = now
				self.PROGRESS["time_last_update_speed"] = now
				self.PROGRESS["time_left"] = 0
				if self.PROGRESS["time_elapsed"] == 0: self.PROGRESS["time_elapsed"] = 0.001
				self.PROGRESS["speed"] = (self.PROGRESS["size"] / self.PROGRESS["time_elapsed"]) / 1024
				self.PROGRESS["bytes_last_emit"] = self.PROGRESS["size"]
				if "verified" in args:
					self.PROGRESS["verified"] = (args["verified"] == True)
				
				if self.PROGRESS["speed"] > self.PROGRESS["size"] / 1024:
					self.PROGRESS["speed"] = self.PROGRESS["size"] / 1024
				
				self.UPDATER(self.PROGRESS)
				del(self.PROGRESS["method"])

		finally:
			self.MUTEX.release()

	
class TAMA5_CMD(Enum):
	RAM_WRITE = 0x0
	RAM_READ = 0x1
	RTC = 0x4

class TAMA5_REG(Enum):
	ROM_BANK_L = 0x0
	ROM_BANK_H = 0x1
	MEM_WRITE_L = 0x4
	MEM_WRITE_H = 0x5
	ADDR_H_SET_MODE = 0x6
	ADDR_L = 0x7
	ENABLE = 0xA
	MEM_READ_L = 0xC
	MEM_READ_H = 0xD

def isx2bin(buffer):
	data_input = io.BytesIO(buffer)
	data_output = bytearray(8 * 1024 * 1024)
	rom_size = 0
	temp = 32 * 1024
	while 1:
		try:
			type = struct.unpack('B', data_input.read(1))[0]
			if type == 4:
				break
			elif type != 1:
				print("WARNING: Unhandled ISX record type 0x{:02X} found. Converted ROM may not be working correctly.".format(type))
				continue
			bank = struct.unpack('B', data_input.read(1))[0]
			offset = struct.unpack('<H', data_input.read(2))[0] % 0x4000
			realoffset = bank * 16 * 1024 + offset
			size = struct.unpack('<H', data_input.read(2))[0]
			data_output[realoffset:realoffset+size] = data_input.read(size)
			rom_size = max(rom_size, realoffset+size)
			temp = 32 * 1024
			while temp < rom_size: temp *= 2
		except:
			print("ERROR: Couldn’t convert ISX file correctly.")
			break
	return data_output[:temp]

def round2(num, decimals=2):
	x = (pow(10, decimals))
	return int(num * x) / x

def formatFileSize(size, asInt=False, nobr=True):
	space = " " if nobr else " "
	if size == 1:
		return "{:d}{:s}Byte".format(size, space)
	elif size < 1024:
		return "{:d}{:s}Bytes".format(size, space)
	elif size < 1024 * 1024:
		val = size / 1024
		val = round2(val)
		if asInt:
			return "{:d}{:s}KiB".format(int(val), space)
		else:
			return "{:.1f}{:s}KiB".format(val, space)
	else:
		val = size / 1024 / 1024
		val = round2(val)
		if asInt:
			return "{:d}{:s}MiB".format(int(val), space)
		else:
			return "{:.2f}{:s}MiB".format(val, space)

def formatProgressTimeShort(sec):
	sec = sec % (24 * 3600)
	hr = sec // 3600
	sec %= 3600
	min = sec // 60
	sec %= 60
	return "{:02d}:{:02d}:{:02d}".format(int(hr), int(min), int(sec))

def formatProgressTime(seconds, asFloat=False):
	hr = int(seconds // 3600)
	min = int((seconds // 60) - (60 * hr))
	sec = seconds % 60
	
	if seconds < 1 and asFloat:
		return "{:.2f} seconds".format(seconds)
	s = ""
	if hr > 0:
		s += "{:d} hour".format(hr)
		if hr != 1: s += "s"
		s += ", "
	if min > 0:
		s += "{:d} minute".format(min)
		if min != 1: s += "s"
		s += ", "
	if sec >= 1 or seconds < 60:
		s += "{:d} second".format(int(sec))
		if int(sec) != 1: s += "s"
		s += ", "
	return s[:-2]

def formatPathOS(path, end_sep=False):
	if platform.system() == "Windows":
		path = path.replace("/", "\\")
		if end_sep:
			path += "\\"
	else:
		if end_sep:
			path += "/"
	return path

def bitswap(n, s):
	p, q = s
	if (((n & (1 << p)) >> p) ^ ((n & (1 << q)) >> q)) == 1:
		n ^= (1 << p)
		n ^= (1 << q)
	return n

def DecodeBCD(value):
	return (((value) & 0x0F) + (((value) >> 4) * 10))
def EncodeBCD(value):
	return math.floor(value / 10) << 4 | value % 10

def ParseCFI(buffer):
	buffer = copy.copy(buffer)
	info = {}
	magic_8bit = "{:s}{:s}{:s}".format(chr(buffer[0x10]), chr(buffer[0x11]), chr(buffer[0x12]))
	magic_16bit = "{:s}{:s}{:s}".format(chr(buffer[0x20]), chr(buffer[0x22]), chr(buffer[0x24]))
	buffer_conv = bytearray()
	if magic_8bit == "QRY":
		buffer_conv = bytearray(b for x in buffer for b in (x, x))
		buffer = buffer_conv

	if magic_8bit != "QRY" and magic_16bit != "QRY": # nothing swapped
		return False
	
	try:
		info["flash_id"] = buffer[0:8]
		info["magic"] = "{:s}{:s}{:s}".format(chr(buffer[0x20]), chr(buffer[0x22]), chr(buffer[0x24]))
		
		if buffer[0x36] == 0xFF and buffer[0x48] == 0xFF:
			print("Note: Invalid values found in Common Flash Interface data.")
			try:
				with open("./cfi_debug.bin", "wb") as f: f.write(buffer)
			except:
				pass
			return False
		
		pri_address = (buffer[0x2A] | (buffer[0x2C] << 8)) * 2
		if (pri_address + 0x3C) >= 0x400: pri_address = 0x80
		
		info["vdd_min"] = (buffer[0x36] >> 4) + ((buffer[0x36] & 0x0F) / 10)
		info["vdd_max"] = (buffer[0x38] >> 4) + ((buffer[0x38] & 0x0F) / 10)
		
		if buffer[0x3E] > 0 and buffer[0x3E] < 0xFF:
			info["single_write"] = True
			info["single_write_time_avg"] = int(math.pow(2, buffer[0x3E]))
			info["single_write_time_max"] = int(math.pow(2, buffer[0x46]) * info["single_write_time_avg"])
		else:
			info["single_write"] = False

		if buffer[0x40] > 0 and buffer[0x40] < 0xFF:
			info["buffer_write"] = True
			info["buffer_write_time_avg"] = int(math.pow(2, buffer[0x40]))
			info["buffer_write_time_max"] = int(math.pow(2, buffer[0x48]) * info["buffer_write_time_avg"])
		else:
			info["buffer_write"] = False

		if buffer[0x42] > 0 and buffer[0x42] < 0xFF:
			info["sector_erase"] = True
			info["sector_erase_time_avg"] = int(math.pow(2, buffer[0x42]))
			info["sector_erase_time_max"] = int(math.pow(2, buffer[0x4A]) * info["sector_erase_time_avg"])
		else:
			info["sector_erase"] = False

		if buffer[0x44] > 0 and buffer[0x44] < 0xFF:
			info["chip_erase"] = True
			info["chip_erase_time_avg"] = int(math.pow(2, buffer[0x44]))
			info["chip_erase_time_max"] = int(math.pow(2, buffer[0x4C]) * info["chip_erase_time_avg"])
		else:
			info["chip_erase"] = False

		info["tb_boot_sector"] = False
		info["tb_boot_sector_raw"] = 0
		if "{:s}{:s}{:s}".format(chr(buffer[pri_address]), chr(buffer[pri_address+2]), chr(buffer[pri_address+4])) == "PRI":
			if buffer[pri_address + 0x1E] not in (0, 0xFF):
				temp = { 0x02: 'As shown', 0x03: 'Reversed' }
				info["tb_boot_sector_raw"] = buffer[pri_address + 0x1E]
				try:
					info["tb_boot_sector"] = "{:s} (0x{:02X})".format(temp[buffer[pri_address + 0x1E]], buffer[pri_address + 0x1E])
				except:
					info["tb_boot_sector"] = "0x{:02X}".format(buffer[pri_address + 0x1E])
		
		info["device_size"] = int(math.pow(2, buffer[0x4E]))
		info["buffer_size"] = buffer[0x56] << 8 | buffer[0x54]
		if info["buffer_size"] > 1:
			info["buffer_write"] = True
			info["buffer_size"] = int(math.pow(2, info["buffer_size"]))
		else:
			del(info["buffer_size"])
			info["buffer_write"] = False
		info["erase_sector_regions"] = buffer[0x58]
		info["erase_sector_blocks"] = []
		total_blocks = 0
		pos = 0
		for i in range(0, min(4, info["erase_sector_regions"])):
			b = (buffer[0x5C+(i*8)] << 8 | buffer[0x5A+(i*8)]) + 1
			t = (buffer[0x60+(i*8)] << 8 | buffer[0x5E+(i*8)]) * 256
			total_blocks += b
			size = b * t
			pos += size
			info["erase_sector_blocks"].append([ t, b, size ])
	
	except:
		print("ERROR: Trying to parse CFI data resulted in an error.")
		try:
			with open("./cfi_debug.bin", "wb") as f: f.write(buffer)
		except:
			pass
		return False
	
	return info

def ConvertMapperToMapperType(mapper_raw):
	i = 0
	for (k, v) in DMG_Mapper_Types.items():
		if i == 0:
			retval = (k, v, i)
		if mapper_raw in v:
			retval = (k, v, i)
			break
		i += 1
	# (string, list of ids, index in DMG_Mapper_Types)
	return retval

def ConvertMapperTypeToMapper(mapper_type):
	i = 0
	for (_, v) in DMG_Mapper_Types.items():
		if mapper_type == i:
			return v[0]
		i += 1
	return 0

def GetDumpReport(di, device):
	header = di["header"]
	if "unchanged" in di["header"]:
		header = di["header"]["unchanged"]
	
	if "db" in di["header"]: header["db"] = di["header"]["db"]
	if di["system"] == "DMG":
		mode = "DMG"
		di["system"] = "Game Boy"
		if di["rom_size"] in DMG_Header_ROM_Sizes_Flasher_Map:
			di["rom_size"] = "{:s}".format(DMG_Header_ROM_Sizes[DMG_Header_ROM_Sizes_Flasher_Map.index(di["rom_size"])])
		else:
			di["rom_size"] = "{:,} bytes".format(di["rom_size"])
		
		if di["mapper_type"] in DMG_Header_Mapper:
			di["mapper_type"] = "{:s}".format(ConvertMapperToMapperType(di["mapper_type"])[0])
		else:
			di["mapper_type"] = "0x{:02X}".format(di["mapper_type"])
	
	elif di["system"] == "AGB":
		mode = "AGB"
		di["system"] = "Game Boy Advance"
		if di["rom_size"] in AGB_Header_ROM_Sizes_Map:
			di["rom_size"] = "{:s}".format(AGB_Header_ROM_Sizes[AGB_Header_ROM_Sizes_Map.index(di["rom_size"])])
		else:
			di["rom_size"] = "{:,} bytes".format(di["rom_size"])
	else:
		raise NotImplementedError
	
	di["cart_type"] = list(device.SUPPORTED_CARTS[mode].keys())[di["cart_type"]]
	if di["file_name"] is None:
		di["file_name"] = ""
	else:
		di["file_name"] = os.path.split(di["file_name"])[1]
	di["file_size"] = "{:s} ({:d} bytes)".format(formatFileSize(size=di["file_size"]), di["file_size"])
	
	s = "" \
		"= FlashGBX Dump Report =\n" \
	
	s += "" \
		"\n== File Information ==\n" \
		"* File Name:       {file_name:s}\n" \
		"* File Size:       {file_size:s}\n" \
		"* CRC32:           {hash_crc32:08x}\n" \
		"* MD5:             {hash_md5:s}\n" \
		"* SHA-1:           {hash_sha1:s}\n" \
		"* SHA-256:         {hash_sha256:s}\n" \
	.format(file_name=di["file_name"], file_size=di["file_size"], hash_crc32=di["hash_crc32"], hash_md5=di["hash_md5"], hash_sha1=di["hash_sha1"], hash_sha256=di["hash_sha256"])

	s += "" \
		"\n== General Information ==\n" \
		"* Hardware:        {hardware:s} – Firmware {firmware:s}\n" \
		"* Software:        {software:s}\n" \
		"* OS Platform:     {platform:s}\n" \
		"* Baud Rate:       {baud_rate:d}\n" \
		"* Dump Time:       {timestamp:s}\n" \
		"* Time Elapsed:    %TIME_ELAPSED% (%TRANSFER_RATE%)\n" \
		"* Transfer Buffer: {buffer_size:d} bytes\n" \
		"* Retries:         {retries:d}\n" \
	.format(hardware=device.GetFullName(), firmware=device.GetFirmwareVersion(), software="{:s} {:s}".format(APPNAME, VERSION), platform=platform.platform(), buffer_size=di["transfer_size"], timestamp=di["timestamp"], baud_rate=device.GetBaudRate(), retries=device.GetReadErrors())
	
	if mode == "DMG":
		s += "" \
			"\n== Dumping Settings ==\n" \
			"* Mode:            {system:s}\n" \
			"* ROM Size:        {rom_size:s}\n" \
			"* Mapper Type:     {mapper_type:s}\n" \
			"* Cartridge Type:  {cart_type:s}\n" \
			"* Read Method:     {read_method:s}\n" \
		.format(system=di["system"], rom_size=di["rom_size"], mapper_type=di["mapper_type"], cart_type=di["cart_type"], read_method=di["dmg_read_method"])
	elif mode == "AGB":
		s += "" \
			"\n== Dumping Settings ==\n" \
			"* Mode:            {system:s}\n" \
			"* ROM Size:        {rom_size:s}\n" \
			"* Cartridge Type:  {cart_type:s}\n" \
			"* Read Method:     {read_method:s}\n" \
		.format(system=di["system"], rom_size=di["rom_size"], cart_type=di["cart_type"], read_method=di["agb_read_method"])

	di["hdr_logo"] = "OK" if header["logo_correct"] else "Invalid"
	header["game_title_raw"] = header["game_title_raw"].replace("\0", "␀")
	if mode == "DMG":
		game_title = header["game_title"]
		game_code = ""
		if header["cgb"] in (0xC0, 0x80):
			if "game_code" in header and len(header["game_code"]) > 0:
				game_code = "* Game Code:       {:s}\n".format(header["game_code"])
			di["hdr_target_platform"] = "Game Boy Color"
		elif header["old_lic"] == 0x33 and header["sgb"] == 0x03:
			di["hdr_target_platform"] = "Super Game Boy"
		else:
			di["hdr_target_platform"] = "Game Boy"

		if header["old_lic"] == 0x33 and header["sgb"] == 0x03:
			di["hdr_sgb"] = "Supported"
		else:
			di["hdr_sgb"] = "No support" # (146h=0x{:02X}, 14Bh=0x{:02X})".format(header["sgb"], header["old_lic"])
		if header["cgb"] in DMG_Header_CGB:
			di["hdr_cgb"] = "{:s}".format(DMG_Header_CGB[header["cgb"]])
		else:
			di["hdr_cgb"] = "Unknown (0x{:02X})".format(header["cgb"])
		
		di["hdr_header_checksum"] = "OK (0x{:02X})".format(header["header_checksum"]) if header["header_checksum_correct"] else "Invalid (0x{:02X}≠0x{:02X})".format(header["header_checksum_calc"], header["header_checksum"])
		header["rom_checksum_calc"] = device.INFO["rom_checksum_calc"]
		header["rom_checksum_correct"] = header["rom_checksum_calc"] == header["rom_checksum"]
		di["hdr_rom_checksum"] = "OK (0x{:04X})".format(header["rom_checksum"]) if header["rom_checksum_correct"] else "Invalid (0x{:04X}≠0x{:04X})".format(header["rom_checksum_calc"], header["rom_checksum"])
		
		di["hdr_rom_size"] = header["rom_size_raw"]
		if di["hdr_rom_size"] in DMG_Header_ROM_Sizes_Map:
			di["hdr_rom_size"] = "{:s} (0x{:02X})".format(DMG_Header_ROM_Sizes[DMG_Header_ROM_Sizes_Map.index(di["hdr_rom_size"])], di["hdr_rom_size"])
		else:
			di["hdr_rom_size"] = "Unknown (0x{:02X})".format(di["hdr_rom_size"])
		
		di["hdr_save_type"] = header["ram_size_raw"]
		if di["hdr_save_type"] == 0x00:
			di["hdr_save_type"] = "No SRAM (0x{:02X})".format(di["hdr_save_type"])
		elif di["hdr_save_type"] in DMG_Header_RAM_Sizes_Map:
			di["hdr_save_type"] = "{:s} (0x{:02X})".format(DMG_Header_RAM_Sizes[DMG_Header_RAM_Sizes_Map.index(di["hdr_save_type"])], di["hdr_save_type"])
		else:
			di["hdr_save_type"] = "Unknown (0x{:02X})".format(di["hdr_save_type"])
		
		di["hdr_mapper_type"] = header["mapper_raw"]
		if di["hdr_mapper_type"] in DMG_Header_Mapper:
			di["hdr_mapper_type"] = "{:s} (0x{:02X})".format(DMG_Header_Mapper[di["hdr_mapper_type"]], di["hdr_mapper_type"])
		else:
			di["hdr_mapper_type"] = "Unknown (0x{:02X})".format(di["hdr_mapper_type"])
		
		s += "" \
			"\n== Parsed Data ==\n" \
			"* Game Title:      {hdr_game_title:s}\n" \
			"{hdr_game_code:s}" \
			"* Revision:        {hdr_revision:s}\n" \
			"* Super Game Boy:  {hdr_sgb:s}\n" \
			"* Game Boy Color:  {hdr_cgb:s}\n" \
			"* Nintendo Logo:   {hdr_logo:s}\n" \
			"* Header Checksum: {hdr_header_checksum:s}\n" \
			"* ROM Checksum:    {hdr_rom_checksum:s}\n" \
			"* ROM Size:        {hdr_rom_size:s}\n" \
			"* SRAM Size:       {hdr_save_type:s}\n" \
			"* Mapper Type:     {hdr_mapper_type:s}\n" \
			"* Target Platform: {hdr_target_platform:s}\n" \
		.format(hdr_game_title=game_title, hdr_game_code=game_code, hdr_revision=str(header["version"]), hdr_sgb=di["hdr_sgb"], hdr_cgb=di["hdr_cgb"], hdr_logo=di["hdr_logo"], hdr_header_checksum=di["hdr_header_checksum"], hdr_rom_checksum=di["hdr_rom_checksum"], hdr_rom_size=di["hdr_rom_size"], hdr_save_type=di["hdr_save_type"], hdr_mapper_type=di["hdr_mapper_type"], hdr_target_platform=di["hdr_target_platform"])
		if "gbmem" in di and di["gbmem"] is not None:
			raw_data = ""
			for i in range(0, 4):
				raw_data += ''.join(format(x, '02X') for x in di["gbmem"][i*0x20:i*0x20+0x20]) + "\n                   "
			raw_data = raw_data[:-20]
			
			if "gbmem_parsed" in di and di["gbmem_parsed"] is not None and len(di["gbmem_parsed"]) > 0:
				if (isinstance(di["gbmem_parsed"], list)):
					s += "" \
						"\n== GB-Memory Data (Multi Menu) ==\n" \
						"* Write Timestamp: {timestamp:s}\n" \
						"* Write Kiosk ID:  {kiosk_id:s}\n" \
						"* Number of Games: {num_games:d}\n" \
						"* Write Counter:   {write_count:d}\n" \
						"* Cartridge ID:    {cart_id:s}\n" \
						"* Raw Map Data:    {raw_data:s}\n" \
					.format(
						timestamp=di["gbmem_parsed"][0]["timestamp"],
						kiosk_id=di["gbmem_parsed"][0]["kiosk_id"],
						cart_id=di["gbmem_parsed"][0]["cart_id"],
						write_count=di["gbmem_parsed"][0]["write_count"],
						num_games=di["gbmem_parsed"][0]["num_games"],
						raw_data=raw_data
					)
					for i in range(1, len(di["gbmem_parsed"])):
						if di["gbmem_parsed"][i]["menu_index"] == 0xFF: continue
						if di["gbmem_parsed"][i]["header"]["logo_correct"] is False: continue
						if i == 1:
							s += "\n=== Menu ROM ===\n"
						else:
							s += "\n=== Game {:d} ===\n".format(i-1)
						s += "" \
							"* Game Code:       {game_code:s}\n" \
							"* Game Title:      {title:s}\n" \
							"* Write Timestamp: {timestamp:s}\n" \
							"* Write Kiosk ID:  {kiosk_id:s}\n" \
							"* Location:        {location:s}\n" \
							"* ROM Size:        {size:s}\n" \
						.format(
							game_code=di["gbmem_parsed"][i]["game_code"],
							title=di["gbmem_parsed"][i]["title"],
							timestamp=di["gbmem_parsed"][i]["timestamp"],
							kiosk_id=di["gbmem_parsed"][i]["kiosk_id"],
							location="0x{:06X}–0x{:06X}".format(di["gbmem_parsed"][i]["rom_offset"], di["gbmem_parsed"][i]["rom_offset"]+di["gbmem_parsed"][i]["rom_size"]-1),
							size="{:s} ({:d} bytes)".format(formatFileSize(size=di["gbmem_parsed"][i]["rom_size"]), di["gbmem_parsed"][i]["rom_size"]),
						)
						if "crc32" in di["gbmem_parsed"][i]: s += "* CRC32:           {:08x}\n".format(di["gbmem_parsed"][i]["crc32"])
						if "md5" in di["gbmem_parsed"][i]: s += "* MD5:             {:s}\n".format(di["gbmem_parsed"][i]["md5"])
						if "sha1" in di["gbmem_parsed"][i]: s += "* SHA-1:           {:s}\n".format(di["gbmem_parsed"][i]["sha1"])
						if "sha256" in di["gbmem_parsed"][i]: s += "* SHA-256:         {:s}\n".format(di["gbmem_parsed"][i]["sha256"])
						
						if "db_entry" in di["gbmem_parsed"][i] and "crc32" in di["gbmem_parsed"][i] and di["gbmem_parsed"][i]["db_entry"]["rc"] == di["gbmem_parsed"][i]["crc32"]:
							s += "* Database Match:  {:s} {:s}\n".format(di["gbmem_parsed"][i]["db_entry"]["gn"], di["gbmem_parsed"][i]["db_entry"]["ne"])
				elif isinstance(di["gbmem_parsed"]["game_code"], str):
					s += "" \
						"\n== GB-Memory Data (Single Game) ==\n" \
						"* Game Code:       {game_code:s}\n" \
						"* Game Title:      {title:s}\n" \
						"* Write Timestamp: {timestamp:s}\n" \
						"* Write Kiosk ID:  {kiosk_id:s}\n" \
						"* Write Counter:   {write_count:d}\n" \
						"* Cartridge ID:    {cart_id:s}\n" \
						"* Raw Map Data:    {raw_data:s}\n" \
					.format(
						game_code=di["gbmem_parsed"]["game_code"],
						title=di["gbmem_parsed"]["title"],
						timestamp=di["gbmem_parsed"]["timestamp"],
						kiosk_id=di["gbmem_parsed"]["kiosk_id"],
						cart_id=di["gbmem_parsed"]["cart_id"],
						write_count=di["gbmem_parsed"]["write_count"],
						raw_data=raw_data
					)
			else:
				s += "" \
					"* GB-Memory Data:  {:s}\n" \
				.format(raw_data)
		
		if header["db"] is not None and header["db"]["rc"] == di["hash_crc32"]:
			db = header["db"]
			s += "\n== Database Match ==\n"
			if "gn" in db and "ne" in db: s += "* Game Name:       {:s} {:s}\n".format(db["gn"], db["ne"])
			elif "gn" in db: s += "* Game Name:       {:s}\n".format(db["gn"])
			if "rg" in db: s += "* Region:          {:s}\n".format(db["rg"])
			if "lg" in db: s += "* Language(s):     {:s}\n".format(db["lg"])
			if "rv" in db: s += "* Revision:        {:s}\n".format(db["rv"])
			if "gc" in db: s += "* Game Code:       {:s}\n".format(db["gc"])
			if "rc" in db: s += "* ROM CRC32:       {:08x}\n".format(db["rc"])
			if "rs" in db: s += "* ROM Size:        {:s}\n".format(formatFileSize(size=db["rs"], asInt=True))

	if mode == "AGB":
		header["game_code_raw"] = header["game_code_raw"].replace("\0", "␀")
		di["hdr_header_checksum"] = "OK (0x{:02X})".format(header["header_checksum"]) if header["header_checksum_correct"] else "Invalid (0x{:02X}≠0x{:02X})".format(header["header_checksum_calc"], header["header_checksum"])
		if "agb_savelib" not in di:
			di["agb_savelib"] = "None"
		elif "SRAM_F_" in di["agb_savelib"]:
			di["agb_savelib"] = "256K SRAM/FRAM ({:s})".format(di["agb_savelib"])
		elif "SRAM_" in di["agb_savelib"]:
			di["agb_savelib"] = "256K SRAM ({:s})".format(di["agb_savelib"])
		elif "EEPROM_V" in di["agb_savelib"]:
			di["agb_savelib"] = "4K or 64K EEPROM ({:s})".format(di["agb_savelib"])
		elif "FLASH_V" in di["agb_savelib"] or "FLASH512_V" in di["agb_savelib"]:
			di["agb_savelib"] = "512K FLASH ({:s})".format(di["agb_savelib"])
		elif "FLASH1M_V" in di["agb_savelib"] or "FLASH512_V" in di["agb_savelib"]:
			di["agb_savelib"] = "1M FLASH ({:s})".format(di["agb_savelib"])
		elif "AGB_8MDACS_DL_V" in di["agb_savelib"]:
			di["agb_savelib"] = "8M DACS ({:s})".format(di["agb_savelib"])
		elif di["agb_savelib"] == "N/A":
			di["agb_savelib"] = "None"
		else:
			di["agb_savelib"] = "Unknown ({:s})".format(di["agb_savelib"])
		s += "" \
			"\n== Parsed Data ==\n" \
			"* Game Title:      {hdr_game_title:s}\n" \
			"* Game Code:       {hdr_game_code:s}\n" \
			"* Revision:        {hdr_revision:s}\n" \
			"* Nintendo Logo:   {hdr_logo:s}\n" \
			"* Header Checksum: {hdr_header_checksum:s}\n" \
			"* Save Type:       {agb_savetype}\n" \
		.format(hdr_game_title=header["game_title_raw"], hdr_game_code=header["game_code_raw"], hdr_revision=str(header["version"]), hdr_logo=di["hdr_logo"], hdr_header_checksum=di["hdr_header_checksum"], agb_savetype=di["agb_savelib"])
		if "agb_save_flash_id" in di and di["agb_save_flash_id"] is not None:
			s += "" \
				"* Save Flash Chip: {agb_save_flash_chip_name:s} (0x{agb_save_flash_chip_id:04X})\n" \
			.format(agb_save_flash_chip_name=di["agb_save_flash_id"][1], agb_save_flash_chip_id=di["agb_save_flash_id"][0])

		if "eeprom_data" in di:
			s += "* EEPROM area:     {:s}…\n".format(''.join(format(x, '02X') for x in di["eeprom_data"]))

		if di["cart_type"] == "Vast Fame":
			s += "\n== Vast Fame Protection Information ==\n"
			s += "* Address Reordering: {:s}\n".format(str(di["vf_addr_reorder"]))
			s += "* Value Reordering: {:s}\n".format(str(di["vf_value_reorder"]))

		if header["db"] is not None and header["db"]["rc"] == di["hash_crc32"]:
			db = header["db"]
			s += "\n== Database Match ==\n"
			if "gn" in db and "ne" in db: s += "* Game Name:       {:s} {:s}\n".format(db["gn"], db["ne"])
			elif "gn" in db: s += "* Game Name:       {:s}\n".format(db["gn"])
			if "rg" in db: s += "* Region:          {:s}\n".format(db["rg"])
			if "lg" in db: s += "* Language(s):     {:s}\n".format(db["lg"])
			if "rv" in db: s += "* Revision:        {:s}\n".format(db["rv"])
			if "gc" in db: s += "* Game Code:       {:s}\n".format(db["gc"])
			if "rc" in db: s += "* ROM CRC32:       {:08x}\n".format(db["rc"])
			if "rs" in db: s += "* ROM Size:        {:s}\n".format(formatFileSize(size=db["rs"], asInt=True))
			if "st" in db: s += "* Save Type:       {:s}\n".format(AGB_Header_Save_Types[db["st"]])
			#if "ss" in db: s += "* Save Size:       {:s}\n".format(formatFileSize(size=db["ss"], asInt=True))

	if platform.system() == "Windows":
		return s.replace("\n", "\r\n")
	else:
		return s

def GenerateFileName(mode, header, settings=None):
	fe_ni = True
	if settings is not None:
		fe_ni = settings.value(key="UseNoIntroFilenames", default="enabled").lower() == "enabled"
	
	path = "ROM"
	if mode == "DMG":
		path_title = header["game_title"]
		path_code = ""
		path_revision = str(header["version"])
		path_extension = "bin"
		path = "%TITLE%-%REVISION%"
		fe_sgb = "enabled"
		if settings is not None:
			path = settings.value(key="FileNameFormatDMG", default=path)
			fe_sgb = settings.value(key="AutoFileExtensionSGB", default="enabled")
		
		if len(header["game_code"]) > 0:
			path_code = header["game_code"]
			path = "%TITLE%_%CODE%-%REVISION%"
			if settings is not None:
				path = settings.value(key="FileNameFormatCGB", default=path)

		if header["mapper_raw"] >= 0x200:
			path = "%TITLE%"
		if header["cgb"] in (0xC0, 0x80):
			path_extension = "gbc"
		elif header["old_lic"] == 0x33 and header["sgb"] == 0x03 and fe_sgb.lower() == "enabled":
			path_extension = "sgb"
		else:
			path_extension = "gb"
		if path_title == "":
			path = "ROM.{:s}".format(path_extension)
		else:
			path = path.replace("%TITLE%", path_title.strip())
			path = path.replace("%CODE%", path_code.strip())
			path = path.replace("%REVISION%", path_revision)
			path = path.replace("%MAPPER%", get_mbc_name(header["mapper_raw"]))
			path = re.sub(r"[<>:\"/\\|\?\*]", "_", path)
			if get_mbc_name(header["mapper_raw"]) == "G-MMC1":
				if "gbmem_parsed" in header:
					if (isinstance(header["gbmem_parsed"], list)):
						path += "_{:s}".format(header["gbmem_parsed"][0]["cart_id"])
					else:
						path += "_{:s}".format(header["gbmem_parsed"]["cart_id"])
			path += ".{:s}".format(path_extension)
	elif mode == "AGB":
		path = "%TITLE%_%CODE%-%REVISION%"
		if settings is not None:
			path = settings.value(key="FileNameFormatAGB", default=path)
		path_title = header["game_title"]
		path_code = header["game_code"]
		path_revision = str(header["version"])
		path_extension = "gba"
		if (path_title == "" and path_code == ""):
			path = "ROM"
		else:
			path = path.replace("%TITLE%", path_title.strip())
			path = path.replace("%CODE%", path_code.strip())
			path = path.replace("%REVISION%", path_revision)
			path = re.sub(r"[<>:\"/\\|\?\*]", "_", path)
		path += "." + path_extension
	
	if fe_ni and header["db"] is not None:
		if mode == "DMG" and get_mbc_name(header["mapper_raw"]) == "G-MMC1" and "gbmem_parsed" in header:
			if (isinstance(header["gbmem_parsed"], list)):
				path = "NP GB-Memory Cartridge ({:s}).{:s}".format(header["gbmem_parsed"][0]["cart_id"], path_extension)
			else:
				path = "NP GB-Memory Cartridge ({:s}).{:s}".format(header["gbmem_parsed"]["cart_id"], path_extension)
		else:
			path = "{:s} {:s}.{:s}".format(header["db"]["gn"], header["db"]["ne"], path_extension)
	
	return path

def compare_mbc(a, b):
	for v in DMG_Mapper_Types.values():
		if a in v and b in v: return True
	return False

def get_mbc_name(id):
	for (k, v) in DMG_Mapper_Types.items():
		if id in v: return k
	return "Unknown mapper type 0x{:02X}".format(id)

def save_size_includes_rtc(mode, mbc, save_size, save_type):
	rtc_size = 0x10
	if mode == "DMG":
		save_type = DMG_Header_RAM_Sizes_Map.index(save_type)
		if get_mbc_name(mbc) in ("MBC3", "MBC30"): rtc_size = 0x30
		elif get_mbc_name(mbc) == "HuC-3": rtc_size = 0x0C
		elif get_mbc_name(mbc) == "TAMA5": rtc_size = 0x28
		return (((DMG_Header_RAM_Sizes_Flasher_Map[save_type] + rtc_size) % save_size) == 0)
	elif mode == "AGB":
		rtc_size = 0x10
		return (((AGB_Header_Save_Sizes[save_type] + rtc_size) % save_size) == 0)
	return False

def validate_datetime_format(string, format):
	try:
		if string != datetime.datetime.strptime(string, format).strftime(format):
			raise ValueError
		return True
	except ValueError:
		return False

def find_size(data, max_size, min_size=0x20):
	offset = max_size
	while offset >= min_size:
		offset = int(offset / 2)
		if data[0:offset] != data[offset:offset*2]:
			offset = offset * 2
			break
	return offset

def bitmap2pixmap(data, scale_factor=4):
	try:
		from .pyside import QtGui
		from PIL.ImageQt import ImageQt
		from PIL import Image
		data_converted = data.convert("RGBA")
		pixmap = QtGui.QPixmap.fromImage(ImageQt(data_converted.resize((data_converted.width * scale_factor, data_converted.height * scale_factor), Image.NEAREST)))
		pixmap.setDevicePixelRatio(scale_factor)
		return pixmap
	except:
		print("Couldn’t convert bitmap to pixmap.")
		return False

def dprint(*args, **kwargs):
	stack = traceback.extract_stack()
	stack = stack[len(stack)-2]

	msg = "[{:s}] [{:s}:{:d}] {:s}(): {:s}".format(datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(), os.path.split(stack.filename)[1], stack.lineno, stack.name, " ".join(map(str, args)), **kwargs)
	DEBUG_LOG.append(msg)
	if len(DEBUG_LOG) > 64*1024: DEBUG_LOG.pop(0)
	if DEBUG:
		msg = "{:s}{:s}".format(ANSI.CLEAR_LINE, msg)
		print(msg)

def write_debug_log(device=False):
	dprint("{:s} version: {:s} ({:d})".format(APPNAME, VERSION_PEP440, VERSION_TIMESTAMP))
	dprint("Platform: {:s}".format(platform.platform()))
	if device is not False:
		if device is not None:
			dprint("Connected device: {:s}".format(device))
		else:
			dprint("No device connected")
	dprint("Now writing debug log file")
	try:
		fn = CONFIG_PATH + "/debug.log"
		with open(fn, "wb") as f:
			if platform.system() == "Windows":
				f.write("\r\n".join(DEBUG_LOG).encode("UTF-8-SIG"))
			else:
				f.write("\n".join(DEBUG_LOG).encode("UTF-8-SIG"))
			print("debug.log written")
		return True
	except:
		return False

def exception_hook(exc_type, exc_value, exc_traceback):
	if issubclass(exc_type, KeyboardInterrupt):
		sys.__excepthook__(exc_type, exc_value, exc_traceback)
		return
	
	s = "⚠️ EXCEPTION OCCURED ⚠️\n"
	lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
	for line in lines:
		s += f"{line:s}"
	print(s)
	dprint(s)
	write_debug_log()
