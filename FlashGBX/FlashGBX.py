# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import sys, os, glob, re, json, zlib, argparse, zipfile, traceback, platform, datetime, copy, time
from .i18n import __, c__, init_language
from .app import AppInfo, AppContext, HW_DEVICES
from .IniSettings import IniSettings
from .CartridgeTypes import RomSizes, AgbSaveTypes, DmgSaveTypes
from .Flashcart import empty_flashcarts_map
from .Logging import ANSI
from .PocketCamera import PocketCamera

STATIC_ACTIONS = ["info", "backup-rom", "flash-rom", "backup-save",
                  "restore-save", "erase-save", "gbcamera-extract",
                  "interactive", "debug-test-save"]
FWUPDATE_ACTIONS = []
for _d in HW_DEVICES:
	try:
		_dev = _d.GbxDevice()
		if _dev.SupportsFirmwareUpdates():
			_action = _dev.FirmwareUpdateAction()
			if _action is not None:
				FWUPDATE_ACTIONS.append(_action)
	except Exception:
		pass
ALL_ACTIONS = STATIC_ACTIONS + FWUPDATE_ACTIONS

def ReadConfigFiles(args):
	reset = args['argparsed'].reset
	settings = IniSettings(path=args["config_path"] + os.sep + "settings.ini")
	config_version = settings.value("ConfigVersion")
	if not os.path.exists(args["config_path"]): os.makedirs(args["config_path"])
	fc_files = glob.glob("{:s}{:s}fc_*.txt".format(glob.escape(args["config_path"]), os.sep))
	if config_version is not None and len(fc_files) == 0:
		print(__("No flashcart profile files found in {config_path}. Resetting configuration...", config_path=args["config_path"]))
		settings.clear()
		os.rename(args["config_path"] + os.sep + "settings.ini", args["config_path"] + os.sep + "settings.ini_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + ".bak")
		config_version = False # extracts the config.zip again
	elif reset:
		settings.clear()
		print(__("All configuration has been reset."))

	if config_version != AppInfo.VERSION:
		settings.setValue("UpdateCheck", None, quiet=True)
	settings.setValue("ConfigVersion", AppInfo.VERSION, quiet=True)
	return (config_version, fc_files)

def LoadConfig(args):
	app_path = args['app_path']
	config_path = args['config_path']
	ret = []
	flashcarts = empty_flashcarts_map()

	# Settings and Config
	(config_version, fc_files) = ReadConfigFiles(args=args)
	if config_version != AppInfo.VERSION:
		# Rename old files that have since been replaced/renamed/merged
		deprecated_files = [ "fc_AGB_TEST.txt", "fc_DMG_TEST.txt", "fc_AGB_Nintendo_E201850.txt", "fc_AGB_Nintendo_E201868.txt", "config.ini", "fc_DMG_MX29LV320ABTC.txt", "fc_DMG_iG_4MB_MBC3_RTC.txt", "fc_AGB_Flash2Advance.txt", "fc_AGB_MX29LV640_AUDIO.txt", "fc_AGB_M36L0R7050T.txt", "fc_AGB_M36L0R8060B.txt", "fc_AGB_M36L0R8060T.txt", "fc_AGB_iG_32MB_S29GL512N.txt", "fc_DMG_SST39SF010_MBC1_AUDIO.txt", "fc_DMG_SST39SF040_MBC5_AUDIO.txt", "fc_DMG_AM29F010_MBC1_AUDIO.txt", "fc_DMG_AM29F040_MBC1_AUDIO.txt", "fc_DMG_AM29F040_MBC1_WR.txt", "fc_DMG_AM29F080_MBC1_AUDIO.txt", "fc_DMG_AM29F080_MBC1_WR.txt", "fc_DMG_SST39SF040_MBC1_AUDIO.txt", "fc_DMG_SST39SF020_MBC1_AUDIO.txt", "fc_DMG_29LV016T.txt", "fc_DMG_Retrostage.txt" ]
		for file in deprecated_files:
			if os.path.exists(config_path + os.sep + file):
				os.rename(config_path + os.sep + file, config_path + os.sep + file + "_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + ".bak")

		rf_list = ""
		if os.path.exists(app_path + os.sep + os.path.join("res", "config.zip")):
			try:
				with zipfile.ZipFile(app_path + os.sep + os.path.join("res", "config.zip")) as zip:
					for zfile in zip.namelist():
						if os.path.exists(config_path + os.sep + zfile):
							zfile_crc = zip.getinfo(zfile).CRC
							with open(config_path + os.sep + zfile, "rb") as ofile: buffer = ofile.read()
							ofile_crc = zlib.crc32(buffer) & 0xFFFFFFFF
							if zfile_crc == ofile_crc: continue
							os.rename(config_path + os.sep + zfile, config_path + os.sep + zfile + "_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + ".bak")
							rf_list += zfile + "\n"
						zip.extract(zfile, config_path + os.sep)
			except zipfile.BadZipFile:
				print(__("Warning: config.zip is corrupted and could not be read."))

			if rf_list != "":
				ret.append([1, __("The application was recently updated and some flashcart profile files have been updated as well. You will find backup copies of them in your configuration directory.")])
			fc_files = glob.glob("{0:s}{1}fc_*.txt".format(glob.escape(config_path), os.sep))
		else:
			print(__("Warning: {config_zip_file} not found. This is required to load new flashcart profile configurations after updating.", config_zip_file=app_path + os.sep + os.path.join("res", "config.zip")))

	# Read flash cart types
	for file in fc_files:
		if os.path.exists(file):
			with open(file, encoding='utf-8') as f:
				data = f.read()
				specs_int = re.sub("(0x[0-9A-F]+)", lambda m: str(int(m.group(1), 16)), data) # hex numbers to int numbers, otherwise not valid json
				try:
					specs = json.loads(specs_int)
				except:
					ret.append([2, "The flashchip type file “{:s}” could not be parsed and needs to be fixed before it can be used.".format(os.path.basename(file))])
					continue
				if "names" not in specs: continue
				for name in specs["names"]:
					if not specs["type"] in flashcarts: continue # only DMG and AGB are supported right now
					temp = copy.deepcopy(specs)
					temp["names"] = [name]
					flashcarts[specs["type"]][name] = temp

	return { "flashcarts":flashcarts, "config_ret":ret }

class ArgParseCustomFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter): pass
def main(portableMode=False):
	if platform.system() == "Windows":
		os.system("color")
	elif platform.system() == "Darwin":
		macos_version = tuple(map(int, platform.mac_ver()[0].split('.')))
		try:
			macos_version = tuple(map(int, platform.mac_ver()[0].split('.')))
		except (ValueError, IndexError):
			macos_version = (0, 0)

		# macOS above Big Sur don't need a compat layer fix in the environment
		if macos_version < (12, 0):
			os.environ['QT_MAC_WANTS_LAYER'] = '1'

	AppContext.LAUNCH_TIMESTAMP = time.time()

	if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
		app_path = os.path.dirname(sys.executable)
	else:
		app_path = os.path.dirname(os.path.abspath(__file__))

	try:
		from .pyside import QtCore
		cp = { "subdir":os.path.join(app_path, "config"), "appdata":os.path.join(QtCore.QDir.toNativeSeparators(QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppConfigLocation)), "FlashGBX") }
	except:
		cp = { "subdir":os.path.join(app_path, "config"), "appdata":os.path.join(os.path.expanduser('~'), "FlashGBX") }

	if portableMode:
		cfgdir_default = "subdir"
	else:
		cfgdir_default = "appdata"

	config_path = None
	language_choice = None
	for i, arg in enumerate(sys.argv):
		if arg == "--cfgdir" and i + 1 < len(sys.argv):
			cfgdir_choice = sys.argv[i + 1].lower()
			if cfgdir_choice in cp:
				config_path = cp[cfgdir_choice]
		elif arg == "--language" and i + 1 < len(sys.argv):
			language_choice = sys.argv[i + 1].lower()

	if config_path is None:
		if cfgdir_default in cp:
			config_path = cp[cfgdir_default]
		else:
			config_path = cp["subdir"]

	init_language(config_path, override=language_choice)

	print("FlashGBX {version}\n© 2020–{year} Lesserkuma".format(version=AppInfo.VERSION, year=time.strftime("%Y")))
	print("https://github.com/Lesserkuma/FlashGBX")

	examples = "\n" + __("Examples") + ":\n" + \
	"  " + __("Backup the ROM of a Game Boy Advance cartridge") + ":\n\tFlashGBX --mode agb --action backup-rom\n\n" + \
	"  " + __("Backup Save Data from a Game Boy cartridge") + ":\n\tFlashGBX --mode dmg --action backup-save\n\n" + \
	"  " + __("Write a Game Boy Advance ROM relying on auto-detecting the flash cartridge") + ":\n\tFlashGBX --mode agb --action flash-rom ROM.gba\n\n" + \
	"  " + __("Extract Game Boy Camera pictures as .png files from a save data file") + ":\n\tFlashGBX --mode dmg --action gbcamera-extract --gbcamera-outfile-format png GAMEBOYCAMERA.sav\n\n" + \
	"  " + __("Backup a {gb_memory_cartridge} ROM including its hidden sector .map file", gb_memory_cartridge="NP GB-Memory Cartridge") + ":\n\tFlashGBX --mode dmg --action backup-rom --dmg-mbc 0x105\n\n"

	parser = argparse.ArgumentParser(formatter_class=ArgParseCustomFormatter, epilog=examples)
	try:
		# pylint: disable=protected-access
		parser._action_groups[1].title = c__("Command Line Arguments Category", "General arguments")
	except:
		pass
	parser.add_argument("--cli", help=c__("Command Line Help", "force command line interface mode"), action="store_true")
	parser.add_argument("--reset", help=c__("Command Line Help", "clears all settings such as last used directory information"), action="store_true")
	parser.add_argument("--debug", help=c__("Command Line Help", "enable debug messages used for development"), action="store_true")
	parser.add_argument("--language", action="store", help=c__("Command Line Help", "sets the language of the program (e.g. “auto”, “en”, “de”, ...)"))

	parser.add_argument_group('')
	ap_config = parser.add_argument_group(c__("Command Line Arguments Category", "Configuration arguments"))
	if "appdata" in cp: ap_config.add_argument("--cfgdir", choices=["appdata", "subdir"], type=str.lower, default=cfgdir_default, help=c__("Configuration Help", "sets the config directory to either the OS-provided local app config directory ({appdata}), or a subdirectory of this application ({subdir})", appdata=cp["appdata"], subdir=cp["subdir"]))

	ap_cli1 = parser.add_argument_group(c__("Command Line Arguments Category", "Main command line interface arguments"))
	ap_cli1.add_argument("--mode", choices=["dmg", "agb"], type=str.lower, default=None, help=c__("Command Line Help", "set platform to “dmg” (Game Boy) or “agb” (Game Boy Advance)"))
	ap_cli1.add_argument("--action", choices=ALL_ACTIONS, type=str.lower, default=None, help=c__("Command Line Help", "select program action"))
	ap_cli1.add_argument("--overwrite", action="store_true", help=c__("Command Line Help", "overwrite without asking if target file already exists"))
	ap_cli1.add_argument("path", nargs="?", default="auto", help=c__("Command Line Help", "target or source file path (optional when reading, required when writing)"))

	ap_cli2 = parser.add_argument_group(c__("Command Line Arguments Category", "Optional command line interface arguments"))
	ap_cli2.add_argument("--dmg-romsize", choices=RomSizes.GetCLINames(mode="DMG"), type=str.lower, default="auto", help=c__("Command Line Help", "set size of Game Boy cartridge ROM data"))
	ap_cli2.add_argument("--dmg-mbc", type=str.lower, default="auto", help=c__("Command Line Help", "set mapper type of Game Boy cartridge"))
	ap_cli2.add_argument("--dmg-savetype", choices=DmgSaveTypes.GetCLINames(), type=str.lower, default="auto", help=c__("Command Line Help", "set type of Game Boy cartridge save data"))
	ap_cli2.add_argument("--agb-romsize", choices=RomSizes.GetCLINames(mode="AGB"), type=str.lower, default="auto", help=c__("Command Line Help", "set size of Game Boy Advance cartridge ROM data"))
	ap_cli2.add_argument("--agb-savetype", choices=AgbSaveTypes.GetCLINames(), type=str.lower, default="auto", help=c__("Command Line Help", "set type of Game Boy Advance cartridge save data"))
	ap_cli2.add_argument("--bl-offset", type=str, default="auto", help=c__("Command Line Help", "Location of Batteryless SRAM data in ROM (e.g. 0xFC0000); only with “{dmg_savetype_batteryless}” or “{agb_savetype_batteryless}”)", dmg_savetype_batteryless="--dmg-savetype batteryless", agb_savetype_batteryless="--agb-savetype batteryless"))
	ap_cli2.add_argument("--bl-size", type=str, default="auto", help=c__("Command Line Help", "Size of Batteryless SRAM data in ROM (e.g. 0x10000)"))
	ap_cli2.add_argument("--bl-layout", choices=["auto", "0", "1", "2"], type=str.lower, default="auto", help=c__("Command Line Help", "Bank layout of Batteryless SRAM data for DMG mode: 0=continuous, 1=first half of ROM bank, 2=second half"))
	ap_cli2.add_argument("--store-rtc", action="store_true", default=False, help=c__("Command Line Help", "store RTC register values if supported"))
	ap_cli2.add_argument("--keep-calibration", action="store_true", default=True, help=c__("Command Line Help", "keep existing calibration data of the e-Reader when writing save data"))
	ap_cli2.add_argument("--ignore-bad-header", action="store_true", help=c__("Command Line Help", "don’t stop if invalid data found in cartridge header data"))
	ap_cli2.add_argument("--flashcart-type", type=str, default="autodetect", help=c__("Command Line Help", "name of flash cart profile; see .txt files in config directory"))
	ap_cli2.add_argument("--prefer-chip-erase", action="store_true", help=c__("Command Line Help", "prefer full chip erase over sector erase when both available"))
	ap_cli2.add_argument("--force-5v", action="store_true", help=c__("Command Line Help", "force 5V when writing Game Boy flash cartridges"))
	ap_cli2.add_argument("--no-verify-write", action="store_true", help=c__("Command Line Help", "do not verify written data"))
	ap_cli2.add_argument("--generate-dump-report", action="store_true", help=c__("Command Line Help", "generate a dump report for a ROM backup"))
	ap_cli2.add_argument("--save-filename-add-datetime", action="store_true", help=c__("Command Line Help", "adds a timestamp to the file name of save data backups"))
	ap_cli2.add_argument("--gbcamera-palette", choices=PocketCamera.PALETTE_NAMES, type=str.lower, default="grayscale", help=c__("Command Line Help", "sets the color palette of pictures extracted from Game Boy Camera saves"))
	ap_cli2.add_argument("--gbcamera-outfile-format", choices=PocketCamera.OUTPUT_FORMATS, type=str.lower, default="png", help=c__("Command Line Help", "sets the file format of saved pictures extracted from Game Boy Camera saves"))
	ap_cli2.add_argument("--gbcamera-extract", action="store_true", default=False, help=c__("Command Line Help", "automatically extract Game Boy Camera pictures after backing up save data"))
	ap_cli2.add_argument("--device-port", help=c__("Command Line Help", "override device port"), default=None)
	ap_cli2.add_argument("--device-limit-baudrate", action="store_true", help=c__("Command Line Help", "limit connection to a slower baud rate"))
	ap_cli2.add_argument("--compare-sectors", action="store_true", help=c__("Command Line Help", "compare sectors and only write those that differ when writing a ROM (only for flash carts that support this feature)"), default=True)
	ap_cli2.add_argument("--wait", action="store_true", help=c__("Command Line Help", "wait for key press after the program has ended"))
	args = None
	try:
		args, _ = parser.parse_known_args()
	except SystemExit:
		if args is None or "--help" in sys.argv:
			input("\n\n" + __("Press ENTER to exit.") + "\n")
			return 0

	if "appdata" in cp and hasattr(args, 'cfgdir'):
		parsed_config_path = cp[args.cfgdir]
		if parsed_config_path != config_path:
			config_path = parsed_config_path

	if args.mode is not None or args.action is not None:
		args.cli = True

	if args.debug == True:
		AppContext.DEBUG = True

	args = {"app_path":app_path, "config_path":config_path, "argparsed":args}
	while True:
		try:
			if not os.path.exists(config_path):
				os.mkdir(config_path)
			tf = "{:s}/settings.ini".format(config_path)
			f = open(tf, "ab")
			f.close()
			break
		except PermissionError:
			print("\n" + ANSI.RED + __("Error: This program has no permission to use the configuration directory “{config_path}”!", config_path=config_path) + ANSI.RESET)
			if "appdata" in cp and args["argparsed"].cfgdir == "subdir":
				answer = input(__("Use directory “{appdata_folder}” instead?", appdata_folder=cp["appdata"]) + " [y/N] ").strip().lower()
				if answer != "y":
					return
				config_path = cp["appdata"]
				args["config_path"]  = config_path
				continue
			else:
				input("")
			if args["argparsed"].wait: input("\n\n" + __("Press ENTER to exit.") + "\n")
			return

	args.update(LoadConfig(args))

	app = None
	exc = None
	retval = -1
	if not args["argparsed"].cli:
		try:
			from . import FlashGBX_GUI
			app = FlashGBX_GUI.FlashGBX_GUI(args)
		except ModuleNotFoundError:
			exc = traceback.format_exc()
			app = None
		except:
			exc = traceback.format_exc()
			app = None

		if app is None:
			from . import FlashGBX_CLI
			if args["argparsed"].action is None:
				parser.print_help()
				print("\n\n{:s}" + __("Note: GUI mode couldn’t be launched, but the application can be run in CLI mode.") + "\n      " + __("Optional command line switches are explained above.") + "{:s}\n".format(ANSI.RED, ANSI.RESET))
				if exc is not None: print(ANSI.YELLOW + str(exc) + ANSI.RESET)

			print(__("Falling back to CLI mode.") + "\n")
			app = FlashGBX_CLI.FlashGBX_CLI(args)
			try:
				retval = app.run()
			except KeyboardInterrupt:
				print("\n\n" + __("Program stopped."))
			if args["argparsed"].wait: input("\n" + __("Press ENTER to exit.") + "\n")
			sys.exit(retval)

		app.run()

	else:
		from . import FlashGBX_CLI
		print("\n" + __("Now running in CLI mode."))
		app = FlashGBX_CLI.FlashGBX_CLI(args)
		try:
			retval = app.run()
		except KeyboardInterrupt:
			print("\n\n" + __("Program stopped."))
		if args["argparsed"].wait: input("\n" + __("Press ENTER to exit.") + "\n")
		sys.exit(retval)
