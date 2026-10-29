# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)
#
# PySide abstraction layer, partly contributed by J-Fox

import os, platform
from .Logging import dprint

try:
	from PySide6 import QtCore
	from PySide6 import QtWidgets
	from PySide6 import QtGui
	from PySide6.QtWidgets import QApplication
	psversion = 6

except ModuleNotFoundError:
	try:
		import PySide2 # pyright: ignore[reportMissingImports]
		import PIL
		# PySide2>=5.14 is required
		major, minor, *_ = PySide2.__version_info__
		if (major, minor) < (5, 14):
			raise ImportError('Requires PySide2>=5.14', name=PySide2.__package__, path=PySide2.__path__)
		# Pillow<10.0.0 is required
		major, minor = map(int, PIL.__version__.split('.')[:2])
		if (major, minor) >= (10, 0):
			raise ImportError('Requires Pillow<10.0.0 if using PySide2', name=PIL.__package__, path=PIL.__path__)

		dprint("PySide6 cannot be loaded. Using PySide2 code path.")
		from PySide2 import QtCore # pyright: ignore[reportMissingImports]
		from PySide2 import QtWidgets # pyright: ignore[reportMissingImports]
		from PySide2 import QtGui # pyright: ignore[reportMissingImports]
		from PySide2.QtWidgets import QApplication # pyright: ignore[reportMissingImports]
		psversion = 2

		os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
		os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
		QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
		QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

	except ImportError as err2:
		dprint("GUI cannot be loaded.")
		raise err2

	except ModuleNotFoundError as err3:
		dprint("GUI cannot be loaded.")
		raise err3

# exec
for qt_class in (QApplication, QtWidgets.QFileDialog, QtWidgets.QMessageBox, QtWidgets.QDialog, QtCore.QEventLoop):
	try:
		if not callable(getattr(qt_class, "exec", None)):
			qt_class.exec = qt_class.exec_
		if not callable(getattr(qt_class, "exec_", None)):
			qt_class.exec_ = qt_class.exec
	except (AttributeError, TypeError):
		pass

# QDesktopWidget
class QDesktopWidget(object):
	def screenGeometry(self, widget):
		if psversion == 2:
			return QtWidgets.QDesktopWidget().screenGeometry()
		else:
			return widget.screen().geometry()

# QActionGroup
if psversion == 2:
	QActionGroup = QtWidgets.QActionGroup
else:
	QActionGroup = QtGui.QActionGroup

# Taskbar Progress
if platform.system() == "Windows":
	if psversion == 2:
		try:
			from PySide2 import QtWinExtras # pyright: ignore[reportMissingImports]
		except ImportError:
			pass
	else:
		import ctypes, types
		from ctypes import POINTER, WINFUNCTYPE, byref, c_int, c_long, c_ulonglong, c_ubyte, c_void_p, c_wchar_p, wintypes

		class _QWinTaskbarProgress:
			def __init__(self):
				self._tb = None
				self._hwnd = None
				self._min, self._max, self._value = 0, 100, 0
				self._visible, self._paused = False, False

			def _bind(self, hwnd):
				self._hwnd = wintypes.HWND(int(hwnd))
				self._tb = c_void_p()
				ole = ctypes.windll.ole32
				ole.CoInitialize(None)
				clsid, iid = (c_ubyte * 16)(), (c_ubyte * 16)()
				ole.CLSIDFromString(c_wchar_p("{56FDF344-FD6D-11D0-958A-006097C9A090}"), clsid)
				ole.CLSIDFromString(c_wchar_p("{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"), iid)
				ole.CoCreateInstance(clsid, None, 1, iid, byref(self._tb))
				self._call(3, WINFUNCTYPE(c_long, c_void_p))  # HrInit

			def _call(self, idx, proto, *args):
				return proto(ctypes.cast(self._tb, POINTER(POINTER(c_void_p)))[0][idx])(self._tb, *args)

			def _apply(self):
				if self._tb is None:
					return
				if not self._visible:
					state = 0  # TBPF_NOPROGRESS
				elif self._max - self._min <= 0:
					state = 1  # TBPF_INDETERMINATE
				else:
					state = 8 if self._paused else 2  # TBPF_PAUSED / TBPF_NORMAL
				self._call(10, WINFUNCTYPE(c_long, c_void_p, wintypes.HWND, c_int), self._hwnd, state)
				if state in (2, 8):
					span = self._max - self._min
					self._call(9, WINFUNCTYPE(c_long, c_void_p, wintypes.HWND, c_ulonglong, c_ulonglong), self._hwnd, c_ulonglong(max(0, min(span, self._value - self._min))), c_ulonglong(span))

			def setRange(self, minimum, maximum):
				self._min, self._max = int(minimum), int(maximum); self._apply()

			def setValue(self, value):
				self._value = int(value); self._apply()

			def setVisible(self, visible):
				self._visible = bool(visible); self._apply()

			def setPaused(self, paused):
				self._paused = bool(paused); self._apply()

		class _QWinTaskbarButton:
			def __init__(self):
				self._progress = _QWinTaskbarProgress()
			def progress(self):
				return self._progress
			def setWindow(self, window):
				self._progress._bind(int(window.winId()))

		class _QtWin:
			@staticmethod
			def setCurrentProcessExplicitAppUserModelID(app_id):
				ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(c_wchar_p(app_id))

		QtWinExtras = types.ModuleType("QtWinExtras")
		QtWinExtras.QWinTaskbarButton = _QWinTaskbarButton
		QtWinExtras.QtWin = _QtWin
elif platform.system() == "Linux":
	import types

	try:
		if psversion == 2:
			from PySide2 import QtDBus # pyright: ignore[reportMissingImports]
		else:
			from PySide6 import QtDBus
	except ImportError:
		pass
	else:
		class _QWinTaskbarProgress:
			_SIGNAL_PATH = "/com/canonical/unity/launcherentry/1"
			_SIGNAL_INTERFACE = "com.canonical.Unity.LauncherEntry"
			_SIGNAL_NAME = "Update"

			def __init__(self):
				self._min, self._max, self._value = 0, 100, 0
				self._visible, self._paused = False, False
				app_name = os.environ.get("FLASHGBX_DESKTOP_FILE", "").strip()
				app = QtWidgets.QApplication.instance()
				if app_name == "":
					app_name = app.applicationName().strip() if app is not None else ""
				if app_name == "":
					desktop_file_name = getattr(QtGui.QGuiApplication, "desktopFileName", None)
					if callable(desktop_file_name):
						try:
							app_name = str(desktop_file_name()).strip()
						except Exception:
							app_name = ""
				if app_name == "":
					app_name = "flashgbx"
				desktop_file = os.path.basename(app_name)
				if not desktop_file.endswith(".desktop"):
					desktop_file += ".desktop"
				self._app_uri = "application://{:s}".format(desktop_file) if desktop_file else ""
				self._last_payload = None
				self._bus = QtDBus.QDBusConnection.sessionBus()
				self._available = bool(self._app_uri) and bool(self._bus.isConnected())
				if not self._bus.isConnected():
					dprint("Unity Launcher progress disabled: no DBus session bus.")

			def _apply(self):
				if not self._available:
					return
				span = self._max - self._min
				progress_visible = bool(self._visible and span > 0)
				if progress_visible:
					progress = float(self._value - self._min) / float(span)
					progress = max(0.0, min(1.0, progress))
				else:
					progress = 0.0
				state = (progress_visible, float(progress), bool(self._paused and progress_visible))
				if state == self._last_payload:
					return
				self._last_payload = state
				payload = {
					"progress-visible": bool(state[0]),
					"progress": float(state[1]),
				}
				sent = False
				try:
					message = QtDBus.QDBusMessage.createSignal(self._SIGNAL_PATH, self._SIGNAL_INTERFACE, self._SIGNAL_NAME)
					message.setArguments([self._app_uri, payload])
					if self._bus.send(message):
						sent = True
					if not sent:
						dprint("Unity Launcher progress disabled: launcher API not available in this desktop environment.")
				except Exception as err:
					dprint("Unity Launcher progress update failed: {:s}".format(str(err)))

			def setRange(self, minimum, maximum):
				self._min, self._max = int(minimum), int(maximum)
				self._apply()

			def setValue(self, value):
				self._value = int(value)
				self._apply()

			def setVisible(self, visible):
				self._visible = bool(visible)
				self._apply()

			def setPaused(self, paused):
				self._paused = bool(paused)
				self._apply()

		class _QWinTaskbarButton:
			def __init__(self):
				self._progress = _QWinTaskbarProgress()

			def progress(self):
				return self._progress

			def setWindow(self, window):
				pass

		class _QtWin:
			@staticmethod
			def setCurrentProcessExplicitAppUserModelID(app_id):
				pass

		QtWinExtras = types.ModuleType("QtWinExtras")
		QtWinExtras.QWinTaskbarButton = _QWinTaskbarButton
		QtWinExtras.QtWin = _QtWin


__all__ = ['QtCore', 'QtWidgets', 'QtGui', 'QApplication', 'QDesktopWidget', 'QActionGroup']

def GetQtVersion():
	return tuple(map(int, QtCore.qVersion().split(".")))

def IsDarkMode():
	if GetQtVersion() < (6, 5, 0):
		return False
	try:
		scheme = QtGui.QGuiApplication.styleHints().colorScheme()
		if scheme == QtCore.Qt.ColorScheme.Dark:
			return True
	except Exception:
		pass
	return False

def bitmap2pixmap(data, scale_factor=4):
	try:
		from PIL.ImageQt import ImageQt
		from PIL import Image
		data_converted = data.convert("RGBA")
		pixmap = QtGui.QPixmap.fromImage(ImageQt(data_converted.resize(
			(data_converted.width * scale_factor, data_converted.height * scale_factor),
			Image.NEAREST,
		)))
		pixmap.setDevicePixelRatio(scale_factor)
		return pixmap
	except Exception as e:
		dprint("Couldn’t convert bitmap to pixmap. Error: {error}", error=str(e))
		return False
