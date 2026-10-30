# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import os, platform

class DumpReport:
	@staticmethod
	def _fields_to_lines(fields, col=19):
		lines = []
		for label, value in fields:
			parts = str(value).split("\n")
			lines.append(f"* {label + ':':<{col}}{parts[0]}")
			lines.extend(" " * (col + 2) + part for part in parts[1:])
		return lines

	@classmethod
	def _section_lines(cls, title, fields, col=19, level=2):
		marker = "=" * level
		return ["", f"{marker} {title} {marker}"] + cls._fields_to_lines(fields, col)

	@staticmethod
	def _render(lines):
		newline = "\r\n" if platform.system() == "Windows" else "\n"
		return newline.join(["= FlashGBX Dump Report ="] + lines + [""])

	@classmethod
	def _common_sections(cls, di, device, elapsed, retries=None):
		from .Formatter import Formatter
		from .app import AppInfo
		from . import i18n

		file_size = di["file_size"]
		lines = cls._section_lines("File Information", [
			("File Name", os.path.basename(di["file_name"]) if di["file_name"] else ""),
			("File Size", f"{Formatter.file_size(file_size, space=' ', localized=False)} ({file_size:d} bytes)"),
			("CRC32", f"{di['hash_crc32']:08x}"),
			("MD5", di["hash_md5"]),
			("SHA-1", di["hash_sha1"]),
			("SHA-256", di["hash_sha256"]),
		])
		general_fields = [
			("Hardware", f"{device.GetFullName()} – Firmware {device.GetFirmwareVersion()}" if device is not None else "N/A (report generated from RAW file)"),
			("Software", f"{AppInfo.NAME} {AppInfo.VERSION}"),
			("OS Platform", f"{AppInfo.os_string()}, {platform.machine()}, {i18n.OS_LANGUAGE}"),
		]
		if device is not None and device.GetName() == "GBxCart RW":
			general_fields.append(("Baud Rate", f"{device.GetBaudRate():d}"))
			flow_control = di.get("flow_control")
			if flow_control is None:
				flow_control = getattr(getattr(device, "DEVICE", None), "ACK_ENABLED", False)
			general_fields.append(("Flow Control", "Enabled" if flow_control else "Disabled"))
		general_fields += [
			("Dump Time", di["timestamp"]),
			("Time Elapsed", elapsed),
			("Transfer Buffer", f"{di['transfer_size']:d} bytes" if di["transfer_size"] is not None else "N/A"),
		]
		if retries is not None: general_fields.append(("Retries", f"{retries:d}"))
		return lines + cls._section_lines("General Information", general_fields)

	@staticmethod
	def _database_fields(db, mode):
		from .CartridgeTypes import AgbSaveTypes
		from .Formatter import Formatter

		fields = []
		if "gn" in db and "ne" in db: fields.append(("Game Name", f"{db['gn']} {db['ne']}"))
		elif "gn" in db: fields.append(("Game Name", db["gn"]))
		for label, key in (("Region", "rg"), ("Language(s)", "lg")):
			if key in db: fields.append((label, db[key]))
		if mode == "DOT":
			if db.get("gc"): fields.append(("Card Serial", db["gc"]))
			if "rc" in db: fields.append(("CRC32", f"{db['rc']:08x}"))
			if "rs" in db: fields.append(("Size", f"{db['rs']} bytes"))
		else:
			if "rv" in db: fields.append(("Revision", db["rv"]))
			if "gc" in db: fields.append(("Game Code", db["gc"]))
			if "rc" in db: fields.append(("ROM CRC32", f"{db['rc']:08x}"))
			if "rs" in db: fields.append(("ROM Size", Formatter.file_size(db["rs"], space=" ", as_int=True, localized=False)))
			if mode == "AGB" and "st" in db: fields.append(("Save Type", AgbSaveTypes(db["st"]).GetString(localized=False)))
		return fields

	@classmethod
	def generate_ereader(cls, di, device, raw, path, header) -> str:
		import hashlib, json, zlib
		from .EReader import EReader
		from .Formatter import Formatter
		from .app import AppContext
		from .Logging import dprint

		crc32 = zlib.crc32(raw)
		sha1 = hashlib.sha1(raw).hexdigest()
		di = dict(di, file_name=path, file_size=len(raw), hash_crc32=crc32,
			hash_md5=hashlib.md5(raw).hexdigest(), hash_sha1=sha1, hash_sha256=hashlib.sha256(raw).hexdigest())
		elapsed = Formatter.progress_time(di["time_elapsed"], localized=False) if di["time_elapsed"] is not None else "N/A"
		lines = cls._common_sections(di, device, elapsed)
		dumping = []
		for label, key in (("Error-correction", "error_correction"), ("Auto Calibration", "auto_calibration"), ("Sensor Brightness", "sensor_brightness"),
			("Vertical Offset", "vertical_offset"), ("PWM Value", "pwm"), ("Threshold Factor", "threshold_factor")):
			values = di["settings"].get(key, ())
			if key in ("auto_calibration", "error_correction"): value = "/".join("Enabled" if item else "Disabled" for item in values) or "N/A"
			elif not values: value = "N/A"
			else: value = str(min(values)) if min(values) == max(values) else f"{min(values)}–{max(values)}"
			dumping.append((label, value))
		states = di.get("block_states", ())
		block_status = "".join(EReader.BLOCK_SYMBOLS[state] for state in states) or "N/A"
		if states:
			block_status += f"\n({len(states)} total, {states.count(EReader.BLOCK_CONFIRMED)} reconfirmed, {di.get('blocks_error_corrected', 'N/A')} error-corrected)"
		dumping.append(("Factory Settings", "\n".join(di["factory"][offset:offset + 16].hex().upper() for offset in range(0, 64, 16)) if di["factory"] is not None else "N/A"))
		dumping.append(("Block Status", block_status))
		lines += cls._section_lines("Dumping Settings and Status", dumping)
		program_type = header["program_type"] or "N/A"
		if program_type == "e-Viewer":
			details = []
			if header["program_title"]: details.append(header["program_title"])
			for strip in header["strips"]:
				if strip["strip_number"] != header["strip_number"]: continue
				if strip["hp"] is not None: details.append(f"HP: {strip['hp']}")
				if strip["id"] is not None: details.append(f"ID: {strip['id']}")
			if details: program_type += " (" + ", ".join(details) + ")"
		parsed_fields = [
			("Region", header["region"]),
			("Dot Code Number", f"{header['strip_number']} of {header['strip_count']}"),
			("Dot Code Type", header["strip_type"]),
			("Program Title", header["program_title"] or "N/A"),
			("Program Type", program_type),
		]
		if header["program_type"] != "e-Viewer":
			parsed_fields.append(("Program Size", f"{header['program_size']} bytes" if header["program_size"] is not None else "N/A"))
		card_id = next((strip["id"] for strip in header["strips"] if strip["strip_number"] == header["strip_number"]), None)
		parsed_fields.append(("Card ID", card_id or "N/A"))
		parsed_fields += [
			("Identifier String", header["id_string"]),
			("Header Checksum", f"0x{header['header_checksum']:02X}"),
			("Data Checksum", f"0x{header['data_checksum']:04X}"),
			("Global Checksum", f"0x{header['global_checksum']:02X}"),
			("Save Permission", "Enabled" if header["save_permission"] else "Disabled"),
		]
		lines += cls._section_lines("Parsed Data", parsed_fields)
		db = None
		try:
			with open(os.path.join(AppContext.CONFIG_PATH, "db_DOT.json"), encoding="utf-8") as file:
				database = json.load(file)
				db = database.get(sha1) if isinstance(database, dict) else None
		except (OSError, ValueError) as e:
			dprint(f"Could not load e-Reader database: {e}")
		if isinstance(db, dict) and db.get("rc") == crc32 and db.get("rs") == len(raw):
			lines += cls._section_lines("Database Match", cls._database_fields(db, "DOT"))
		return cls._render(lines)

	@classmethod
	def generate(cls, di, device) -> str:
		from .Mapper import DMG_Mapper, ConvertMapperToMapperType
		from .CartridgeTypes import RomSizes, DmgSaveTypes, AgbSaveTypes
		from .Formatter import Formatter

		# Resolve header into a shallow copy so we never mutate the caller's dict
		header = dict(di["header"].get("unchanged", di["header"]))
		if "db" in di["header"]:
			header["db"] = di["header"]["db"]

		mode = di["system"]
		if mode not in ("DMG", "AGB"):
			raise NotImplementedError

		system_name = "Game Boy" if mode == "DMG" else "Game Boy Advance"

		rom_size_int = di["rom_size"]
		if rom_size_int in RomSizes():
			rom_size_str = RomSizes(rom_size_int).GetString(localized=False)
		else:
			rom_size_str = f"{rom_size_int:,} bytes"

		keys = list(device.SUPPORTED_CARTS[mode].keys())
		cart_type_str = keys[di["cart_type"]] if 0 <= di["cart_type"] < len(keys) else f"#{di['cart_type']}"
		logo_str = "OK" if header["logo_correct"] else "Invalid"
		lines = cls._common_sections(di, device, "%TIME_ELAPSED% (%TRANSFER_RATE%)", retries=device.GetReadErrors())

		dumping_fields = [
			("Mode",     system_name),
			("ROM Size", rom_size_str),
		]
		if mode == "DMG":
			mapper_int = di["mapper_type"]
			if mapper_int in DMG_Mapper().GetAllMapperIds():
				mapper_str = ConvertMapperToMapperType(mapper_int)[0]
			else:
				mapper_str = f"0x{mapper_int:02X}"
			dumping_fields += [
				("Mapper Type",       mapper_str),
				("Cartridge Profile", cart_type_str),
				("Read Method",       di["dmg_read_method"]),
			]
		else:  # AGB
			dumping_fields += [
				("Cartridge Profile", cart_type_str),
				("Read Method",       di["agb_read_method"]),
			]
		lines += cls._section_lines("Dumping Settings", dumping_fields)

		hdr_chk = header["header_checksum"]
		hdr_chk_calc = header.get("header_checksum_calc", hdr_chk)
		header_checksum_str = f"OK (0x{hdr_chk:02X})" if header["header_checksum_correct"] \
			else f"Invalid (0x{hdr_chk_calc:02X}≠0x{hdr_chk:02X})"

		if mode == "DMG":
			cgb_raw = header["cgb"]
			if cgb_raw == 0xC0:
				target_platform = "Game Boy Color exclusive"
			elif cgb_raw == 0x80:
				target_platform = "Game Boy Color"
			elif header["old_lic"] == 0x33 and header["sgb"] == 0x03:
				target_platform = "Super Game Boy"
			else:
				target_platform = "Original Game Boy"

			sgb_str = "Supported" if (header["old_lic"] == 0x33 and header["sgb"] == 0x03) else "No support"
			cgb_str = DMG_Mapper().CGB_MAP.get(cgb_raw, f"Unknown (0x{cgb_raw:02X})")

			header["rom_checksum_calc"] = device.INFO.get("rom_checksum_calc", header.get("rom_checksum_calc"))
			rom_chk_ok = header["rom_checksum_calc"] == header["rom_checksum"]
			rom_checksum_str = f"OK (0x{header['rom_checksum']:04X})" if rom_chk_ok \
				else f"Invalid (0x{header['rom_checksum_calc']:04X}≠0x{header['rom_checksum']:04X})"

			hdr_rom_size_raw = header["rom_size_raw"]
			if hdr_rom_size_raw < RomSizes().GetNumberOfTypes():
				hdr_rom_size_str = RomSizes().GetString(index=hdr_rom_size_raw, localized=False)
			else:
				hdr_rom_size_str = f"Unknown (0x{hdr_rom_size_raw:02X})"

			hdr_save_raw = header["ram_size_raw"]
			if hdr_save_raw == 0x00:
				hdr_save_str = f"No SRAM (0x{hdr_save_raw:02X})"
			elif hdr_save_raw in DmgSaveTypes():
				hdr_save_str = f"{DmgSaveTypes(mbc=hdr_save_raw).GetString(localized=False)} (0x{hdr_save_raw:02X})"
			else:
				hdr_save_str = f"Unknown (0x{hdr_save_raw:02X})"

			mapper_raw = header["mapper_raw"]
			if mapper_raw in DMG_Mapper().GetAllMapperIds():
				hdr_mapper_str = f"{DMG_Mapper().GetMapperName(mapper_raw)} (0x{mapper_raw:02X})"
			else:
				hdr_mapper_str = f"Unknown (0x{mapper_raw:02X})"

			parsed_fields = [("Game Title", (header.get("game_title") or "").replace("\0", "␀"))]
			if cgb_raw in (0xC0, 0x80) and header.get("game_code"):
				parsed_fields.append(("Game Code", header["game_code"].replace("\0", "␀")))
			parsed_fields += [
				("Revision",        str(header["version"])),
				("Super Game Boy",  sgb_str),
				("Game Boy Color",  cgb_str),
				("Nintendo Logo",   logo_str),
				("Header Checksum", header_checksum_str),
				("ROM Checksum",    rom_checksum_str),
				("ROM Size",        hdr_rom_size_str),
				("SRAM Size",       hdr_save_str),
				("Mapper Type",     hdr_mapper_str),
				("Target Platform", target_platform),
			]
			lines += cls._section_lines("Parsed Data", parsed_fields)

			if "gbmem" in di and di["gbmem"] is not None:
				raw_data = "\n".join(
					''.join(f"{x:02X}" for x in di["gbmem"][i*0x20:i*0x20+0x20])
					for i in range(4)
				)
				if "gbmem_parsed" in di and di["gbmem_parsed"] is not None and len(di["gbmem_parsed"]) > 0:
					if isinstance(di["gbmem_parsed"], list):
						p0 = di["gbmem_parsed"][0]
						lines += cls._section_lines("GB-Memory Data (Multi Menu)", [
							("Write Timestamp", p0["timestamp"]),
							("Write Kiosk ID",  p0["kiosk_id"]),
							("Number of Games", f"{p0['num_games']:d}"),
							("Write Counter",   f"{p0['write_count']:d}"),
							("Cartridge ID",    p0["cart_id"]),
							("Raw Map Data",    raw_data),
						])
						for i in range(1, len(di["gbmem_parsed"])):
							entry = di["gbmem_parsed"][i]
							if entry["menu_index"] == 0xFF or not entry["header"]["logo_correct"]:
								continue
							section = "Menu ROM" if i == 1 else f"Game {i - 1}"
							entry_rom_bytes = entry["rom_size"]
							entry_size_str = f"{Formatter.file_size(entry_rom_bytes, space=' ', localized=False)} ({entry_rom_bytes:d} bytes)"
							entry_fields = [
								("Game Code",        entry["game_code"]),
								("Game Title",       entry["title"]),
								("Write Timestamp",  entry["timestamp"]),
								("Write Kiosk ID",   entry["kiosk_id"]),
								("Location",         f"0x{entry['rom_offset']:06X}–0x{entry['rom_offset'] + entry['rom_size'] - 1:06X}"),
								("ROM Size",         entry_size_str),
							]
							if "crc32" in entry: entry_fields.append(("CRC32",    f"{entry['crc32']:08x}"))
							if "md5"   in entry: entry_fields.append(("MD5",      entry["md5"]))
							if "sha1"  in entry: entry_fields.append(("SHA-1",    entry["sha1"]))
							if "sha256" in entry: entry_fields.append(("SHA-256", entry["sha256"]))
							lines += cls._section_lines(section, entry_fields, level=3)
							if "db_entry" in entry and "crc32" in entry and entry["db_entry"]["rc"] == entry["crc32"]:
								lines += cls._fields_to_lines([("Database Match", f"{entry['db_entry']['gn']} {entry['db_entry']['ne']}")])
					elif isinstance(di["gbmem_parsed"]["game_code"], str):
						p = di["gbmem_parsed"]
						lines += cls._section_lines("GB-Memory Data (Single Game)", [
							("Game Code",       p["game_code"]),
							("Game Title",      p["title"]),
							("Write Timestamp", p["timestamp"]),
							("Write Kiosk ID",  p["kiosk_id"]),
							("Write Counter",   f"{p['write_count']:d}"),
							("Cartridge ID",    p["cart_id"]),
							("Raw Map Data",    raw_data),
						])
				else:
					lines += cls._fields_to_lines([("GB-Memory Data", raw_data)])

		elif mode == "AGB":
			savelib_str = AgbSaveTypes().GetStringFromSaveLib(di["agb_savelib"], localized=False)
			game_title_raw = (header.get("game_title_raw") or "").replace("\0", "␀")
			game_code_raw  = (header.get("game_code_raw")  or "").replace("\0", "␀")

			parsed_fields = [
				("Game Title",      game_title_raw),
				("Game Code",       game_code_raw),
				("Revision",        str(header["version"])),
				("Nintendo Logo",   logo_str),
				("Header Checksum", header_checksum_str),
				("Save Type",       savelib_str),
			]
			if "agb_save_flash_id" in di and di["agb_save_flash_id"] is not None:
				chip_id, chip_name = di["agb_save_flash_id"]
				parsed_fields.append(("Save Flash Chip", f"{chip_name} (0x{chip_id:04X})"))
			if "eeprom_data" in di:
				eeprom_hex = ''.join(f"{x:02X}" for x in di["eeprom_data"])
				parsed_fields.append(("EEPROM area", f"{eeprom_hex}"))
			lines += cls._section_lines("Parsed Data", parsed_fields)

			if cart_type_str == "Vast Fame":
				lines += cls._section_lines("Vast Fame Protection Information", [
					("Address Reordering", str(di.get("vf_addr_reorder", "N/A"))),
					("Value Reordering",   str(di.get("vf_value_reorder", "N/A"))),
				], col=21)

		if header["db"] is not None and header["db"]["rc"] == di["hash_crc32"]:
			lines += cls._section_lines("Database Match", cls._database_fields(header["db"], mode))
		if "sintax_binary_log" in di:
			log = di["sintax_binary_log"]
			lines += cls._section_lines("Sintax YJencrypted Binary Unlock Log File Information", [
				("File Name", os.path.basename(log["file_name"])),
				("File Size", f"{Formatter.file_size(log['file_size'], space=' ', localized=False)} ({log['file_size']} bytes)"),
				("CRC32", f"{log['hash_crc32']:08x}"),
				("MD5", log["hash_md5"]), ("SHA-1", log["hash_sha1"]), ("SHA-256", log["hash_sha256"]),
			])
			lines += cls._section_lines("Sintax YJencrypted Trap Areas", [])
			for offset in di["sintax_traps"][0]: lines.append(f"* Trap Offset 0x{offset:08X} (2 bytes)")
			for address, length in di["sintax_traps"][1]: lines.append(f"* Trap Region 0x{address:08X}–0x{address + length - 1:08X} ({length} bytes)")
		return cls._render(lines)
