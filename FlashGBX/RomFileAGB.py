# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import hashlib, re, zlib, string, os, json, copy, struct
from .i18n import __
from .Logging import dprint
from .app import AppContext

try:
	Image = None
	from PIL import Image
except:
	pass

class RomFileAGB:
	ROMFILE_PATH = None
	ROMFILE = bytearray()
	DATA = None

	def __init__(self, file=None):
		if isinstance(file, str):
			self.ROMFILE_PATH = file
			if self.ROMFILE_PATH != None: self.Load()
		elif isinstance(file, bytearray):
			self.ROMFILE = file

	def Open(self, file):
		self.ROMFILE_PATH = file
		self.Load()

	def Load(self):
		with open(self.ROMFILE_PATH, "rb") as f:
			self.ROMFILE = bytearray(f.read())

	def CalcChecksumHeader(self, fix=False):
		checksum = 0
		for i in range(0xA0, 0xBD):
			checksum = checksum - self.ROMFILE[i]
		checksum = (checksum - 0x19) & 0xFF

		if fix: self.ROMFILE[0xBD] = checksum
		return checksum

	def CalcChecksumGlobal(self):
		return (zlib.crc32(self.ROMFILE) & 0xFFFFFFFF)

	def FixHeader(self):
		self.CalcChecksumHeader(True)
		return self.ROMFILE[0:0x200]

	@staticmethod
	def GetSaveTypeFromHeaderMarker(header):
		if header is False or len(header) <= 0xBF:
			return None
		if header[0xBE] != 0x4C:
			return None

		flags = header[0xBF]
		save_size_map = {
			0b000: 0,
			0b001: 512,
			0b010: 8192,
			0b011: 32768,
			0b100: 65536,
			0b101: 131072,
		}
		save_size_code = flags & 0x07
		if save_size_code not in save_size_map:
			return None

		save_size = save_size_map[save_size_code]
		save_medium = (flags & 0x18) >> 3
		batteryless = (flags & 0x20) != 0

		# Waitstate (0x40) and Fake RTC (0x80) are independent of the
		# save configuration and therefore do not affect its decoding.
		if save_medium == 0:
			if save_size != 0 or batteryless:
				return None
			return (0, 0)

		if save_medium == 1: # SRAM
			if batteryless:
				if save_size == 0:
					return None
				return (9, save_size)
			if save_size <= 32768:
				return (3, save_size)
			if save_size == 65536:
				return (7, save_size)
			if save_size == 131072:
				return (8, save_size)

		if batteryless:
			return None
		if save_medium == 2: # EEPROM
			if save_size == 0:
				# FlashGBX uses save type 1 for the EEPROM family. A size of
				# zero keeps 4K and 64K EEPROM intentionally unresolved.
				return (1, 0)
			if save_size == 512:
				return (1, save_size)
			if save_size == 8192:
				return (2, save_size)
		if save_medium == 3: # FLASH
			if save_size == 131072:
				return (5, save_size)
			else:
				return (4, save_size)
		return None

	def LogoToImage(self, data, valid=True):
		if Image is None: return False
		if data in (bytearray([0] * len(data)), bytearray([0xFF] * len(data))): return False

		# Based on a HuffUnComp function provided by Winter1760, thank you!
		def HuffUnComp(data):
			BITS = 4
			OUT_SIZE = 0xD4
			TREE = bytes([0x40, 0x00, 0x00, 0x00, 0x01, 0x81, 0x82, 0x82, 0x83, 0x0F, 0x83, 0x0C, 0xC3, 0x03, 0x83, 0x01, 0x83, 0x04, 0xC3, 0x08, 0x0E, 0x02, 0xC2, 0x0D, 0xC2, 0x07, 0x0B, 0x06, 0x0A, 0x05, 0x09])
			data = bytes([0x20 | BITS]) + OUT_SIZE.to_bytes(3, "little") + bytes([len(TREE) // 2]) + TREE + data
			bits = data[0] & 15
			out_size = int.from_bytes(data[1:4], "little") & 0xFFFF
			i = 6 + data[4] * 2
			node_offs = 5
			out_units = 0
			out_ready = 0
			out = b""
			while len(out) < out_size:
				in_unit = int.from_bytes(data[i:i+2], "little") | int.from_bytes(data[i^2:(i^2)+2], "little") << 16
				i += 4
				for b in range(31, -1, -1):
					node = data[node_offs]
					node_offs &= ~1
					node_offs += (node & 0x3F) * 2 + 2 + (in_unit >> b & 1)
					if node << (in_unit >> b & 1) & 0x80:
						out_ready >>= bits
						out_ready |= data[node_offs] << 32 - bits
						out_ready &= 0xFFFFFFFF
						out_units += 1
						if out_units == bits % 8 + 4:
							out += out_ready.to_bytes(4, "little")
							if len(out) >= out_size:
								return out
							out_units = 0
							out_ready = 0
						node_offs = 5
			return out

		def Diff16BitUnFilter(data):
			header = struct.unpack("I", data[0:4])[0]
			out_size = (header >> 8) & 0xFFFF
			pos = 4
			prev = 0
			dest = bytearray()
			while pos < out_size:
				if pos+2 > len(data): break
				temp = (struct.unpack("H", data[pos:pos+2])[0] + prev) & 0xFFFF
				dest += struct.pack("H", temp)
				pos += 2
				prev = temp
			return dest

		data = HuffUnComp(data)
		data = Diff16BitUnFilter(data)

		img = Image.new(mode='P', size=(104, 16))
		img.info["transparency"] = 0
		img.putpalette([ 255, 255, 255, 0, 0, 0 ])
		pixels = img.load()

		for tile_row in range(0, 2):
			for tile_w in range(0, 13):
				for tile_h in range(0, 8):
					for bit in range(0, 8):
						pos = (tile_row * 13 * 8) + (tile_w * 8) + tile_h
						if pos >= len(data): break
						pixel = (data[pos] >> bit) & 1
						x = tile_w * 8 + bit
						y = tile_row * 8 + tile_h
						pixels[x, y] = pixel
		return img

	def GetHeader(self, unchanged=False):
		buffer = bytearray(self.ROMFILE)
		data = {}
		if len(buffer) < 0x180: return {}
		hash = hashlib.sha1(buffer[0:0x180]).digest()
		nocart_hashes = []
		nocart_hashes.append(bytearray([ 0x4F, 0xE9, 0x3E, 0xEE, 0xBC, 0x55, 0x93, 0xFE, 0x2E, 0x23, 0x1A, 0x39, 0x86, 0xCE, 0x86, 0xC9, 0x5C, 0x11, 0x00, 0xDD ])) # Method 0
		nocart_hashes.append(bytearray([ 0xA5, 0x03, 0xA1, 0xB5, 0xF5, 0xDD, 0xBE, 0xFC, 0x87, 0xC7, 0x9B, 0x13, 0x59, 0xF7, 0xE1, 0xA5, 0xCF, 0xE0, 0xAC, 0x9F ])) # Method 1
		nocart_hashes.append(bytearray([ 0x46, 0x86, 0xE3, 0x81, 0xB2, 0x4A, 0x2D, 0xB0, 0x7D, 0xE8, 0x3D, 0x45, 0x2F, 0xA3, 0x1E, 0x8A, 0x04, 0x4B, 0x3A, 0x50 ])) # Method 2
		data["empty_nocart"] = hash in nocart_hashes
		if not data["empty_nocart"]:
			nocart_hashes.append(bytearray([ 0x2B, 0xDC, 0x7D, 0xEF, 0x6C, 0x48, 0x1F, 0xBF, 0xEE, 0xB8, 0x80, 0xB1, 0xD0, 0xFD, 0xF6, 0x57, 0x5D, 0x6A, 0x39, 0xBE ]))
			nocart_hashes.append(bytearray([ 0x09, 0xB9, 0x0E, 0x53, 0x5E, 0x85, 0x50, 0xF8, 0x90, 0xA4, 0xF4, 0x77, 0x13, 0x7E, 0x45, 0x59, 0xA5, 0xC0, 0xA4, 0x45 ]))
			data["empty_nocart"] = hashlib.sha1(buffer[0x10:0x50]).digest() in nocart_hashes

		data["empty"] = (buffer[0x04:0xA0] == bytearray([buffer[0x04]] * 0x9C)) or data["empty_nocart"]
		if data["empty_nocart"]: buffer = bytearray([0x00] * len(buffer))
		data["logo_correct"] = hashlib.sha1(buffer[0x04:0xA0]).digest() == bytearray([ 0x17, 0xDA, 0xA0, 0xFE, 0xC0, 0x2F, 0xC3, 0x3C, 0x0F, 0x6A, 0xBB, 0x54, 0x9A, 0x8B, 0x80, 0xB6, 0x61, 0x3B, 0x48, 0xEE ])
		temp = self.LogoToImage(buffer[0x04:0xA0], data["logo_correct"])
		if temp is not False and not data["empty"]: data["logo"] = temp

		data["game_title_raw"] = bytearray(buffer[0xA0:0xAC]).decode("ascii", "replace")
		game_title = data["game_title_raw"]
		game_title = re.sub(r"(\x00+)$", "", game_title)
		game_title = re.sub(r"((_)_+|(\x00)\x00+|(\s)\s+)", "\\2\\3\\4", game_title).replace("\x00", "_")
		game_title = ''.join(filter(lambda x: x in set(string.printable), game_title))
		data["game_title"] = game_title.replace("\n", "")
		data["game_code_raw"] = bytearray(buffer[0xAC:0xB0]).decode("ascii", "replace")
		game_code = data["game_code_raw"]
		game_code = re.sub(r"(\x00+)$", "", game_code)
		game_title = re.sub(r"((_)_+|(\x00)\x00+|(\s)\s+)", "\\2\\3\\4", game_title).replace("\x00", "_")
		game_code = ''.join(filter(lambda x: x in set(string.printable), game_code))
		data["game_code"] = game_code
		maker_code = bytearray(buffer[0xB0:0xB2]).decode("ascii", "replace")
		maker_code = re.sub(r"(\x00+)$", "", maker_code)
		game_title = re.sub(r"((_)_+|(\x00)\x00+|(\s)\s+)", "\\2\\3\\4", game_title).replace("\x00", "_")
		maker_code = ''.join(filter(lambda x: x in set(string.printable), maker_code))

		data["maker_code"] = maker_code
		data["header_checksum"] = int(buffer[0xBD])
		data["header_checksum_calc"] = self.CalcChecksumHeader()
		data["header_checksum_correct"] = data["header_checksum"] == data["header_checksum_calc"]
		if len(game_code) == 4 and game_code[0] == "M":
			data["header_sha1"] = hashlib.sha1(buffer[0x0:0x100]).hexdigest()
		else:
			data["header_sha1"] = hashlib.sha1(buffer[0x0:0x180]).hexdigest()
		data["version"] = int(buffer[0xBC])
		data["96h_correct"] = (buffer[0xB2] == 0x96)
		data["rom_checksum_calc"] = self.CalcChecksumGlobal()
		data["rom_size_calc"] = int(len(buffer))
		data["save_type"] = None
		data["save_size"] = 0
		save_type_marker = self.GetSaveTypeFromHeaderMarker(buffer)
		if save_type_marker is not None:
			dprint("Patch header marker found: {identifier:02X}, {flags:08b}. Result: {save_type_marker}".format(identifier=buffer[0xBE], flags=buffer[0xBF], save_type_marker=str(save_type_marker)))
			data["save_type"], data["save_size"] = save_type_marker

		# Vast Fame (unlicensed protected carts)
		data["vast_fame"] = False
		if buffer[0x15C:0x16C] == bytearray([ 0xB4, 0x00, 0x9F, 0xE5, 0x99, 0x10, 0xA0, 0xE3, 0x00, 0x10, 0xC0, 0xE5, 0xAC, 0x00, 0x9F, 0xE5 ]): # Initialization code always present in Vast Fame carts
			data["vast_fame"] = True

		# 8M FLASH DACS
		data["dacs_8m"] = False
		if (data["game_title"] == "NGC-HIKARU3" and data["game_code"] == "GHTJ" and data["header_checksum"] == 0xB3):
			data["dacs_8m"] = True

		# e-Reader
		data["ereader"] = False
		if (data["game_title"] == "CARDE READER" and data["game_code"] == "PEAJ" and data["header_checksum"] == 0x9E) or \
		(data["game_title"] == "CARDEREADER+" and data["game_code"] == "PSAJ" and data["header_checksum"] == 0x85) or \
		(data["game_title"] == "CARDE READER" and data["game_code"] == "PSAE" and data["header_checksum"] == 0x95):
			data["ereader"] = True

		if unchanged:
			data["unchanged"] = copy.copy(data)

		self.DATA = data
		data["db"] = self.GetDatabaseEntry()

		# 3D Memory (GBA Video 64 MB)
		data["3d_memory"] = False
		if data["db"] is not None and "3d" in data["db"]:
			data["3d_memory"] = data["db"]["3d"]

		return data

	def GetDatabaseEntry(self):
		data = self.DATA
		db_entry = None
		if os.path.exists("{0:s}/db_AGB.json".format(AppContext.CONFIG_PATH)):
			with open("{0:s}/db_AGB.json".format(AppContext.CONFIG_PATH), encoding="UTF-8") as f:
				db = f.read()
				try:
					db = json.loads(db)
				except (json.JSONDecodeError, ValueError) as e:
					print(__("Error: Database for Game Boy Advance titles is corrupted.") + "\n" + str(e))
					return None
				if data["header_sha1"] in db.keys():
					db_entry = db[data["header_sha1"]]
					if db_entry["gc"] in ("ZMAJ", "ZMBJ", "ZMDE"):
						db_entry["gc"] = "AGS-{:s}".format(db_entry["gc"])
					elif db_entry["gc"] == "ZBBJ":
						db_entry["gc"] = "NTR-{:s}".format(db_entry["gc"])
					elif db_entry["gc"] == "PEAJ":
						db_entry["gc"] = "PEC-{:s}".format(db_entry["gc"])
					elif db_entry["gc"] in ("PSAJ", "PSAE"):
						db_entry["gc"] = "PES-{:s}".format(db_entry["gc"])
					else:
						db_entry["gc"] = "AGB-{:s}".format(db_entry["gc"])
				else:
					dprint(__("No database entry found for this title (Header SHA1: {sha1})", sha1=data["header_sha1"]))
		else:
			print(__("Error: Database for Game Boy Advance titles not found at {path}", path=AppContext.CONFIG_PATH + os.sep + "db_AGB.json"))
		return db_entry
