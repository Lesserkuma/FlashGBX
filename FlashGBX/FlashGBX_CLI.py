# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import sys
import datetime, shutil, platform, os, math, traceback, re, time, serial, zipfile, zlib, hashlib, tempfile
from .i18n import __, c__, ___, format_decimal
try:
	# pylint: disable=import-error
	import readline
	readline.set_completer_delims('\t\n=')
	readline.parse_and_bind("tab:complete")
except:
	pass

from .RomFileDMG import RomFileDMG
from .RomFileAGB import RomFileAGB
from .PocketCamera import PocketCamera, PocketCameraCapture
from .Mapper import DMG_Mapper
from .app import AppInfo, AppContext, generate_filename, HW_DEVICES
from .Logging import ANSI, Logger
from .CartridgeTypes import RomSizes, AgbSaveTypes, DmgSaveTypes
from .InteractiveConsole import InteractiveConsole
from .EReader import EReader, EReaderScanWorker, ScanControl
from .Progress import Progress
from .Formatter import Formatter
from .Flashcart import empty_flashcarts_map, has_3v_compatible_profile
from .RomFileDMG import from_isx
from .IniSettings import IniSettings
from .Logging import dprint

class FlashGBX_CLI():
	ARGS = {}
	CONFIG_PATH = ""
	FLASHCARTS = empty_flashcarts_map()
	CONN = None
	DEVICE = None
	PROGRESS = None
	FWUPD_R = False
	INI = None
	RETVAL = 0
	# Shell convention: 128 + SIGINT (2) = 130; also used for EOF and explicit cancellation.
	EXIT_CANCELLED = 130

	def __init__(self, args):
		self.ARGS = args
		AppContext.APP_PATH = args['app_path']
		AppContext.CONFIG_PATH = args['config_path']
		self.FLASHCARTS = args["flashcarts"]
		self.PROGRESS = Progress(self.UpdateProgress, self.WaitProgress)

		global prog_bar_part_char
		if platform.system() == "Windows":
			prog_bar_part_char = [" ", " ", " ", " ", "▌", "▌", "▌", "▌"]
		else:
			prog_bar_part_char = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]

	def _GetPlatformName(self, mode):
		return {
			"DMG": __("Game Boy or Game Boy Color"),
			"AGB": __("Game Boy Advance"),
		}.get(mode, mode)

	def _GetAutoPlatformMode(self, conn, supported_modes=None):
		if supported_modes is None:
			supported_modes = conn.GetSupportedModes()
		if len(supported_modes) == 1:
			return supported_modes[0]
		if conn.FW.get("cart_mode_switch"):
			switch_mode = conn.GetCartModeSwitchState()
			if switch_mode is not False:
				mode = "AGB" if switch_mode == 1 else "DMG"
				if mode in supported_modes:
					return mode
		mode = conn.GetMode()
		if mode in supported_modes:
			return mode
		return None

	def run(self):
		self.RETVAL = 0
		try:
			return self.Run()
		except (KeyboardInterrupt, EOFError):
			print("\n\n" + __("Operation stopped."))
			self.RETVAL = self.EXIT_CANCELLED
			if self.CONN is not None:
				self.DisconnectDevice()
			return self.RETVAL

	def Run(self):
		sys.stdout = Logger()
		config_ret = self.ARGS["config_ret"]
		for i in range(0, len(config_ret)):
			if config_ret[i][0] < 1:
				print(config_ret[i][1])
			elif config_ret[i][0] == 1:
				print("{:s}{:s}{:s}".format(ANSI.YELLOW, config_ret[i][1], ANSI.RESET))
			elif config_ret[i][0] == 2:
				print("{:s}{:s}{:s}".format(ANSI.RED, config_ret[i][1], ANSI.RESET))

		args = self.ARGS["argparsed"]
		config_path = AppContext.CONFIG_PATH
		print(__("Configuration folder:") + " " + config_path + "\n")

		menu_items = [
			("info",             __("Read Cartridge Information")),
			("flash-info",       __("Read Flash Chip Information")),
			("backup-rom",       __("Backup ROM")),
			("flash-rom",        __("Write ROM")),
			("backup-save",      __("Backup Save Data")),
			("restore-save",     __("Restore Save Data")),
			("erase-save",       __("Erase Save Data")),
			("gbcamera-extract", __("Extract Game Boy Camera Pictures From Existing Save Data Backup")),
			("interactive",      __("Interactive Console")),
			("ereader-dump",     __("e-Reader Dot Code Dumper")),
			("gbcamera-live-image", __("Save Live Game Boy Camera Image")),
		]
		for hw_mod in HW_DEVICES:
			try:
				cls = hw_mod.GbxDevice
				dev = cls()
				action = dev.FirmwareUpdateAction()
				if dev.SupportsFirmwareUpdates() and action is not None:
					menu_items.append((action, __("Firmware Update for {device_name}", device_name=cls.DEVICE_LABEL_SHORT)))
			except Exception:
				pass

		fwupdate_actions = set()
		for hw_mod in HW_DEVICES:
			try:
				dev = hw_mod.GbxDevice()
				if dev.SupportsFirmwareUpdates():
					action = dev.FirmwareUpdateAction()
					if action is not None:
						fwupdate_actions.add(action)
			except Exception:
				pass

		# Ask interactively if no args set
		if args.action is None:
			self.ARGS["called_with_args"] = False
			print(__("Select Operation:"))
			for i, (_, label) in enumerate(menu_items, start=1):
				print(f"{i:>3d}) {label}")
			print()
			n = len(menu_items)
			args.action = input(__("Enter number ({range}) [{default}]:", range=f"1-{n}", default="1") + " ").lower().strip()
			try:
				if int(args.action) == 0:
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return self.RETVAL
				args.action = menu_items[int(args.action) - 1][0]
			except:
				if args.action == "":
					args.action = "info"
				else:
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return self.RETVAL
		else:
			self.ARGS["called_with_args"] = True

		if args.action == "ereader-dump" and args.mode not in (None, "agb"):
			print(ANSI.RED + __("The e-Reader Dot Code Dumper requires Game Boy Advance mode.") + ANSI.RESET)
			return 1
		if args.action == "gbcamera-live-image" and args.mode not in (None, "dmg"):
			print(ANSI.RED + __("Live Game Boy Camera capture requires Game Boy mode.") + ANSI.RESET)
			return 1

		if args.action is None or args.action not in ({"gbcamera-extract"} | fwupdate_actions):
			if not self.FindDevices(port=args.device_port, connect=True):
				if self.DEVICE is None:
					print(__("No devices found."))
				else:
					print(__("Couldn’t connect to the device."))
				return 1
			else:
				dev = self.DEVICE[1]
				builddate = dev.GetFWBuildDate()

				if dev.FirmwareUpdateAvailable() and dev.FW_UPDATE_REQ:
					if dev.FW_UPDATE_REQ == 2:
						print(__("Support for {device_name} devices has been discontinued. The last fully supported version is {appname} v{version}.", device_name=dev.GetFullName(), appname=AppInfo.NAME, version=dev.GetLastSupportedVersion()))
						print(__("More modern alternatives include GBFlash, Joey Jr and GBxCart RW v1.4."))
					else:
						print(__("The current firmware version of your device is not supported.\nPlease update to a supported firmware version first."))
					self.DisconnectDevice()
					return 1

				if builddate != "":
					print("\n" + __("Connected to {device_name}", device_name=dev.GetFullNameExtended(more=True)))
				else:
					print("\n" + __("Connected to {device_name}", device_name=dev.GetFullNameExtended(more=False)))

				self.CONN.SetAutoPowerOff(value=1500)
				self.CONN.SetAGBReadMethod(method=2)

		if args.action == "gbcamera-extract":
			if args.path == "auto":
				args.path = input(__("Enter file path of Game Boy Camera save data file:") + " ").strip().replace("\"", "")
				print("")
				if args.path == "":
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return self.RETVAL

			pc = PocketCamera()
			try:
				if pc.LoadFile(args.path) == False:
					print("\n" + ANSI.RED + __("Couldn’t parse the save data file.") + ANSI.RESET)
					return 1
				pc.SetPalette(PocketCamera.PALETTE_NAMES.index(args.gbcamera_palette))
				directory = os.path.splitext(args.path)[0]
				if os.path.isfile(directory):
					print("\n" + ANSI.RED + __("Can’t save pictures at location “{path}”.", path=os.path.abspath(directory)) + ANSI.RESET)
					return 1
				files = [os.path.join(directory, "IMG_PC{:02d}.{}".format(i, args.gbcamera_outfile_format)) for i in range(1, 33)]
				if not self._ConfirmCameraExport(files): return self.RETVAL
				if not os.path.isdir(directory):
					os.makedirs(directory)
				for i, file in enumerate(files):
					pc.ExportPicture(i, file, scale=1)
			except (OSError, ValueError, IndexError) as e:
				print("\n" + ANSI.RED + __("The pictures could not be extracted: {error}", error=str(e)) + ANSI.RESET)
				return 1
			print(__("The pictures from “{save_file}” were extracted to “{destination}”.", save_file=os.path.abspath(args.path), destination=os.path.abspath(directory) + os.sep + "IMG_PC**.{:s}".format(args.gbcamera_outfile_format)))
			return 0

		if args.action in fwupdate_actions:
			for hw_mod in HW_DEVICES:
				cls = hw_mod.GbxDevice
				dev = cls()
				action = dev.FirmwareUpdateAction()
				if dev.SupportsFirmwareUpdates() and action == args.action:
					method = getattr(self, dev.CLIUpdaterMethod())
					kwargs = {"port": args.device_port}
					method(**kwargs)
					return self.RETVAL

		if args.action == "gbcamera-live-image":
			try:
				return self.CaptureCameraImage(args)
			finally:
				self.DisconnectDevice()

		if args.action == "ereader-dump":
			try:
				retval = self.DumpEReader(args)
				print("")
				return retval
			finally:
				self.DisconnectDevice()

		if args.mode is None:
			supported_modes = self.CONN.GetSupportedModes()
			auto_mode = self._GetAutoPlatformMode(self.CONN, supported_modes)
			if len(supported_modes) == 0:
				print(__("The connected device does not support any platform modes.") + "\n")
				self.DisconnectDevice()
				return 1
			elif len(supported_modes) == 1:
				mode = auto_mode or supported_modes[0]
				print(__("Using only supported platform: {platform}", platform=mode) + "\n")
				args.mode = mode.lower()
			elif auto_mode is not None:
				if self.CONN.FW.get("cart_mode_switch"):
					print(__("Using platform mode set by cartridge mode switch: {platform}", platform=self._GetPlatformName(auto_mode)) + "\n")
				else:
					print(__("Using platform mode: {platform}", platform=self._GetPlatformName(auto_mode)) + "\n")
				args.mode = auto_mode.lower()
			else:
				print(
					__("Select Platform:") + "\n"
					"  1) " + __("Game Boy or Game Boy Color") + "\n"
					"  2) " + __("Game Boy Advance") + "\n"
				)
				answer = input(__("Enter number ({range}) [{default}]:", range="1-2", default="2") + " ").lower().strip()
				print("")
				if answer == "1":
					args.mode = "dmg"
				elif answer == "2" or answer == "":
					args.mode = "agb"
				else:
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					self.DisconnectDevice()
					return self.RETVAL
				print("")

		if args.mode == "dmg":
			print(__("Platform: {platform}", platform=__("Game Boy or Game Boy Color")))
			self.CONN.SetMode("DMG")
		else:
			print(__("Platform: {platform}", platform=__("Game Boy Advance")))
			self.CONN.SetMode("AGB")
		#time.sleep(0.2)

		if args.action == "interactive":
			try:
				self.InteractiveConsole()
			except (KeyboardInterrupt, EOFError):
				self.RETVAL = self.EXIT_CANCELLED
				print("\n\n" + __("Operation stopped."))
			self.DisconnectDevice()
			return self.RETVAL

		header = self.CONN.ReadHeader()
		(bad_read, s_header, header) = self.ReadCartridge(header)
		if s_header == "":
			print("\n" + ANSI.RED + __("Couldn’t read cartridge header. Please try again.") + ANSI.RESET + "\n")
			self.DisconnectDevice()
			return 1
		if bad_read and not args.ignore_bad_header and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and "mapper_raw" in header and header["mapper_raw"] != 0x203)):
			print("\n" + ANSI.RED + __("Invalid data was detected which usually means that the cartridge couldn’t be read correctly. Please make sure you selected the correct platform and that the cartridge contacts are clean. This check can be disabled with the command line switch “{switch}”.", switch="--ignore-bad-header") + ANSI.RESET + "\n")
			print(__("Cartridge Information:"))
			print(s_header)
			self.DisconnectDevice()
			return 1

		print("\n" + __("Cartridge Information:"))
		print(s_header)

		try:
			if args.action == "backup-rom":
				self.BackupROM(args, header)

			elif args.action == "backup-save":
				self.BackupRestoreRAM(args, header)

			elif args.action == "restore-save":
				if args.path == "auto":
					args.path = input(__("Enter file path of save data file:") + " ").strip().replace("\"", "")
					print("")
					if args.path == "":
						self.RETVAL = self.EXIT_CANCELLED
						print(__("Canceled."))
						self.DisconnectDevice()
						return self.RETVAL
				self.BackupRestoreRAM(args, header)

			elif args.action == "erase-save":
				self.BackupRestoreRAM(args, header)

			elif args.action == "debug-test-save":
				self.BackupRestoreRAM(args, header)

			elif args.action == "flash-rom":
				if args.path == "auto":
					args.path = input(__("Enter file path of ROM file:") + " ").strip().replace("\"", "")
					print("")
					if args.path == "":
						self.RETVAL = self.EXIT_CANCELLED
						print(__("Canceled."))
						self.DisconnectDevice()
						return self.RETVAL
				self.FlashROM(args, header)

			elif args.action == "flash-info":
				if self.DetectCartridge() in (-1, -2): self.RETVAL = 1

			if args.action != "info" and args.action != "flash-info":
				print("")

		except (KeyboardInterrupt, EOFError):
			self.RETVAL = self.EXIT_CANCELLED
			print("\n\n" + __("Operation stopped."))

		self.DisconnectDevice()
		return self.RETVAL

	def WaitProgress(self, args):
		if args["user_action"] == "REINSERT_CART":
			msg = "\n\n"
			msg += args["msg"]
			msg += "\n\n" + __("Press ENTER to continue.") + "\n"
			answer = input(msg).strip().lower()
			if len(answer.strip()) != 0:
				self.RETVAL = self.EXIT_CANCELLED
				self.CONN.USER_ANSWER = False
			else:
				self.CONN.USER_ANSWER = True
		elif args["user_action"] == "RETRY_5V":
			msg = "\n\n"
			msg += args["msg"]
			msg += "\n\n" + args["title"] + " [y/N] "
			answer = input(msg).strip().lower()
			self.CONN.USER_ANSWER = answer in ("y", "yes")
			if not self.CONN.USER_ANSWER:
				self.RETVAL = self.EXIT_CANCELLED

	def UpdateProgress(self, args):
		if args is None: return

		if "error" in args:
			print("{:s}{:s}{:s}".format(ANSI.RED, args["error"], ANSI.RESET))
			return

		pos = 0
		size = 0
		speed = 0
		elapsed = 0
		left = 0
		if "pos" in args: pos = args["pos"]
		if "size" in args: size = args["size"]
		if "speed" in args: speed = args["speed"]
		if "time_elapsed" in args: elapsed = args["time_elapsed"]
		if "time_left" in args: left = args["time_left"]

		if "action" in args:
			if args["action"] == "INITIALIZE":
				if args["method"] == "ROM_WRITE_VERIFY":
					print("\n\n" + __("The newly written ROM data will now be checked for errors.") + "\n")
				elif args["method"] == "SAVE_WRITE_VERIFY":
					print("\n\n" + __("The newly written save data will now be checked for errors.") + "\n")
			elif args["action"] == "ERASE":
				print(ANSI.CLEAR_LINE + __("Please wait while the flash chip is being erased... (Elapsed time: {elapsed_time})", elapsed_time=Formatter.progress_time(elapsed)), end="\r")
			elif args["action"] == "UNLOCK":
				print(ANSI.CLEAR_LINE + (args.get("text") or __("Please wait while the flash chip is being unlocked... (Elapsed time: {elapsed_time})", elapsed_time=Formatter.progress_time(elapsed))), end="\r", flush=True)
			elif args["action"] == "SECTOR_ERASE":
				print(ANSI.CLEAR_LINE + __("Erasing flash sector at address {address}...", address="0x{:X}".format(args["sector_pos"])), end="\r")
			elif args["action"] == "UPDATE_RTC":
				print("\n" + __("Updating Real Time Clock..."))
			elif args["action"] == "CALC_CHECKSUMS":
				pass
			elif args["action"] == "ERROR":
				print(ANSI.CLEAR_LINE + ANSI.RED + args["text"] + ANSI.RESET)
			elif args["action"] == "ABORTING":
				print("\n" + __("Stopping..."))
			elif args["action"] == "FINISHED":
				print("\n")
				self.FinishOperation()
			elif args["action"] == "ABORT":
				if args.get("from_user", False):
					self.RETVAL = self.EXIT_CANCELLED
				print("\n" + __("Operation stopped.") + "\n")
				if "info_type" in args.keys() and "info_msg" in args.keys():
					if args["info_type"] == "msgbox_critical":
						self.RETVAL = 1
						print(ANSI.RED + args["info_msg"] + ANSI.RESET)
					elif args["info_type"] == "msgbox_information":
						print(args["info_msg"])
					elif args["info_type"] == "label":
						print(args["info_msg"])
				return
			elif args["action"] == "PROGRESS":
				# pv style progress status
				prog_str = "{:s}/{:s} {:s} [{:s}{:s}] [{:s}] {:s}% {:s} {:s} ".format(Formatter.file_size(pos, space="", short=True).replace(" ", "").rjust(8), Formatter.file_size(size, space="", short=True).replace(" ", ""), Formatter.progress_time_short(elapsed), format_decimal(speed, precision=2).rjust(6), __(" KiB/s").replace(" ", ""), "%PROG_BAR%", "{:d}".format(int(pos/size*100)).rjust(3), c__("Estimated Time abbreviation (3 characters)", "ETA"), Formatter.progress_time_short(left))
				prog_width = shutil.get_terminal_size((80, 20))[0] - (len(prog_str) - 10)
				progress = min(1, max(0, pos/size))
				whole_width = math.floor(progress * prog_width)
				remainder_width = (progress * prog_width) % 1
				part_width = math.floor(remainder_width * 8)
				try:
					part_char = prog_bar_part_char[part_width]
					if (prog_width - whole_width - 1) < 0: part_char = ""
					prog_bar = "█" * whole_width + part_char + " " * (prog_width - whole_width - 1)
					print(prog_str.replace("%PROG_BAR%", prog_bar), end="\r")
				except UnicodeEncodeError:
					prog_bar = "#" * whole_width + " " * (prog_width - whole_width)
					print(prog_str.replace("%PROG_BAR%", prog_bar), end="\r", flush=True)
				except:
					pass

	def ShowROMBackupResult(self):
		if self.CONN.GetMode() == "DMG":
			print("CRC32: {:08x}".format(self.CONN.INFO["file_crc32"]))
			print("SHA-1: {:s}\n".format(self.CONN.INFO["file_sha1"]))
			if self.CONN.INFO["rom_checksum"] == self.CONN.INFO["rom_checksum_calc"]:
				print(ANSI.GREEN + __("The ROM backup is complete and the checksum was verified successfully!") + ANSI.RESET)
			elif ("DMG-MMSA-JPN" in self.ARGS["argparsed"].flashcart_type) or ("mapper_raw" in self.CONN.INFO and self.CONN.INFO["mapper_raw"] in (0x105, 0x202)):
				print(__("The ROM backup is complete!"))
			else:
				msg = __("The ROM was dumped, but the checksum is not correct.")
				if self.CONN.INFO["loop_detected"] is not False:
					msg += "\n" + __("A data loop was detected in the ROM backup at position {pos} ({size}). This may indicate a bad dump or overdump.", pos="0x{:X}".format(self.CONN.INFO["loop_detected"]), size=Formatter.file_size(self.CONN.INFO["loop_detected"], as_int=True))
				else:
					msg += "\n" + __("This may indicate a bad dump, however this can be normal for some reproduction cartridges, unlicensed games, prototypes, patched games and intentional overdumps.")
				print("{:s}{:s}{:s}".format(ANSI.YELLOW, msg, ANSI.RESET))
		elif self.CONN.GetMode() == "AGB":
			print("CRC32: {:08x}".format(self.CONN.INFO["file_crc32"]))
			print("SHA-1: {:s}\n".format(self.CONN.INFO["file_sha1"]))
			if "db" in self.CONN.INFO and self.CONN.INFO["db"] is not None:
				if self.CONN.INFO["db"]["rc"] == self.CONN.INFO["file_crc32"]:
					print(ANSI.GREEN + __("The ROM backup is complete and the checksum was verified successfully!") + ANSI.RESET)
				else:
					msg = __("The ROM backup is complete, but the checksum doesn’t match the known database entry.")
					if self.CONN.INFO["loop_detected"] is not False:
						msg += "\n" + __("A data loop was detected in the ROM backup at position {pos} ({size}). This may indicate a bad dump or overdump.", pos="0x{:X}".format(self.CONN.INFO["loop_detected"]), size=Formatter.file_size(self.CONN.INFO["loop_detected"], as_int=True))
					else:
						msg += "\n" + __("This may indicate a bad dump, however this can be normal for some reproduction cartridges, unlicensed games, prototypes, patched games and intentional overdumps.")
					print(ANSI.YELLOW + msg + ANSI.RESET)
			else:
				msg = __("The ROM backup is complete! As there is no known checksum for this ROM in the database, verification was skipped.")
				if self.CONN.INFO["loop_detected"] is not False:
					msg += "\n" + __("A data loop was detected in the ROM backup at position {pos} ({size}). This may indicate a bad dump or overdump.", pos="0x{:X}".format(self.CONN.INFO["loop_detected"]), size=Formatter.file_size(self.CONN.INFO["loop_detected"], as_int=True))
				print(ANSI.YELLOW + msg + ANSI.RESET)

	def _ConfirmCameraExport(self, files):
		if self.ARGS["argparsed"].overwrite or not any(os.path.exists(file) for file in files): return True
		print(__("There are already pictures that use the same file names. If you continue, these files will be overwritten."))
		answer = input(__("Do you want to continue?") + " [y/N]: ").strip().lower()
		print("")
		if answer == "y": return True
		self.RETVAL = self.EXIT_CANCELLED
		print(__("Canceled."))
		return False

	def FinishOperation(self):
		time_elapsed = None
		speed = None
		if "time_start" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["time_start"] > 0:
			time_elapsed = time.perf_counter() - self.PROGRESS.PROGRESS["time_start"]
			transfer_rate = (self.CONN.INFO["transferred"] / 1024.0) / time_elapsed
			if self.CONN.INFO["last_action"] == 1 and self.PROGRESS.PROGRESS.get("transfer_elapsed", 0) > 0:
				transfer_rate = self.PROGRESS.PROGRESS["speed"]
			speed = format_decimal(transfer_rate, precision=2) + __(" KiB/s")
			self.PROGRESS.PROGRESS["time_start"] = 0

		if self.CONN.INFO["last_action"] == 4: # Flash ROM
			self.CONN.INFO["last_action"] = 0
			if "verified" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["verified"] == True:
				print(ANSI.GREEN + __("The ROM was written and verified successfully!") + ANSI.RESET)
			else:
				if "broken_sectors" in self.CONN.INFO:
					s = ""
					sc = 0
					for sector in self.CONN.INFO["broken_sectors"]:
						sc += 1
						if sc > 10:
							s += c__("Shortened list of Broken Sectors (e.g. 0x0000~0x07FF and others)", "and others") + "  "
							break
						s += "0x{:X}~0x{:X}, ".format(sector[0], sector[0]+sector[1]-1)
					print(ANSI.RED + ___("The ROM was written completely, but verification of written data failed in the following sector: {sectors}.", "The ROM was written completely, but verification of written data failed in the following sectors: {sectors}.", n=sc, sectors=s[:-2]) + ANSI.RESET)
					self.RETVAL = 1
				else:
					print(__("ROM writing complete!"))

		elif self.CONN.INFO["last_action"] == 1: # Backup ROM
			self.CONN.INFO["last_action"] = 0
			dump_report = False
			dumpinfo_file = ""
			if self.ARGS["argparsed"].generate_dump_report is True:
				try:
					dump_report = self.CONN.GetDumpReport()
					if dump_report is not False:
						if time_elapsed is not None and speed is not None:
							dump_report = dump_report.replace("%TRANSFER_RATE%", "{:.2f}".format(transfer_rate) + " KiB/s")
							dump_report = dump_report.replace("%TIME_ELAPSED%", Formatter.progress_time(time_elapsed, localized=False))
						else:
							dump_report = dump_report.replace("%TRANSFER_RATE%", "N/A")
							dump_report = dump_report.replace("%TIME_ELAPSED%", "N/A")
						dumpinfo_file = os.path.splitext(self.CONN.INFO["last_path"])[0] + ".txt"
						if os.path.splitext(self.CONN.INFO["last_path"])[1].lower() == ".txt": dumpinfo_file = self.CONN.INFO["last_path"] + ".txt"
						with open(dumpinfo_file, "wb") as f:
							f.write(bytearray([ 0xEF, 0xBB, 0xBF ])) # UTF-8 BOM
							f.write(dump_report.encode("UTF-8"))
				except Exception as e:
					print(__("Error:") + " " + str(e))

			self.ShowROMBackupResult()

		elif self.CONN.INFO["last_action"] == 2: # Backup RAM
			self.CONN.INFO["last_action"] = 0
			if not "debug" in self.ARGS and self.CONN.GetMode() == "DMG" and self.CONN.INFO["mapper_raw"] == 252 and self.CONN.INFO["transferred"] == 0x20000 or (self.CONN.INFO["transferred"] == 0x100000 and "ram_size_raw" in self.CONN.INFO["dump_info"]["header"] and self.CONN.INFO["dump_info"]["header"]["ram_size_raw"] == 0x204):
				if getattr(self.ARGS["argparsed"], "gbcamera_extract", False):
					base = os.path.splitext(self.CONN.INFO["last_path"])[0]
					if self.CONN.INFO["transferred"] == 0x100000:
						files = [os.path.join(base, "IMG_P{:1d}{:02d}.{}".format(roll, i, self.ARGS["argparsed"].gbcamera_outfile_format)) for roll in range(1, 9) for i in range(32)]
					else:
						files = [os.path.join(base, "IMG_PC{:02d}.{}".format(i, self.ARGS["argparsed"].gbcamera_outfile_format)) for i in range(32)]
					if not self._ConfirmCameraExport(files): return
					if self.CONN.INFO["transferred"] == 0x100000:
						if os.path.isfile(base):
							print(__("Can’t save pictures at location “{path}”.", path=os.path.abspath(base)))
							self.RETVAL = 1
							return
						if not os.path.isdir(base):
							os.makedirs(base)
						pc = PocketCamera()
						for roll in range(1, 9):
							with open(self.CONN.INFO["last_path"], "rb") as f:
								f.seek(0x20000 * (roll - 1))
								roll_data = bytearray(f.read(0x20000))
							if pc.LoadFile(roll_data) != False:
								pc.SetPalette(PocketCamera.PALETTE_NAMES.index(self.ARGS["argparsed"].gbcamera_palette))
								for i, file in enumerate(files[(roll - 1) * 32:roll * 32]):
									pc.ExportPicture(i, file, scale=1)
					else:
						file = self.CONN.INFO["last_path"]
						pc = PocketCamera()
						if pc.LoadFile(file) != False:
							pc.SetPalette(PocketCamera.PALETTE_NAMES.index(self.ARGS["argparsed"].gbcamera_palette))
							if os.path.isfile(base):
								print(__("Can’t save pictures at location “{path}”.", path=os.path.abspath(base)))
								self.RETVAL = 1
								return
							if not os.path.isdir(base):
								os.makedirs(base)
							for i, file in enumerate(files):
								pc.ExportPicture(i, file, scale=1)
					print(__("The pictures were extracted."))
				print("")

			print(__("The save data backup is complete!"))

		elif self.CONN.INFO["last_action"] == 3: # Restore RAM
			self.CONN.INFO["last_action"] = 0
			if "save_erase" in self.CONN.INFO and self.CONN.INFO["save_erase"]:
				print(__("The save data was erased."))
				del(self.CONN.INFO["save_erase"])
			else:
				print(__("The save data was restored!"))

		else:
			self.CONN.INFO["last_action"] = 0

	def FindDevices(self, port=None, connect=False):
		self.DEVICE = None
		for hw_device in HW_DEVICES:
			dev = hw_device.GbxDevice()
			keep_connection = False
			try:
				if hasattr(dev, "SetFlowControl"):
					dev.SetFlowControl(self.ARGS["argparsed"].device_flow_control)
				ret = dev.Initialize(self.FLASHCARTS, port=port, max_baud=1000000 if self.ARGS["argparsed"].device_limit_baudrate else 2000000)
				if ret is False:
					self.CONN = None
				elif isinstance(ret, list):
					if len(ret) > 0: print("")
					for i in range(0, len(ret)):
						status = ret[i][0]
						msg = re.sub('<[^<]+?>', '', ret[i][1])
						if status == 3:
							print(ANSI.RED + msg.replace("\n\n", "\n") + ANSI.RESET)
							self.CONN = None

				if dev.IsConnected():
					self.DEVICE = (dev.GetFullNameExtended(), dev)
					if connect:
						keep_connection = self.ConnectDevice(connection_messages=ret)
						return keep_connection
					break
			finally:
				connection = dev.DEVICE
				if connection is not None and not keep_connection:
					try:
						dev.Close()
					finally:
						connection.close()
						if self.CONN is dev: self.CONN = None

		if self.DEVICE is None: return False
		return True

	def ConnectDevice(self, connection_messages=None):
		dev = self.DEVICE[1]
		port = dev.GetPort()
		if hasattr(dev, "SetFlowControl"):
			dev.SetFlowControl(self.ARGS["argparsed"].device_flow_control)
		if connection_messages is not None and dev.IsConnected():
			ret = connection_messages
		else:
			ret = dev.Initialize(self.FLASHCARTS, port=port, max_baud=1000000 if self.ARGS["argparsed"].device_limit_baudrate else 2000000)

		if ret is False:
			print("\n" + ANSI.RED + __("An error occured while trying to connect to the device.") + ANSI.RESET)
			traceback.print_stack()
			self.CONN = None
			return False

		elif isinstance(ret, list):
			for i in range(0, len(ret)):
				status = ret[i][0]
				msg = re.sub('<[^<]+?>', '', ret[i][1])
				if status == 0:
					print("\n" + msg)
				elif status == 1:
					print("{:s}".format(msg))
				elif status == 2:
					print(ANSI.YELLOW + msg + ANSI.RESET)
				elif status == 3:
					print(ANSI.RED + msg + ANSI.RESET)
					self.CONN = None
					return False

		if dev.FW_UPDATE_REQ is True:
			print(ANSI.RED + __("A firmware update for your {device_name} is required to fully use this software.", device_name=dev.GetFullName()) + "\n" + ANSI.YELLOW + __("Current firmware version: {fw_version}", fw_version=dev.GetFirmwareVersion()) + ANSI.RESET)
			time.sleep(5)

		self.CONN = dev
		settings = IniSettings(path=AppContext.CONFIG_PATH + os.sep + "settings.ini")
		if (self.CONN.GetName() == "GBFlash" and dev.USB_MODE == dev.USBMode.CH340
			and dev.FW.get("cfw_id") == "L" and dev.FW.get("fw_ver", 0) >= 16
			and sys.stdin is not None and sys.stdin.isatty()
			and settings.value("SkipGBFlashCDCModePrompt", default="disabled") != "enabled"):
			print(
				"\n" + __("Your GBFlash is currently using CH340 mode.") + "\n"
				+ __("CDC mode provides faster data transfers, so ROM backups and other transfers take less time.") + "\n"
				+ (__("On Linux, CDC mode uses a different USB VID/PID combination (16C0:27DD), which may also need to be whitelisted. See the README for more information.") + "\n" if platform.system() == "Linux" else "")
				+ __("If anything does not work as expected, a short press of the U22 button on your GBFlash lets you switch between CDC and CH340 mode at any time.")
			)
			answer = input(__("Would you like to switch to the new CDC mode now?") + " [Y/n] ").strip().lower()
			if answer != "n":
				try:
					success = dev.ChangeUSBMode(dev.USBMode.CDC)
				except (OSError, serial.SerialException, RuntimeError) as e:
					dprint("Could not change GBFlash USB mode:", e)
					success = False
				if not success:
					print(ANSI.YELLOW + __("Could not switch the GBFlash USB mode. Please reconnect the device and try again.") + ANSI.RESET)
					self.CONN = None
					return False
			settings.setValue("SkipGBFlashCDCModePrompt", "enabled")
		return True

	def InteractiveConsole(self):
		self.CONN.SetAutoPowerOff(value=0)
		self.CONN.CartPowerOn()

		im = InteractiveConsole(
			self.CONN,
			on_output=print,
			on_error=lambda text: print(ANSI.RED + text + ANSI.RESET),
		)

		print("")
		im.print_help()
		print("")

		while True:
			print("> ", end="", flush=True)
			try:
				line = input().strip()
			except EOFError:
				self.RETVAL = self.EXIT_CANCELLED
				break
			if not line:
				continue
			if not im.execute_line(line):
				break

	def CaptureCameraImage(self, args):
		camera = None
		try:
			if "DMG" not in self.CONN.GetSupportedModes():
				raise RuntimeError(__("Live Game Boy Camera capture requires Game Boy mode."))
			path = args.path
			name = "IMG_PC." + args.gbcamera_outfile_format
			if path == "auto": path = name
			elif os.path.isdir(path): path = os.path.join(path, name)
			else: path = os.path.splitext(path)[0] + "." + args.gbcamera_outfile_format
			path = os.path.abspath(path)
			if not os.path.isdir(os.path.dirname(path)):
				raise OSError(__("The output directory must already exist."))
			if not args.overwrite and os.path.exists(path):
				answer = input(__("The target file “{file_path}” already exists.\nDo you want to overwrite it?", file_path=path) + " [y/N]: ").strip().lower()
				print("")
				if answer != "y":
					print(__("Canceled."))
					return self.EXIT_CANCELLED
			self.CONN.SetMode("DMG")
			print(__("Calibrating Game Boy Camera exposure..."), flush=True)
			camera = PocketCameraCapture(self.CONN)
			with camera:
				for _ in range(60):
					image = camera.Capture()
					if camera.EXPOSURE == camera.USED_EXPOSURE: break
				if not 35 <= camera.LEVEL <= 37:
					print(ANSI.YELLOW + __("Automatic exposure did not reach the target range. Calibration will continue during capture.") + ANSI.RESET)
				print(__("Continuously updating the live Game Boy Camera image at “{path}”.", path=path) + " " + __("Press Ctrl+C to stop."), flush=True)
				palette = PocketCamera.PALETTES[PocketCamera.PALETTE_NAMES.index(args.gbcamera_palette)]
				fps_start, fps_frames = time.monotonic(), 0
				images_taken, framerate = 0, 0.0
				def print_status():
					print("\r" + ANSI.CLEAR_LINE + __("Images taken: {count}, Framerate: {framerate} fps", count=images_taken, framerate=format_decimal(framerate, precision=1)), end="", flush=True)
				print_status()
				while True:
					images_taken += 1
					image.putpalette(palette)
					# Stage beside the destination so replacement stays on the same filesystem.
					with tempfile.NamedTemporaryFile(dir=os.path.dirname(path), prefix=".IMG_PC_", suffix="." + args.gbcamera_outfile_format, delete=False) as temporary:
						staged_path = temporary.name
					try:
						PocketCamera.ExportImage(image, staged_path, scale=1)
						try:
							os.replace(staged_path, path)
							fps_frames += 1
						except PermissionError as error:
							# Windows readers may briefly prevent replacement; try the next frame.
							if getattr(error, "winerror", None) not in (32, 33): raise
					finally:
						if os.path.exists(staged_path): os.unlink(staged_path)
					now = time.monotonic()
					if now - fps_start >= 1:
						framerate = fps_frames / (now - fps_start)
						fps_start, fps_frames = now, 0
					print_status()
					image = camera.Capture()
		except (KeyboardInterrupt, EOFError):
			if camera is not None: camera.Abort()
			print("\n" + __("Operation stopped."))
			return self.EXIT_CANCELLED
		except Exception as error:
			if camera is not None: camera.Abort()
			print("\n" + ANSI.RED + __("Error:") + " " + str(error) + ANSI.RESET)
			return 1

	def DumpEReader(self, args):
		try:
			if args.mode not in (None, "agb"):
				print(ANSI.RED + __("The e-Reader Dot Code Dumper requires Game Boy Advance mode.") + ANSI.RESET)
				return 1
			if "AGB" not in self.CONN.GetSupportedModes():
				print(ANSI.RED + __("This device does not support e-Reader scanning.") + ANSI.RESET)
				return 1
			if (self.CONN.FW or {}).get("fw_ver", 0) < 16 or not self.CONN.IsClkConnected():
				print(ANSI.RED + __("The e-Reader Dot Code Dumper requires firmware L16 or newer and a connected CLK pin.") + ANSI.RESET)
				return 1
			args.mode = "agb"
			self.CONN.SetMode("AGB")
			header = self.CONN.ReadHeader(checkRtc=False)
			if (not isinstance(header, dict) or header.get("game_code") not in ("PSAE", "PSAJ")
					or header.get("logo_correct") is not True or header.get("header_checksum_correct") is not True):
				print(ANSI.RED + __("No compatible e-Reader cartridge was detected.") + ANSI.RESET)
				return 1

			values = {key:getattr(args, "ereader_" + key, None) for key in ScanControl.RANGES}
			automatic = not any(value is not None for value in values.values())
			if values["threshold_factor"] is None: values["threshold_factor"] = 56
			control = ScanControl(auto_calibration=automatic, **values)
			factory = None
			factory_path = getattr(args, "ereader_factory_data", None)
			if factory_path is not None:
				with open(factory_path, "rb") as file:
					factory = EReader().ExtractFactoryCalibration(file.read())
				if factory is False:
					print(ANSI.RED + __("No valid e-Reader factory calibration found.") + ANSI.RESET)
					return 1

			path = args.path
			directory = os.getcwd()
			if path != "auto" and os.path.isdir(path):
				directory = os.path.abspath(path)
				path = "auto"
			if path != "auto":
				if not path:
					print(ANSI.RED + __("Please specify a path for saving the Dot Code.") + ANSI.RESET)
					return 1
				if os.path.splitext(path)[1].lower() != ".raw": path = os.path.splitext(path)[0] + ".raw"
				path = os.path.abspath(path)
				if not os.path.isdir(os.path.dirname(path)):
					print(ANSI.RED + __("The output directory must already exist.") + ANSI.RESET)
					return 1

			print(__("Platform: {platform}", platform=__("Game Boy Advance")))
			print("\n" + __("e-Reader Dot Code Dumper"))
			if automatic:
				print(__("Place the card so that the Dot Code strip is centered in the e-Reader.") + "\n" + __("Do not move the card during calibration."))
			else:
				print(__("Automatic calibration is disabled. Unspecified values use the factory calibration."))
			print(__("After calibration, move the card to the left and right until the scan is complete.") + " " + __("Press Ctrl+C to stop.") + "\n")
			raw = self.ScanEReader(factory, control)
			if raw is False:
				return self.EXIT_CANCELLED if self.EREADER_READER.CANCEL_REQUESTED and not self.EREADER_READER.ERROR else 1
			if path == "auto":
				path = os.path.join(directory, self.EREADER_READER.GetFileName(raw))
			overwrite = args.overwrite
			if os.path.lexists(path) and not overwrite:
				print(__("The target file “{file_path}” already exists.\nDo you want to overwrite it?", file_path=path))
				if input("[y/N] ").strip().lower() not in ("y", "yes"):
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return self.RETVAL
				overwrite = True
			if not self.EREADER_READER.SaveRaw(raw, path, overwrite=overwrite):
				print(ANSI.RED + __("Invalid e-Reader Dot Code data") + ANSI.RESET)
				return 1
			print("\n" + __("The Dot Code was saved to “{path}”.", path=os.path.abspath(path)))
			print("\nCRC32: {:08x}".format(zlib.crc32(raw)))
			print("SHA-1: {:s}\n".format(hashlib.sha1(raw).hexdigest()))
			print(ANSI.GREEN + __("The e-Reader Dot Code backup is complete and the checksum was verified successfully!") + ANSI.RESET)
			if args.generate_dump_report:
				try:
					if self.EREADER_READER.SaveDumpReport(raw, path) is False:
						dprint("No scan information is available for the dump report.")
				except Exception as e:
					print(__("Dump Report Error:") + " " + str(e))
			return 0
		except (KeyboardInterrupt, EOFError):
			print("\n" + __("Operation stopped."))
			return self.EXIT_CANCELLED
		except Exception as e:
			dprint(traceback.format_exc())
			print("\n" + ANSI.RED + str(e) + ANSI.RESET)
			return 1

	def ScanEReader(self, factory, control):
		# Only the worker communicates with the device. Terminal output stays on the main thread.
		state = {"status":None, "raw":None, "error":None, "stopped":False}
		worker = EReaderScanWorker(self.CONN, factory, control,
			on_status=lambda status: state.update(status=status),
			on_completed=lambda raw: state.update(raw=raw),
			on_stopped=lambda: state.update(stopped=True),
			on_failed=lambda message, disconnected: state.update(error=message),
			on_warning=lambda message: print("\n" + ANSI.YELLOW + message + ANSI.RESET, flush=True))
		self.EREADER_READER = worker.READER
		stream = sys.__stdout__ if isinstance(sys.stdout, Logger) else sys.stdout
		in_place = getattr(stream, "isatty", lambda: False)()
		last_line, last_width, last_update = None, 0, 0

		def Redraw(force=False):
			nonlocal last_line, last_width, last_update
			status = state["status"]
			line = __("Initializing...")
			if status is not None:
				values = dict(status)
				values["status"] = __(status["status"])
				values["bar"] = "[" + "".join(EReader.BLOCK_SYMBOLS[item] for item in status["block_states"]) + "]"
				values["mode"] = "AUTO" if status["auto_calibration"] else "MAN"
				values["factor"] = status["active_factor"] if status["active_factor"] is not None else control.Get()["threshold_factor"]
				values["framerate"] = format_decimal(status["framerate"], precision=1)
				line = ("{status} {bar} {blocks_confirmed}/{block_count} | {framerate} fps | "
					"{mode} B{sensor_brightness} V{vertical_offset} P{pwm} T{factor}").format(**values)
			now = time.monotonic()
			if not force and (line == last_line or now - last_update < (0.1 if in_place else 0.5)): return
			if in_place:
				print("\r" + line.ljust(last_width), end="\n" if force else "", flush=True)
				last_width = len(line)
			elif line != last_line:
				print(line, flush=True)
			last_line, last_update = line, now

		cancelled = False
		try:
			worker.start()
			while worker.is_alive():
				try:
					Redraw()
					time.sleep(0.02)
				except KeyboardInterrupt:
					worker.READER.Cancel()
					if not cancelled: print("\n" + __("Stopping..."))
					cancelled = True
		except KeyboardInterrupt:
			cancelled = True
			worker.READER.Cancel()
		finally:
			# Never close the connection while a scan or its cleanup is still running.
			# Avoid an interruptible join while the thread owns the serial connection.
			while worker.is_alive():
				worker.READER.Cancel()
				try:
					time.sleep(0.02)
				except KeyboardInterrupt:
					cancelled = True
			if worker.ident is not None: worker.join()
		Redraw(force=True)
		if state["error"] is not None:
			print(ANSI.RED + state["error"] + ANSI.RESET)
			return False
		if cancelled or state["stopped"]:
			worker.READER.Cancel()
			print(__("Operation stopped."))
			return False
		if state["raw"] is None:
			print(ANSI.RED + __("Scan ended without Dot Code data.") + ANSI.RESET)
			return False
		return state["raw"]

	def DisconnectDevice(self):
		try:
			devname = self.CONN.GetFullNameExtended()
			self.CONN.SetAutoPowerOff(value=0)
			self.CONN.Close(cartPowerOff=True)
			print(__("Disconnected from {device_name}", device_name=devname))
		except:
			pass
		self.CONN = None

	def ReadCartridge(self, data):
		bad_read = False
		s = ""
		if self.CONN.GetMode() == "DMG":
			# Use (label_with_colon, value) pairs to match existing GUI translation keys
			rows = []

			game_name = None
			if data["db"]:
				game_name = os.path.splitext(generate_filename(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=None))[0]
			if game_name is not None:
				rows.append((__("Game Name:"), game_name))

			rows.append((__("ROM Title:"), Formatter.title(data["game_title"])))

			if data["db"] is not None:
				rows.append((__("Game Code and Revision:"), "{:s}-{:s}".format(data["db"]["gc"], str(data["version"]))))
			elif len(data['game_code']) > 0:
				rows.append((__("Game Code and Revision:"), "{:s}-{:s}".format(data['game_code'], str(data["version"]))))
			else:
				rows.append((__("Revision:"), str(data["version"])))

			cgb = data.get("cgb", 0)
			sgb = data.get("sgb", 0)
			old_lic = data.get("old_lic", 0)
			if cgb == 0xC0:
				platform_str = __("Game Boy Color exclusive")
			elif cgb == 0x80:
				platform_str = __("Game Boy Color")
			elif old_lic == 0x33 and sgb == 0x03:
				platform_str = __("Super Game Boy")
			else:
				platform_str = __("Original Game Boy")
			rows.append((__("Platform:"), platform_str))

			rows.append((__("Real Time Clock:"), data["rtc_string"]))

			if data["logo_correct"] and data['header_checksum_correct']:
				rows.append((__("Boot Logo:"), c__("Game Data", "OK")))
				if not os.path.exists(AppContext.CONFIG_PATH + os.sep + "bootlogo_dmg.bin"):
					with open(AppContext.CONFIG_PATH + os.sep + "bootlogo_dmg.bin", "wb") as f:
						f.write(data['raw'][0x104:0x134])
			else:
				rows.append((__("Boot Logo:"), ANSI.RED + c__("Game Data", "Invalid") + ANSI.RESET))
				bad_read = True

			rows.append((__("ROM Checksum:"), "0x{:04X}".format(data['rom_checksum'])))

			try:
				rows.append((__("ROM Size:"), RomSizes().GetString(index=data['rom_size_raw'])))
			except:
				rows.append((__("ROM Size:"), ANSI.RED + c__("Game Data", "Not detected") + ANSI.RESET))
				bad_read = True

			try:
				if data['mapper_raw'] == 0x06: # MBC2
					save_type_str = DmgSaveTypes(index=1).GetString()
				elif data['mapper_raw'] == 0x22 and data["game_title"] in ("KORO2 KIRBY", "KIRBY TNT"): # MBC7 Kirby
					save_type_str = DmgSaveTypes(mbc=0x101).GetString()
				elif data['mapper_raw'] == 0x22 and data["game_title"] in ("CMASTER"): # MBC7 Command Master
					save_type_str = DmgSaveTypes(mbc=0x102).GetString()
				elif data['mapper_raw'] == 0xFD: # TAMA5
					save_type_str = DmgSaveTypes(mbc=0x103).GetString()
				elif data['mapper_raw'] == 0x20: # MBC6
					save_type_str = DmgSaveTypes(mbc=0x104).GetString()
				else:
					save_type_str = DmgSaveTypes(mbc=data['ram_size_raw']).GetString()
			except:
				save_type_str = c__("Game Data", "Not detected")
			rows.append((__("Save Type:"), save_type_str))

			try:
				rows.append((__("Mapper Type:"), DMG_Mapper().GetMapperName(data['mapper_raw'])))
			except:
				rows.append((__("Mapper Type:"), ANSI.RED + c__("Game Data", "Not detected") + ANSI.RESET))
				bad_read = True

			if data['logo_correct'] and not self.CONN.IsSupportedMbc(data["mapper_raw"]):
				print(ANSI.YELLOW + "\n" + __("Warning: This cartridge uses a mapper that may not be completely supported by FlashGBX using the current firmware version of the {device_name}. Please check for firmware updates.", device_name=self.CONN.GetFullName()) + ANSI.RESET)

		elif self.CONN.GetMode() == "AGB":
			rows = []

			game_name = None
			if data["db"]:
				game_name = os.path.splitext(generate_filename(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=None))[0]
			if game_name is not None:
				rows.append((__("Game Name:"), game_name))

			rows.append((__("ROM Title:"), Formatter.title(data["game_title"])))

			if data["db"] is not None:
				rows.append((__("Game Code and Revision:"), "{:s}-{:s}".format(data["db"]["gc"], str(data["version"]))))
			elif len(data["game_code"]) > 0:
				rows.append((__("Game Code and Revision:"), "{:s}-{:s}".format(data["game_code"], str(data["version"]))))

			rows.append((__("Real Time Clock:"), data["rtc_string"]))

			if data.get("sintax"):
				rows.append((__("Boot Logo:"), "YJencrypted"))
			elif data["logo_correct"]:
				rows.append((__("Boot Logo:"), c__("Game Data", "OK")))
				if not os.path.exists(AppContext.CONFIG_PATH + os.sep + "bootlogo_agb.bin"):
					with open(AppContext.CONFIG_PATH + os.sep + "bootlogo_agb.bin", "wb") as f:
						f.write(data['raw'][0x04:0xA0])
			else:
				rows.append((__("Boot Logo:"), ANSI.RED + c__("Game Data", "Invalid") + ANSI.RESET))
				bad_read = True

			if data['header_checksum_correct']:
				rows.append((__("Header Checksum:"), c__("Game Data", "Valid") + " (0x{:02X})".format(data['header_checksum'])))
			else:
				rows.append((__("Header Checksum:"), ANSI.RED + c__("Game Data", "Invalid") + " (0x{:02X})".format(data['header_checksum']) + ANSI.RESET))
				bad_read = True

			db_agb_entry = data["db"]
			rom_checksum_str = None
			rom_size_str = None
			if db_agb_entry != None:
				if data["rom_size_calc"] < 0x400000:
					rom_checksum_str = c__("Game Data", "In database") + " (0x{:06X})".format(db_agb_entry['rc'])
				rom_size_str = "{:d} MiB".format(int(db_agb_entry['rs']/1024/1024))
				data['rom_size'] = db_agb_entry['rs']
			elif data["rom_size"] != 0:
				rom_checksum_str = c__("Game Data", "No database entry")
				if not data["rom_size"] in RomSizes():
					data["rom_size"] = 0x2000000
				rom_size_str = "{:d} MiB".format(int(data["rom_size"]/1024/1024))
			else:
				rom_checksum_str = c__("Game Data", "No database entry")
				rom_size_str = c__("Game Data", "Not detected")
				bad_read = True
			if rom_checksum_str is not None:
				rows.append((__("ROM Checksum:"), rom_checksum_str))
			rows.append((__("ROM Size:"), rom_size_str))

			stok = False
			save_type_str = None
			if data["save_type"] != None:
				stok = True
				save_type_str = AgbSaveTypes(data["save_type"]).GetString()
			else:
				if db_agb_entry != None:
					if db_agb_entry['st'] < AgbSaveTypes().GetNumberOfTypes():
						stok = True
						save_type_str = AgbSaveTypes(db_agb_entry['st']).GetString()
						data["save_type"] = db_agb_entry['st']
				if data["dacs_8m"] is True:
					stok = True
					save_type_str = AgbSaveTypes(6).GetString()
					data["save_type"] = 6
			if stok is False:
				save_type_str = c__("Game Data", "No database entry")
			rows.append((__("Save Type:"), save_type_str))

			if data['logo_correct'] and isinstance(db_agb_entry, dict) and "rs" in db_agb_entry and db_agb_entry['rs'] == 0x4000000 and not self.CONN.IsSupported3dMemory():
				print(ANSI.YELLOW + "\n" + __("Warning: This cartridge uses a mapper that may not be completely supported yet. A future version of the {device_name} firmware may add support for it.", device_name=self.CONN.GetFullName()) + ANSI.RESET)

		max_len = max((len(label) for label, _ in rows), default=0)
		for label, value in rows:
			if value is not None:
				s += "{:s} {:s}\n".format(label.ljust(max_len + 1), value)

		return (bad_read, s, data)

	def DetectCartridge(self, limitVoltage=False):
		print(__("Now attempting to auto-detect the flashcart profile..."))
		if self.CONN.CheckROMStable() is False:
			print(ANSI.RED + __("The cartridge connection is unstable!\nPlease clean the cartridge pins, carefully re-align the cartridge and then try again.") + ANSI.RESET)
			return -1
		if self.CONN.GetMode() in self.FLASHCARTS and len(self.FLASHCARTS[self.CONN.GetMode()]) == 0:
			print(ANSI.RED + __("No flashcart profile configuration files found. Try to restart the application with the “{switch}” command line switch to reset the configuration.", switch="--reset") + ANSI.RESET)
			return -2

		header = self.CONN.ReadHeader()
		self.ReadCartridge(header)
		self.CONN._DetectCartridge(args={"limitVoltage":limitVoltage, "checkSaveType":True})
		ret = self.CONN.INFO.get("detect_cart")
		if not ret or len(ret) < 11:
			print(ANSI.RED + __("Cartridge detection failed.") + ANSI.RESET)
			return -1
		(header, _, save_type, save_chip, sram_unstable, cart_types, cart_type_id, cfi_s, _, flash_id, detected_size) = ret

		# Save Type
		if save_type is None:
			save_type = 0

		# Cart Type
		cart_type = None
		msg_cart_type = ""
		if self.CONN.GetMode() == "DMG":
			supp_cart_types = self.CONN.GetSupportedCartridgesDMG()
		elif self.CONN.GetMode() == "AGB":
			supp_cart_types = self.CONN.GetSupportedCartridgesAGB()
		else:
			raise NotImplementedError

		if len(cart_types) > 0:
			cart_type = cart_type_id
			for i in range(0, len(cart_types)):
				if cart_types[i] == cart_type_id:
					msg_cart_type += "- {:s} ← {:s}\n".format(supp_cart_types[0][cart_types[i]], c__("Flashcart Profile List “- PROFILE NAME ← selected”", "selected"))
				else:
					msg_cart_type += "- {:s}\n".format(supp_cart_types[0][cart_types[i]])
			msg_cart_type = msg_cart_type[:-1]

		# Messages
		# Header
		msg_header_s = __("Game Title:") + " " + Formatter.title(header["game_title"]) + "\n"

		# Save Type
		msg_save_type_s = ""
		temp = ""
		if save_chip is not None:
			temp = "{:s} ({:s})".format(AgbSaveTypes(save_type).GetString(), save_chip)
		else:
			if self.CONN.GetMode() == "DMG":
				temp = "{:s}".format(DmgSaveTypes(index=save_type).GetString())
			elif self.CONN.GetMode() == "AGB":
				temp = "{:s}".format(AgbSaveTypes(save_type).GetString())
		if save_type == 0:
			if save_chip and "Unknown" not in save_chip:
				msg_save_type_s = __("Save Type:")  + " " + save_chip + "\n"
			else:
				msg_save_type_s = __("Save Type:") + " " + c__("Save Type", "None or unknown (no save data detected)") + "\n"
		else:
			if sram_unstable and "SRAM" in temp:
				msg_save_type_s = __("Save Type:") + " " + temp + " " + ANSI.RED + c__("Save Data Access", "not stable or not battery-backed") + ANSI.RESET + "\n"
			else:
				msg_save_type_s = __("Save Type:") + " " + temp + "\n"

		# Cart Type
		msg_cart_type_s = ""
		msg_flash_size_s = ""
		msg_flash_mapper_s = ""

		if cart_type is not None:
			msg_cart_type_s = __("Flashcart Profile:") + " " + __("Supported flash cartridge – compatible with:") + "\n" + msg_cart_type + "\n\n"

			if detected_size > 0:
				size = detected_size
				msg_flash_size_s = __("ROM Size:") + " " + Formatter.file_size(size, as_int=True) + "\n"
			elif "flash_size" in supp_cart_types[1][cart_type_id]:
				size = supp_cart_types[1][cart_type_id]["flash_size"]
				msg_flash_size_s = __("ROM Size:") + " " + Formatter.file_size(size, as_int=True) + "\n"

			if self.CONN.GetMode() == "DMG":
				if "mbc" in supp_cart_types[1][cart_type_id]:
					if supp_cart_types[1][cart_type_id]["mbc"] == "manual":
						msg_flash_mapper_s = __("Mapper Type:") + " " + __("Manual selection") + "\n"
					elif supp_cart_types[1][cart_type_id]["mbc"] in DMG_Mapper().GetAllMapperIds():
						msg_flash_mapper_s = __("Mapper Type:") + " " + DMG_Mapper().GetMapperType(supp_cart_types[1][cart_type_id]["mbc"]) + "\n"
				else:
					msg_flash_mapper_s = __("Mapper Type:") + " " + c__("Mapper Type", "Default") + " (MBC5)\n"

		else:
			if (len(flash_id.split("\n")) > 2) and ((self.CONN.GetMode() == "DMG") or ("dacs_8m" in header and header["dacs_8m"] is not True)):
				msg_cart_type_s = __("Flashcart Profile:") + " " + __("Unknown flash cartridge")
				try_this = ""
				if ("[     0/90]" in flash_id):
					try_this = "Generic Flash Cartridge (0/90)"
				elif ("[   AAA/AA]" in flash_id):
					try_this = "Generic Flash Cartridge (AAA/AA)"
				elif ("[   AAA/A9]" in flash_id):
					try_this = "Generic Flash Cartridge (AAA/A9)"
				elif ("[WR   / AAA/AA]" in flash_id):
					try_this = "Generic Flash Cartridge (WR/AAA/AA)"
				elif ("[WR   / AAA/A9]" in flash_id):
					try_this = "Generic Flash Cartridge (WR/AAA/A9)"
				elif ("[WR   / 555/AA]" in flash_id):
					try_this = "Generic Flash Cartridge (WR/555/AA)"
				elif ("[WR   / 555/A9]" in flash_id):
					try_this = "Generic Flash Cartridge (WR/555/A9)"
				elif ("[AUDIO/ AAA/AA]" in flash_id):
					try_this = "Generic Flash Cartridge (AUDIO/AAA/AA)"
				elif ("[AUDIO/ 555/AA]" in flash_id):
					try_this = "Generic Flash Cartridge (AUDIO/555/AA)"
				if try_this != "":
					msg_cart_type_s += " " + __("For ROM writing, you can give the option called “{try_this}” a try at your own risk.", try_this=try_this)
				msg_cart_type_s += "\n"
			else:
				msg_cart_type_s = __("Flashcart Profile:") + " " + "Generic ROM Cartridge" + " (" + c__("Flashcart Profile", "not rewritable or not auto-detectable") + ")\n"

		msg_flash_id_s = __("Flash ID Check:") + "\n" + flash_id[:-1] + "\n\n"

		if cfi_s != "":
			msg_cfi_s = __("{common_flash_interface} Data:", common_flash_interface="Common Flash Interface") + "\n" + cfi_s + "\n\n"
		else:
			msg_cfi_s = __("{common_flash_interface} Data:", common_flash_interface="Common Flash Interface") + " " + c__("Common Flash Interface Data", "No data provided") + "\n\n"

		msg = "\n\n" + __("The following cartridge configuration was detected:") + "\n\n"
		temp = msg + f"{msg_header_s}{msg_flash_size_s}{msg_flash_mapper_s}{msg_save_type_s}\n{msg_flash_id_s}{msg_cfi_s}{msg_cart_type_s}"
		print(temp[:-1])

		return cart_type

	def BackupROM(self, args, header):
		mbc = 1
		rom_size = 0

		path = generate_filename(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=None)
		if self.CONN.GetMode() == "DMG":
			if args.dmg_mbc == "auto":
				try:
					mbc = header["mapper_raw"]
					if mbc == 0: mbc = 0x19 # MBC5 default
				except:
					print(ANSI.YELLOW + __("Couldn’t determine mapper type, will try to use MBC5. It can also be manually set with the “{switch}” command line switch.", switch="--dmg-mbc") + ANSI.RESET)
					mbc = 0x19
			else:
				if args.dmg_mbc.startswith("0x"):
					mbc = int(args.dmg_mbc[2:], 16)
				elif args.dmg_mbc.isnumeric():
					mbc = int(args.dmg_mbc)
					if mbc == 1: mbc = 0x01
					elif mbc == 2: mbc = 0x06
					elif mbc == 3: mbc = 0x13
					elif mbc == 5: mbc = 0x19
					elif mbc == 6: mbc = 0x20
					elif mbc == 7: mbc = 0x22
					else: mbc = 0x19
				else:
					mbc = 0x19

			if args.dmg_romsize == "auto":
				try:
					rom_size = RomSizes().GetSize(header["rom_size_raw"])
				except:
					print(ANSI.YELLOW + __("Couldn’t determine ROM size, will use 8{mib}. It can also be manually set with the “{switch}” command line switch.", mib=__(" MiB"), switch="--dmg-romsize") + ANSI.RESET)
					rom_size = 8 * 1024 * 1024
			else:
				rom_size = RomSizes.GetSizeFromCLIName(args.dmg_romsize, mode="DMG")

		elif self.CONN.GetMode() == "AGB":
			if args.agb_romsize == "auto":
				rom_size = header["rom_size"]
			else:
				rom_size = RomSizes.GetSizeFromCLIName(args.agb_romsize, mode="AGB")

		if args.path != "auto":
			if os.path.isdir(args.path):
				path = args.path + os.sep + path
			else:
				path = args.path

		if (path == ""): return
		if not args.overwrite and os.path.exists(os.path.abspath(path)):
			answer = input(__("The target file “{file_path}” already exists.\nDo you want to overwrite it?", file_path=os.path.abspath(path)) + " [y/N]: ").strip().lower()
			print("")
			if answer != "y":
				self.RETVAL = self.EXIT_CANCELLED
				print(__("Canceled."))
				return

		try:
			f = open(path, "ab+")
			f.close()
		except PermissionError:
			self.RETVAL = 1
			print(ANSI.RED + __("Couldn’t access file “{path}”.", path=path) + ANSI.RESET)
			return
		except FileNotFoundError:
			self.RETVAL = 1
			print(ANSI.RED + __("Couldn’t find file “{path}”.", path=path) + ANSI.RESET)
			return

		print(__("The ROM will now be read and saved to “{path}”.", path=os.path.abspath(path)))
		if self.CONN.GetMode() == "DMG":
			if mbc in DMG_Mapper().GetAllMapperIds():
				print(__("Mapper Type “{mapper_type}” is used.", mapper_type=DMG_Mapper().GetMapperType(mbc)))
			else:
				print(__("Mapper Type {mapper_type_value} is used.", mapper_type_value="0x{:02X}".format(mbc)))

		print("")

		cart_type = 0
		if args.flashcart_type != "autodetect": 
			if self.CONN.GetMode() == "DMG":
				carts = self.CONN.GetSupportedCartridgesDMG()[1]
			elif self.CONN.GetMode() == "AGB":
				carts = self.CONN.GetSupportedCartridgesAGB()[1]
			else:
				raise NotImplementedError

			cart_type = 0
			for i in range(0, len(carts)):
				if not "names" in carts[i]: continue
				if carts[i]["type"] != self.CONN.GetMode(): continue
				if args.flashcart_type in carts[i]["names"] and "flash_size" in carts[i]:
					print(__("Selected flashcart profile: {profile}", profile=args.flashcart_type) + "\n")
					rom_size = carts[i]["flash_size"]
					cart_type = i
					break
			if cart_type == 0:
				self.RETVAL = 1
				print(__("Error: Couldn’t select the flashcart profile.") + "\n")
				return
		else:
			if self.CONN.GetMode() == "AGB":
				cart_types = self.CONN.GetSupportedCartridgesAGB()
				if "flash_type" in header:
					print(__("Selected flashcart profile: {profile}", profile=cart_types[0][header["flash_type"]]) + "\n")
					cart_type = header["flash_type"]
				elif header['logo_correct']:
					for i in range(0, len(cart_types[0])):
						if ((header['3d_memory'] is True and "3d_memory" in cart_types[1][i]) or
							(header['vast_fame'] is True and "vast_fame" in cart_types[1][i])):
							print(__("Selected flashcart profile: {profile}", profile=cart_types[0][i]) + "\n")
							cart_type = i
							break
		sintax_unlock_log = False
		if self.CONN.GetMode() == "AGB":
			cart = self.CONN.GetSupportedCartridgesAGB()[1][cart_type]
			if isinstance(cart, dict) and cart.get("sintax"):
				settings = IniSettings(path=AppContext.CONFIG_PATH + os.sep + "settings.ini")
				setting = settings.value("SintaxUnlockLog", default="enabled")
				sintax_unlock_log = setting == "enabled"
		self.CONN.TransferData(args={ 'mode':1, 'path':path, 'mbc':mbc, 'rom_size':rom_size, 'agb_rom_size':rom_size, 'start_addr':0, 'fast_read_mode':True, 'cart_type':cart_type, 'sintax_unlock_log':sintax_unlock_log }, signal=self.PROGRESS.SetProgress)

	def FlashROM(self, args, header):
		path = ""
		mbc = 0

		mode = self.CONN.GetMode()
		if mode == "DMG":
			carts = self.CONN.GetSupportedCartridgesDMG()[1]
		elif mode == "AGB":
			carts = self.CONN.GetSupportedCartridgesAGB()[1]
		else:
			return

		cart_type = 0

		for i in range(0, len(carts)):
			if not "names" in carts[i]: continue
			if carts[i]["type"] != mode: continue
			if args.flashcart_type in carts[i]["names"]:
				print(__("Selected flashcart profile: {profile}", profile=args.flashcart_type))
				cart_type = i
				break

		if cart_type <= 0 and args.flashcart_type == "autodetect":
			cart_type = self.DetectCartridge()
			if cart_type is None: cart_type = 0
			if cart_type == 0:
				self.RETVAL = 1
				msg_5v = ""
				if mode == "DMG":
					msg_5v = __("If your flash cartridge requires 5V to work, you can use the “{switch}” command line switch, however please note that 5V can be unsafe for some flash chips.", switch="--force-5v")
				print("\n" + ANSI.RED + __("Auto-detection failed. Please use the “{switch}” command line switch to select the flashcart profile manually.", switch="--flashcart-type") + "\n" + ANSI.RESET + msg_5v + ANSI.RESET)
				return
			elif cart_type < 0:
				self.RETVAL = 1
				return
		elif cart_type == 0 and args.flashcart_type != "autodetect":
			self.RETVAL = 1
			print(ANSI.RED + __("Couldn’t find the selected flashcart profile “{profile}”. Please make sure the correct platform is selected and copy the exact name from the configuration files located in {config_path}.", profile=args.flashcart_type, config_path=AppContext.CONFIG_PATH) + ANSI.RESET)
			return

		if args.path == "auto":
			self.RETVAL = 1
			print(ANSI.RED + __("No ROM file for writing was selected.") + ANSI.RESET)
			return
		else:
			path = args.path

		try:
			if os.path.getsize(path) > 0x20000000: # reject too large files to avoid exploding RAM
				self.RETVAL = 1
				print(ANSI.RED + __("ROM files bigger than 512{mib} are not supported.", mib=__(" MiB")) + ANSI.RESET)
				return
			elif os.path.getsize(path) < 0x400:
				self.RETVAL = 1
				print(ANSI.RED + __("ROM files smaller than 1{kib} are not supported.", kib=__(" KiB")) + ANSI.RESET)
				return

			with open(path, "rb") as file:
				ext = os.path.splitext(path)[1]
				if ext.lower() == ".isx":
					buffer = bytearray(file.read())
					buffer = from_isx(buffer)
				elif mode == "DMG":
					buffer = RomFileDMG.ReadHeaderBuffer(file)
				else:
					buffer = RomFileAGB.ReadHeaderBuffer(file)
			rom_size = os.stat(path).st_size
			if "flash_size" in carts[cart_type]:
				if rom_size > carts[cart_type]['flash_size']:
					print(ANSI.YELLOW + __("The selected flashcart profile seems to support ROMs that are up to {max_size} in size, but the file you selected is {file_size}. You can still give it a try, but it’s possible that it’s too large which may cause the ROM writing to fail.", max_size=Formatter.file_size(carts[cart_type]['flash_size']), file_size=Formatter.file_size(os.path.getsize(path))) + ANSI.RESET)
					answer = input(__("Do you want to continue?") + " [y/N]: ").strip().lower()
					print("")
					if answer != "y":
						self.RETVAL = self.EXIT_CANCELLED
						print(__("Canceled."))
						return

		except PermissionError:
			self.RETVAL = 1
			print(ANSI.RED + __("Couldn’t access file “{path}”.", path=args.path) + ANSI.RESET)
			return
		except FileNotFoundError:
			self.RETVAL = 1
			print(ANSI.RED + __("Couldn’t find file “{path}”.", path=args.path) + ANSI.RESET)
			return

		override_voltage = False
		voltage_fallback = False
		device_voltage_locked = self.CONN.CanSetVoltageByAutoswitch() and not self.CONN.CanSetVoltageByCode()
		if not device_voltage_locked:
			if args.force_5v is True:
				override_voltage = 5
			elif 'voltage_variants' in carts[cart_type] and carts[cart_type]['voltage'] == 3.3:
				print(__("The selected flashcart profile usually flashes fine with 3.3V, however sometimes it may require 5V. You can use the “{switch}” command line switch if necessary. Please note that 5V can be unsafe for some flash chips.", switch="--force-5v"))
			elif carts[cart_type].get('voltage') == 5 and has_3v_compatible_profile(carts, cart_type):
				# Some PCBs share the same flash chip but need 3.3V; try 3.3V silently first,
				# fall back to 5V if writing fails.
				override_voltage = 3.3
				voltage_fallback = 5

		prefer_chip_erase = args.prefer_chip_erase is True
		if not prefer_chip_erase and 'chip_erase' in carts[cart_type]['commands'] and 'sector_erase' in carts[cart_type]['commands']:
			print(__("This flash cartridge supports both Sector Erase and Full Chip Erase methods. You can use the “{switch}” command line switch if necessary.", switch="--prefer-chip-erase"))

		verify_write = args.no_verify_write is False
		compare_sectors = args.compare_sectors is True

		fix_bootlogo = False
		fix_header = False
		if self.CONN.GetMode() == "DMG":
			hdr = RomFileDMG.GetParser(buffer).GetHeader()

			mbc = 0x19 # MBC5 default
			if "mbc" in carts[cart_type]:
				if carts[cart_type]["mbc"] == "manual":
					if args.dmg_mbc != "auto":
						if args.dmg_mbc.startswith("0x"):
							mbc = int(args.dmg_mbc[2:], 16)
						elif args.dmg_mbc.isnumeric():
							mbc = int(args.dmg_mbc)
							if mbc == 1: mbc = 0x01
							elif mbc == 2: mbc = 0x06
							elif mbc == 3: mbc = 0x13
							elif mbc == 5: mbc = 0x19
							elif mbc == 6: mbc = 0x20
							elif mbc == 7: mbc = 0x22
							else: mbc = 0x19
				elif isinstance(carts[cart_type]["mbc"], int):
					mbc = carts[cart_type]["mbc"]
				else:
					if args.dmg_mbc.startswith("0x"):
						mbc = int(args.dmg_mbc[2:], 16)
					elif args.dmg_mbc.isnumeric():
						mbc = int(args.dmg_mbc)
						if mbc == 1: mbc = 0x01
						elif mbc == 2: mbc = 0x06
						elif mbc == 3: mbc = 0x13
						elif mbc == 5: mbc = 0x19
						elif mbc == 6: mbc = 0x20
						elif mbc == 7: mbc = 0x22
						else: mbc = 0x19
					else:
						mbc = 0x19

		elif self.CONN.GetMode() == "AGB":
			hdr = RomFileAGB.GetParser(buffer).GetHeader()
		else:
			raise NotImplementedError

		if not hdr["logo_correct"] and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and mbc not in (0x203, 0x205))):
			print(ANSI.YELLOW + __("Warning: The ROM file you selected will not boot on actual hardware due to invalid boot logo data.") + ANSI.RESET)
			bootlogo = None
			if self.CONN.GetMode() == "DMG":
				if os.path.exists(AppContext.CONFIG_PATH + os.sep + "bootlogo_dmg.bin"):
					with open(AppContext.CONFIG_PATH + os.sep + "bootlogo_dmg.bin", "rb") as f:
						bootlogo = bytearray(f.read(0x30))
			elif self.CONN.GetMode() == "AGB":
				if os.path.exists(AppContext.CONFIG_PATH + os.sep + "bootlogo_agb.bin"):
					with open(AppContext.CONFIG_PATH + os.sep + "bootlogo_agb.bin", "rb") as f:
						bootlogo = bytearray(f.read(0x9C))
			if bootlogo is not None:
				answer = input(__("Fix the boot logo before continuing?") + " [Y/n]: ").strip().lower()
				print("")
				if answer != "n":
					fix_bootlogo = bootlogo
			else:
				dprint(__("Couldn’t find boot logo file in configuration folder."))

		if not hdr["header_checksum_correct"] and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and mbc not in (0x203, 0x205))):
			print(ANSI.YELLOW + __("Warning: The ROM file you selected will not boot on actual hardware due to an invalid header checksum (expected {expected} instead of {actual}).", expected="0x{:02X}".format(hdr["header_checksum_calc"]), actual="0x{:02X}".format(hdr["header_checksum"])) + ANSI.RESET)
			answer = input(__("Fix the header checksum before continuing?") + " [Y/n]: ").strip().lower()
			print("")
			if answer != "n":
				fix_header = True

		print("")
		v = carts[cart_type]["voltage"]
		if override_voltage: v = override_voltage
		print(__("The following ROM file will now be written to the flash cartridge at {voltage}V:", voltage=str(v)) + "\n" + os.path.abspath(path))
		if self.CONN.GetMode() == "DMG":
			if mbc in DMG_Mapper().GetAllMapperIds():
				print(__("Mapper Type “{mapper_type}” is used.", mapper_type=DMG_Mapper().GetMapperType(mbc)))
			else:
				print(__("Mapper Type {mapper_type_value} is used.", mapper_type_value="0x{:02X}".format(mbc)))

		if (v == 3.3 or 'voltage_variants' in carts[cart_type]) and device_voltage_locked and self.CONN.GetMode() == "DMG":
			print("")
			print(ANSI.YELLOW + __("Warning: A 3.3V flashcart profile is selected, but your device is fixed to a 5V supply in Game Boy mode. Writing to a 3.3V flash chip at 5V may cause overvoltage issues.") + ANSI.RESET)
			answer = input(__("Do you want to continue?") + " [y/N]: ").strip().lower()
			if answer != "y":
				self.RETVAL = self.EXIT_CANCELLED
				print(__("Canceled."))
				return

		print("")
		if len(buffer) > 0x1000:
			args = { "mode":4, "path":"", "buffer":buffer, "cart_type":cart_type, "override_voltage":override_voltage, "prefer_chip_erase":prefer_chip_erase, "fast_read_mode":True, "verify_write":verify_write, "fix_header":fix_header, "fix_bootlogo":fix_bootlogo, "mbc":mbc, "compare_sectors":compare_sectors, "voltage_fallback":voltage_fallback }
		else:
			args = { "mode":4, "path":path, "cart_type":cart_type, "override_voltage":override_voltage, "prefer_chip_erase":prefer_chip_erase, "fast_read_mode":True, "verify_write":verify_write, "fix_header":fix_header, "fix_bootlogo":fix_bootlogo, "mbc":mbc, "compare_sectors":compare_sectors, "voltage_fallback":voltage_fallback }
		self.CONN.TransferData(signal=self.PROGRESS.SetProgress, args=args)

		buffer = None

	def BackupRestoreRAM(self, args, header):
		add_date_time = args.save_filename_add_datetime is True
		rtc = args.store_rtc is True
		cart_type = 0

		path_datetime = ""
		if add_date_time:
			path_datetime = "_{:s}".format(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

		path = generate_filename(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=None)
		path = os.path.splitext(path)[0]
		path += "{:s}.sav".format(path_datetime)

		if self.CONN.GetMode() == "DMG":
			if args.dmg_mbc == "auto":
				try:
					mbc = header["mapper_raw"]
					if mbc == 0: mbc = 0x19 # MBC5 default
				except:
					print(ANSI.YELLOW + __("Couldn’t determine mapper type, will try to use MBC5. It can also be manually set with the “{switch}” command line switch.", switch="--dmg-mbc") + ANSI.RESET)
					mbc = 0x19
			else:
				if args.dmg_mbc.startswith("0x"):
					mbc = int(args.dmg_mbc[2:], 16)
				elif args.dmg_mbc.isnumeric():
					mbc = int(args.dmg_mbc)
					if mbc == 1: mbc = 0x01
					elif mbc == 2: mbc = 0x06
					elif mbc == 3: mbc = 0x13
					elif mbc == 5: mbc = 0x19
					elif mbc == 6: mbc = 0x20
					elif mbc == 7: mbc = 0x22
					else: mbc = 0x19
				else:
					mbc = 0x19

			if args.dmg_savetype == "auto":
				try:
					if header['mapper_raw'] == 0x06: # MBC2
						save_type = 0x100
					elif header['mapper_raw'] == 0x22 and header["game_title"] in ("KORO2 KIRBYKKKJ", "KIRBY TNT_KTNE"): # MBC7 Kirby
						save_type = 0x101
					elif header['mapper_raw'] == 0x22 and header["game_title"] in ("CMASTER_KCEJ"): # MBC7 Command Master
						save_type = 0x102
					elif header['mapper_raw'] == 0xFD: # TAMA5
						save_type = 0x103
					elif header['mapper_raw'] == 0x20: # MBC6
						save_type = 0x104
					else:
						save_type = header['ram_size_raw']
				except:
					save_type = 0
			elif args.dmg_savetype == "batteryless":
				save_type = 0x205
			else:
				save_type = DmgSaveTypes.GetMbcFromCLIName(args.dmg_savetype) or 0

			if save_type == 0:
				print(ANSI.RED + __("Unable to auto-detect the save size. Please use the “{switch}” command line switch to manually select it.", switch="--dmg-savetype") + ANSI.RESET)
				return

			if save_type == 0x204:
				cart_type = self.DetectCartridge()

		elif self.CONN.GetMode() == "AGB":
			if args.agb_savetype == "auto":
				save_type = header["save_type"]
			elif args.agb_savetype == "batteryless":
				save_type = 9
			else:
				save_type = AgbSaveTypes.GetIndexFromCLIName(args.agb_savetype)

			mbc = 0
			if save_type == 0 or save_type == None:
				print(ANSI.RED + __("Unable to auto-detect the save type. Please use the “{switch}” command line switch to manually select it.", switch="--agb-savetype") + ANSI.RESET)
				return

		else:
			return

		if args.path != "auto":
			if os.path.isdir(args.path):
				path = args.path + os.sep + path
			else:
				path = args.path

		if (path == ""): return

		# Batteryless SRAM saves are stored inside the ROM flash, so they take a
		# separate code path (BackupROM/FlashROM with bl_offset) instead of the
		# normal SRAM/EEPROM save transfer.
		if (self.CONN.GetMode() == "DMG" and save_type == 0x205) or \
		   (self.CONN.GetMode() == "AGB" and save_type == 9):
			self._BatterylessSRAM(args=args, header=header, mbc=mbc, save_type=save_type, path=path)
			return

		buffer = None
		if args.action == "backup-save":
			if not args.overwrite and os.path.exists(os.path.abspath(path)):
				answer = input(__("The target file “{file_path}” already exists.\nDo you want to overwrite it?", file_path=os.path.abspath(path)) + " [y/N]: ").strip().lower()
				print("")
				if answer != "y":
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return
			print(__("The cartridge save data will now be read and saved to the following file:") + "\n" + os.path.abspath(path))
		elif args.action == "restore-save":
			if not args.overwrite:
				answer = input(__("Do you want to overwrite the existing save data that’s currently on the cartridge?") + " [y/N]: ").strip().lower()
				if answer != "y":
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return
			print(__("The following save data file will now be written to the cartridge:") + "\n" + os.path.abspath(path))
		elif args.action == "erase-save":
			if not args.overwrite:
				answer = input(__("Do you really want to erase the save data from the cartridge?") + " [y/N]: ").strip().lower()
				if answer != "y":
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return
			print(__("The cartridge save data will now be erased from the cartridge."))
		elif args.action == "debug-test-save":
			print(__("The cartridge save data size will now be examined.") + "\n" + __("Note: This is for debug use only.") + "\n")

		if self.CONN.GetMode() == "DMG":
			if mbc in DMG_Mapper().GetAllMapperIds():
				print(__("Mapper Type “{mapper_type}” is used.", mapper_type=DMG_Mapper().GetMapperType(mbc)))
			else:
				print(__("Mapper Type {mapper_type_value} is used.", mapper_type_value="0x{:02X}".format(mbc)))

		if self.CONN.GetMode() == "AGB":
			if args.action == "restore-save" or args.action == "erase-save":
				if self.CONN.GetMode() == "AGB" and "ereader" in self.CONN.INFO and self.CONN.INFO["ereader"] is True:
					if self.CONN.GetFWBuildDate() == "": # Legacy Mode
						print(__("This cartridge is not supported in Legacy Mode."))
						return
					self.CONN.ReadHeader()
					if "ereader_calibration" in self.CONN.INFO:
						with open(path, "rb") as f: buffer = bytearray(f.read())
						if buffer[0xD000:0xF000] != self.CONN.INFO["ereader_calibration"]:
							if args.keep_calibration:
								if args.action == "erase-save": args.action = "restore-save"
								print(__("Note: Keeping existing e-Reader calibration data."))
								buffer[0xD000:0xF000] = self.CONN.INFO["ereader_calibration"]
							else:
								print(__("Note: Overwriting existing e-Reader calibration data."))
					else:
						print(__("Note: No existing e-Reader calibration data found."))
			print(__("Using Save Type “{save_type}”.", save_type=AgbSaveTypes(save_type).GetString()))
		elif self.CONN.GetMode() == "DMG":
			if rtc and header["mapper_raw"] in (0x10, 0x110, 0xFE): # RTC of MBC3, MBC30, HuC-3
				print(__("Real Time Clock register values will also be written if applicable/possible."))

		try:
			if args.action == "backup-save":
				f = open(path, "ab+")
				f.close()
			elif args.action == "restore-save":
				f = open(path, "rb+")
				f.close()
		except PermissionError:
			print(ANSI.RED + __("Couldn’t access file “{path}”.", path=path) + ANSI.RESET)
			return
		except FileNotFoundError:
			print(ANSI.RED + __("Couldn’t find file “{path}”.", path=path) + ANSI.RESET)
			return

		print("")
		if args.action == "backup-save":
			self.CONN.TransferData(args={ 'mode':2, 'path':path, 'mbc':mbc, 'save_type':save_type, 'rtc':rtc }, signal=self.PROGRESS.SetProgress)
		elif args.action == "restore-save":
			verify_write = args.no_verify_write is False
			targs = { 'mode':3, 'path':path, 'mbc':mbc, 'save_type':save_type, 'erase':False, 'rtc':rtc, 'verify_write':verify_write, 'cart_type':cart_type }
			if buffer is not None:
				targs["buffer"] = buffer
				targs["path"] = None
			self.CONN.TransferData(args=targs, signal=self.PROGRESS.SetProgress)
		elif args.action == "erase-save":
			self.CONN.TransferData(args={ 'mode':3, 'path':path, 'mbc':mbc, 'save_type':save_type, 'erase':True, 'rtc':rtc, 'cart_type':cart_type }, signal=self.PROGRESS.SetProgress)
		elif args.action == "debug-test-save": # debug
			self.ARGS["debug"] = True

			print(__("Making a backup of the original save data."))
			ret = self.CONN.TransferData(args={ 'mode':2, 'path':AppContext.CONFIG_PATH + os.sep + "test1.bin", 'mbc':mbc, 'save_type':save_type }, signal=self.PROGRESS.SetProgress)
			if ret is False: return False
			time.sleep(0.1)
			print(__("Writing random data."))
			test2 = bytearray(os.urandom(os.path.getsize(AppContext.CONFIG_PATH + os.sep + "test1.bin")))
			with open(AppContext.CONFIG_PATH + os.sep + "test2.bin", "wb") as f: f.write(test2)
			self.CONN.TransferData(args={ 'mode':3, 'path':AppContext.CONFIG_PATH + os.sep + "test2.bin", 'mbc':mbc, 'save_type':save_type, 'erase':False }, signal=self.PROGRESS.SetProgress)
			time.sleep(0.1)
			print(__("Reading back and comparing data."))
			self.CONN.TransferData(args={ 'mode':2, 'path':AppContext.CONFIG_PATH + os.sep + "test3.bin", 'mbc':mbc, 'save_type':save_type }, signal=self.PROGRESS.SetProgress)
			time.sleep(0.1)
			with open(AppContext.CONFIG_PATH + os.sep + "test3.bin", "rb") as f: test3 = bytearray(f.read())
			if self.CONN.CanPowerCycleCart():
				print("\n" + __("Power cycling."))
				for _ in range(0, 5):
					self.CONN.CartPowerCycle()
					time.sleep(0.1)
				self.CONN.ReadHeader(checkRtc=False)
			time.sleep(0.2)
			print("\n" + __("Reading back and comparing data again."))
			self.CONN.TransferData(args={ 'mode':2, 'path':AppContext.CONFIG_PATH + os.sep + "test4.bin", 'mbc':mbc, 'save_type':save_type }, signal=self.PROGRESS.SetProgress)
			time.sleep(0.1)
			with open(AppContext.CONFIG_PATH + os.sep + "test4.bin", "rb") as f: test4 = bytearray(f.read())
			print(__("Restoring original save data."))
			self.CONN.TransferData(args={ 'mode':3, 'path':AppContext.CONFIG_PATH + os.sep + "test1.bin", 'mbc':mbc, 'save_type':save_type, 'erase':False }, signal=self.PROGRESS.SetProgress)
			time.sleep(0.1)

			if mbc == 6:
				for i in range(0, len(test2)):
					test2[i] &= 0x0F
					test3[i] &= 0x0F
					test4[i] &= 0x0F

			if test2 != test4:
				diffcount = 0
				for i in range(0, len(test2)):
					if test2[i] != test4[i]: diffcount += 1
				print("\n" + ANSI.RED + __("Differences found:") + str(diffcount) + ANSI.RESET)
			if test3 != test4:
				diffcount = 0
				for i in range(0, len(test3)):
					if test3[i] != test4[i]: diffcount += 1
				print("\n" + ANSI.RED + __("Differences found between two consecutive readbacks:") + str(diffcount) + ANSI.RESET)
				input("")

			found_offset = test2.find(test3[0:512])
			if found_offset < 0:
				if self.CONN.GetMode() == "AGB":
					print("\n" + ANSI.RED + __("It was not possible to save any data to the cartridge using save type “{save_type}”.", save_type=AgbSaveTypes(save_type).GetString()) + ANSI.RESET)
				else:
					print("\n" + ANSI.RED + __("It was not possible to save any data to the cartridge.") + ANSI.RESET)
			else:
				if found_offset == 0 and test2 != test3: # Pokémon Crystal JPN
					found_length = 0
					for i in range(0, len(test2)):
						if test2[i] != test3[i]: break
						found_length += 1
				else:
					found_length = len(test2) - found_offset

				if self.CONN.GetMode() == "DMG":
					print("\n" + ANSI.GREEN + __("Done! The writable save data size is {data_writable} out of {data_checked} checked.", data_writable=Formatter.file_size(found_length), data_checked=Formatter.file_size(DmgSaveTypes(mbc=save_type).GetSize())) + ANSI.RESET)
				elif self.CONN.GetMode() == "AGB":
					print("\n" + ANSI.GREEN + __("Done! The writable save data size using save type “{save_type}” is {data_writable}.", save_type=AgbSaveTypes(save_type).GetString(), data_writable=Formatter.file_size(found_length)) + ANSI.RESET)

	def _ResolveBLArgs(self, args, header):
		mode = self.CONN.GetMode()
		bl_offset = None
		bl_size = None
		bl_layout = None

		# 1) CLI flags take precedence
		if args.bl_offset != "auto":
			try:
				txt = args.bl_offset.strip()
				bl_offset = int(txt, 16) if txt.lower().startswith("0x") else int(txt, 0)
			except ValueError:
				print(ANSI.RED + __("Invalid value for {switch}: {value}", switch="--bl-offset", value=args.bl_offset) + ANSI.RESET)
				return None
		if args.bl_size != "auto":
			try:
				txt = args.bl_size.strip()
				bl_size = int(txt, 16) if txt.lower().startswith("0x") else int(txt, 0)
			except ValueError:
				print(ANSI.RED + __("Invalid value for {switch}: {value}", switch="--bl-size", value=args.bl_size) + ANSI.RESET)
				return None
		if mode == "DMG" and args.bl_layout != "auto":
			bl_layout = int(args.bl_layout)

		# 2) Previously auto-detected on this connection
		if (bl_offset is None or bl_size is None) and "dump_info" in self.CONN.INFO and "batteryless_sram" in self.CONN.INFO["dump_info"]:
			detected = self.CONN.INFO["dump_info"]["batteryless_sram"]
			if bl_offset is None and "bl_offset" in detected: bl_offset = detected["bl_offset"]
			if bl_size is None and "bl_size" in detected: bl_size = detected["bl_size"]
			if mode == "DMG" and bl_layout is None and "bl_layout" in detected: bl_layout = detected["bl_layout"]

		# 3) DMG title-based fallback database
		if mode == "DMG" and (bl_offset is None or bl_size is None):
			preselect = header.get("batteryless_sram") or RomFileDMG.GetBatterylessSramConfig(header)
			if preselect is not None:
				if bl_offset is None: bl_offset = preselect["bl_offset"]
				if bl_size is None: bl_size = preselect["bl_size"]
				if bl_layout is None and "bl_layout" in preselect: bl_layout = preselect["bl_layout"]

		if bl_offset is None or bl_size is None:
			print(ANSI.RED + __("Batteryless SRAM offset and size could not be auto-detected. Use the “{switch_offset}” and “{switch_size}” command line switches to specify them manually.", switch_offset="--bl-offset", switch_size="--bl-size") + ANSI.RESET)
			return None
		if mode == "DMG" and bl_layout is None:
			bl_layout = 0  # continuous

		bl_args = {"bl_offset": bl_offset, "bl_size": bl_size}
		if mode == "DMG":
			bl_args["bl_layout"] = bl_layout
		return bl_args

	def _BatterylessSRAM(self, args, header, mbc, save_type, path):
		mode = self.CONN.GetMode()

		if args.action == "debug-test-save":
			print(ANSI.RED + __("Stress test is not supported for this save type.") + ANSI.RESET)
			return

		# Resolve Batteryless SRAM region (offset, size, layout for DMG)
		bl_args = self._ResolveBLArgs(args, header)
		if bl_args is None: return
		bl_offset = bl_args["bl_offset"]
		bl_size = bl_args["bl_size"]

		print(__("Batteryless SRAM Mode"))
		print("- " + __("Location:") + " 0x{:X}–0x{:X} ({:s})".format(bl_offset, bl_offset + bl_size - 1, Formatter.file_size(bl_size, as_int=True)))
		if mode == "DMG":
			layout_names = [__("Continuous"), __("First half of ROM bank"), __("Second half of ROM bank")]
			print("- " + __("Layout:") + " " + layout_names[bl_args["bl_layout"]])
		print("")

		if args.action == "backup-save":
			if not args.overwrite and os.path.exists(os.path.abspath(path)):
				answer = input(__("The target file “{file_path}” already exists.\nDo you want to overwrite it?", file_path=os.path.abspath(path)) + " [y/N]: ").strip().lower()
				print("")
				if answer != "y":
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return
			print(__("The Batteryless SRAM save data will now be read and saved to the following file:") + "\n" + os.path.abspath(path))
			try:
				f = open(path, "ab+"); f.close()
			except (PermissionError, FileNotFoundError):
				print(ANSI.RED + __("Couldn’t access file “{path}”.", path=path) + ANSI.RESET)
				return
			print("")
			targs = {'mode': 1, 'path': path, 'mbc': mbc, 'rom_size': bl_size, 'agb_rom_size': bl_size, 'fast_read_mode': True, 'cart_type': 0}
			targs.update(bl_args)
			self.CONN.TransferData(args=targs, signal=self.PROGRESS.SetProgress)
			return

		# restore-save / erase-save: write into ROM flash, so a flash cart profile is required.
		erase = (args.action == "erase-save")
		cart_type = self._ResolveFlashcartType(args)
		if cart_type is None: return

		if args.action == "restore-save":
			if not args.overwrite:
				answer = input(__("Do you want to overwrite the existing Batteryless SRAM save data on the cartridge?") + " [y/N]: ").strip().lower()
				print("")
				if answer != "y":
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return
			print(__("The following save data file will now be written to the cartridge’s Batteryless SRAM region:") + "\n" + os.path.abspath(path))
			try:
				f = open(path, "rb+"); f.close()
			except (PermissionError, FileNotFoundError):
				print(ANSI.RED + __("Couldn’t access file “{path}”.", path=path) + ANSI.RESET)
				return
		elif erase:
			if not args.overwrite:
				answer = input(__("Do you really want to erase the Batteryless SRAM save data from the cartridge?") + " [y/N]: ").strip().lower()
				print("")
				if answer != "y":
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return
			print(__("The Batteryless SRAM save data will now be erased from the cartridge."))

		if mode == "DMG" and self.CONN.CanSetVoltageByAutoswitch() and not self.CONN.CanSetVoltageByCode():
			bl_carts = self.CONN.GetSupportedCartridgesDMG()[1]
			if isinstance(bl_carts[cart_type], dict) and (bl_carts[cart_type].get("voltage") == 3.3 or 'voltage_variants' in bl_carts[cart_type]):
				print("")
				print(ANSI.YELLOW + __("Warning: A 3.3V flashcart profile is selected, but your device is fixed to a 5V supply in Game Boy mode. Writing to a 3.3V flash chip at 5V may cause overvoltage issues.") + ANSI.RESET)
				answer = input(__("Do you want to continue?") + " [y/N]: ").strip().lower()
				if answer != "y":
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return

		print("")
		verify_write = args.no_verify_write is False
		targs = {
			'mode': 4,
			'path': path,
			'cart_type': cart_type,
			'override_voltage': False,
			'prefer_chip_erase': False,
			'fast_read_mode': True,
			'verify_write': verify_write,
			'fix_header': False,
			'fix_bootlogo': False,
			'mbc': mbc,
			'compare_sectors': args.compare_sectors is True,
			'bl_save': True,
			'flash_offset': bl_offset,
			'flash_size': bl_size,
		}
		targs.update(bl_args)
		if erase:
			targs["path"] = ""
			targs["buffer"] = bytearray([0xFF] * bl_size)
		self.CONN.TransferData(args=targs, signal=self.PROGRESS.SetProgress)

	def _ResolveFlashcartType(self, args):
		mode = self.CONN.GetMode()
		if mode == "DMG":
			carts = self.CONN.GetSupportedCartridgesDMG()[1]
		elif mode == "AGB":
			carts = self.CONN.GetSupportedCartridgesAGB()[1]
		else:
			return None

		if args.flashcart_type != "autodetect":
			for i in range(0, len(carts)):
				if not isinstance(carts[i], dict): continue
				if "names" not in carts[i]: continue
				if carts[i].get("type") != mode: continue
				if args.flashcart_type in carts[i]["names"]:
					print(__("Selected flashcart profile: {profile}", profile=args.flashcart_type))
					return i
			print(ANSI.RED + __("Couldn’t find the selected flashcart profile “{profile}”. Please make sure the correct platform is selected and copy the exact name from the configuration files located in {config_path}.", profile=args.flashcart_type, config_path=AppContext.CONFIG_PATH) + ANSI.RESET)
			return None

		cart_type = self.DetectCartridge()
		if cart_type is None or cart_type == 0 or not isinstance(cart_type, int) or cart_type < 0:
			print("\n" + ANSI.RED + __("Auto-detection failed. Please use the “{switch}” command line switch to select the flashcart profile manually.", switch="--flashcart-type") + ANSI.RESET)
			return None
		return cart_type

	def UpdateFirmware_PrintText(self, text, enableUI=False, setProgress=None):
		if setProgress is not None:
			self.FWUPD_R = True
			print("\33[2K\r{:s} ({:d}%)".format(text, int(setProgress)), flush=True, end="")
		else:
			if self.FWUPD_R is True:
				print("")
			print(text, flush=True)

	def UpdateFirmwareGBxCartRW(self, pcb=5, port=False):
		self.RETVAL = 1
		if pcb != 5: return False
		title = __("Firmware Updater for {device_name}", device_name="GBxCart RW v1.4")
		print("\n" + title)
		print("=" * len(title) + "\n")
		print(__("Select your PCB version:") + "\n1) GBxCart RW v1.4\n2) GBxCart RW v1.4a/b/c\n")
		answer = input(__("Enter number ({range}):", range="1-2") + " ").lower().strip()
		print("")
		if answer == "1":
			led = "Done"
			file_name = AppContext.APP_PATH + os.sep + os.path.join("res", "fw_GBxCart_RW_v1_4.zip")
		elif answer == "2":
			led = "Status"
			file_name = AppContext.APP_PATH + os.sep + os.path.join("res", "fw_GBxCart_RW_v1_4a.zip")
		else:
			self.RETVAL = self.EXIT_CANCELLED
			print(__("Canceled."))
			return

		with zipfile.ZipFile(file_name) as zf:
			with zf.open("fw.ini") as f: ini_file = f.read()
			ini_file = ini_file.decode(encoding="utf-8")
			self.INI = IniSettings(ini=ini_file, main_section="Firmware")
			fw_ver = self.INI.GetValue("fw_ver")
			fw_buildts = self.INI.GetValue("fw_buildts")

		print(__("Available firmware version:") + "\n{:s}\n".format("{:s} ({:s})".format(fw_ver, datetime.datetime.fromtimestamp(int(fw_buildts)).astimezone().replace(microsecond=0).isoformat())))
		text = __("Please follow these steps to proceed with the firmware update:")
		text += "\n\n" + __(
			"- Disconnect the USB cable of your GBxCart RW.\n"
			"- On the circuit board of your GBxCart RW, press and hold down the small button while connecting the USB cable again.\n"
			"- Keep the small button held for at least 2 seconds, then let go of it.\n"
			"- If done right, the green LED labeled “{led}” should remain lit.",
			led=led
		)
		text += "\n" + __("- Press ENTER to continue.")
		print(text)
		if len(input("").strip()) != 0:
			self.RETVAL = self.EXIT_CANCELLED
			print(__("Canceled."))
			return False

		try:
			ports = []
			if port is None or port is False:
				comports = serial.tools.list_ports.comports()
				for i in range(0, len(comports)):
					if comports[i].vid == 0x1A86 and comports[i].pid == 0x7523:
						ports.append(comports[i].device)
				if len(ports) == 0:
					print(__("No devices found."))
					return False
				port = ports[0]

			from . import hw_GBxCartRW
			while True:
				try:
					print(__("Using port {port}", port=port) + "\n")
					FirmwareUpdater = hw_GBxCartRW.FirmwareUpdater
					FWUPD = FirmwareUpdater(port=port)
					ret = FWUPD.WriteFirmware(file_name, self.UpdateFirmware_PrintText)
					break
				except serial.serialutil.SerialException:
					port = input(__("Couldn’t access port {port}.\nEnter new port:", port=port) + " ").strip()
					if len(port) == 0:
						self.RETVAL = self.EXIT_CANCELLED
						print(__("Canceled."))
						return False
					continue

			if ret == 1:
				self.RETVAL = 0
				print(__("The firmware update is complete!"))
				return True
			elif ret == 3:
				print(__("Please re-install the application."))
				return False
			else:
				return False

		except (KeyboardInterrupt, EOFError):
			self.RETVAL = self.EXIT_CANCELLED
			print("\n" + __("Operation stopped."))
			return False
		except Exception as err:
			traceback.print_exception(type(err), err, err.__traceback__)
			print(str(err))
			return False

	def UpdateFirmwareGBFlash(self, port=False):
		self.RETVAL = 1
		from . import hw_GBFlash
		FWUPD = hw_GBFlash.FirmwareUpdater(port=port) if port else None
		title = __("Firmware Updater for {device_name}", device_name="GBFlash")
		print("\n" + title)
		print("=" * len(title))
		print(__("Supported revisions:") + " v1.0, v1.1, v1.2, v1.3\n")
		file_name = AppContext.APP_PATH + os.sep + os.path.join("res", "fw_GBFlash.zip")

		with zipfile.ZipFile(file_name) as zf:
			with zf.open("fw.ini") as f: ini_file = f.read()
			ini_file = ini_file.decode(encoding="utf-8")
			self.INI = IniSettings(ini=ini_file, main_section="Firmware")
			fw_ver = self.INI.GetValue("fw_ver")
			fw_buildts = self.INI.GetValue("fw_buildts")

		print(__("Available firmware version:") + "\n{:s}\n".format("{:s} ({:s})".format(fw_ver, datetime.datetime.fromtimestamp(int(fw_buildts)).astimezone().replace(microsecond=0).isoformat())))
		text = __("Note: Cloned GBFlash hardware often don’t come with a firmware update feature.") + "\n\n"
		text += __("Please follow these steps to proceed with the firmware update:") + "\n\n" + __(
			"- Unplug your GBFlash device.\n"
			"- On your GBFlash circuit board, push and hold the small button (U22) while plugging the USB cable back in.\n"
			"- If done right, the blue LED labeled “ACT” should now keep blinking twice."
		)
		text += "\n" + __("- Press ENTER to continue.")
		print(text)

		if len(input("").strip()) != 0:
			self.RETVAL = self.EXIT_CANCELLED
			print(__("Canceled."))
			return False

		try:
			ports = []
			if port is None or port is False:
				comports = serial.tools.list_ports.comports()
				for i in range(0, len(comports)):
					if (comports[i].vid, comports[i].pid) in hw_GBFlash.USB_IDS.values():
						ports.append(comports[i].device)
				if len(ports) == 0:
					print(__("No device found."))
					return False
				if len(ports) > 1:
					print(__("More than one device found. Please select a port."))
					return False
				port = ports[0]
			while True:
				try:
					print(__("Using port {port}", port=port) + "\n")
					FirmwareUpdater = hw_GBFlash.FirmwareUpdater
					if FWUPD is None or FWUPD.PORT != port:
						FWUPD = FirmwareUpdater(port=port)
					ret = FWUPD.WriteFirmware(file_name, self.UpdateFirmware_PrintText)
					break
				except serial.serialutil.SerialException:
					port = input(__("Couldn’t access port {port}.\nEnter new port:", port=port) + " ").strip()
					if len(port) == 0:
						self.RETVAL = self.EXIT_CANCELLED
						print(__("Canceled."))
						return False
					continue

			if ret == 1:
				self.RETVAL = 0
				print(__("The firmware update is complete!"))
				return True
			elif ret == 3:
				print(__("Please re-install the application."))
				return False
			else:
				return False

		except (KeyboardInterrupt, EOFError):
			self.RETVAL = self.EXIT_CANCELLED
			print("\n" + __("Operation stopped."))
			return False
		except Exception as err:
			traceback.print_exception(type(err), err, err.__traceback__)
			print(str(err))
			return False

	def UpdateFirmwareJoeyJr(self, port=False):
		self.RETVAL = 1
		title = __("Firmware Updater for {device_name}", device_name="Joey Jr")
		print("\n" + title)
		print("=" * len(title))
		file_name = AppContext.APP_PATH + os.sep + os.path.join("res", "fw_JoeyJr.zip")

		with zipfile.ZipFile(file_name) as zf:
			with zf.open("fw.ini") as f: ini_file = f.read()
			ini_file = ini_file.decode(encoding="utf-8")
			self.INI = IniSettings(ini=ini_file, main_section="Firmware")

		print("")
		print(
			__("Select the firmware to install:") + "\n"
			"  1) " + __("Lesserkuma’s FlashGBX firmware") + "\n"
			"  2) " + __("BennVenn’s Drag’n’Drop firmware") + "\n"
			"  3) " + __("BennVenn’s JoeyGUI firmware") + "\n"
		)
		answer = input(__("Enter number ({range}):", range="1-3") + " ").lower().strip()
		print("")
		if answer == "1":
			fw_choice = 1
		elif answer == "2":
			fw_choice = 2
		elif answer == "3":
			fw_choice = 3
		else:
			fw_choice = 0

		if fw_choice == 0:
			self.RETVAL = self.EXIT_CANCELLED
			print(__("Canceled."))
			return False

		try:
			ports = []
			msc_path = None
			if port is None or port is False:
				comports = serial.tools.list_ports.comports()
				for i in range(0, len(comports)):
					if comports[i].vid == 0x483 and comports[i].pid == 0x5740:
						ports.append(comports[i].device)
				if len(ports) == 0:
					if platform.system() != "Darwin":
						print(__("No devices found. If your Joey Jr is running the Drag’n’Drop firmware, you will have to use the JoeyGUI software to update the firmware."))
						return False
					msc_path = input(__("Enter the path to the {mode_txt} file of your Joey Jr removable drive:", mode_txt="MODE.TXT") + " ").strip().strip('"')
					if len(msc_path) == 0:
						self.RETVAL = self.EXIT_CANCELLED
						print(__("Canceled."))
						return False
					port = None
				else:
					port = ports[0]

			if msc_path is not None and fw_choice != 2:
				print(__("After installing this firmware, the Joey Jr removable drive will no longer be available. You can restore it at any time by reinstalling the Drag’n’Drop firmware using this updater.") + "\n")
				answer = input(__("Do you want to continue?") + " [y/N]: ").strip().lower()
				if answer not in ("y", "yes"):
					self.RETVAL = self.EXIT_CANCELLED
					print(__("Canceled."))
					return False

			from . import hw_JoeyJr
			while True:
				try:
					if msc_path is None: print(__("Using port {port}", port=port) + "\n")
					FirmwareUpdater = hw_JoeyJr.FirmwareUpdater
					FWUPD = FirmwareUpdater(port=port)
					file_name = AppContext.APP_PATH + os.sep + os.path.join("res", "fw_JoeyJr.zip")
					with zipfile.ZipFile(file_name) as archive:
						fw_data = None
						if fw_choice == 1:
							with archive.open("FIRMWARE_LK.JR") as f: fw_data = bytearray(f.read())
						elif fw_choice == 2:
							with archive.open("FIRMWARE_MSC.JR") as f: fw_data = bytearray(f.read())
						elif fw_choice == 3:
							with archive.open("FIRMWARE_JOEYGUI.JR") as f: fw_data = bytearray(f.read())

					if msc_path is None:
						ret = FWUPD.WriteFirmware(fw_data, self.UpdateFirmware_PrintText)
					else:
						ret = FWUPD.WriteFirmwareMSC(msc_path, fw_data, self.UpdateFirmware_PrintText)
					break
				except serial.serialutil.SerialException:
					port = input(__("Couldn’t access port {port}.\nEnter new port:", port=port) + " ").strip()
					if len(port) == 0:
						self.RETVAL = self.EXIT_CANCELLED
						print(__("Canceled."))
						return False
					continue

			print("")
			if ret == 1:
				self.RETVAL = 0
				print(__("The firmware update is complete!"))
				return True
			elif ret == 3:
				print(__("Please re-install the application."))
				return False
			else:
				return False

		except (KeyboardInterrupt, EOFError):
			self.RETVAL = self.EXIT_CANCELLED
			print("\n" + __("Operation stopped."))
			return False
		except Exception as err:
			traceback.print_exception(type(err), err, err.__traceback__)
			print(str(err))
			return False
