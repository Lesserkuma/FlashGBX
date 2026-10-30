# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import os, configparser
from io import StringIO

from .i18n import __
from .Logging import dprint

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
				print(__("Can’t access the configuration directory or settings file."))
				return
			self.FILENAME = path
			self.SETTINGS = configparser.RawConfigParser()
			self.SETTINGS.optionxform = str
			try:
				self.reload()
			except configparser.MissingSectionHeaderError:
				print(__("Resetting invalid settings file..."))
				with open(path, "w+", encoding="UTF-8") as f: f.close()
				path = ""

		if path == "":
			self.FILENAME = False
			self.SETTINGS = configparser.RawConfigParser()
			self.SETTINGS.read_string(ini)
			self.SETTINGS.optionxform = str

		self.MAIN_SECTION = main_section

	def reload(self):
		if self.SETTINGS is None: return
		if self.FILENAME is not False:
			settings = configparser.RawConfigParser()
			settings.optionxform = str
			with open(self.FILENAME, "r", encoding="UTF-8") as f:
				settings.read_file(f)
			self.SETTINGS = settings
		if not self.SETTINGS.has_section(self.MAIN_SECTION):
			self.SETTINGS.add_section(self.MAIN_SECTION)

	def value(self, key, default=None):
		if self.SETTINGS is None: return None
		self.reload()
		if key not in self.SETTINGS[self.MAIN_SECTION]:
			if default is not None: self.setValue(key, default)
			return default
		return (self.SETTINGS[self.MAIN_SECTION][key])

	def setValue(self, key, value, quiet=False):
		if self.SETTINGS is None: return None
		self.reload()
		if value is None:
			if key in self.SETTINGS[self.MAIN_SECTION]:
				del(self.SETTINGS[self.MAIN_SECTION][key])
		else:
			self.SETTINGS[self.MAIN_SECTION][key] = value
		if not quiet: dprint("Updating settings:", key, "=", value)
		if self.FILENAME is not False:
			with open(self.FILENAME, "w", encoding="UTF-8") as f:
				self.SETTINGS.write(f)

	def clear(self):
		if self.SETTINGS is None: return None
		self.SETTINGS.clear()
		if self.FILENAME is not False:
			with open(self.FILENAME, "w", encoding="UTF-8") as f:
				self.SETTINGS.write(f)

	def get_string(self):
		output = StringIO()
		self.SETTINGS.write(output)
		return output.getvalue()

	# Legacy PascalCase aliases — drop in a follow-up consumer sweep.
	def Reload(self): return self.reload()
	def GetValue(self, key, default=None): return self.value(key, default)
	def SetValue(self, key, value, quiet=False): return self.setValue(key, value, quiet)
	def Clear(self): return self.clear()
	def GetString(self): return self.get_string()
