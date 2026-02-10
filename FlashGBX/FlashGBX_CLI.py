# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import datetime, shutil, platform, os, math, traceback, re, time, serial, zipfile
try:
	# pylint: disable=import-error
	import readline
	readline.set_completer_delims('\t\n=')
	readline.parse_and_bind("tab:complete")
except:
	pass

from .RomFileDMG import RomFileDMG
from .RomFileAGB import RomFileAGB
from .PocketCamera import PocketCamera
from .Util import APPNAME, ANSI
from . import Util
from . import hw_Bacon, hw_GBxCartRW, hw_GBFlash, hw_JoeyJr
hw_devices = [hw_Bacon, hw_GBxCartRW, hw_GBFlash, hw_JoeyJr]

class FlashGBX_CLI():
	ARGS = {}
	CONFIG_PATH = ""
	FLASHCARTS = { "DMG":{}, "AGB":{} }
	CONN = None
	DEVICE = None
	PROGRESS = None
	FWUPD_R = False
	INI = None

	def __init__(self, args):
		self.ARGS = args
		Util.APP_PATH = args['app_path']
		Util.CONFIG_PATH = args['config_path']
		self.FLASHCARTS = args["flashcarts"]
		self.PROGRESS = Util.Progress(self.UpdateProgress, self.WaitProgress)
		
		global prog_bar_part_char
		if platform.system() == "Windows":
			prog_bar_part_char = [" ", " ", " ", " ", "▌", "▌", "▌", "▌"]
		else:
			prog_bar_part_char = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉"]
	
	def run(self):
		config_ret = self.ARGS["config_ret"]
		for i in range(0, len(config_ret)):
			if config_ret[i][0] < 1:
				print(config_ret[i][1])
			elif config_ret[i][0] == 2:
				print("{:s}{:s}{:s}".format(ANSI.YELLOW, config_ret[i][1], ANSI.RESET))
			elif config_ret[i][0] == 2:
				print("{:s}{:s}{:s}".format(ANSI.RED, config_ret[i][1], ANSI.RESET))
		
		args = self.ARGS["argparsed"]
		config_path = Util.formatPathOS(Util.CONFIG_PATH)
		print("Configuration folder: {:s}\n".format(config_path))
		
		# Ask interactively if no args set
		if args.action is None:
			self.ARGS["called_with_args"] = False
			actions = ["info", "backup-rom", "flash-rom", "backup-save", "restore-save", "erase-save", "gbcamera-extract", "fwupdate-gbxcartrw", "fwupdate-gbflash", "fwupdate-joeyjr", "debug-test-save"]
			print("Select Operation:\n 1) Read Cartridge Information\n 2) Backup ROM\n 3) Write ROM\n 4) Backup Save Data\n 5) Restore Save Data\n 6) Erase Save Data\n 7) Extract Game Boy Camera Pictures From Existing Save Data Backup\n 8) Firmware Update for GBxCart RW v1.4/v1.4a only\n 9) Firmware Update for GBFlash\n 10) Firmware Update for Joey Jr\n")
			args.action = input("Enter number 1-10 [1]: ").lower().strip()
			try:
				if int(args.action) == 0:
					print("Canceled.")
					return
				args.action = actions[int(args.action) - 1]
			except:
				if args.action == "":
					args.action = "info"
				else:
					print("Canceled.")
					return
		else:
			self.ARGS["called_with_args"] = True
		
		if args.action is None or args.action not in ("gbcamera-extract", "fwupdate-gbxcartrw", "fwupdate-gbflash", "fwupdate-joeyjr"):
			if not self.FindDevices(port=args.device_port):
				print("No devices found.")
				return
			else:
				if not self.ConnectDevice():
					print("Couldn’t connect to the device.")
					return
				dev = self.DEVICE[1]
				builddate = dev.GetFWBuildDate()

				if dev.FirmwareUpdateAvailable() and dev.FW_UPDATE_REQ is True:
					print("The current firmware version of your device is not supported.\nPlease update the a supported firmware version first.")
					return

				if builddate != "":
					print("\nConnected to {:s}".format(dev.GetFullNameExtended(more=True)))
				else:
					print("\nConnected to {:s}".format(dev.GetFullNameExtended()))

				self.CONN.SetAutoPowerOff(value=1500)
				self.CONN.SetAGBReadMethod(method=2)

		if args.action == "gbcamera-extract":
			if args.path == "auto":
				args.path = input("Enter file path of Game Boy Camera save data file: ").strip().replace("\"", "")
				print("")
				if args.path == "":
					print("Canceled.")
					return
			
			pc = PocketCamera()
			if pc.LoadFile(args.path) != False:
				palettes = [ "grayscale", "dmg", "sgb", "cgb1", "cgb2", "cgb3" ]
				pc.SetPalette(palettes.index(args.gbcamera_palette))
				file = os.path.splitext(args.path)[0] + "/IMG_PC00.png"
				if os.path.isfile(os.path.dirname(file)):
					print("\n{:s}Can’t save pictures at location “{:s}”.{:s}\n".format(ANSI.RED, os.path.abspath(os.path.dirname(file)), ANSI.RESET))
					return
				if not os.path.isdir(os.path.dirname(file)):
					os.makedirs(os.path.dirname(file))
				for i in range(0, 32):
					file = os.path.splitext(args.path)[0] + "/IMG_PC{:02d}".format(i+1) + "." + args.gbcamera_outfile_format
					pc.ExportPicture(i, file, scale=1)
				print("The pictures from “{:s}” were extracted to “{:s}”.".format(os.path.abspath(args.path), Util.formatPathOS(os.path.abspath(os.path.dirname(file)), end_sep=True) + "IMG_PC**.{:s}".format(args.gbcamera_outfile_format)))
			else:
				print("\n{:s}Couldn’t parse the save data file.{:s}\n".format(ANSI.RED, ANSI.RESET))
			return
		
		if args.action == "fwupdate-gbxcartrw":
			self.UpdateFirmwareGBxCartRW(pcb=5, port=args.device_port)
			return 0
		
		if args.action == "fwupdate-gbflash":
			self.UpdateFirmwareGBFlash(port=args.device_port)
			return 0
		
		if args.action == "fwupdate-joeyjr":
			self.UpdateFirmwareJoeyJr(port=args.device_port)
			return 0
		
		elif args.mode is None:
			print("Select Cartridge Mode:\n 1) Game Boy or Game Boy Color\n 2) Game Boy Advance\n")
			answer = input("Enter number 1-2 [2]: ").lower().strip()
			print("")
			if answer == "1":
				args.mode = "dmg"
			elif answer == "2" or answer == "":
				args.mode = "agb"
			else:
				print("Canceled.")
				self.DisconnectDevice()
				return
			print("")
		
		if args.mode == "dmg":
			print("Cartridge Mode: Game Boy or Game Boy Color")
			self.CONN.SetMode("DMG")
		else:
			print("Cartridge Mode: Game Boy Advance")
			self.CONN.SetMode("AGB")
		time.sleep(0.2)

		header = self.CONN.ReadInfo()
		(bad_read, s_header, header) = self.ReadCartridge(header)
		if s_header == "":
			print("\n{:s}Couldn’t read cartridge header. Please try again.{:s}\n".format(ANSI.RED, ANSI.RESET))
			self.DisconnectDevice()
			return
		if bad_read and not args.ignore_bad_header and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and "mapper_raw" in header and header["mapper_raw"] != 0x203)):
			print("\n{:s}Invalid data was detected which usually means that the cartridge couldn’t be read correctly. Please make sure you selected the correct mode and that the cartridge contacts are clean. This check can be disabled with the command line switch “--ignore-bad-header”.{:s}\n".format(ANSI.RED, ANSI.RESET))
			print("Cartridge Information:")
			print(s_header)
			self.DisconnectDevice()
			return
		
		print("\nCartridge Information:")
		print(s_header)

		try:
			if args.action == "backup-rom":
				self.BackupROM(args, header)
			
			elif args.action == "backup-save":
				self.BackupRestoreRAM(args, header)
			
			elif args.action == "restore-save":
				if args.path == "auto":
					args.path = input("Enter file path of save data file: ").strip().replace("\"", "")
					print("")
					if args.path == "":
						print("Canceled.")
						self.DisconnectDevice()
						return
				self.BackupRestoreRAM(args, header)
			
			elif args.action == "erase-save":
				self.BackupRestoreRAM(args, header)
			
			elif args.action == "debug-test-save":
				self.BackupRestoreRAM(args, header)
			
			elif args.action == "flash-rom":
				if args.path == "auto":
					args.path = input("Enter file path of ROM file: ").strip().replace("\"", "")
					print("")
					if args.path == "":
						print("Canceled.")
						self.DisconnectDevice()
						return
				self.FlashROM(args, header)
			
			if args.action != "info":
				print("")
		
		except KeyboardInterrupt:
			print("\n\nOperation stopped.")
		
		self.DisconnectDevice()
		return 0
	
	def WaitProgress(self, args):
		if args["user_action"] == "REINSERT_CART":
			msg = "\n\n"
			msg += args["msg"]
			msg += "\n\nPress ENTER or RETURN to continue.\n"
			answer = input(msg).strip().lower()
			if len(answer.strip()) != 0:
				self.CONN.USER_ANSWER = False
			else:
				self.CONN.USER_ANSWER = True

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
					print("\n\nThe newly written ROM data will now be checked for errors.\n")
				elif args["method"] == "SAVE_WRITE_VERIFY":
					print("\n\nThe newly written save data will now be checked for errors.\n")
			elif args["action"] == "ERASE":
				print("\033[KPlease wait while the flash chip is being erased... (Elapsed time: {:s})".format(Util.formatProgressTime(elapsed)), end="\r")
			elif args["action"] == "UNLOCK":
				print("\033[KPlease wait while the flash chip is being unlocked... (Elapsed time: {:s})".format(Util.formatProgressTime(elapsed)), end="\r")
			elif args["action"] == "SECTOR_ERASE":
				print("\033[KErasing flash sector at address 0x{:X}...".format(args["sector_pos"]), end="\r")
			elif args["action"] == "UPDATE_RTC":
				print("\nUpdating Real Time Clock...")
			elif args["action"] == "ERROR":
				print("{:s}{:s}{:s}{:s}".format(ANSI.CLEAR_LINE, ANSI.RED, args["text"], ANSI.RESET))
			elif args["action"] == "ABORTING":
				print("\nStopping...")
			elif args["action"] == "FINISHED":
				print("\n")
				self.FinishOperation()
			elif args["action"] == "ABORT":
				print("\nOperation stopped.\n")
				if "info_type" in args.keys() and "info_msg" in args.keys():
					if args["info_type"] == "msgbox_critical":
						print(ANSI.RED + args["info_msg"] + ANSI.RESET)
					elif args["info_type"] == "msgbox_information":
						print(args["info_msg"])
					elif args["info_type"] == "label":
						print(args["info_msg"])
				return
			elif args["action"] == "PROGRESS":
				# pv style progress status
				prog_str = "{:s}/{:s} {:s} [{:s}KiB/s] [{:s}] {:s}% ETA {:s} ".format(Util.formatFileSize(size=pos).replace(" ", "").replace("Bytes", "B").replace("Byte", "B").rjust(8), Util.formatFileSize(size=size).replace(" ", "").replace("Bytes", "B"), Util.formatProgressTimeShort(elapsed), "{:.2f}".format(speed).rjust(6), "%PROG_BAR%", "{:d}".format(int(pos/size*100)).rjust(3), Util.formatProgressTimeShort(left))
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
	
	def FinishOperation(self):
		time_elapsed = None
		speed = None
		if "time_start" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["time_start"] > 0:
			time_elapsed = time.time() - self.PROGRESS.PROGRESS["time_start"]
			speed = "{:.2f} KiB/s".format((self.CONN.INFO["transferred"] / 1024.0) / time_elapsed)
			self.PROGRESS.PROGRESS["time_start"] = 0

		if self.CONN.INFO["last_action"] == 4: # Flash ROM
			self.CONN.INFO["last_action"] = 0
			if "verified" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["verified"] == True:
				print("{:s}The ROM was written and verified successfully!{:s}".format(ANSI.GREEN, ANSI.RESET))
			else:
				print("ROM writing complete!")

		if "verified" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["verified"] != True:
			print(self.PROGRESS.PROGRESS)
			input("An error occured.")
		
		elif self.CONN.INFO["last_action"] == 1: # Backup ROM
			self.CONN.INFO["last_action"] = 0
			dump_report = False
			dumpinfo_file = ""
			if self.ARGS["argparsed"].generate_dump_report is True:
				try:
					dump_report = self.CONN.GetDumpReport()
					if dump_report is not False:
						if time_elapsed is not None and speed is not None:
							dump_report = dump_report.replace("%TRANSFER_RATE%", speed)
							dump_report = dump_report.replace("%TIME_ELAPSED%", Util.formatProgressTime(time_elapsed))
						else:
							dump_report = dump_report.replace("%TRANSFER_RATE%", "N/A")
							dump_report = dump_report.replace("%TIME_ELAPSED%", "N/A")
						dumpinfo_file = os.path.splitext(self.CONN.INFO["last_path"])[0] + ".txt"
						with open(dumpinfo_file, "wb") as f:
							f.write(bytearray([ 0xEF, 0xBB, 0xBF ])) # UTF-8 BOM
							f.write(dump_report.encode("UTF-8"))
				except Exception as e:
					print("ERROR: {:s}".format(str(e)))
			
			if self.CONN.GetMode() == "DMG":
				print("CRC32: {:08x}".format(self.CONN.INFO["file_crc32"]))
				print("SHA-1: {:s}\n".format(self.CONN.INFO["file_sha1"]))
				if self.CONN.INFO["rom_checksum"] == self.CONN.INFO["rom_checksum_calc"]:
					print("{:s}The ROM backup is complete and the checksum was verified successfully!{:s}".format(ANSI.GREEN, ANSI.RESET))
				elif ("DMG-MMSA-JPN" in self.ARGS["argparsed"].flashcart_type) or ("mapper_raw" in self.CONN.INFO and self.CONN.INFO["mapper_raw"] in (0x105, 0x202)):
					print("The ROM backup is complete!")
				else:
					msg = "The ROM was dumped, but the checksum is not correct."
					if self.CONN.INFO["loop_detected"] is not False:
						msg += "\nA data loop was detected in the ROM backup at position 0x{:X} ({:s}). This may indicate a bad dump or overdump.".format(self.CONN.INFO["loop_detected"], Util.formatFileSize(size=self.CONN.INFO["loop_detected"], asInt=True))
					else:
						msg += "\nThis may indicate a bad dump, however this can be normal for some reproduction cartridges, unlicensed games, prototypes, patched games and intentional overdumps."
					print("{:s}{:s}{:s}".format(ANSI.YELLOW, msg, ANSI.RESET))
			elif self.CONN.GetMode() == "AGB":
				print("CRC32: {:08x}".format(self.CONN.INFO["file_crc32"]))
				print("SHA-1: {:s}\n".format(self.CONN.INFO["file_sha1"]))
				if "db" in self.CONN.INFO and self.CONN.INFO["db"] is not None:
					if self.CONN.INFO["db"]["rc"] == self.CONN.INFO["file_crc32"]:
						print("{:s}The ROM backup is complete and the checksum was verified successfully!{:s}".format(ANSI.GREEN, ANSI.RESET))
					else:
						msg = "The ROM backup is complete, but the checksum doesn’t match the known database entry."
						if self.CONN.INFO["loop_detected"] is not False:
							msg += "\nA data loop was detected in the ROM backup at position 0x{:X} ({:s}). This may indicate a bad dump or overdump.".format(self.CONN.INFO["loop_detected"], Util.formatFileSize(size=self.CONN.INFO["loop_detected"], asInt=True))
						else:
							msg += "\nThis may indicate a bad dump, however this can be normal for some reproduction cartridges, unlicensed games, prototypes, patched games and intentional overdumps."
						print("{:s}{:s}{:s}".format(ANSI.YELLOW, msg, ANSI.RESET))
				else:
					msg = "The ROM backup is complete! As there is no known checksum for this ROM in the database, verification was skipped."
					if self.CONN.INFO["loop_detected"] is not False:
						msg += "\nNOTE: A data loop was detected in the ROM backup at position 0x{:X} ({:s}). This may indicate a bad dump or overdump.".format(self.CONN.INFO["loop_detected"], Util.formatFileSize(size=self.CONN.INFO["loop_detected"], asInt=True))
					print("{:s}{:s}{:s}".format(ANSI.YELLOW, msg, ANSI.RESET))

		elif self.CONN.INFO["last_action"] == 2: # Backup RAM
			self.CONN.INFO["last_action"] = 0
			if not "debug" in self.ARGS and self.CONN.GetMode() == "DMG" and self.CONN.INFO["mapper_raw"] == 252 and self.CONN.INFO["transferred"] == 0x20000 or (self.CONN.INFO["transferred"] == 0x100000 and self.CONN.INFO["dump_info"]["header"]["ram_size_raw"] == 0x204):
				answer = input("Would you like to extract Game Boy Camera pictures to “{:s}” now? [Y/n]: ".format(Util.formatPathOS(os.path.abspath(os.path.splitext(self.CONN.INFO["last_path"])[0]), end_sep=True) + "IMG_PC**.{:s}".format(self.ARGS["argparsed"].gbcamera_outfile_format))).strip().lower()
				if answer != "n":
					if self.CONN.INFO["transferred"] == 0x100000:
						answer = int(input("A Photo! save file was detected. Please select the roll of pictures that you would like to load.\n- 1:   Current Save Data\n- 2-8: Flash Directory Slots\nLoad Roll [1-8]: "))
						if answer == 0:
							return
						with open(self.CONN.INFO["last_path"], "rb") as f:
							f.seek(0x20000 * (answer - 1))
							file = bytearray(f.read(0x20000))
					else:
						file = self.CONN.INFO["last_path"]

					pc = PocketCamera()
					if pc.LoadFile(file) != False:
						palettes = [ "grayscale", "dmg", "sgb", "cgb1", "cgb2", "cgb3" ]
						pc.SetPalette(palettes.index(self.ARGS["argparsed"].gbcamera_palette))
						file = os.path.splitext(self.CONN.INFO["last_path"])[0] + "/IMG_PC00.png"
						if os.path.isfile(os.path.dirname(file)):
							print("Can’t save pictures at location “{:s}”.".format(os.path.abspath(os.path.dirname(file))))
							return
						if not os.path.isdir(os.path.dirname(file)):
							os.makedirs(os.path.dirname(file))
						for i in range(0, 32):
							file = os.path.splitext(self.CONN.INFO["last_path"])[0] + "/IMG_PC{:02d}".format(i) + "." + self.ARGS["argparsed"].gbcamera_outfile_format
							pc.ExportPicture(i, file, scale=1)
						print("The pictures were extracted.")
				print("")
			
			print("The save data backup is complete!")
		
		elif self.CONN.INFO["last_action"] == 3: # Restore RAM
			self.CONN.INFO["last_action"] = 0
			if "save_erase" in self.CONN.INFO and self.CONN.INFO["save_erase"]:
				print("The save data was erased.")
				del(self.CONN.INFO["save_erase"])
			else:
				print("The save data was restored!")
		
		else:
			self.CONN.INFO["last_action"] = 0
	
	def FindDevices(self, port=None):
		# pylint: disable=global-variable-not-assigned
		global hw_devices
		for hw_device in hw_devices:
			dev = hw_device.GbxDevice()
			ret = dev.Initialize(self.FLASHCARTS, port=port, max_baud=1000000 if self.ARGS["argparsed"].device_limit_baudrate else 2000000)
			if ret is False:
				self.CONN = None
			elif isinstance(ret, list):
				if len(ret) > 0: print("\n")
				for i in range(0, len(ret)):
					status = ret[i][0]
					msg = re.sub('<[^<]+?>', '', ret[i][1])
					if status == 3:
						print("{:s}{:s}{:s}".format(ANSI.RED, msg.replace("\n\n", "\n"), ANSI.RESET))
						self.CONN = None
			
			if dev.IsConnected():
				self.DEVICE = (dev.GetFullNameExtended(), dev)
				dev.Close()
				break
		
		if self.DEVICE is None: return False
		return True
	
	def ConnectDevice(self):
		dev = self.DEVICE[1]
		port = dev.GetPort()
		ret = dev.Initialize(self.FLASHCARTS, port=port, max_baud=1000000 if self.ARGS["argparsed"].device_limit_baudrate else 2000000)

		if ret is False:
			print("\n{:s}An error occured while trying to connect to the device.{:s}".format(ANSI.RED, ANSI.RESET))
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
					print("{:s}{:s}{:s}".format(ANSI.YELLOW, msg, ANSI.RESET))
				elif status == 3:
					print("{:s}{:s}{:s}".format(ANSI.RED, msg, ANSI.RESET))
					self.CONN = None
					return False
		
		if dev.FW_UPDATE_REQ:
			print("{:s}A firmware update for your {:s} device is required to fully use this software.\n{:s}Current firmware version: {:s}{:s}".format(ANSI.RED, dev.GetFullName(), ANSI.YELLOW, dev.GetFirmwareVersion(), ANSI.RESET))
			time.sleep(5)
	
		self.CONN = dev
		return True

	def DisconnectDevice(self):
		try:
			devname = self.CONN.GetFullNameExtended()
			self.CONN.SetAutoPowerOff(value=0)
			self.CONN.Close(cartPowerOff=True)
			print("Disconnected from {:s}".format(devname))
		except:
			pass
		self.CONN = None
	
	def ReadCartridge(self, data):
		bad_read = False
		s = ""
		if self.CONN.GetMode() == "DMG":
			if data["db"]:
				s += "Game Name:       {:s}\n".format(os.path.splitext(Util.GenerateFileName(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=None))[0])

			s += "Game Title:      {:s}\n".format(data["game_title"])
			if len(data['game_code']) > 0:
				s += "Game Code:       {:s}\n".format(data['game_code'])
			s += "Revision:        {:s}\n".format(str(data["version"]))
			s += "Super Game Boy:  "
			if data['sgb'] in Util.DMG_Header_SGB:
				s += "{:s}\n".format(Util.DMG_Header_SGB[data['sgb']])
			else:
				s += "Unknown (0x{:02X})\n".format(data['sgb'])
			s += "Game Boy Color:  "
			if data['cgb'] in Util.DMG_Header_CGB:
				s += "{:s}\n".format(Util.DMG_Header_CGB[data['cgb']])
			else:
				s += "Unknown (0x{:02X})\n".format(data['cgb'])

			s += "Real Time Clock: " + data["rtc_string"] + "\n"

			if data["logo_correct"]:
				s += "Nintendo Logo:   OK\n"
				if not os.path.exists(Util.CONFIG_PATH + "/bootlogo_dmg.bin"):
					with open(Util.CONFIG_PATH + "/bootlogo_dmg.bin", "wb") as f:
						f.write(data['raw'][0x104:0x134])
			else:
				s += "Nintendo Logo:   {:s}Invalid{:s}\n".format(ANSI.RED, ANSI.RESET)
				bad_read = True

			if data['header_checksum_correct']:
				s += "Header Checksum: Valid (0x{:02X})\n".format(data['header_checksum'])
			else:
				s += "Header Checksum: {:s}Invalid (0x{:02X}){:s}\n".format(ANSI.RED, data['header_checksum'], ANSI.RESET)
				bad_read = True
			s += "ROM Checksum:    0x{:04X}\n".format(data['rom_checksum'])
			try:
				s += "ROM Size:        {:s}\n".format(Util.DMG_Header_ROM_Sizes[data['rom_size_raw']])
			except:
				s += "ROM Size:        {:s}Not detected{:s}\n".format(ANSI.RED, ANSI.RESET)
				bad_read = True
			
			try:
				if data['mapper_raw'] == 0x06: # MBC2
					s += "Save Type:       {:s}\n".format(Util.DMG_Header_RAM_Sizes[1])
				elif data['mapper_raw'] == 0x22 and data["game_title"] in ("KORO2 KIRBY", "KIRBY TNT"): # MBC7 Kirby
					s += "Save Type:       {:s}\n".format(Util.DMG_Header_RAM_Sizes[Util.DMG_Header_RAM_Sizes_Map.index(0x101)])
				elif data['mapper_raw'] == 0x22 and data["game_title"] in ("CMASTER"): # MBC7 Command Master
					s += "Save Type:       {:s}\n".format(Util.DMG_Header_RAM_Sizes[Util.DMG_Header_RAM_Sizes_Map.index(0x102)])
				elif data['mapper_raw'] == 0xFD: # TAMA5
					s += "Save Type:       {:s}\n".format(Util.DMG_Header_RAM_Sizes[Util.DMG_Header_RAM_Sizes_Map.index(0x103)])
				elif data['mapper_raw'] == 0x20: # MBC6
					s += "Save Type:       {:s}\n".format(Util.DMG_Header_RAM_Sizes[Util.DMG_Header_RAM_Sizes_Map.index(0x104)])
				else:
					s += "Save Type:       {:s}\n".format(Util.DMG_Header_RAM_Sizes[Util.DMG_Header_RAM_Sizes_Map.index(data['ram_size_raw'])])
			except:
				s += "Save Type:       Not detected\n"
			
			try:
				s += "Mapper Type:     {:s}\n".format(Util.DMG_Header_Mapper[data['mapper_raw']])
			except:
				s += "Mapper Type:     {:s}Not detected{:s}\n".format(ANSI.RED, ANSI.RESET)
				bad_read = True

			if data['logo_correct'] and not self.CONN.IsSupportedMbc(data["mapper_raw"]):
				print("{:s}\nWARNING: This cartridge uses a mapper that may not be completely supported by {:s} using the current firmware version of the {:s} device. Please check for firmware updates.{:s}".format(ANSI.YELLOW, APPNAME, self.CONN.GetFullName(), ANSI.RESET))
			if data['logo_correct'] and data['game_title'] in ("NP M-MENU MENU", "DMG MULTI MENU ") and self.ARGS["argparsed"].flashcart_type == "autodetect":
				cart_types = self.CONN.GetSupportedCartridgesDMG()
				for i in range(0, len(cart_types[0])):
					if "DMG-MMSA-JPN" in cart_types[0][i]:
						self.ARGS["argparsed"].flashcart_type = cart_types[0][i]

		elif self.CONN.GetMode() == "AGB":
			if data["db"]:
				s += "Game Name:            {:s}\n".format(os.path.splitext(Util.GenerateFileName(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=None))[0])

			s += "Game Title:           {:s}\n".format(data["game_title"])
			s += "Game Code:            {:s}\n".format(data["game_code"])
			s += "Revision:             {:d}\n".format(data["version"])

			s += "Real Time Clock:      " + data["rtc_string"] + "\n"

			if data["logo_correct"]:
				s += "Nintendo Logo:        OK\n"
				if not os.path.exists(Util.CONFIG_PATH + "/bootlogo_agb.bin"):
					with open(Util.CONFIG_PATH + "/bootlogo_agb.bin", "wb") as f:
						f.write(data['raw'][0x04:0xA0])
			else:
				s += "Nintendo Logo:        {:s}Invalid{:s}\n".format(ANSI.RED, ANSI.RESET)
				bad_read = True
			if data["96h_correct"]:
				s += "Cartridge Identifier: OK\n"
			else:
				s += "Cartridge Identifier: {:s}Invalid{:s}\n".format(ANSI.RED, ANSI.RESET)
				bad_read = True

			if data['header_checksum_correct']:
				s += "Header Checksum:      Valid (0x{:02X})\n".format(data['header_checksum'])
			else:
				s += "Header Checksum:      {:s}Invalid (0x{:02X}){:s}\n".format(ANSI.RED, data['header_checksum'], ANSI.RESET)
				bad_read = True
			
			s += "ROM Checksum:         "
			db_agb_entry = data["db"]
			if db_agb_entry != None:
				if data["rom_size_calc"] < 0x400000:
					s += "In database (0x{:06X})\n".format(db_agb_entry['rc'])
				s += "ROM Size:             {:d} MiB\n".format(int(db_agb_entry['rs']/1024/1024))
				data['rom_size'] = db_agb_entry['rs']
			elif data["rom_size"] != 0:
				s += "Not in database\n"
				if not data["rom_size"] in Util.AGB_Header_ROM_Sizes_Map:
					data["rom_size"] = 0x2000000
				s += "ROM Size:             {:d} MiB\n".format(int(data["rom_size"]/1024/1024))
			else:
				s += "Not in database\n"
				s += "ROM Size:             Not detected\n"
				bad_read = True
			
			stok = False
			if data["save_type"] == None:
				if db_agb_entry != None:
					if db_agb_entry['st'] < len(Util.AGB_Header_Save_Types):
						stok = True
						s += "Save Type:            {:s}\n".format(Util.AGB_Header_Save_Types[db_agb_entry['st']])
						data["save_type"] = db_agb_entry['st']
				if data["dacs_8m"] is True:
					stok = True
					s += "Save Type:            {:s}\n".format(Util.AGB_Header_Save_Types[6])
					data["save_type"] = 6

			if stok is False:
				s += "Save Type:            Not detected\n"
			
			if data['logo_correct'] and isinstance(db_agb_entry, dict) and "rs" in db_agb_entry and db_agb_entry['rs'] == 0x4000000 and not self.CONN.IsSupported3dMemory():
				print("{:s}\nWARNING: This cartridge uses a Memory Bank Controller that may not be completely supported yet. A future version of the {:s} device firmware may add support for it.{:s}".format(ANSI.YELLOW, self.CONN.GetFullName(), ANSI.RESET))

		return (bad_read, s, data)
	
	def DetectCartridge(self, limitVoltage=False):
		print("Now attempting to auto-detect the flash cartridge type...")
		if self.CONN.CheckROMStable() is False:
			print("{:s}The cartridge connection is unstable!\nPlease clean the cartridge pins, carefully re-align the cartridge and then try again.{:s}".format(ANSI.RED, ANSI.RESET))
			return -1
		if self.CONN.GetMode() in self.FLASHCARTS and len(self.FLASHCARTS[self.CONN.GetMode()]) == 0:
			print("{:s}No flash cartridge type configuration files found. Try to restart the application with the “--reset” command line switch to reset the configuration.{:s}".format(ANSI.RED, ANSI.RESET))
			return -2
		
		header = self.CONN.ReadInfo()
		self.ReadCartridge(header)
		self.CONN._DetectCartridge(args={"limitVoltage":limitVoltage, "checkSaveType":True})
		ret = self.CONN.INFO["detect_cart"]
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
					msg_cart_type += "- {:s}*\n".format(supp_cart_types[0][cart_types[i]])
				else:
					msg_cart_type += "- {:s}\n".format(supp_cart_types[0][cart_types[i]])
			msg_cart_type = msg_cart_type[:-1]
		
		# Messages
		# Header
		msg_header_s = "Game Title: {:s}\n".format(header["game_title"])

		# Save Type
		msg_save_type_s = ""
		temp = ""
		if save_chip is not None:
			temp = "{:s} ({:s})".format(Util.AGB_Header_Save_Types[save_type], save_chip)
		else:
			if self.CONN.GetMode() == "DMG":
				temp = "{:s}".format(Util.DMG_Header_RAM_Sizes[save_type])
			elif self.CONN.GetMode() == "AGB":
				temp = "{:s}".format(Util.AGB_Header_Save_Types[save_type])
		if save_type == 0:
			if "Unknown" in save_chip:
				msg_save_type_s = "Save Type: {:s}\n".format(save_chip)
			else:
				msg_save_type_s = "Save Type: None or unknown (no save data detected)\n"
		else:
			if sram_unstable and "SRAM" in temp:
				msg_save_type_s = "Save Type: {:s} {:s}(not battery-backed){:s}\n".format(temp, ANSI.RED, ANSI.RESET)
			else:
				msg_save_type_s = "Save Type: {:s}\n".format(temp)
		
		# Cart Type
		msg_cart_type_s = ""
		msg_flash_size_s = ""
		msg_flash_mapper_s = ""
		if cart_type is not None:
			msg_cart_type_s = "Cartridge Type: Supported flash cartridge – compatible with:\n{:s}\n".format(msg_cart_type)

			if detected_size > 0:
				size = detected_size
				msg_flash_size_s = "ROM Size: {:s}\n".format(Util.formatFileSize(size=size, asInt=True))
			elif "flash_size" in supp_cart_types[1][cart_type_id]:
				size = supp_cart_types[1][cart_type_id]["flash_size"]
				msg_flash_size_s = "ROM Size: {:s}\n".format(Util.formatFileSize(size=size, asInt=True))

			if self.CONN.GetMode() == "DMG":
				if "mbc" in supp_cart_types[1][cart_type_id]:
					if supp_cart_types[1][cart_type_id]["mbc"] == "manual":
						msg_flash_mapper_s = "Mapper Type: Manual selection\n"
					elif supp_cart_types[1][cart_type_id]["mbc"] in Util.DMG_Header_Mapper.keys():
						msg_flash_mapper_s = "Mapper Type: {:s}\n".format(Util.DMG_Header_Mapper[supp_cart_types[1][cart_type_id]["mbc"]])
				else:
					msg_flash_mapper_s = "Mapper Type: Default (MBC5)\n"

		else:
			if (len(flash_id.split("\n")) > 2) and ((self.CONN.GetMode() == "DMG") or ("dacs_8m" in header and header["dacs_8m"] is not True)):
				msg_cart_type_s = "Cartridge Type: Unknown flash cartridge."
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
				if try_this is not None:
					msg_cart_type_s += " For ROM writing, you can give the option called “{:s}” a try at your own risk.".format(try_this)
				msg_cart_type_s += "\n"
			else:
				msg_cart_type_s = "Cartridge Type: Generic ROM Cartridge (not rewritable or not auto-detectable)\n"
		
		msg_flash_id_s = "Flash ID Check:\n{:s}\n".format(flash_id[:-1])

		if cfi_s != "":
			msg_cfi_s = "Common Flash Interface Data:\n{:s}\n".format(cfi_s)
		else:
			msg_cfi_s = "Common Flash Interface Data: No data provided\n"
		
		msg = "\n\nThe following cartridge configuration was detected:\n\n"
		temp = msg + "{:s}{:s}{:s}{:s}\n{:s}\n{:s}\n{:s}".format(msg_header_s, msg_flash_size_s, msg_flash_mapper_s, msg_save_type_s, msg_flash_id_s, msg_cfi_s, msg_cart_type_s)
		print(temp[:-1])
		
		return cart_type
	
	def BackupROM(self, args, header):
		mbc = 1
		rom_size = 0

		path = Util.GenerateFileName(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=None)
		if self.CONN.GetMode() == "DMG":
			if args.dmg_mbc == "auto":
				try:
					mbc = header["mapper_raw"]
					if mbc == 0: mbc = 0x19 # MBC5 default
				except:
					print("{:s}Couldn’t determine MBC type, will try to use MBC5. It can also be manually set with the “--dmg-mbc” command line switch.{:s}".format(ANSI.YELLOW, ANSI.RESET))
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
					rom_size = Util.DMG_Header_ROM_Sizes_Flasher_Map[header["rom_size_raw"]]
				except:
					print("{:s}Couldn’t determine ROM size, will use 8 MiB. It can also be manually set with the “--dmg-romsize” command line switch.{:s}".format(ANSI.YELLOW, ANSI.RESET))
					rom_size = 8 * 1024 * 1024
			else:
				sizes = [ "auto", "32kb", "64kb", "128kb", "256kb", "512kb", "1mb", "2mb", "4mb", "8mb", "16mb", "32mb", "64mb", "128mb" ]
				rom_size = Util.DMG_Header_ROM_Sizes_Flasher_Map[sizes.index(args.dmg_romsize) - 1]
		
		elif self.CONN.GetMode() == "AGB":
			if args.agb_romsize == "auto":
				rom_size = header["rom_size"]
			else:
				sizes = [ "auto", "32kb", "64kb", "128kb", "256kb", "512kb", "1mb", "2mb", "4mb", "8mb", "16mb", "32mb", "64mb", "128mb", "256mb", "512mb" ]
				rom_size = Util.AGB_Header_ROM_Sizes_Map[sizes.index(args.agb_romsize) - 1]
		
		if args.path != "auto":
			if os.path.isdir(args.path):
				path = args.path + "/" + path
			else:
				path = args.path
		
		if (path == ""): return
		if not args.overwrite and os.path.exists(os.path.abspath(path)):
			answer = input("The target file “{:s}” already exists.\nDo you want to overwrite it? [y/N]: ".format(os.path.abspath(path))).strip().lower()
			print("")
			if answer != "y":
				print("Canceled.")
				return
		
		try:
			f = open(path, "ab+")
			f.close()
		except PermissionError:
			print("{:s}Couldn’t access file “{:s}”.{:s}".format(ANSI.RED, path, ANSI.RESET))
			return
		except FileNotFoundError:
			print("{:s}Couldn’t find file “{:s}”.{:s}".format(ANSI.RED, path, ANSI.RESET))
			return
		
		s_mbc = ""
		if self.CONN.GetMode() == "DMG":
			if mbc in Util.DMG_Header_Mapper:
				s_mbc = " using Mapper Type “{:s}”".format(Util.DMG_Header_Mapper[mbc])
			else:
				s_mbc = " using Mapper Type 0x{:X}".format(mbc)
		if self.CONN.GetMode() == "DMG":
			print("The ROM will now be read{:s} and saved to “{:s}”.".format(s_mbc, os.path.abspath(path)))
		else:
			print("The ROM will now be read and saved to “{:s}”.".format(os.path.abspath(path)))
		
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
					print("Selected cartridge type: {:s}\n".format(args.flashcart_type))
					rom_size = carts[i]["flash_size"]
					cart_type = i
					break
			if cart_type == 0:
				print("ERROR: Couldn’t select the selected cartridge type.\n")
		else:
			if self.CONN.GetMode() == "AGB":
				cart_types = self.CONN.GetSupportedCartridgesAGB()
				if "flash_type" in header:
					print("Selected cartridge type: {:s}\n".format(cart_types[0][header["flash_type"]]))
					cart_type = header["flash_type"]
				elif header['logo_correct']:
					for i in range(0, len(cart_types[0])):
						if ((header['3d_memory'] is True and "3d_memory" in cart_types[1][i]) or
							(header['vast_fame'] is True and "vast_fame" in cart_types[1][i])):
							print("Selected cartridge type: {:s}\n".format(cart_types[0][i]))
							cart_type = i
							break
		self.CONN.TransferData(args={ 'mode':1, 'path':path, 'mbc':mbc, 'rom_size':rom_size, 'agb_rom_size':rom_size, 'start_addr':0, 'fast_read_mode':True, 'cart_type':cart_type }, signal=self.PROGRESS.SetProgress)
	
	def FlashROM(self, args, header):
		path = ""
		s_mbc = ""
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
				print("Selected flash cartridge type: {:s}".format(args.flashcart_type))
				cart_type = i
				break
		
		if cart_type <= 0 and args.flashcart_type == "autodetect":
			cart_type = self.DetectCartridge()
			if cart_type is None: cart_type = 0
			if cart_type == 0:
				msg_5v = ""
				if mode == "DMG": msg_5v = "If your flash cartridge requires 5V to work, you can use the “--force-5v” command line switch, however please note that 5V can be unsafe for some flash chips."
				print("\n{:s}Auto-detection failed. Please use the “--flashcart-type” command line switch to select the flash cartridge type manually.\n{:s}{:s}{:s}".format(ANSI.RED, ANSI.RESET, msg_5v, ANSI.RESET))
				return
			elif cart_type < 0: return
		elif cart_type == 0 and args.flashcart_type != "autodetect":
			print("{:s}Couldn’t find the selected flash cartridge type “{:s}”. Please make sure the correct cartridge mode is selected and copy the exact name from the configuration files located in {:s}.{:s}".format(ANSI.RED, args.flashcart_type, Util.CONFIG_PATH, ANSI.RESET))
			return
		
		if args.path == "auto":
			print("{:s}No ROM file for writing was selected.{:s}".format(ANSI.RED, ANSI.RESET))
			return
		else:
			path = args.path
		
		try:
			if os.path.getsize(path) > 0x20000000: # reject too large files to avoid exploding RAM
				print("{:s}ROM files bigger than 512 MiB are not supported.{:s}".format(ANSI.RED, ANSI.RESET))
				return
			elif os.path.getsize(path) < 0x400:
				print("{:s}ROM files smaller than 1 KiB are not supported.{:s}".format(ANSI.RED, ANSI.RESET))
				return

			with open(path, "rb") as file:
				ext = os.path.splitext(path)[1]
				if ext.lower() == ".isx":
					buffer = bytearray(file.read())
					buffer = Util.isx2bin(buffer)
				else:
					buffer = bytearray(file.read(0x1000))
			rom_size = os.stat(path).st_size
			if "flash_size" in carts[cart_type]:
				if rom_size > carts[cart_type]['flash_size']:
					msg = "The selected flash cartridge type seems to support ROMs that are up to {:s} in size, but the file you selected is {:s}.".format(Util.formatFileSize(size=carts[cart_type]['flash_size']), Util.formatFileSize(size=os.path.getsize(path)))
					msg += " You can still give it a try, but it’s possible that it’s too large which may cause the ROM writing to fail."
					print("{:s}{:s}{:s}".format(ANSI.YELLOW, msg, ANSI.RESET))
					answer = input("Do you want to continue? [y/N]: ").strip().lower()
					print("")
					if answer != "y":
						print("Canceled.")
						return

		except PermissionError:
			print("{:s}Couldn’t access file “{:s}”.{:s}".format(ANSI.RED, args.path, ANSI.RESET))
			return
		except FileNotFoundError:
			print("{:s}Couldn’t find file “{:s}”.{:s}".format(ANSI.RED, args.path, ANSI.RESET))
			return
		
		override_voltage = False
		if args.force_5v is True:
			override_voltage = 5
		elif 'voltage_variants' in carts[cart_type] and carts[cart_type]['voltage'] == 3.3:
			print("The selected flash cartridge type usually flashes fine with 3.3V, however sometimes it may require 5V. You can use the “--force-5v” command line switch if necessary. Please note that 5V can be unsafe for some flash chips.")
		
		prefer_chip_erase = args.prefer_chip_erase is True
		if not prefer_chip_erase and 'chip_erase' in carts[cart_type]['commands'] and 'sector_erase' in carts[cart_type]['commands']:
			print("This flash cartridge supports both Sector Erase and Full Chip Erase methods. You can use the “--prefer-chip-erase” command line switch if necessary.")
		
		verify_write = args.no_verify_write is False
		
		fix_bootlogo = False
		fix_header = False
		if self.CONN.GetMode() == "DMG":
			hdr = RomFileDMG(buffer).GetHeader()

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
			
			if mbc in Util.DMG_Header_Mapper:
				s_mbc = " using Mapper Type “{:s}”".format(Util.DMG_Header_Mapper[mbc])
			else:
				s_mbc = " using Mapper Type 0x{:X}".format(mbc)
		elif self.CONN.GetMode() == "AGB":
			hdr = RomFileAGB(buffer).GetHeader()
		else:
			raise NotImplementedError

		if not hdr["logo_correct"] and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and mbc not in (0x203, 0x205))):
			print("{:s}Warning: The ROM file you selected will not boot on actual hardware due to invalid boot logo data.{:s}".format(ANSI.YELLOW, ANSI.RESET))
			bootlogo = None
			if self.CONN.GetMode() == "DMG":
				if os.path.exists(Util.CONFIG_PATH + "/bootlogo_dmg.bin"):
					with open(Util.CONFIG_PATH + "/bootlogo_dmg.bin", "rb") as f:
						bootlogo = bytearray(f.read(0x30))
			elif self.CONN.GetMode() == "AGB":
				if os.path.exists(Util.CONFIG_PATH + "/bootlogo_agb.bin"):
					with open(Util.CONFIG_PATH + "/bootlogo_agb.bin", "rb") as f:
						bootlogo = bytearray(f.read(0x9C))
			if bootlogo is not None:
				answer = input("Fix the boot logo before continuing? [Y/n]: ").strip().lower()
				print("")
				if answer != "n":
					fix_bootlogo = bootlogo
			else:
				Util.dprint("Couldn’t find boot logo file in configuration folder.")
		
		if not hdr["header_checksum_correct"] and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and mbc not in (0x203, 0x205))):
			print("{:s}WARNING: The ROM file you selected will not boot on actual hardware due to an invalid header checksum (expected 0x{:02X} instead of 0x{:02X}).{:s}".format(ANSI.YELLOW, hdr["header_checksum_calc"], hdr["header_checksum"], ANSI.RESET))
			answer = input("Fix the header checksum before continuing? [Y/n]: ").strip().lower()
			print("")
			if answer != "n":
				fix_header = True
		
		print("")
		v = carts[cart_type]["voltage"]
		if override_voltage: v = override_voltage
		print("The following ROM file will now be written to the flash cartridge{:s} at {:s}V:\n{:s}".format(s_mbc, str(v), os.path.abspath(path)))
		
		print("")
		if len(buffer) > 0x1000:
			args = { "mode":4, "path":"", "buffer":buffer, "cart_type":cart_type, "override_voltage":override_voltage, "prefer_chip_erase":prefer_chip_erase, "fast_read_mode":True, "verify_write":verify_write, "fix_header":fix_header, "fix_bootlogo":fix_bootlogo, "mbc":mbc }
		else:
			args = { "mode":4, "path":path, "cart_type":cart_type, "override_voltage":override_voltage, "prefer_chip_erase":prefer_chip_erase, "fast_read_mode":True, "verify_write":verify_write, "fix_header":fix_header, "fix_bootlogo":fix_bootlogo, "mbc":mbc }
		self.CONN.TransferData(signal=self.PROGRESS.SetProgress, args=args)

		buffer = None
	
	def BackupRestoreRAM(self, args, header):
		add_date_time = args.save_filename_add_datetime is True
		rtc = args.store_rtc is True
		cart_type = 0
		
		path_datetime = ""
		if add_date_time:
			path_datetime = "_{:s}".format(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))
		
		path = Util.GenerateFileName(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=None)
		path = os.path.splitext(path)[0]
		path += "{:s}.sav".format(path_datetime)
		
		if self.CONN.GetMode() == "DMG":
			if args.dmg_mbc == "auto":
				try:
					mbc = header["mapper_raw"]
					if mbc == 0: mbc = 0x19 # MBC5 default
				except:
					print("{:s}Couldn’t determine MBC type, will try to use MBC5. It can also be manually set with the “--dmg-mbc” command line switch.{:s}".format(ANSI.YELLOW, ANSI.RESET))
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
						save_type = 1
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
			else:
				sizes = [ "auto", "4k", "16k", "64k", "256k", "512k", "1m", "mbc6", "mbc7_2k", "mbc7_4k", "tama5", "sram4m", "eeprom1m", "photo" ]
				save_type = Util.DMG_Header_RAM_Sizes_Map[sizes.index(args.dmg_savetype)]

			if save_type == 0:
				print("{:s}Unable to auto-detect the save size. Please use the “--dmg-savetype” command line switch to manually select it.{:s}".format(ANSI.RED, ANSI.RESET))
				return

			if save_type == 0x204:
				cart_type = self.DetectCartridge()
		
		elif self.CONN.GetMode() == "AGB":
			if args.agb_savetype == "auto":
				save_type = header["save_type"]
			else:
				sizes = [ "auto", "eeprom4k", "eeprom64k", "sram256k", "flash512k", "flash1m", "dacs8m", "sram512k", "sram1m" ]
				save_type = sizes.index(args.agb_savetype)
			
			mbc = 0
			if save_type == 0 or save_type == None:
				print("{:s}Unable to auto-detect the save type. Please use the “--agb-savetype” command line switch to manually select it.{:s}".format(ANSI.RED, ANSI.RESET))
				return
		
		else:
			return
		
		if args.path != "auto":
			if os.path.isdir(args.path):
				path = args.path + "/" + path
			else:
				path = args.path
		
		if (path == ""): return
		
		buffer = None
		s_mbc = ""
		if self.CONN.GetMode() == "DMG":
			if mbc in Util.DMG_Header_Mapper:
				s_mbc = " using Mapper Type “{:s}”".format(Util.DMG_Header_Mapper[mbc])
			else:
				s_mbc = " using Mapper Type 0x{:X}".format(mbc)
		if args.action == "backup-save":
			if not args.overwrite and os.path.exists(os.path.abspath(path)):
				answer = input("The target file “{:s}” already exists.\nDo you want to overwrite it? [y/N]: ".format(os.path.abspath(path))).strip().lower()
				print("")
				if answer != "y":
					print("Canceled.")
					return
			print("The cartridge save data will now be read{:s} and saved to the following file:\n{:s}".format(s_mbc, os.path.abspath(path)))
		elif args.action == "restore-save":
			if not args.overwrite:
				answer = input("Restoring save data to the cartridge will erase the existing save.\nDo you want to overwrite it? [y/N]: ").strip().lower()
				if answer != "y":
					print("Canceled.")
					return
			print("The following save data file will now be written to the cartridge{:s}:\n{:s}".format(s_mbc, os.path.abspath(path)))
		elif args.action == "erase-save":
			if not args.overwrite:
				answer = input("Do you really want to erase the save data from the cartridge? [y/N]: ").strip().lower()
				if answer != "y":
					print("Canceled.")
					return
			print("The cartridge save data will now be erased from the cartridge{:s}.".format(s_mbc))
		elif args.action == "debug-test-save":
			print("The cartridge save data size will now be examined{:s}.\nNote: This is for debug use only.\n".format(s_mbc))
		
		if self.CONN.GetMode() == "AGB":
			if args.action == "restore-save" or args.action == "erase-save":
				if self.CONN.GetMode() == "AGB" and "ereader" in self.CONN.INFO and self.CONN.INFO["ereader"] is True:
					if self.CONN.GetFWBuildDate() == "": # Legacy Mode
						print("This cartridge is not supported in Legacy Mode.")
						return
					self.CONN.ReadInfo()
					if "ereader_calibration" in self.CONN.INFO:
						with open(path, "rb") as f: buffer = bytearray(f.read())
						if buffer[0xD000:0xF000] != self.CONN.INFO["ereader_calibration"]:
							if args.keep_calibration:
								if args.action == "erase-save": args.action = "restore-save"
								print("Note: Keeping existing e-Reader calibration data.")
								buffer[0xD000:0xF000] = self.CONN.INFO["ereader_calibration"]
							else:
								print("Note: Overwriting existing e-Reader calibration data.")
					else:
						print("Note: No existing e-Reader calibration data found.")
			print("Using Save Type “{:s}”.".format(Util.AGB_Header_Save_Types[save_type]))
		elif self.CONN.GetMode() == "DMG":
			if rtc and header["mapper_raw"] in (0x10, 0x110, 0xFE): # RTC of MBC3, MBC30, HuC-3
				print("Real Time Clock register values will also be written if applicable/possible.")

		try:
			if args.action == "backup-save":
				f = open(path, "ab+")
				f.close()
			elif args.action == "restore-save":
				f = open(path, "rb+")
				f.close()
		except PermissionError:
			print("{:s}Couldn’t access file “{:s}”.{:s}".format(ANSI.RED, path, ANSI.RESET))
			return
		except FileNotFoundError:
			print("{:s}Couldn’t find file “{:s}”.{:s}".format(ANSI.RED, path, ANSI.RESET))
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

			print("Making a backup of the original save data.")
			ret = self.CONN.TransferData(args={ 'mode':2, 'path':Util.CONFIG_PATH + "/test1.bin", 'mbc':mbc, 'save_type':save_type }, signal=self.PROGRESS.SetProgress)
			if ret is False: return False
			time.sleep(0.1)
			print("Writing random data.")
			test2 = bytearray(os.urandom(os.path.getsize(Util.CONFIG_PATH + "/test1.bin")))
			with open(Util.CONFIG_PATH + "/test2.bin", "wb") as f: f.write(test2)
			self.CONN.TransferData(args={ 'mode':3, 'path':Util.CONFIG_PATH + "/test2.bin", 'mbc':mbc, 'save_type':save_type, 'erase':False }, signal=self.PROGRESS.SetProgress)
			time.sleep(0.1)
			print("Reading back and comparing data.")
			self.CONN.TransferData(args={ 'mode':2, 'path':Util.CONFIG_PATH + "/test3.bin", 'mbc':mbc, 'save_type':save_type }, signal=self.PROGRESS.SetProgress)
			time.sleep(0.1)
			with open(Util.CONFIG_PATH + "/test3.bin", "rb") as f: test3 = bytearray(f.read())
			if self.CONN.CanPowerCycleCart():
				print("\nPower cycling.")
				for _ in range(0, 5):
					self.CONN.CartPowerCycle(delay=0.1)
					time.sleep(0.1)
				self.CONN.ReadInfo(checkRtc=False)
			time.sleep(0.2)
			print("\nReading back and comparing data again.")
			self.CONN.TransferData(args={ 'mode':2, 'path':Util.CONFIG_PATH + "/test4.bin", 'mbc':mbc, 'save_type':save_type }, signal=self.PROGRESS.SetProgress)
			time.sleep(0.1)
			with open(Util.CONFIG_PATH + "/test4.bin", "rb") as f: test4 = bytearray(f.read())
			print("Restoring original save data.")
			self.CONN.TransferData(args={ 'mode':3, 'path':Util.CONFIG_PATH + "/test1.bin", 'mbc':mbc, 'save_type':save_type, 'erase':False }, signal=self.PROGRESS.SetProgress)
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
				print("\n{:s}Differences found: {:d}{:s}".format(ANSI.RED, diffcount, ANSI.RESET))
			if test3 != test4:
				diffcount = 0
				for i in range(0, len(test3)):
					if test3[i] != test4[i]: diffcount += 1
				print("\n{:s}Differences found between two consecutive readbacks: {:d}{:s}".format(ANSI.RED, diffcount, ANSI.RESET))
				input("")
			
			found_offset = test2.find(test3[0:512])
			if found_offset < 0:
				if self.CONN.GetMode() == "AGB":
					print("\n{:s}It was not possible to save any data to the cartridge using save type “{:s}”.{:s}".format(ANSI.RED, Util.AGB_Header_Save_Types[save_type], ANSI.RESET))
				else:
					print("\n{:s}It was not possible to save any data to the cartridge.{:s}".format(ANSI.RED, ANSI.RESET))
			else:
				if found_offset == 0 and test2 != test3: # Pokémon Crystal JPN
					found_length = 0
					for i in range(0, len(test2)):
						if test2[i] != test3[i]: break
						found_length += 1
				else:
					found_length = len(test2) - found_offset
				
				if self.CONN.GetMode() == "DMG":
					print("\n{:s}Done! The writable save data size is {:s} out of {:s} checked.{:s}".format(ANSI.GREEN, Util.formatFileSize(size=found_length), Util.formatFileSize(size=Util.DMG_Header_RAM_Sizes_Flasher_Map[Util.DMG_Header_RAM_Sizes_Map.index(save_type)]), ANSI.RESET))
				elif self.CONN.GetMode() == "AGB":
					print("\n{:s}Done! The writable save data size using save type “{:s}” is {:s}.{:s}".format(ANSI.GREEN, Util.AGB_Header_Save_Types[save_type], Util.formatFileSize(size=found_length), ANSI.RESET))

	def UpdateFirmware_PrintText(self, text, enableUI=False, setProgress=None):
		if setProgress is not None:
			self.FWUPD_R = True
			print("\r{:s} ({:d}%)".format(text, int(setProgress)), flush=True, end="")
		else:
			if self.FWUPD_R is True:
				print("")
			print(text, flush=True)
	
	def UpdateFirmwareGBxCartRW(self, pcb=5, port=False):
		if pcb != 5: return False
		print("\nFirmware Updater for GBxCart RW v1.4")
		print("====================================\n")
		print("Select your PCB version:\n1) GBxCart RW v1.4\n2) GBxCart RW v1.4a\n")
		answer = input("Enter number 1-2: ").lower().strip()
		print("")
		if answer == "1":
			device_name = "v1.4"
			file_name = Util.APP_PATH + "/res/fw_GBxCart_RW_v1_4.zip"
		elif answer == "2":
			device_name = "v1.4a"
			file_name = Util.APP_PATH + "/res/fw_GBxCart_RW_v1_4a.zip"
		else:
			print("Canceled.")
			return

		with zipfile.ZipFile(file_name) as zf:
			with zf.open("fw.ini") as f: ini_file = f.read()
			ini_file = ini_file.decode(encoding="utf-8")
			self.INI = Util.IniSettings(ini=ini_file, main_section="Firmware")
			fw_ver = self.INI.GetValue("fw_ver")
			fw_buildts = self.INI.GetValue("fw_buildts")
		
		print("Available firmware version:\n{:s}\n".format("{:s} ({:s})".format(fw_ver, datetime.datetime.fromtimestamp(int(fw_buildts)).astimezone().replace(microsecond=0).isoformat())))
		print("Please follow these steps to proceed with the firmware update:\n1. Disconnect the USB cable of your GBxCart RW {:s} device.\n2. On the circuit board of your GBxCart RW {:s}, press and hold down\n   the small button while connecting the USB cable again.\n3. Keep the small button held for at least 2 seconds, then let go of it.\n   If done right, the green LED labeled “Done” should remain lit.\n4. Press ENTER or RETURN to continue.".format(device_name, device_name))
		if len(input("").strip()) != 0:
			print("Canceled.")
			return False
		
		try:
			ports = []
			if port is None or port is False:
				comports = serial.tools.list_ports.comports()
				for i in range(0, len(comports)):
					if comports[i].vid == 0x1A86 and comports[i].pid == 0x7523:
						ports.append(comports[i].device)
				if len(ports) == 0:
					print("No device found.")
					return False
				port = ports[0]

			from . import fw_GBxCartRW_v1_4
			while True:
				try:
					print("Using port {:s}.\n".format(port))
					FirmwareUpdater = fw_GBxCartRW_v1_4.FirmwareUpdater
					FWUPD = FirmwareUpdater(port=port)
					ret = FWUPD.WriteFirmware(file_name, self.UpdateFirmware_PrintText)
					break
				except serial.serialutil.SerialException:
					port = input("Couldn’t access port {:s}.\nEnter new port: ".format(port)).strip()
					if len(port) == 0:
						print("Canceled.")
						return False
					continue
				except Exception as err:
					traceback.print_exception(type(err), err, err.__traceback__)
					print(err)
					return False
			
			if ret == 1:
				print("The firmware update is complete!")
				return True
			elif ret == 3:
				print("Please re-install the application.")
				return False
			else:
				return False
		
		except Exception as err:
			traceback.print_exception(type(err), err, err.__traceback__)
			print(err)
			return False
	
	def UpdateFirmwareGBFlash(self, port=False):
		print("\nFirmware Updater for GBFlash")
		print("==============================")
		print("Supported revisions: v1.0, v1.1, v1.2, v1.3\n")
		file_name = Util.APP_PATH + "/res/fw_GBFlash.zip"
		
		with zipfile.ZipFile(file_name) as zf:
			with zf.open("fw.ini") as f: ini_file = f.read()
			ini_file = ini_file.decode(encoding="utf-8")
			self.INI = Util.IniSettings(ini=ini_file, main_section="Firmware")
			fw_ver = self.INI.GetValue("fw_ver")
			fw_buildts = self.INI.GetValue("fw_buildts")
		
		print("Available firmware version:\n{:s}\n".format("{:s} ({:s})".format(fw_ver, datetime.datetime.fromtimestamp(int(fw_buildts)).astimezone().replace(microsecond=0).isoformat())))
		print("Please follow these steps to proceed with the firmware update:\n1. Unplug your GBFlash device.\n2. On your GBFlash circuit board, push and hold the small button (U22) while plugging the USB cable back in.\n3. If done right, the blue LED labeled “ACT” should now keep blinking twice.\n4. Press ENTER or RETURN to continue.")
		if len(input("").strip()) != 0:
			print("Canceled.")
			return False
		
		try:
			ports = []
			if port is None or port is False:
				comports = serial.tools.list_ports.comports()
				for i in range(0, len(comports)):
					if comports[i].vid == 0x1A86 and comports[i].pid == 0x7523:
						ports.append(comports[i].device)
				if len(ports) == 0:
					print("No device found.")
					return False
				port = ports[0]

			from . import fw_GBFlash
			while True:
				try:
					print("Using port {:s}.\n".format(port))
					FirmwareUpdater = fw_GBFlash.FirmwareUpdater
					FWUPD = FirmwareUpdater(port=port)
					ret = FWUPD.WriteFirmware(file_name, self.UpdateFirmware_PrintText)
					break
				except serial.serialutil.SerialException:
					port = input("Couldn’t access port {:s}.\nEnter new port: ".format(port)).strip()
					if len(port) == 0:
						print("Canceled.")
						return False
					continue
				except Exception as err:
					traceback.print_exception(type(err), err, err.__traceback__)
					print(err)
					return False
			
			if ret == 1:
				print("The firmware update is complete!")
				return True
			elif ret == 3:
				print("Please re-install the application.")
				return False
			else:
				return False

		except Exception as err:
			traceback.print_exception(type(err), err, err.__traceback__)
			print(err)
			return False

	def UpdateFirmwareJoeyJr(self, port=False):
		print("\nFirmware Updater for Joey Jr")
		print("==============================")
		file_name = Util.APP_PATH + "/res/fw_JoeyJr.zip"
		
		with zipfile.ZipFile(file_name) as zf:
			with zf.open("fw.ini") as f: ini_file = f.read()
			ini_file = ini_file.decode(encoding="utf-8")
			self.INI = Util.IniSettings(ini=ini_file, main_section="Firmware")
			#fw_ver = self.INI.GetValue("fw_ver")
			#fw_buildts = self.INI.GetValue("fw_buildts")
		
		print("Select the firmware to install:\n1) Lesserkuma’s FlashGBX firmware\n2) BennVenn’s Drag’n’Drop firmware\n3) BennVenn’s JoeyGUI firmware\n")
		answer = input("Enter number 1-3: ").lower().strip()
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
			print("Canceled.")
			return False
		
		try:
			ports = []
			if port is None or port is False:
				comports = serial.tools.list_ports.comports()
				for i in range(0, len(comports)):
					if comports[i].vid == 0x483 and comports[i].pid == 0x5740:
						ports.append(comports[i].device)
				if len(ports) == 0:
					print("No device found. If you use the Drag’n’Drop firmware, please update to JoeyGUI first.")
					return False
				port = ports[0]

			from . import fw_JoeyJr
			while True:
				try:
					print("Using port {:s}.\n".format(port))
					FirmwareUpdater = fw_JoeyJr.FirmwareUpdater
					FWUPD = FirmwareUpdater(port=port)
					file_name = Util.APP_PATH + "/res/fw_JoeyJr.zip"
					with zipfile.ZipFile(file_name) as archive:
						fw_data = None
						if fw_choice == 1:
							with archive.open("FIRMWARE_LK.JR") as f: fw_data = bytearray(f.read())
						elif fw_choice == 2:
							with archive.open("FIRMWARE_MSC.JR") as f: fw_data = bytearray(f.read())
						elif fw_choice == 3:
							with archive.open("FIRMWARE_JOEYGUI.JR") as f: fw_data = bytearray(f.read())
					
					ret = FWUPD.WriteFirmware(fw_data, self.UpdateFirmware_PrintText)
					break
				except serial.serialutil.SerialException:
					port = input("Couldn’t access port {:s}.\nEnter new port: ".format(port)).strip()
					if len(port) == 0:
						print("Canceled.")
						return False
					continue
				except Exception as err:
					traceback.print_exception(type(err), err, err.__traceback__)
					print(err)
					return False
			
			if ret == 1:
				print("The firmware update is complete!")
				return True
			elif ret == 3:
				print("Please re-install the application.")
				return False
			else:
				return False

		except Exception as err:
			traceback.print_exception(type(err), err, err.__traceback__)
			print(err)
			return False
