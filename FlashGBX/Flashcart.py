# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import time, copy, math, struct, os
from .Logging import dprint
from .app import AppContext
from .i18n import __, c__, format_decimal

class Flashcart:
	CONFIG = {}
	COMMAND_SET = None
	CART_WRITE_FNCPTR = None
	CART_WRITE_FAST_FNCPTR = None
	CART_READ_FNCPTR = None
	CART_POWERCYCLE_FNCPTR = None
	PROGRESS_FNCPTR = None
	SET_WE_PIN_WR = None
	SET_WE_PIN_AUDIO = None
	DEFAULT_WE = None
	SECTOR_COUNT = 0
	SECTOR_POS = 0
	SECTOR_MAP = None
	CFI = None
	LAST_SR = 0x00

	def __init__(self, config=None, fncptr=None):
		if config is None: config = {}
		if fncptr is None:
			raise ValueError("fncptr must not be None")
		self.CART_WRITE_FNCPTR = fncptr["cart_write_fncptr"]
		self.CART_WRITE_FAST_FNCPTR = fncptr["cart_write_fast_fncptr"]
		self.CART_READ_FNCPTR = fncptr["cart_read_fncptr"]
		self.CART_POWERCYCLE_FNCPTR = fncptr["cart_powercycle_fncptr"]
		self.PROGRESS_FNCPTR = fncptr["progress_fncptr"]
		self.SET_WE_PIN_WR = fncptr["set_we_pin_wr"]
		self.SET_WE_PIN_AUDIO = fncptr["set_we_pin_audio"]
		self.CONFIG = config
		if "command_set" in config:
			self.CONFIG["_command_set"] = config["command_set"]
		elif "read_identifier" in config and config["read_identifier"][0][1] == 0x90:
			self.CONFIG["_command_set"] = "INTEL"
		else:
			self.CONFIG["_command_set"] = ""
		if "write_pin" in config:
			self.DEFAULT_WE = config["write_pin"]

	def CartRead(self, address, length=0):
		if self.CONFIG["type"].upper() == "AGB":
			if length % 2 == 1:
				length += 1
			if length == 0:
				length = 2
		else:
			if length == 0:
				length = 1
		return self.CART_READ_FNCPTR(address, length)

	def CartWrite(self, commands, fast_write=True, sram=False):
		if "command_set" in self.CONFIG and self.CONFIG["command_set"] in ("GBMEMORY", "DMG-MBC5-32M-FLASH"): fast_write = False
		if fast_write and not sram:
			self.CART_WRITE_FAST_FNCPTR(commands, flashcart=True)
		else:
			for command in commands:
				address = command[0]
				value = command[1]
				self.CART_WRITE_FNCPTR(address, value, flashcart=fast_write, sram=sram)

	def GetCommandSetType(self):
		return self.CONFIG["_command_set"].upper()

	def GetName(self, index=0):
		return self.CONFIG["names"][index]

	@staticmethod
	def GetFlashIDSets(config):
		flash_ids = []
		for flash_id_set in config.get("flash_ids", []):
			if len(flash_id_set) > 1 and isinstance(flash_id_set[1], list):
				flash_ids.append([(flash_id_set[i], flash_id_set[i + 1]) for i in range(0, len(flash_id_set), 2)])
			else:
				flash_ids.append([(None, flash_id_set)])
		return flash_ids

	@staticmethod
	def GetROMAccessParameters(config, offset):
		if config["type"].upper() != "DMG": return ([], offset)
		bank, address = divmod(offset, 0x4000)
		return ([[0x2000, bank & 0xFF], [0x3000, bank >> 8]], 0x4000 + address)

	@staticmethod
	def RelocateFlashCommands(commands, address):
		if len(commands) == 0: return []
		old_address = commands[0][0]
		return [[address if command[0] == old_address else command[0]] + command[1:] for command in commands]

	def GetFlashID(self, index=0):
		return self.GetFlashIDSets(self.CONFIG)[index][0][1]

	def GetVoltage(self):
		return self.CONFIG["voltage"]

	def GetMBC(self):
		if (self.CONFIG["type"].upper() == "AGB") or ("mbc" not in self.CONFIG): return False
		mbc = self.CONFIG["mbc"]
		return mbc

	def FlashCommandsOnBank1(self):
		return ("flash_commands_on_bank_1" in self.CONFIG and self.CONFIG["flash_commands_on_bank_1"] is True)

	def AudioGatesFlashWrite(self):
		return (self.CONFIG.get("set_audio_high") is True and self.CONFIG.get("audio_gates_flash_write") is True)

	def PulseResetAfterWrite(self):
		return ("pulse_reset_after_write" in self.CONFIG and self.CONFIG["pulse_reset_after_write"] is True)

	def HasRTC(self):
		return ("rtc" in self.CONFIG and self.CONFIG["rtc"] is True)

	def HasDoubleDie(self):
		return ("double_die" in self.CONFIG and self.CONFIG["double_die"] is True)

	def SupportsBufferWrite(self):
		buffer_size = self.GetBufferSize()
		if buffer_size is False:
			return False
		else:
			return ("buffer_write" in self.CONFIG["commands"])

	def SupportsPageWrite(self):
		buffer_size = self.GetBufferSize()
		if buffer_size is False:
			return False
		else:
			return ("page_write" in self.CONFIG["commands"])

	def SupportsSingleWrite(self):
		return ("single_write" in self.CONFIG["commands"])

	def SupportsChipErase(self):
		return ("chip_erase" in self.CONFIG["commands"])

	def SupportsSectorErase(self):
		return ("sector_erase" in self.CONFIG["commands"])

	def IsF2A(self):
		if "buffer_write" not in self.CONFIG["commands"]: return False
		for cmd in self.CONFIG["commands"]["buffer_write"]:
			if cmd[0] == "SA+2": return True
		return False

	def WEisWR(self):
		if "write_pin" not in self.CONFIG: return False
		return (self.CONFIG["write_pin"] == "WR")

	def WEisAUDIO(self):
		if "write_pin" not in self.CONFIG: return False
		return (self.CONFIG["write_pin"] in ("AUDIO", "VIN"))

	def WEisWR_RESET(self):
		if "write_pin" not in self.CONFIG: return False
		return (self.CONFIG["write_pin"] == "WR+RESET")

	def GetFlashSize(self, default=False):
		if "flash_size" not in self.CONFIG: return default
		return self.CONFIG["flash_size"]

	def SetFlashSize(self, size):
		if "flash_size" not in self.CONFIG: return
		self.CONFIG["flash_size"] = size

	def GetBufferSize(self):
		if "buffer_size" in self.CONFIG:
			return self.CONFIG["buffer_size"]
		elif "buffer_write" in self.CONFIG["commands"]:
			if "cfi" in self.CONFIG:
				cfi = self.CONFIG["cfi"]
			else:
				cfi = self.ReadCFI()
				if cfi is False:
					print(__("CFI Error: Couldn’t retrieve buffer size from the cartridge."))
					if "single_write" in self.CONFIG["commands"]:
						del(self.CONFIG["commands"]["buffer_write"])
						print(__("Buffered write disabled."))
					return False
			if not "buffer_size" in cfi: return False
			buffer_size = cfi["buffer_size"]
			dprint("Buffer size was read from CFI data:", cfi["buffer_size"])
			self.CONFIG["buffer_size"] = buffer_size
			return buffer_size
		else:
			return False

	def GetCommands(self, key):
		if key not in self.CONFIG["commands"]: return []
		return self.CONFIG["commands"][key]

	def GetROMWriteBankSwitchConflictValues(self):
		values = set()
		if "commands" not in self.CONFIG:
			return values
		for key in ("single_write", "buffer_write", "page_write", "sector_erase", "chip_erase"):
			if key not in self.CONFIG["commands"]:
				continue
			for command in self.CONFIG["commands"][key]:
				if not isinstance(command, (list, tuple)):
					continue
				if len(command) < 2:
					continue
				value = command[1]
				if isinstance(value, int):
					values.add(value & 0xFF)
					break
		return values

	def Unlock(self):
		self.CartRead(0) # dummy read
		if "unlock_read" in self.CONFIG["commands"]:
			for command in self.CONFIG["commands"]["unlock_read"]:
				for _ in range(0, command[2]):
					temp = self.CartRead(command[0], command[1])
					dprint("Reading 0x{:X} bytes from cartridge at 0x{:X} = {:s}".format(command[1], command[0], str(temp)))
			time.sleep(0.001)
		if "unlock" in self.CONFIG["commands"]:
			self.CartWrite(self.CONFIG["commands"]["unlock"], fast_write=False)
			time.sleep(0.001)

	def Reset(self, full_reset=False, max_address=0x2000000):
		if full_reset and "power_cycle" in self.CONFIG:
			self.CART_POWERCYCLE_FNCPTR()
			time.sleep(0.001)
			if self.Unlock() is False: return False
		elif full_reset and "reset_every" in self.CONFIG and "flash_size" in self.CONFIG:
			for j in range(0, self.CONFIG["flash_size"], self.CONFIG["reset_every"]):
				if j >= max_address: break
				dprint("reset_every @ 0x{:X}".format(j))
				for command in self.CONFIG["commands"]["reset"]:
					self.CartWrite([[j + command[0], command[1]]])
					#time.sleep(0.01)
		elif "reset" in self.CONFIG["commands"]:
			self.CartWrite(self.CONFIG["commands"]["reset"])

	def _VerifyFlashID(self, config):
		if "read_identifier" not in config["commands"]: return (False, [])
		flash_id_sets = self.GetFlashIDSets(config)
		if len(flash_id_sets) == 0: return (False, [])
		if "power_cycle" in config and config["power_cycle"] is True:
			self.CART_POWERCYCLE_FNCPTR()

		lengths = {}
		for flash_id_set in flash_id_sets:
			for offset, flash_id in flash_id_set:
				lengths[offset] = max(lengths.get(offset, 0), len(flash_id))

		observations = {}
		try:
			for offset, length in lengths.items():
				if offset is None:
					self.Reset()
					rom = list(self.CartRead(0, length))
					self.Unlock()
					address = config.get("read_identifier_at", 0)
					read_identifier = config["commands"]["read_identifier"]
					reset = config["commands"].get("reset", [])
				else:
					bank_commands, address = self.GetROMAccessParameters(config, offset)
					if bank_commands:
						self.CartWrite(bank_commands, fast_write=False)
					read_identifier = self.RelocateFlashCommands(config["commands"]["read_identifier"], address)
					reset = self.RelocateFlashCommands(config["commands"].get("reset", []), address)
					if reset:
						self.CartWrite(reset)
					rom = list(self.CartRead(address, length))

				self.CartWrite(read_identifier)
				time.sleep(0.001)
				cart_flash_id = list(self.CartRead(address, length))
				observations[offset] = (rom, cart_flash_id)
				if reset:
					self.CartWrite(reset)
		finally:
			if any(offset is not None for offset in lengths):
				bank_commands, address = self.GetROMAccessParameters(config, 0)
				self.CartWrite(bank_commands, fast_write=False)
				reset = self.RelocateFlashCommands(config["commands"].get("reset", []), address)
				if reset: self.CartWrite(reset)

		verified = False
		for flash_id_set in flash_id_sets:
			verified = True
			for offset, expected in flash_id_set:
				rom, flash_id = observations[offset]
				flash_id = list(flash_id[:len(expected)])
				if flash_id != expected or flash_id == list(rom[:len(expected)]):
					verified = False
					break
			if verified: break
		cart_flash_id = list(next(iter(observations.values()))[1])
		dprint(config["names"], config["commands"]["read_identifier"])
		for offset, (_rom, observed) in observations.items():
			dprint("Flash ID at {:s}: {:s}".format("default" if offset is None else "0x{:X}".format(offset), ' '.join(format(x, '02X') for x in observed)))
		return (verified, cart_flash_id)

	def VerifyFlashID(self):
		if "flash_ids_banks" in self.CONFIG:
			cart_flash_ids = []
			for i in range(0, len(self.CONFIG["flash_ids_banks"])):
				self.SelectBankROM(i)
				config = copy.copy(self.CONFIG)
				config["flash_ids"] = [ self.CONFIG["flash_ids_banks"][i] ]
				del(config["flash_ids_banks"])
				(verified, cart_flash_id) = self._VerifyFlashID(config)
				cart_flash_ids.append(cart_flash_id)
				if not verified: return (verified, cart_flash_id)
			cart_flash_id = cart_flash_ids[0]
			self.SelectBankROM(0)
		else:
			(verified, cart_flash_id) = self._VerifyFlashID(self.CONFIG)
		return (verified, cart_flash_id)

	def ReadCFI(self):
		if self.CFI is not None: return self.CFI
		if "read_cfi" not in self.CONFIG["commands"]:
			if self.CONFIG["_command_set"] == "INTEL":
				self.CONFIG["commands"]["read_cfi"] = [ [ 0, 0x98 ] ]
			elif self.CONFIG["_command_set"] == "AMD":
				self.CONFIG["commands"]["read_cfi"] = [ [ 0xAA, 0x98 ] ]

		if "read_cfi" in self.CONFIG["commands"]:
			flash_id_sets = self.GetFlashIDSets(self.CONFIG)
			offset = flash_id_sets[0][0][0] if len(flash_id_sets) > 0 else None
			read_address = 0
			bank_commands = []
			read_cfi = self.CONFIG["commands"]["read_cfi"]
			if offset is not None:
				bank_commands, read_address = self.GetROMAccessParameters(self.CONFIG, offset)
				read_cfi = self.RelocateFlashCommands(read_cfi, read_address)
			try:
				if bank_commands: self.CartWrite(bank_commands, fast_write=False)
				self.CartWrite(read_cfi)
				time.sleep(0.1)
				buffer = self.CartRead(read_address, 0x400)
			finally:
				if offset is None:
					self.Reset()
				else:
					reset = self.RelocateFlashCommands(self.CONFIG["commands"].get("reset", []), read_address)
					if reset: self.CartWrite(reset)
					bank_commands, read_address = self.GetROMAccessParameters(self.CONFIG, 0)
					self.CartWrite(bank_commands, fast_write=False)
					reset = self.RelocateFlashCommands(self.CONFIG["commands"].get("reset", []), read_address)
					if reset: self.CartWrite(reset)
			cfi = CFI().Parse(buffer)
			if cfi is not False:
				cfi["raw"] = buffer
			dprint(cfi)
			if cfi is not False:
				self.CONFIG["cfi"] = cfi
			return cfi
		return False

	def GetSmallestSectorSize(self):
		sector_map = self.GetSectorMap()
		if isinstance(sector_map, int): return sector_map
		smallest_sector_size = sector_map[0][0]
		for sector in sector_map:
			smallest_sector_size = min(smallest_sector_size, sector[0])
		return smallest_sector_size

	def GetSectorOffsets(self, rom_size=0, rom_bank_size=0x4000):
		regions = self.GetSectorMap()
		pos = 0
		offsets = []
		if isinstance(regions, list):
			for region in regions:
				size = region[0]
				count = region[1]
				for _ in range(0, count):
					offsets.append([ pos, size ])
					pos += size
		else:
			while pos < rom_size:
				dprint("Adding extra sector:", pos, regions)
				offsets.append([ pos, regions ])
				pos += regions
		return offsets

	def GetSectorMap(self):
		if self.SECTOR_MAP is not None:
			return self.SECTOR_MAP
		elif "sector_size" in self.CONFIG:
			return self.CONFIG["sector_size"]
		elif "sector_erase" in self.CONFIG["commands"]:
			if "cfi" in self.CONFIG:
				cfi = self.CONFIG["cfi"]
			else:
				cfi = self.ReadCFI()
				if cfi is False:
					print(__("CFI Error: Couldn’t retrieve sector size map from the cartridge."))
					if "chip_erase" in self.CONFIG["commands"]:
						del(self.CONFIG["commands"]["sector_erase"])
						print(__("Sector erase mode disabled."))
					return False
			sector_size = cfi["erase_sector_blocks"]
			if cfi["tb_boot_sector_raw"] == 0x03: sector_size.reverse()
			dprint("Sector size map was read from CFI data:", cfi["erase_sector_blocks"])
			self.CONFIG["sector_size"] = sector_size
			return sector_size
		else:
			return False

	def ChipErase(self):
		self.Reset(full_reset=True)
		time_start = time.time()
		if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"ERASE", "time_start":time_start, "time_estimated": self.CONFIG["chip_erase_timeout"], "abortable":False})
		for i in range(0, len(self.CONFIG["commands"]["chip_erase"])):
			addr = self.CONFIG["commands"]["chip_erase"][i][0]
			data = self.CONFIG["commands"]["chip_erase"][i][1]
			if len(self.CONFIG["commands"]["chip_erase"][i]) > 2:
				we = self.CONFIG["commands"]["chip_erase"][i][2]
			else:
				we = None

			if not addr == None:
				if we == "WR":
					self.SET_WE_PIN_WR()
				elif we == "AUDIO":
					self.SET_WE_PIN_AUDIO()
				self.CartWrite([[addr, data]])
				if we is not None:
					if self.DEFAULT_WE == "WR":
						self.SET_WE_PIN_WR()
					elif self.DEFAULT_WE == "AUDIO":
						self.SET_WE_PIN_AUDIO()

			time.sleep(0.1)
			if self.CONFIG["commands"]["chip_erase_wait_for"][i][0] != None:
				addr = self.CONFIG["commands"]["chip_erase_wait_for"][i][0]
				data = self.CONFIG["commands"]["chip_erase_wait_for"][i][1]
				timeout = self.CONFIG["chip_erase_timeout"]
				while True:
					if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"ERASE", "time_start":time_start, "time_estimated": self.CONFIG["chip_erase_timeout"], "abortable":False})
					if "wait_read_status_register" in self.CONFIG and self.CONFIG["wait_read_status_register"]:
						for j in range(0, len(self.CONFIG["commands"]["read_status_register"])):
							sr_data = self.CONFIG["commands"]["read_status_register"][j][1]

							if we == "WR":
								self.SET_WE_PIN_WR()
							elif we == "AUDIO":
								self.SET_WE_PIN_AUDIO()
							self.CartWrite([[addr, sr_data]])
							if we is not None:
								if self.DEFAULT_WE == "WR":
									self.SET_WE_PIN_WR()
								elif self.DEFAULT_WE == "AUDIO":
									self.SET_WE_PIN_AUDIO()

					self.CartRead(addr, 2) # dummy read (fixes some bootlegs)
					temp = self.CartRead(addr, 2)
					if len(temp) < 2:
						dprint("Communication error 1 in ChipErase():", temp)
						return False
					wait_for = struct.unpack("<H", temp)[0]
					self.LAST_SR = wait_for
					dprint("Status Register Check: 0x{:X} & 0x{:X} == 0x{:X}? {:s}".format(wait_for, self.CONFIG["commands"]["chip_erase_wait_for"][i][2], data, str((wait_for & self.CONFIG["commands"]["chip_erase_wait_for"][i][2]) == data)))
					wait_for = wait_for & self.CONFIG["commands"]["chip_erase_wait_for"][i][2]
					if wait_for == data: break
					time.sleep(0.5)
					timeout -= 0.5
					if timeout <= 0:
						self.PROGRESS_FNCPTR({
							"action": "ABORT",
							"info_type": "msgbox_critical",
							"info_msg":
								__("Erasing the flash chip timed out. The last status register value was {value}.", value="0x{:X}".format(self.LAST_SR)) + "\n\n" +
								__("Please make sure that the cartridge contacts are clean, and that the selected flashcart profile and settings are correct."),
							"abortable": False
						})
						return False
		self.Reset(full_reset=True)
		return True

	def SectorErase(self, pos=0, buffer_pos=0, skip=False):
		if not skip:
			self.Reset(full_reset=False)
			if "sector_erase" not in self.CONFIG["commands"]: return False
			for i in range(0, len(self.CONFIG["commands"]["sector_erase"])):
				addr = self.CONFIG["commands"]["sector_erase"][i][0]
				data = self.CONFIG["commands"]["sector_erase"][i][1]
				if len(self.CONFIG["commands"]["sector_erase"][i]) > 2:
					we = self.CONFIG["commands"]["sector_erase"][i][2]
				else:
					we = None

				if addr == "SA": addr = pos
				if addr == "SA+1": addr = pos + 1
				if addr == "SA+2": addr = pos + 2
				if addr == "SA+16384": addr = pos + 0x4000
				if addr == "SA+28672": addr = pos + 0x7000
				if addr == "SA+66": addr = pos + 0x42
				if addr == "SA+132": addr = pos + 0x84
				if not addr == None:
					if we == "WR":
						self.SET_WE_PIN_WR()
					elif we == "AUDIO":
						self.SET_WE_PIN_AUDIO()
					self.CartWrite([[addr, data]])
					if we is not None:
						if self.DEFAULT_WE == "WR":
							self.SET_WE_PIN_WR()
						elif self.DEFAULT_WE == "AUDIO":
							self.SET_WE_PIN_AUDIO()

				if self.CONFIG["commands"]["sector_erase_wait_for"][i][0] != None:
					addr = self.CONFIG["commands"]["sector_erase_wait_for"][i][0]
					data = self.CONFIG["commands"]["sector_erase_wait_for"][i][1]
					if addr == "SA": addr = pos
					if addr == "SA+1": addr = pos + 1
					if addr == "SA+2": addr = pos + 2
					if addr == "SA+16384": addr = pos + 0x4000
					if addr == "SA+28672": addr = pos + 0x7000
					if addr == "SA+66": addr = pos + 0x42
					if addr == "SA+132": addr = pos + 0x84
					time.sleep(0.05)
					timeout = 100
					while True:
						if "wait_read_status_register" in self.CONFIG and self.CONFIG["wait_read_status_register"] == True:
							for j in range(0, len(self.CONFIG["commands"]["read_status_register"])):
								sr_addr = self.CONFIG["commands"]["read_status_register"][j][0]
								sr_data = self.CONFIG["commands"]["read_status_register"][j][1]

								if we == "WR":
									self.SET_WE_PIN_WR()
								elif we == "AUDIO":
									self.SET_WE_PIN_AUDIO()
								self.CartWrite([[sr_addr, sr_data]])
								if we is not None:
									if self.DEFAULT_WE == "WR":
										self.SET_WE_PIN_WR()
									elif self.DEFAULT_WE == "AUDIO":
										self.SET_WE_PIN_AUDIO()

						self.CartRead(addr, 2) # dummy read (fixes some bootlegs)
						temp = self.CartRead(addr, 2)
						if len(temp) != 2:
							dprint("Communication error 1 in SectorErase():", temp)
							return False
						wait_for = self.CartRead(addr, 2)
						if len(wait_for) != 2:
							dprint("Communication error 2 in SectorErase():", temp)
							return False
						wait_for = struct.unpack("<H", wait_for)[0]
						self.LAST_SR = wait_for
						dprint("Status Register Check: 0x{:X} & 0x{:X} == 0x{:X}? {:s}".format(wait_for, self.CONFIG["commands"]["sector_erase_wait_for"][i][2], data, str(wait_for & self.CONFIG["commands"]["sector_erase_wait_for"][i][2] == data)))
						wait_for = wait_for & self.CONFIG["commands"]["sector_erase_wait_for"][i][2]
						time.sleep(0.05)
						timeout -= 1
						if timeout < 1:
							dprint(f"Timeout error in SectorErase(): 0x{self.LAST_SR:X}")
							#self.PROGRESS_FNCPTR({"action":"ABORT", "info_type":"msgbox_critical", "info_msg":"The sector erase attempt timed out. The last status register value was 0x{:X}.\n\nPlease make sure that the cartridge contacts are clean, and that the selected flashcart profile and settings are correct.".format(self.LAST_SR), "abortable":False})
							return False
						if wait_for == data: break
						self.PROGRESS_FNCPTR({"action":"SECTOR_ERASE", "sector_pos":buffer_pos, "time_start":time.time(), "abortable":True})
					dprint("Done waiting!")

			self.Reset(full_reset=False)

		if "sector_size" not in self.CONFIG: return False
		if isinstance(self.CONFIG["sector_size"], list):
			self.CONFIG["sector_size"][self.SECTOR_POS][1] -= 1
			if (self.CONFIG["sector_size"][self.SECTOR_POS][1] == 0) and (len(self.CONFIG["sector_size"]) > self.SECTOR_POS + 1):
				self.SECTOR_POS += 1
			try:
				sector_size = self.CONFIG["sector_size"][self.SECTOR_POS][0]
			except:
				dprint("Warning: Sector map is smaller than expected.")
				self.SECTOR_POS -= 1
			return sector_size
		else:
			return self.CONFIG["sector_size"]

	def HasBanks(self):
		return "flash_bank_select_type" in self.CONFIG

	def SelectBankROM(self, index):
		if "flash_bank_select_type" not in self.CONFIG: return False
		dprint(f"Setting flash bank to {index:d}")
		if self.CONFIG["flash_bank_select_type"] == 1:
			index = index & 0xF
			self.CartWrite([[2, index << 4]], sram=True)
			self.CartWrite([[3, 0x40]], sram=True)
			self.CartWrite([[4, 0x00]], sram=True)
			return True
		elif self.CONFIG["flash_bank_select_type"] == 2: # Flash2Advance Ultra
			bank1 = 0 if index < 4 else 0x10
			bank2 = index % 4 * 0x400
			self.CartWrite([[0x987654*2, 0x5354]], fast_write=False)
			self.CartWrite([[0xE12345*2, 0xA55A]], fast_write=False)
			self.CartWrite([[6, bank1]], fast_write=False, sram=True)
			self.CartWrite([[0x987654*2, 0x5354]], fast_write=False)
			self.CartWrite([[0xB5AC97*2, bank2]], fast_write=False)
			self.CartWrite([[0x987654*2, 0x5354]], fast_write=False)
			self.CartWrite([[0xF12345*2, 0x9413]], fast_write=False)
			return True

		return False

class CFI:
	@classmethod
	def swap_bits(cls, n: int, pair: tuple) -> int:
		p, q = pair
		if (((n & (1 << p)) >> p) ^ ((n & (1 << q)) >> q)) == 1:
			n ^= (1 << p)
			n ^= (1 << q)
		return n

	def Parse(self, buffer):
		if buffer is False or buffer == b'': return False
		buffer = copy.copy(buffer)
		info = {}
		magic = "{:s}{:s}{:s}".format(chr(buffer[0x20]), chr(buffer[0x22]), chr(buffer[0x24]))

		info["d_swap"] = None
		if magic == "QRY": # nothing swapped
			info["d_swap"] = [( 0, 0 )]
		elif magic == "RQZ": # D0D1 swapped
			info["d_swap"] = [( 0, 1 )]
		elif magic == "\x92\x91\x9A": # D0D1+D6D7 swapped
			info["d_swap"] = [( 0, 1 ), ( 6, 7 )]
		else:
			return False

		if info["d_swap"] is not None:
			for j2 in range(0, len(info["d_swap"])):
				for j in range(0, len(buffer)):
					buffer[j] = CFI.swap_bits(buffer[j], info["d_swap"][j2])
		try:
			info["flash_id"] = buffer[0:8]
			info["magic"] = "{:s}{:s}{:s}".format(chr(buffer[0x20]), chr(buffer[0x22]), chr(buffer[0x24]))

			if buffer[0x36] == 0xFF and buffer[0x48] == 0xFF:
				print(__("Warning: No information about the voltage range found in CFI data."))
				try:
					with open(AppContext.CONFIG_PATH + os.sep + "cfi_debug.bin", "wb") as f: f.write(buffer)
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
			pos = 0
			for i in range(0, min(4, info["erase_sector_regions"])):
				b = (buffer[0x5C+(i*8)] << 8 | buffer[0x5A+(i*8)]) + 1
				t = (buffer[0x60+(i*8)] << 8 | buffer[0x5E+(i*8)]) * 256
				size = b * t
				pos += size
				info["erase_sector_blocks"].append([ t, b, size ])	

		except:
			print(__("Error: Trying to parse CFI data resulted in an error."))
			try:
				with open(AppContext.CONFIG_PATH + os.sep + "cfi_debug.bin", "wb") as f: f.write(buffer)
			except:
				pass
			return False

		s = ""
		if info["d_swap"] is not None and info["d_swap"] != [( 0, 0 )]: s += __("Swapped pins: {pins}", pins=str(info["d_swap"])) + "\n"
		s += __("Device size: {size_hex} ({size_mib})", size_hex="0x{:07X}".format(info["device_size"]), size_mib=format_decimal(info["device_size"] / 1024 / 1024, precision=2) + __(" MiB")) + "\n"
		s += __("Voltage: {min_v}–{max_v} V", min_v=format_decimal(info["vdd_min"], precision=1), max_v=format_decimal(info["vdd_max"], precision=1)) + "\n"
		s += __("Single write: {val}", val=c__("ROM Write Method", "Supported") if info["single_write"] else c__("ROM Write Method", "Not supported")) + "\n"
		if "buffer_size" in info:
			s += __("Buffered write: {val}", val=c__("ROM Write Method", "Supported") if info["buffer_write"] else c__("ROM Write Method", "Not supported")) + " " + "({bytes})".format(bytes=str(info["buffer_size"]) + __(" Bytes")) + "\n"
		else:
			s += __("Buffered write: {val}", val=c__("ROM Write Method", "Supported") if info["buffer_write"] else c__("ROM Write Method", "Not supported")) + "\n"
		if info["chip_erase"]: s += __("Chip erase: {avg}–{max} ms", avg=str(info["chip_erase_time_avg"]), max=str(info["chip_erase_time_max"])) + "\n"
		if info["sector_erase"]: s += __("Sector erase: {avg}–{max} ms", avg=str(info["sector_erase_time_avg"]), max=str(info["sector_erase_time_max"])) + "\n"
		if info["tb_boot_sector"] is not False: s += __("Sector flags: {flags}", flags=str(info["tb_boot_sector"])) + "\n"
		pos = 0
		oversize = False
		s = s[:-1]
		for i in range(0, info['erase_sector_regions']):
			esb = info['erase_sector_blocks'][i]
			if oversize:
				s += "\n" + __("Region {region}: {start}–{end} @ {size} × {count} (alternative)", region=str(i+1), start="0x{:07X}".format(pos), end="0x{:07X}".format(pos+esb[2]-1), size="0x{:X}".format(esb[0]) + __(" Bytes"), count=str(esb[1]))
			else:
				s += "\n" + __("Region {region}: {start}–{end} @ {size} × {count}", region=str(i+1), start="0x{:07X}".format(pos), end="0x{:07X}".format(pos+esb[2]-1), size="0x{:X}".format(esb[0]) + __(" Bytes"), count=str(esb[1]))
			pos += esb[2]
			if pos >= info['device_size']:
				pos = 0
				oversize = True
		info["info"] = s

		return info

class Flashcart_AGB_GBAMP(Flashcart):
	def SectorErase(self, pos=0, buffer_pos=0, skip=False):
		for i in range(0, 4):
			sector = pos >> 13 << 16 | (pos & 0x1FFF) + (i * 4)
			ret = super().SectorErase(sector, buffer_pos, skip)
			if ret is False: break
		return ret

	def VerifyFlashID(self):
		self.CART_POWERCYCLE_FNCPTR()
		verified = False
		self.Unlock()
		rom = list(self.CartRead(0x1E8F << 1, 2) + self.CartRead(0x168F << 1, 2))
		self.CartWrite(self.CONFIG["commands"]["read_identifier"], fast_write=True)
		cart_flash_id = list(self.CartRead(0x1E8F << 1, 2) + self.CartRead(0x168F << 1, 2))
		if rom != cart_flash_id and cart_flash_id == self.CONFIG["flash_ids"][0]:
			self.CartWrite(self.CONFIG["commands"]["reset"], fast_write=True)
			verified = True
		dprint(verified, rom, cart_flash_id)
		return (verified, cart_flash_id)

class Flashcart_DMG_BUNG_16M(Flashcart):
	def SupportsSectorErase(self):
		return False

	def SupportsChipErase(self):
		return True

	def ChipErase(self, pos=0, buffer_pos=0, skip=False):
		time_start = time.time()
		if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"ERASE", "time_start":time_start, "abortable":False})

		self.CartWrite([[0x2000, 0x02]], fast_write=False)
		self.CartWrite([[0x6AAA, 0xAA]], fast_write=True)
		self.CartWrite([[0x2000, 0x01]], fast_write=False)
		self.CartWrite([[0x5554, 0x55]], fast_write=True)
		self.CartWrite([[0x2000, 0x02]], fast_write=False)
		self.CartWrite([[0x6AAA, 0x80]], fast_write=True)
		self.CartWrite([[0x2000, 0x02]], fast_write=False)
		self.CartWrite([[0x6AAA, 0xAA]], fast_write=True)
		self.CartWrite([[0x2000, 0x01]], fast_write=False)
		self.CartWrite([[0x5554, 0x55]], fast_write=True)
		self.CartWrite([[0x2000, 0x02]], fast_write=False)
		self.CartWrite([[0x6AAA, 0x10]], fast_write=True)

		lives = 10
		while lives > 0:
			raw = self.CartRead(0)
			sr = raw[0] if raw else 0
			self.LAST_SR = sr
			dprint("Status Register Check: 0x{:X} & 0x{:X} == 0x{:X}? {:s}".format(sr, 0x80, 0x80, str((sr & 0x80) == 0x80)))
			if (sr & 0x80) == 0x80: break
			time.sleep(0.5)
			lives -= 1
		if lives == 0:
			self.PROGRESS_FNCPTR({
				"action": "ABORT",
				"info_type": "msgbox_critical",
				"info_msg":
					__("Erasing the flash chip timed out. The last status register value was {value}.", value="0x{:X}".format(self.LAST_SR)) + "\n\n" +
					__("Please make sure that the cartridge contacts are clean, and that the selected flashcart profile and settings are correct."),
				"abortable": False
			})
			return False

		self.Reset()
		return True

	def Reset(self, full_reset=None, max_address=None):
		self.CartWrite([[0x2000, 0x02]], fast_write=False)
		self.CartWrite([[0x6AAA, 0xAA]], fast_write=True)
		self.CartWrite([[0x2000, 0x01]], fast_write=False)
		self.CartWrite([[0x5554, 0x55]], fast_write=True)
		self.CartWrite([[0x2000, 0x02]], fast_write=False)
		self.CartWrite([[0x6AAA, 0xF0]], fast_write=True)

	def VerifyFlashID(self):
		rom = list(self.CartRead(0, 4))
		self.CartWrite([[0x2000, 0x02]], fast_write=False)
		self.CartWrite([[0x6AAA, 0xAA]], fast_write=True)
		self.CartWrite([[0x2000, 0x01]], fast_write=False)
		self.CartWrite([[0x5554, 0x55]], fast_write=True)
		self.CartWrite([[0x2000, 0x02]], fast_write=False)
		self.CartWrite([[0x6AAA, 0x90]], fast_write=True)
		cart_flash_id = list(self.CartRead(0, 4))
		verified = False
		if rom != cart_flash_id and cart_flash_id == self.CONFIG["flash_ids"][0]:
			self.Reset()
			verified = True
		return (verified, cart_flash_id)

class Flashcart_DMG_MMSA(Flashcart):
	def ReadCFI(self):
		return False

	def GetMBC(self):
		return 0x105

	def SupportsSectorErase(self):
		return False

	def SupportsChipErase(self):
		return True

	def EraseHiddenSector(self, buffer):
		if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"SECTOR_ERASE", "sector_pos":0, "time_start":time.time(), "abortable":False})

		if self.UnlockForWriting() is False: return False

		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xAA ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x2A ],
			[ 0x126, 0xAA ],
			[ 0x127, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0x60 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xAA ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x2A ],
			[ 0x126, 0xAA ],
			[ 0x127, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0x04 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		lives = 10
		while lives > 0:
			if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"SECTOR_ERASE", "sector_pos":0, "time_start":time.time(), "abortable":False})
			raw = self.CartRead(0)
			sr = raw[0] if raw else 0
			self.LAST_SR = sr
			dprint("Status Register Check: 0x{:X} & 0x{:X} == 0x{:X}? {:s}".format(sr, 0x80, 0x80, str((sr & 0x80) == 0x80)))
			if (sr & 0x80) == 0x80: break
			time.sleep(0.5)
			lives -= 1
		if lives == 0:
			self.PROGRESS_FNCPTR({
				"action": "ABORT",
				"info_type": "msgbox_critical",
				"info_msg":
					__("Erasing the hidden sector timed out. The last status register value was {value}.", value="0x{:X}".format(self.LAST_SR)) + "\n\n" +
					__("Please make sure that the cartridge contacts are clean, and that the selected flashcart profile and settings are correct."),
				"abortable": False
			})
			return False

		# Write Hidden Sector
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xAA ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x2A ],
			[ 0x126, 0xAA ],
			[ 0x127, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0x60 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xAA ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x2A ],
			[ 0x126, 0xAA ],
			[ 0x127, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xE0 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x2100, 0x01 ],
		]
		self.CartWrite(cmds)

		# Disable writes to MBC registers
		cmds = [
			[ 0x120, 0x10 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		# Undo Wakeup
		cmds = [
			[ 0x120, 0x08 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		return True

	def ChipErase(self):
		time_start = time.time()
		if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"ERASE", "time_start":time_start, "abortable":False})

		if self.UnlockForWriting() is False: return False

		# Erase Chip
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xAA ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x2A ],
			[ 0x126, 0xAA ],
			[ 0x127, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0x80 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xAA ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x2A ],
			[ 0x126, 0xAA ],
			[ 0x127, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0x10 ],
			[ 0x13F, 0xA5 ]
		]
		self.CartWrite(cmds)
		lives = 10
		while lives > 0:
			if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"ERASE", "time_start":time_start, "abortable":False})
			raw = self.CartRead(0)
			sr = raw[0] if raw else 0
			self.LAST_SR = sr
			dprint("Status Register Check: 0x{:X} & 0x{:X} == 0x{:X}? {:s}".format(sr, 0x80, 0x80, str((sr & 0x80) == 0x80)))
			if (sr & 0x80) == 0x80: break
			time.sleep(0.5)
			lives -= 1
		if lives == 0:
			self.PROGRESS_FNCPTR({
				"action": "ABORT",
				"info_type": "msgbox_critical",
				"info_msg":
					__("Erasing the flash chip timed out. The last status register value was {value}.", value="0x{:X}".format(self.LAST_SR)) + "\n\n" +
					__("Please make sure that the cartridge contacts are clean, and that the selected flashcart profile and settings are correct."),
				"abortable": False
			})
			return False

		# Reset flash to read mode
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x40 ],
			[ 0x126, 0x80 ],
			[ 0x127, 0xF0 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)

		# Map all the flash memory before writing
		cmds = [
			[ 0x120, 0x04 ],
			[ 0x13F, 0xa5 ],
		]
		self.CartWrite(cmds)
		return True

	def Unlock(self):
		return self.UnlockForWriting()

	def UnlockForWriting(self):
		time_start = time.time()
		if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"UNLOCK", "time_start":time_start, "abortable":False})

		self.CartWrite([[ 0x2100, 0x01 ]])
		# Enable Flash Chip Access
		cmds = [
			[ 0x120, 0x09 ],
			[ 0x121, 0xAA ],
			[ 0x122, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		# Re-Enable writes to MBC registers
		cmds = [
			[ 0x120, 0x11 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		# Disable flash chip protection
		cmds = [
			[ 0x120, 0x0A ],
			[ 0x125, 0x62 ],
			[ 0x126, 0x04 ],
			[ 0x13F, 0xA5 ],
			[ 0x120, 0x02 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		self.CartWrite([[ 0x2100, 0x01 ]])

		# Suspend potential previous erase
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x00 ],
			[ 0x126, 0x00 ],
			[ 0x127, 0xB0 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)

		# Unlock Hidden Sector
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xAA ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x2A ],
			[ 0x126, 0xAA ],
			[ 0x127, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0x60 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x55 ],
			[ 0x126, 0x55 ],
			[ 0x127, 0xAA ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x2A ],
			[ 0x126, 0xAA ],
			[ 0x127, 0x55 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		cmds = [
			[ 0x120, 0x0F ],
			[ 0x125, 0x00 ],
			[ 0x126, 0x00 ],
			[ 0x127, 0x40 ],
			[ 0x13F, 0xA5 ],
		]
		self.CartWrite(cmds)
		lives = 10
		while lives > 0:
			raw = self.CartRead(0)
			sr = raw[0] if raw else 0
			self.LAST_SR = sr
			dprint("Status Register Check: 0x{:X} & 0x{:X} == 0x{:X}? {:s}".format(sr, 0x80, 0x80, str((sr & 0x80) == 0x80)))
			if (sr & 0x80) == 0x80: break
			if self.PROGRESS_FNCPTR is not None: self.PROGRESS_FNCPTR({"action":"UNLOCK", "time_start":time_start, "abortable":False})
			time.sleep(0.5)
			lives -= 1
		if lives == 0:
			self.PROGRESS_FNCPTR({
				"action": "ABORT",
				"info_type": "msgbox_critical",
				"info_msg":
					__("Unlocking the hidden sector timed out. The last status register value was {value}.", value="0x{:X}".format(self.LAST_SR)) + "\n\n" +
					__("Please make sure that the cartridge contacts are clean, and that the selected flashcart profile and settings are correct."),
				"abortable": False
			})
			return False


def empty_flashcarts_map():
	return {"DMG": {}, "AGB": {}}

def has_3v_compatible_profile(carts, cart_type_index):
	if not isinstance(carts, list):
		try:
			carts = list(carts)
		except TypeError:
			return False
	if cart_type_index is None or cart_type_index < 0 or cart_type_index >= len(carts):
		return False
	selected = carts[cart_type_index]
	if not isinstance(selected, dict):
		return False
	if selected.get("voltage", 5) != 5:
		return False
	selected_ids = selected.get("flash_ids")
	if not selected_ids:
		return False
	selected_type = selected.get("type")
	for i, profile in enumerate(carts):
		if i == cart_type_index: continue
		if not isinstance(profile, dict): continue
		if profile.get("type") != selected_type: continue
		if profile.get("voltage", 5) != 3.3 and not profile.get("voltage_variants", False): continue
		for flash_id in profile.get("flash_ids", []):
			if flash_id in selected_ids:
				return True
	return False
