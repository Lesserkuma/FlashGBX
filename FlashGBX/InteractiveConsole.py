# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import os, re, shlex
from .i18n import __

class InteractiveConsole:
	def __init__(self, conn, on_output, on_error=None):
		self.CONN = conn
		self.MODE = conn.GetMode()
		self.on_output = on_output
		self.on_error = on_error if on_error is not None else on_output
		self.last_read_data = None

	def get_help_lines(self):
		lines = []
		lines.append(__("Interactive Console") + " – " + __("Commands:"))
		lines.append("  r <addr> <size>               " + __("Read from ROM region"))
		lines.append("  s <filepath>                  " + __("Save last read data to file"))
		lines.append("  w <addr> <value>              " + __("Write to ROM region (e.g. mapper registers)"))
		if self.MODE == "AGB":
			lines.append("  rs <addr> <size>              " + __("Read from SRAM or FLASH save region"))
			lines.append("  ws <addr> <value>             " + __("Write to SRAM or FLASH save region"))
			lines.append("  wf <addr> <value>             " + __("Send commands to FLASH save chip"))
			lines.append("  re <4|64> <addr> <size>       " + __("Read from EEPROM save region"))
			lines.append("  we <4|64> <addr> <data>       " + __("Write to EEPROM save region"))
		if self.CONN.CanPowerCycleCart():
			lines.append("  on                            " + __("Cartridge Power On"))
			lines.append("  off                           " + __("Cartridge Power Off"))
		lines.append("  h                             " + __("Show this help"))
		lines.append("  q                             " + __("Quit interactive console"))
		lines.append("")
		lines.append("  " + __("Multiple commands can be entered on one line, separated by commas."))
		lines.append("  " + __("All addresses, sizes and values are hexadecimal."))
		lines.append("")
		return lines

	def print_help(self):
		for line in self.get_help_lines():
			self.on_output(line)

	def hexdump(self, base_addr, data):
		if isinstance(data, int):
			data = bytearray([data])
		for offset in range(0, len(data), 16):
			chunk = data[offset:offset + 16]
			hex_part = " ".join("{:02x}".format(b) for b in chunk)
			ascii_part = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
			self.on_output("{:08x}: {:<47}  {:s}".format(base_addr + offset, hex_part, ascii_part))

	def execute_line(self, line):
		cmds = [c.strip() for c in line.split(",") if c.strip()]
		for cmdline in cmds:
			if not self.execute_command(cmdline):
				return False
		return True

	def execute_command(self, cmdline):
		try:
			return self._execute_command_inner(cmdline)
		except Exception:
			return False

	def _execute_command_inner(self, cmdline):
		try:
			parts = shlex.split(cmdline)
		except ValueError:
			self.on_output(__("Invalid command syntax."))
			return True
		if not parts:
			return True
		command = parts[0].lower()

		if command == "q":
			return False

		if command == "h":
			self.print_help()
			return True

		if command == "w" and len(parts) == 3:
			try:
				address = int(parts[1], 16)
				if re.fullmatch(r"[01]{8}|[01]{16}", parts[2]):
					value = int(parts[2], 2)
				else:
					value = int(parts[2], 16)
			except ValueError:
				self.on_output(__("Invalid input. Use hexadecimal or 8/16-bit binary for the value."))
				return True
			self.CONN._cart_write(address, value, sram=True if self.MODE == "DMG" and 0xA000 <= address < 0xC000 else False)
			self.on_output(__("OK"))
			return True

		if command == "r" and len(parts) == 3:
			try:
				address = int(parts[1], 16)
				size = int(parts[2], 16)
			except ValueError:
				self.on_output(__("Invalid hexadecimal input."))
				return True
			if size == 0: 
				return True
			_raw = self.CONN._cart_read(address, size)
			if _raw is False or (isinstance(_raw, bytearray) and len(_raw) == 0):
				self.on_error(__("ERROR"))
			else:
				data = bytearray(_raw)[:size]
				self.last_read_data = data
				self.hexdump(address, data)
			return True

		if command == "s" and len(parts) == 2:
			if self.last_read_data is None:
				self.on_output(__("No data available. Read data first with “r”, “rs” or “re”."))
				return True
			filepath = os.path.abspath(parts[1])
			if os.path.isdir(filepath):
				self.on_output(__("Invalid file path. Path is a directory."))
				return True
			dir_path = os.path.dirname(filepath)
			if dir_path and not os.path.exists(dir_path):
				self.on_output(__("Invalid file path. Directory does not exist."))
				return True
			backup_path = filepath + ".bak"
			try:
				if os.path.exists(filepath):
					if os.path.exists(backup_path):
						os.remove(backup_path)
					os.replace(filepath, backup_path)
				with open(filepath, "wb") as fh:
					fh.write(self.last_read_data)
			except OSError as e:
				self.on_error(__("Failed to save file: {error}", error=str(e)))
				return True
			self.on_output(__("Saved to {filepath}", filepath=filepath))
			return True

		if self.MODE == "AGB":
			if command == "rs" and len(parts) == 3:
				try:
					address = int(parts[1], 16)
					size = int(parts[2], 16)
				except ValueError:
					self.on_output(__("Invalid hexadecimal input."))
					return True
				if size == 0: 
					return True
				_raw = self.CONN._cart_read(address, size, agb_save_flash=True)
				if _raw is False or (isinstance(_raw, bytearray) and len(_raw) == 0):
					self.on_error(__("ERROR"))
				else:
					data = bytearray(_raw)[:size]
					self.last_read_data = data
					self.hexdump(address, data)
				return True

			if command == "ws" and len(parts) == 3:
				try:
					address = int(parts[1], 16)
					if re.fullmatch(r"[01]{8}", parts[2]):
						value = int(parts[2], 2)
					else:
						value = int(parts[2], 16)
				except ValueError:
					self.on_output(__("Invalid input. Use hexadecimal or 8-bit binary for the value."))
					return True
				self.CONN._cart_write(address, value, sram=True)
				self.on_output(__("OK"))
				return True

			if command == "wf" and len(parts) == 3:
				try:
					address = int(parts[1], 16)
					value = int(parts[2], 16)
				except ValueError:
					self.on_output(__("Invalid hexadecimal input."))
					return True
				self.CONN._cart_write_flash([[address, value]])
				self.on_output(__("OK"))
				return True

			if command == "re" and len(parts) == 4:
				if parts[1] not in ("4", "64"):
					self.on_output(__("EEPROM type must be 4 or 64."))
					return True
				eeprom_type = 2 if parts[1] == "64" else 1
				try:
					address = int(parts[2], 16)
					size = int(parts[3], 16)
				except ValueError:
					self.on_output(__("Invalid hexadecimal input."))
					return True
				if size % 8 != 0 or size == 0:
					self.on_output(__("EEPROM read requires size to be a multiple of 8 bytes."))
					return True
				self.CONN._set_fw_variable("TRANSFER_SIZE", size)
				self.CONN._set_fw_variable("ADDRESS", address // 8)  # EEPROM commands use address divided by 8
				cmd = bytearray([self.CONN.DEVICE_CMD["AGB_CART_READ_EEPROM"], eeprom_type])
				self.CONN._write(cmd)
				data = self.CONN._read(size)
				if data is False or (isinstance(data, bytearray) and len(data) == 0):
					self.on_error(__("ERROR"))
				else:
					self.last_read_data = bytearray(data)
					self.hexdump(address, data)
				return True

			if command == "we" and len(parts) == 4:
				if parts[1] not in ("4", "64"):
					self.on_output(__("EEPROM type must be 4 or 64."))
					return True
				eeprom_type = 2 if parts[1] == "64" else 1
				try:
					address = int(parts[2], 16)
					data = bytearray.fromhex(parts[3])
				except ValueError:
					self.on_output(__("Invalid input."))
					return True
				if len(data) == 0 or len(data) % 8 != 0:
					self.on_output(__("EEPROM write requires data length to be a multiple of 8 bytes."))
					return True
				self.CONN._set_fw_variable("TRANSFER_SIZE", len(data))
				self.CONN._set_fw_variable("ADDRESS", address // 8)  # EEPROM commands use address divided by 8
				cmd = bytearray([self.CONN.DEVICE_CMD["AGB_CART_WRITE_EEPROM"], eeprom_type])
				self.CONN._write(cmd)
				ack = self.CONN._write(data, wait=True)
				if ack is False:
					self.on_error(__("ERROR"))
				else:
					self.on_output(__("OK"))
				return True

		if command == "on":
			if not self.CONN.CanPowerCycleCart():
				self.on_output(__("This device does not support cartridge power control."))
				return True
			try:
				self.CONN.CartPowerOn()
				self.on_output(__("OK"))
			except Exception as e:
				self.on_error(__("ERROR") + ": " + str(e))
			return True

		if command == "off":
			if not self.CONN.CanPowerCycleCart():
				self.on_output(__("This device does not support cartridge power control."))
				return True
			try:
				self.CONN.CartPowerOff()
				self.on_output(__("OK"))
			except Exception as e:
				self.on_error(__("ERROR") + ": " + str(e))
			return True

		self.on_output(__("Unknown command. Type “h” for help."))
		return True
