# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)
#
# Terminal output, debug logging, and Python exception hook.

import sys, os, re, time, datetime, traceback, platform
from .app import AppInfo, AppContext
from . import i18n
from .i18n import __

class ANSI:
	BOLD = '\033[1m'
	RED = '\033[91m'
	GREEN = '\033[92m'
	YELLOW = '\033[33m'
	DARK_GRAY = '\033[90m'
	RESET = '\033[0m'
	CLEAR_LINE = '\033[2K'

class Logger:
	LOG_ERROR = False

	def __init__(self):
		AppContext.PRINT_LOG.append(
			"FlashGBX {version}\n© 2020–{year} Lesserkuma".format(
				version=AppInfo.VERSION, year=time.strftime("%Y"),
			)
		)

	def write(self, *args, **kwargs):
		msg = "{:s}".format(" ".join(map(str, args)), **kwargs)
		if len(msg.strip()) > 0:
			if ANSI.RED in msg:
				self.LOG_ERROR = True
			AppContext.PRINT_LOG.append(re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', msg.strip()))
			if len(AppContext.PRINT_LOG) > 16 * 1024: AppContext.PRINT_LOG.pop(0)
		try:
			sys.__stdout__.write(msg)
		except (OSError, ValueError):
			pass

	def flush(self):
		try:
			sys.__stdout__.flush()
		except (OSError, ValueError):
			pass

	@classmethod
	def dprint(cls, *args, **kwargs):
		stack = traceback.extract_stack()
		stack = stack[len(stack) - 2]
		msg = "[{:s}] [{:s}:{:d}] {:s}(): {:s}".format(
			str(datetime.datetime.now().astimezone()),
			os.path.split(stack.filename)[1], stack.lineno, stack.name,
			" ".join(map(str, args)), **kwargs,
		)
		AppContext.DEBUG_LOG.append(msg)
		if len(AppContext.DEBUG_LOG) > 64 * 1024: AppContext.DEBUG_LOG.pop(0)
		if AppContext.DEBUG:
			msg = ANSI.CLEAR_LINE + msg
			if isinstance(sys.stdout, Logger):
				temp = sys.stdout
				try:
					sys.stdout = sys.__stdout__
					print(msg)
				except (OSError, ValueError):
					pass
				finally:
					sys.stdout = temp

	@classmethod
	def write_debug_log(cls, device=False):
		if not AppContext.CONFIG_PATH: return False
		cls.dprint("Now writing debug log file")
		msg = "\n\n\n---- Debug Log ----\n"
		msg += "{:s} version: {:s} ({:d})\n".format(
			AppInfo.NAME, AppInfo.VERSION_PEP440, AppInfo.VERSION_TIMESTAMP,
		)
		msg += "Language: {:s}\n".format(i18n.CONFIGURED_LANGUAGE)
		msg += "Platform: {:s}\n".format(
			AppInfo.os_string() + ", " + platform.machine() + ", " + i18n.OS_LANGUAGE
		)
		if device is not False:
			if device is not None:
				msg += "Connected device: {:s}\n".format(device)
			else:
				msg += "No device connected\n"

		launch_time = datetime.datetime.fromtimestamp(AppContext.LAUNCH_TIMESTAMP).astimezone().replace(microsecond=0)
		now = datetime.datetime.now().astimezone().replace(microsecond=0)
		runtime = now - launch_time
		days, hours, minutes, seconds = (
			runtime.days, runtime.seconds // 3600,
			(runtime.seconds % 3600) // 60, runtime.seconds % 60,
		)
		msg += "Launched: {:s}\n".format(launch_time.isoformat())
		msg += "Log generated: {:s}\n".format(now.isoformat())
		msg += "Runtime: {}d {}h {}m {}s\n\n".format(days, hours, minutes, seconds)

		try:
			fn = AppContext.CONFIG_PATH + os.sep + "debug.log"
			with open(fn, "wb") as f:
				f.write("".encode("UTF-8-SIG"))
				if platform.system() == "Windows":
					f.write("\r\n".join(AppContext.PRINT_LOG).encode("UTF-8"))
					f.write(msg.replace("\n", "\r\n").encode("UTF-8"))
					f.write("\r\n".join(AppContext.DEBUG_LOG).encode("UTF-8"))
				else:
					f.write("\n".join(AppContext.PRINT_LOG).encode("UTF-8"))
					f.write(msg.encode("UTF-8"))
					f.write("\n".join(AppContext.DEBUG_LOG).encode("UTF-8"))
				print(__("The debug log was written to {logfile}", logfile=fn))
			return True
		except:
			return False

	@classmethod
	def exception_hook(cls, exc_type, exc_value, exc_traceback):
		if issubclass(exc_type, KeyboardInterrupt):
			sys.__excepthook__(exc_type, exc_value, exc_traceback)
			return
		s = "EXCEPTION OCCURED\n"
		lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
		for line in lines:
			s += f"{line:s}"
		print(s)
		cls.write_debug_log()
		if isinstance(sys.stdout, Logger):
			sys.stdout.LOG_ERROR = True

# Top-level alias kept because dprint is the most-used helper in the codebase.
dprint = Logger.dprint
