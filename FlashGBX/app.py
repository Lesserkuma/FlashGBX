# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import platform, importlib, re, sys

class AppInfo:
	NAME = "FlashGBX"
	VERSION_PEP440 = "5.1"
	VERSION = "v{:s}".format(VERSION_PEP440)
	VERSION_TIMESTAMP = 1788008809

	@classmethod
	def os_string(cls) -> str:
		if platform.system() != "Windows":
			return platform.platform()

		try:
			w = sys.getwindowsversion()
			if w.major == 10 and w.build >= 22000:
				name = "Windows 11"
			elif w.major == 10:
				name = "Windows 10"
			elif w.major == 6 and w.minor == 3:
				name = "Windows 8.1"
			elif w.major == 6 and w.minor == 2:
				name = "Windows 8"
			elif w.major == 6 and w.minor == 1:
				name = "Windows 7"
			elif w.major == 6 and w.minor == 0:
				name = "Windows Vista"
			elif w.major == 5 and w.minor == 1:
				name = "Windows XP"
			else:
				name = f"Windows {w.major}.{w.minor}"

			display_version = None
			ubr = None
			try:
				import winreg
				with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion") as key:
					try:
						product_name = winreg.QueryValueEx(key, "ProductName")[0]
						# Keep build-based naming for 10/11 to avoid compatibility-masked ProductName values.
						if w.major != 10 and isinstance(product_name, str) and product_name.startswith("Windows "):
							parts = product_name.split(" ")
							if len(parts) >= 2:
								name = " ".join(parts[:2])
					except:
						pass
					try:
						display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]
					except:
						try:
							display_version = winreg.QueryValueEx(key, "ReleaseId")[0]
						except:
							pass
					try:
						ubr = int(winreg.QueryValueEx(key, "UBR")[0])
					except:
						pass
			except:
				pass

			build_str = f"{w.build}.{ubr}" if ubr is not None else f"{w.build}"
			if display_version:
				return f"{name} (Version {display_version}, Build {build_str})"
			return f"{name} (Build {build_str})"
		except:
			release = platform.release()
			version = platform.version()
			if release:
				return f"Windows {release} ({version})"
			return platform.platform()

class AppContext:
	DEBUG = False
	APP_PATH = ""
	CONFIG_PATH = ""
	LAUNCH_TIMESTAMP = 0
	DEBUG_LOG: list = []
	PRINT_LOG: list = []

def generate_filename(mode, header, settings=None):
	from .Mapper import get_mbc_name
	fe_ni = True
	if settings is not None:
		fe_ni = settings.value(key="UseNoIntroFilenames", default="enabled").lower() == "enabled"

	path = "ROM"
	path_extension = "bin"
	
	if mode == "DMG":
		path_title = header["game_title"]
		path_code = ""
		path_revision = str(header["version"])
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
				if "gbmem_parsed" in header and "cart_id" in header["gbmem_parsed"]	and header["gbmem_parsed"]["cart_id"] is not None:
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

	if fe_ni and header.get("db") is not None:
		if mode == "DMG" and get_mbc_name(header["mapper_raw"]) == "G-MMC1" and "gbmem_parsed" in header:
			if (isinstance(header["gbmem_parsed"], list)):
				path = "NP GB-Memory Cartridge ({:s}).{:s}".format(header["gbmem_parsed"][0]["cart_id"], path_extension)
			else:
				path = "NP GB-Memory Cartridge ({:s}).{:s}".format(header["gbmem_parsed"]["cart_id"], path_extension)
		else:
			path = "{:s} {:s}.{:s}".format(header["db"]["gn"], header["db"]["ne"], path_extension)

	return path

# Hardware device backends
_hw_devices = []
HW_DEVICE_MODULES = [ "hw_GBxCartRW", "hw_GBFlash", "hw_JoeyJr", "hw_GameBub" ]
for _name in HW_DEVICE_MODULES:
	try:
		_hw_devices.append(importlib.import_module(f"{__package__}.{_name}"))
	except Exception:
		pass
HW_DEVICES = _hw_devices
