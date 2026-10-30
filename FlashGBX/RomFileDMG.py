# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import hashlib, re, string, struct, os, json, copy
from .i18n import __
from .CartridgeTypes import RomSizes, DmgSaveTypes
from .Logging import dprint, ANSI
from .app import AppContext

try:
	Image = None
	from PIL import Image
except:
	pass

class RomFileDMG:
	ROMFILE_PATH = None
	ROMFILE = bytearray()
	DATA = None
	BATTERYLESS_SRAM_DB = None

	@staticmethod
	def GetParser(file=None):
		return RomFileDMG(file)

	@staticmethod
	def ReadHeaderBuffer(file):
		return bytearray(file.read(0x1000))

	def __init__(self, file=None):
		if isinstance(file, str):
			self.Open(file)
		elif isinstance(file, bytearray):
			self.ROMFILE = file

	def Open(self, file):
		self.ROMFILE_PATH = file
		self.Load()

	def Load(self):
		with open(self.ROMFILE_PATH, "rb") as f:
			self.ROMFILE = bytearray(f.read(0x1000))

	def CalcChecksumHeader(self, fix=False):
		checksum = 0
		for i in range(0x134, 0x14D):
			checksum = checksum - self.ROMFILE[i] - 1
		checksum = checksum & 0xFF

		if fix: self.ROMFILE[0x14D] = checksum
		return checksum

	def CalcChecksumGlobal(self, fix=False):
		temp1 = self.ROMFILE[0x14E]
		temp2 = self.ROMFILE[0x14F]
		self.ROMFILE[0x14E] = 0
		self.ROMFILE[0x14F] = 0
		checksum = sum(self.ROMFILE) & 0xFFFF
		if fix:
			self.ROMFILE[0x14E] = checksum >> 8
			self.ROMFILE[0x14F] = checksum & 0xFF
		else:
			self.ROMFILE[0x14E] = temp1
			self.ROMFILE[0x14F] = temp2
		return checksum

	def FixHeader(self):
		self.CalcChecksumHeader(True)
		self.CalcChecksumGlobal(True)
		return self.ROMFILE[0:0x200]

	def LogoToImage(self, data, valid=True):
		if Image is None: return False
		img = Image.new(mode='P', size=(48, 8))
		if valid:
			img.putpalette([ 255, 255, 255, 0, 0, 0 ])
		else:
			img.putpalette([ 255, 255, 255, 255, 0, 0 ])
		img.info["transparency"] = 0
		pixels = img.load()

		for y in range(0, 8):
			i = int((y/2)%2) + int(y/4)*24
			x = 0
			ix = 0
			while True:
				x += 1
				nibble = (data[i]&0xF) if (y%2) else (data[i]>>4)
				for b in range(3, -1, -1):
					if ((nibble>>b)&1):
						pixels[ix, y] = 1
					else:
						pixels[ix, y] = 0
					ix += 1
				i += 2
				if x >= 12: break
		return img

	def GetHeader(self, unchanged=False):
		buffer = self.ROMFILE
		data = {}
		if len(buffer) < 0x180: return {}
		data["empty"] = (buffer[0x104:0x134] == bytearray([buffer[0x104]] * 0x30))
		data["empty_nocart"] = (buffer == bytearray([0x00] * len(buffer)))
		data["logo_correct"] = hashlib.sha1(buffer[0x104:0x134]).digest() == bytearray([ 0x07, 0x45, 0xFD, 0xEF, 0x34, 0x13, 0x2D, 0x1B, 0x3D, 0x48, 0x8C, 0xFB, 0xDF, 0x03, 0x79, 0xA3, 0x9F, 0xD5, 0x4B, 0x4C ])
		data["cgb"] = int(buffer[0x143])
		data["sgb"] = int(buffer[0x146])
		data["old_lic"] = int(buffer[0x14B])
		temp = self.LogoToImage(buffer[0x104:0x134], data["logo_correct"])
		if temp is not False and not data["empty"]: data["logo"] = temp

		if data["cgb"] in (0x80, 0xC0):
			data["game_title_raw"] = bytearray(buffer[0x134:0x143]).decode("ascii", "replace")
		else:
			data["game_title_raw"] = bytearray(buffer[0x134:0x144]).decode("ascii", "replace")
		game_title = data["game_title_raw"]
		game_title = re.sub(r"(\x00+)$", "", game_title)
		game_title = re.sub(r"((_)_+|(\x00)\x00+|(\s)\s+)", "\\2\\3\\4", game_title).replace("\x00", "_")
		game_title = ''.join(filter(lambda x: x in set(string.printable), game_title))
		data["game_code"] = ""
		if data["cgb"] in (0x80, 0xC0):
			if len(data["game_title_raw"].rstrip("\x00")) == 15:
				if data["game_title_raw"][-4:][0] in ("A", "B", "H", "K", "V") and data["game_title_raw"][-4:][3] in ("A", "B", "D", "E", "F", "I", "J", "K", "P", "S", "U", "X", "Y"):
					data["game_code"] = game_title[-4:]
					game_title = game_title[:-4].rstrip("_")
		data["game_title"] = game_title

		data["maker_code"] = format(int(buffer[0x14B]), "02X")
		if data["maker_code"] == '33':
			maker_code = bytearray(buffer[0x144:0x146]).decode("ascii", "replace")
			maker_code = ''.join(filter(lambda x: x in set(string.printable), maker_code))
			data["maker_code_new"] = maker_code
		data["mapper_raw"] = int(buffer[0x147])
		data["mapper"] = "?"
		data["rom_size_raw"] = int(buffer[0x148])
		data["rom_size"] = "?"
		if buffer[0x148] < RomSizes().GetNumberOfTypes():
			data["rom_size"] = RomSizes().GetString(index=buffer[0x148])
		data["ram_size_raw"] = int(buffer[0x149])
		if data["mapper_raw"] == 0x05 or data["mapper_raw"] == 0x06:
			data["ram_size"] = 0x200
		else:
			data["ram_size"] = "?"
			if buffer[0x149] < DmgSaveTypes().GetNumberOfTypes():
				data["ram_size"] = DmgSaveTypes(index=buffer[0x149]).GetString()
		data["header_sha1"] = hashlib.sha1(buffer[0x0:0x180]).hexdigest()
		if data["header_sha1"] == "70b207b42d87ff0102211a61b62aa4ad22e5d00e" and len(buffer) >= 0x280:
			data["header_sha1"] = hashlib.sha1(buffer[0x0:0x280]).hexdigest()
		data["version"] = int(buffer[0x14C])
		data["header_checksum"] = int(buffer[0x14D])
		data["header_checksum_calc"] = self.CalcChecksumHeader()
		data["header_checksum_correct"] = data["header_checksum"] == data["header_checksum_calc"]
		data["rom_checksum"] = int(256 * buffer[0x14E] + buffer[0x14F])
		data["rom_checksum_calc"] = self.CalcChecksumGlobal()
		data["rom_checksum_correct"] = data["rom_checksum"] == data["rom_checksum_calc"]

		if unchanged:
			data["unchanged"] = copy.copy(data)
		else:
			# MBC2
			if data["mapper_raw"] == 0x06:
				data["ram_size_raw"] = 0x100

			# MBC30
			if data["mapper_raw"] == 0x10 and data["ram_size_raw"] == 0x05:
				data["mapper_raw"] += 0x100

			# MBC6
			if data["mapper_raw"] == 0x20:
				data["ram_size_raw"] = 0x104

			# MBC7
			if data["mapper_raw"] == 0x22 and data["game_title"] in ("KORO2 KIRBY", "KIRBY TNT"):
				data["ram_size_raw"] = 0x101
			elif data["mapper_raw"] == 0x22 and data["game_title"] == "CMASTER":
				data["ram_size_raw"] = 0x102

			# TAMA5
			if data["mapper_raw"] == 0xFD:
				data["ram_size_raw"] = 0x103

			# MBC1M
			if data["mapper_raw"] == 0x03 and data["game_title"] == "MOMOCOL" and data["header_checksum"] == 0x28 or \
			data["mapper_raw"] == 0x01 and data["game_title"] == "BOMCOL" and data["header_checksum"] == 0x86 or \
			data["mapper_raw"] == 0x01 and data["game_title"] == "BOMSEL" and data["header_checksum"] == 0x9C or \
			data["mapper_raw"] == 0x01 and data["game_title"] == "GENCOL" and data["header_checksum"] == 0x8A or \
			data["mapper_raw"] == 0x01 and data["game_title"] == "SUPERCHINESE 123" and data["header_checksum"] == 0xE4 or \
			data["mapper_raw"] == 0x01 and data["game_title"] == "MORTALKOMBATI&II" and data["header_checksum"] == 0xB9 or \
			data["mapper_raw"] == 0x01 and data["game_title"] == "MORTALKOMBAT DUO" and data["header_checksum"] == 0xA7:
				data["mapper_raw"] += 0x100

			# GB-Memory (DMG-MMSA-JPN)
			if data["mapper_raw"] == 0x19 and data["game_title"] == "NP M-MENU MENU" and data["header_checksum"] == 0xD3:
				data["rom_size_raw"] = 0x05
				data["ram_size_raw"] = 0x04
				data["mapper_raw"] = 0x105
			elif data["mapper_raw"] == 0x01 and data["game_title"] == "DMG MULTI MENU " and data["header_checksum"] == 0x36:
				data["rom_size_raw"] = 0x05
				data["ram_size_raw"] = 0x04
				data["mapper_raw"] = 0x105
			elif data["mapper_raw"] == 0x1B and data["game_title"] == "GBMEM-MENU MMSA" and data["version"] == 0x01:
				data["rom_size_raw"] = 0x05
				data["ram_size_raw"] = 0x04
				data["mapper_raw"] = 0x105

			# M161 (Mani 4 in 1)
			elif data["mapper_raw"] == 0x10 and data["game_title"] == "TETRIS SET" and data["header_checksum"] == 0x3F:
				data["mapper_raw"] = 0x104

			# MMM01 (Mani 4 in 1)
			elif data["mapper_raw"] == 0x11 and data["game_title"] == "BOUKENJIMA2 SET" and data["header_checksum"] == 0 or \
			data["mapper_raw"] == 0x11 and data["game_title"] == "BUBBLEBOBBLE SET" and data["header_checksum"] == 0xC6 or \
			data["mapper_raw"] == 0x11 and data["game_title"] == "GANBARUGA SET" and data["header_checksum"] == 0x90 or \
			data["mapper_raw"] == 0x11 and data["game_title"] == "RTYPE 2 SET" and data["header_checksum"] == 0x32:
				data["mapper_raw"] = 0x0B

			# Unlicensed 256M Mapper
			elif (data["game_title"].upper() == "GB HICOL" and data["header_checksum"] in (0x4A, 0x49, 0xE8, 0xE9)) or \
			(data["game_title"] == "BennVenn" and data["header_checksum"] == 0x48):
				data["rom_size_raw"] = 0x0A
				data["ram_size_raw"] = 0x201
				data["mapper_raw"] = 0x201
			elif buffer[0x150:0x160].decode("ascii", "replace") == "256M ROM Builder" or (data["mapper_raw"] in (0x19, 0x1B) and data["game_title"] == "GBMEM-MENU 256M" and data["version"] == 0x01):
				data["rom_size_raw"] = 0x0A
				data["ram_size_raw"] = 0x201
				data["mapper_raw"] = 0x201

			# Unlicensed Wisdom Tree Mapper
			elif hashlib.sha1(buffer[0x0:0x150]).digest() == bytearray([ 0xF5, 0xD2, 0x91, 0x7D, 0x5E, 0x5B, 0xAB, 0xD8, 0x5F, 0x0A, 0xC7, 0xBA, 0x56, 0xEB, 0x49, 0x8A, 0xBA, 0x12, 0x49, 0x13 ]): # Exodus / Joshua
				data["rom_size_raw"] = 0x02
				data["mapper_raw"] = 0x202
			elif hashlib.sha1(buffer[0x0:0x150]).digest() == bytearray([ 0xE9, 0xF8, 0x32, 0x78, 0x39, 0x19, 0xE3, 0xB2, 0xFC, 0x6F, 0xC2, 0x60, 0x30, 0x33, 0x20, 0xD0, 0x3B, 0x1A, 0xA9, 0xA2 ]): # Spiritual Warfare
				data["rom_size_raw"] = 0x03
				data["mapper_raw"] = 0x202
			elif hashlib.sha1(buffer[0x0:0x150]).digest() == bytearray([ 0xE6, 0xC0, 0x39, 0x7F, 0xA5, 0x99, 0xD6, 0x60, 0xD7, 0x90, 0x45, 0xB9, 0xF0, 0x64, 0x3B, 0x2A, 0x41, 0xA4, 0xD6, 0x35 ]): # King James Bible
				data["rom_size_raw"] = 0x05
				data["mapper_raw"] = 0x202
			elif hashlib.sha1(buffer[0x0:0x150]).digest() == bytearray([ 0x36, 0x89, 0x60, 0xDD, 0x1B, 0xE1, 0x73, 0x86, 0x8B, 0x24, 0xA3, 0xDC, 0x57, 0xA5, 0xCB, 0x7C, 0xCA, 0x62, 0xDD, 0x34 ]): # NIV Bible
				data["rom_size_raw"] = 0x06
				data["mapper_raw"] = 0x202

			# Unlicensed Xploder GB Mapper
			elif hashlib.sha1(buffer[0x104:0x150]).digest() == bytearray([ 0x06, 0xAC, 0xDC, 0xB6, 0xD1, 0x9B, 0xD9, 0xE3, 0x95, 0xA2, 0x38, 0xB8, 0x00, 0x97, 0x0D, 0x78, 0x3F, 0xC6, 0xB7, 0xBD ]):
				data["rom_size_raw"] = 0x02
				data["ram_size_raw"] = 0x203
				data["mapper_raw"] = 0x203
				data["cgb"] = 0x80
				try:
					game_title = bytearray(buffer[0:0x10]).decode("ascii", "replace").replace("\xFF", "")
					game_title = re.sub(r"(\x00+)$", "", game_title)
					game_title = re.sub(r"((_)_+|(\x00)\x00+|(\s)\s+)", "\\2\\3\\4", game_title).replace("\x00", "")
					game_title = ''.join(filter(lambda x: x in set(string.printable), game_title))
					data["game_title"] = game_title
				except:
					pass
				data["version"] = "{:d}.{:d}.{:d}:{:c} ({:02d}:{:02d} {:02d}-{:02d}-{:02d} / {:04X})".format(buffer[0xD8], buffer[0xD9], buffer[0xDA], buffer[0xD7], buffer[0xD0], buffer[0xD1], buffer[0xD2], buffer[0xD3], buffer[0xD4], struct.unpack("<H", buffer[0xD5:0xD7])[0]).replace("\x00", "")

			# Unlicensed Datel Orbit V2 Mapper
			elif hashlib.sha1(buffer[0x101:0x134]).digest() == bytearray([ 0xFA, 0x68, 0x5A, 0x37, 0x85, 0xEF, 0x65, 0x23, 0x2D, 0x6F, 0x23, 0xAC, 0x02, 0x05, 0x15, 0x20, 0x8B, 0xDE, 0xC5, 0x23 ]):
				data["rom_size_raw"] = 0x02
				data["ram_size_raw"] = 0
				data["mapper_raw"] = 0x205
				data["cgb"] = 0x80
				try:
					game_title = bytearray(buffer[0x134:0x150]).decode("ascii", "replace").replace("\xFF", "")
					game_title = re.sub(r"(\x00+)$", "", game_title)
					game_title = re.sub(r"((_)_+|(\x00)\x00+|(\s)\s+)", "\\2\\3\\4", game_title).replace("\x00", "")
					game_title = ''.join(filter(lambda x: x in set(string.printable), game_title))
					data["game_title"] = game_title
				except:
					pass

			# Unlicensed Datel Orbit V2 Mapper (older firmware)
			elif (
				hashlib.sha1(buffer[0x101:0x140]).digest() == bytearray([ 0xC1, 0xF4, 0x15, 0x4A, 0xEF, 0xCC, 0x5B, 0xE7, 0xEC, 0x83, 0xA8, 0xBB, 0x7B, 0xC0, 0x95, 0x83, 0x35, 0xEC, 0x9A, 0xF2 ]) or \
				hashlib.sha1(buffer[0x101:0x140]).digest() == bytearray([ 0xC9, 0x50, 0x65, 0xCB, 0x31, 0x96, 0x26, 0x6C, 0x32, 0x58, 0xAB, 0x07, 0xA1, 0x9E, 0x0C, 0x10, 0xA6, 0xED, 0xCC, 0x67 ])
			):
				data["rom_size_raw"] = 0x02
				data["ram_size_raw"] = 0
				data["mapper_raw"] = 0x205
				try:
					game_title = bytearray(buffer[0x134:0x140]).decode("ascii", "replace").replace("\xFF", "")
					game_title = re.sub(r"(\x00+)$", "", game_title)
					game_title = re.sub(r"((_)_+|(\x00)\x00+|(\s)\s+)", "\\2\\3\\4", game_title).replace("\x00", "")
					game_title = ''.join(filter(lambda x: x in set(string.printable), game_title))
					data["game_title"] = game_title
				except:
					pass

			# Unlicensed Sachen MMC1/MMC2
			elif len(buffer) >= 0x280:
				sachen_version = 0
				sachen_hash = hashlib.sha1(buffer[0x200:0x280]).digest()
				if sachen_hash == bytearray([ 0x73, 0x9B, 0x46, 0x86, 0x97, 0x1C, 0x0B, 0xAE, 0xAF, 0x26, 0xF1, 0x73, 0xAC, 0xAE, 0x4B, 0x2B, 0xBF, 0x00, 0x70, 0x77 ]):
					data["rom_size_raw"] = 0x03
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x8793
					data["game_title"] = "SACHEN 4B-001"
					sachen_version = 1
				elif sachen_hash == bytearray([ 0x22, 0x8B, 0x40, 0x4F, 0x1C, 0xCF, 0x4D, 0xDC, 0x4D, 0xF2, 0x35, 0xF3, 0x7B, 0x6D, 0x61, 0x5E, 0xBE, 0xF1, 0xEF, 0x42 ]):
					data["rom_size_raw"] = 0x01
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0xB180
					data["game_title"] = "SACHEN 4B-002"
					sachen_version = 1
				elif sachen_hash == bytearray([ 0xF9, 0xB8, 0x6A, 0x8F, 0x2E, 0x8B, 0x31, 0xD4, 0xC5, 0x02, 0xC8, 0x80, 0x75, 0x35, 0x9C, 0x02, 0xB3, 0xB5, 0x68, 0x01 ]):
					data["rom_size_raw"] = 0x03
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x7CFD
					data["game_title"] = "SACHEN 4B-004"
					sachen_version = 1
				elif sachen_hash == bytearray([ 0xD6, 0xB5, 0x33, 0x81, 0x1A, 0x01, 0x0D, 0x4D, 0x1C, 0xCC, 0x5A, 0x2C, 0x34, 0x9D, 0x0F, 0x63, 0xD3, 0xF4, 0x9D, 0x34 ]):
					data["rom_size_raw"] = 0x03
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x80DF
					data["game_title"] = "SACHEN 4B-005"
					sachen_version = 1
				elif sachen_hash == bytearray([ 0x3E, 0x56, 0xCC, 0x2D, 0xDF, 0xE0, 0x00, 0xED, 0x53, 0xA7, 0x9D, 0x62, 0xC8, 0xBF, 0x7F, 0x20, 0x27, 0x47, 0xCD, 0x8E ]):
					data["rom_size_raw"] = 0x03
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x55E6
					data["game_title"] = "SACHEN 4B-006"
					sachen_version = 1
				elif sachen_hash == bytearray([ 0xD8, 0x24, 0xD2, 0xB2, 0x71, 0x6B, 0x08, 0xFA, 0xEA, 0xA4, 0xFB, 0xD9, 0x7D, 0x81, 0x94, 0x57, 0x46, 0x77, 0x91, 0x60 ]):
					sachen_hash2 = hashlib.sha1(buffer[0x0:0x80]).digest()
					if sachen_hash2 == bytearray([ 0x20, 0x17, 0x3B, 0x95, 0xFB, 0x1A, 0xAC, 0x81, 0x6C, 0x66, 0xF5, 0x62, 0x11, 0xF4, 0x96, 0xFB, 0xFB, 0x88, 0x03, 0xBC ]):
						data["rom_size_raw"] = 0x04
						data["mapper_raw"] = 0x204
						data["rom_checksum"] = 0x657A
						data["game_title"] = "SACHEN 8B-001"
						sachen_version = 2
					else:
						data["rom_size_raw"] = 0x03
						data["mapper_raw"] = 0x204
						data["rom_checksum"] = 0x8E9F
						data["game_title"] = "SACHEN 4B-007"
						sachen_version = 1
				elif sachen_hash == bytearray([ 0x19, 0x3E, 0xF8, 0xE2, 0x12, 0x8A, 0x24, 0x10, 0xFE, 0xE9, 0xEA, 0x27, 0xC9, 0x1B, 0xC4, 0xDD, 0x04, 0x74, 0x1B, 0xA8 ]):
					data["rom_size_raw"] = 0x03
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x99C7
					data["game_title"] = "SACHEN 4B-008"
					sachen_version = 1
				elif sachen_hash == bytearray([ 0xA5, 0x07, 0xCB, 0xB0, 0x63, 0x7A, 0xE7, 0x1A, 0xF2, 0xC8, 0x32, 0x9B, 0xA6, 0x6D, 0xC4, 0x21, 0x68, 0x78, 0xE5, 0x39 ]):
					data["rom_size_raw"] = 0x03
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0xCDD3
					data["game_title"] = "SACHEN 4B-009"
					sachen_version = 1
				elif sachen_hash == bytearray([ 0x18, 0xEC, 0x2B, 0x15, 0x97, 0xD7, 0x80, 0x51, 0x58, 0xB2, 0xB8, 0x53, 0xA7, 0x00, 0xD7, 0x0B, 0xCE, 0x0A, 0xB3, 0xFF ]):
					data["rom_size_raw"] = 0x01
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x3889
					data["game_title"] = "SACHEN 4B-003"
					sachen_version = 1
				elif sachen_hash == bytearray([ 0x96, 0x1C, 0xE3, 0x5D, 0x3A, 0x81, 0x44, 0x95, 0xCF, 0x42, 0x92, 0x42, 0x30, 0x83, 0x14, 0x17, 0xA9, 0xBF, 0xE0, 0x9F ]):
					data["rom_size_raw"] = 0x06
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x3934
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN 31B-001"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0xB8, 0x59, 0x61, 0x1C, 0x03, 0xAF, 0x5F, 0x7F, 0x50, 0x3E, 0x8C, 0xB0, 0x9C, 0x81, 0x4A, 0x0C, 0xE8, 0xBA, 0xB5, 0x99 ]):
					data["rom_size_raw"] = 0x06
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x2E45
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN 31B-001"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0xF5, 0xC6, 0xC2, 0xE6, 0xA6, 0xF2, 0xEE, 0x86, 0x29, 0x22, 0x3D, 0x7C, 0x72, 0xF9, 0xDD, 0x6F, 0x32, 0x0A, 0xA0, 0x9D ]):
					data["rom_size_raw"] = 0x04
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x125B
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN 8B-001"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0xF2, 0x8A, 0xDF, 0x84, 0xBA, 0x56, 0x8C, 0x54, 0xF9, 0x4B, 0x25, 0xFA, 0x12, 0x92, 0x4E, 0xD6, 0x7D, 0xD1, 0x7E, 0x9D ]):
					data["rom_size_raw"] = 0x04
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x598F
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN 8B-002"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0x1C, 0x08, 0x6F, 0x94, 0xD8, 0xFD, 0x40, 0x4D, 0xA3, 0x85, 0xCE, 0x57, 0x35, 0xF3, 0x43, 0x92, 0xEE, 0xB7, 0x26, 0xE1 ]):
					data["rom_size_raw"] = 0x04
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x6485
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN 8B-003"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0x2C, 0xFD, 0xE1, 0x8D, 0x2C, 0x57, 0xBA, 0xDB, 0xC0, 0xF8, 0xDF, 0x52, 0x79, 0x38, 0x44, 0x56, 0x3B, 0xB0, 0xA0, 0xDE ]):
					data["rom_size_raw"] = 0x04
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x02A4
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN 8B-004"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0x4E, 0xEA, 0x3C, 0x0A, 0x23, 0x5C, 0xF9, 0x2D, 0xC6, 0x22, 0xC2, 0x21, 0xD3, 0xBB, 0x73, 0x3B, 0xA7, 0x21, 0xFB, 0x78 ]):
					data["rom_size_raw"] = 0x02
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0xA709
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0x3F, 0xE9, 0xB7, 0xAB, 0xBC, 0x18, 0x95, 0x60, 0x80, 0xF7, 0xDF, 0x9B, 0x5E, 0x5A, 0x0C, 0x9F, 0x18, 0x63, 0x34, 0x7B ]):
					data["rom_size_raw"] = 0x04
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x929D
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN 1B-003"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0xD8, 0x9B, 0x0D, 0x55, 0x48, 0x97, 0x7F, 0xD5, 0x0E, 0x46, 0x20, 0xD6, 0x9E, 0x0B, 0x8C, 0x6B, 0x05, 0xD4, 0x8F, 0x2C ]):
					data["rom_size_raw"] = 0x04
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x2F50
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN 4B-003"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0x8B, 0x98, 0xB1, 0xD3, 0x6B, 0x84, 0x66, 0x51, 0xC0, 0x23, 0x19, 0xF2, 0xDC, 0xD3, 0xF4, 0x97, 0xDB, 0x39, 0x47, 0xE7 ]):
					data["rom_size_raw"] = 0x06
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x9769
					data["cgb"] = 0x80
					data["game_title"] = "SACHEN"
					sachen_version = 2
				elif sachen_hash == bytearray([ 0xD0, 0xAE, 0xC9, 0xFB, 0xF0, 0x8D, 0x7A, 0x72, 0x34, 0x8E, 0x96, 0xB6, 0x75, 0x6B, 0x30, 0xC1, 0xCB, 0xF6, 0x2F, 0x00 ]):
					data["rom_size_raw"] = 0x06
					data["mapper_raw"] = 0x204
					data["rom_checksum"] = 0x0346
					data["game_title"] = "SACHEN 6B-001"
					sachen_version = 2

				if sachen_version == 1:
					temp = self.LogoToImage(buffer[0x184:0x184+0x30])
					if temp is not False: data["logo_sachen"] = temp
				elif sachen_version == 2:
					temp = self.LogoToImage(buffer[0x104:0x104+0x30])
					if temp is not False: data["logo_sachen"] = temp

			# GBFlash MBCX
			if data["game_title"] == "MBCX_MENU":
				data["rom_size_raw"] = 0x0A
				data["ram_size_raw"] = 0x03
				data["mapper_raw"] = 0x206

			# Photo!
			if data["game_title"] == "PHOTO":
				data["ram_size_raw"] = 0x204

		from .Mapper import DMG_Mapper
		if data["mapper_raw"] in DMG_Mapper().GetAllMapperIds():
			data["mapper"] = DMG_Mapper().GetMapperName(data["mapper_raw"])
		elif data["logo_correct"]:
			print("{:s}{}{:s}".format(ANSI.YELLOW, __("Warning: Unknown mapper type value {mapper}", mapper="0x{:02X}".format(data["mapper_raw"])), ANSI.RESET))

		self.DATA = data
		data["db"] = self.GetDatabaseEntry()
		batteryless_sram = self.GetBatterylessSramConfig(data)
		if batteryless_sram is not None:
			data["batteryless_sram"] = batteryless_sram
		if data["db"] is not None and data["game_code"] == "" and data["db"]["gc"] != "":
			data["game_code"] = data["db"]["gc"][4:]
		return data

	def GetDatabaseEntry(self):
		data = self.DATA
		db_entry = None
		if os.path.exists("{0:s}/db_DMG.json".format(AppContext.CONFIG_PATH)):
			with open("{0:s}/db_DMG.json".format(AppContext.CONFIG_PATH), encoding="UTF-8") as f:
				db = f.read()
				try:
					db = json.loads(db)
				except (json.JSONDecodeError, ValueError) as e:
					print(__("Error: Database for Game Boy titles is corrupted.") + "\n" + str(e))
					return None
				if data["header_sha1"] in db.keys():
					db_entry = db[data["header_sha1"]]
				else:
					dprint(__("No database entry found for this title (Header SHA1: {sha1})", sha1=data["header_sha1"]))
		else:
			print(__("Error: Database for Game Boy titles not found at {path}", path=AppContext.CONFIG_PATH + os.sep + "db_DMG.json"))
		return db_entry

	@classmethod
	def GetBatterylessSramConfig(cls, header):
		if not isinstance(header, dict): return None
		if "game_title_raw" not in header: return None

		if cls.BATTERYLESS_SRAM_DB is None:
			config_paths = [
				AppContext.CONFIG_PATH,
				os.path.join(os.path.dirname(__file__), "config")
			]
			for config_path in config_paths:
				if config_path == "": continue
				db_path = os.path.join(config_path, "db_DMG_bl.json")
				if not os.path.exists(db_path): continue
				try:
					with open(db_path, encoding="UTF-8") as f:
						cls.BATTERYLESS_SRAM_DB = json.loads(f.read())
					break
				except Exception as e:
					print("Error: Could not load the database of batteryless SRAM configurations.", e, sep="\n")
			if cls.BATTERYLESS_SRAM_DB is None:
				cls.BATTERYLESS_SRAM_DB = False

		db = cls.BATTERYLESS_SRAM_DB
		if not db: return None

		titles = [
			header["game_title_raw"],
			header["game_title_raw"].replace("\x00", "").rstrip(),
			header["game_title"] if "game_title" in header else ""
		]
		for title in titles:
			if title == "": continue
			if title not in db: continue
			entry = db[title]
			batteryless_sram = {
				"bl_offset": entry[0],
				"bl_size": entry[1],
			}
			if len(entry) >= 3:
				batteryless_sram["bl_layout"] = entry[2]
			return batteryless_sram

		return None

def from_isx(buffer):
	import io
	import struct
	from .i18n import __
	data_input = io.BytesIO(buffer)
	data_output = bytearray(8 * 1024 * 1024)
	rom_size = 0
	temp = 32 * 1024
	while 1:
		try:
			rec_type = struct.unpack('B', data_input.read(1))[0]
			if rec_type == 4:
				break
			elif rec_type != 1:
				print(__("Warning: Unhandled ISX record type {type} found. Converted ROM may not be working correctly.", type="0x{:02X}".format(rec_type)))
				continue
			bank = struct.unpack('B', data_input.read(1))[0]
			offset = struct.unpack('<H', data_input.read(2))[0] % 0x4000
			realoffset = bank * 16 * 1024 + offset
			size = struct.unpack('<H', data_input.read(2))[0]
			data_output[realoffset:realoffset+size] = data_input.read(size)
			rom_size = max(rom_size, realoffset + size)
			temp = 32 * 1024
			while temp < rom_size: temp *= 2
		except:
			print(__("Error: Couldn’t convert ISX file correctly."))
			break
	return data_output[:temp]
