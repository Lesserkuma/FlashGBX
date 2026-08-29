# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import sys, os, time, datetime, json, platform, subprocess, requests, webbrowser, threading, calendar, queue, urllib.parse, re, html
from .pyside import QtCore, QtWidgets, QtGui, QApplication, QActionGroup
from serial import SerialException
from packaging import version
from .RomFileDMG import RomFileDMG
from .RomFileAGB import RomFileAGB
from .PocketCameraWindow import PocketCameraWindow
from .InteractiveConsoleWindow import InteractiveConsoleWindow
from .UserInputDialog import UserInputDialog
from .Mapper import DMG_Mapper
from .app import AppInfo, AppContext, generate_filename, HW_DEVICES
from .CartridgeTypes import RomSizes, AgbSaveTypes, DmgSaveTypes
from .i18n import LANGUAGES, CONFIGURED_LANGUAGE, __, c__, ___, loadQtTranslation, format_decimal, init_language
from .Logging import Logger, dprint
from .Progress import Progress
from .Formatter import Formatter
from .IniSettings import IniSettings
from .Flashcart import empty_flashcarts_map, has_3v_compatible_profile
from .RomFileDMG import from_isx
from .Mapper import ConvertMapperToMapperType, ConvertMapperTypeToMapper, get_mbc_name, save_size_includes_rtc, compare_mbc
from .pyside import bitmap2pixmap, GetQtVersion, IsDarkMode

SAVE_EXTS = (".sav", ".srm", ".fla", ".eep")
ROM_EXTS_DMG = (".gb", ".sgb", ".gbc", ".bin", ".isx")
ROM_EXTS_AGB = (".gba", ".srl", ".bin")
ROM_EXTS_DMG_READ = (".gb", ".sgb", ".gbc")
DROP_ROM_EXTS_ALL = ROM_EXTS_DMG + ROM_EXTS_AGB

class FlashGBX_GUI(QtWidgets.QMainWindow):
	CONN = None
	SETTINGS = None
	DEVICES = {}
	FLASHCARTS = empty_flashcarts_map()
	APP_PATH = ""
	CONFIG_PATH = ""
	TBPROG = None # Taskbar progress handle (platform-dependent)
	PROGRESS = None
	CAMWIN = None
	FWUPWIN = None
	INTWIN = None
	STATUS = {}
	TEXT_COLOR = (0, 0, 0, 255)
	MSGBOX_QUEUE = queue.Queue()
	MSGBOX_DISPLAYING = False
	DEFAULT_STYLESHEET = None

	def __init__(self, args):
		sys.excepthook = Logger.exception_hook
		self.SETTINGS = IniSettings(path=args["config_path"] + os.sep + "settings.ini")
		self.FLASHCARTS = args["flashcarts"]
		self.PROGRESS = Progress(self.UpdateProgress, self.WaitProgress)

		try:
			if GetQtVersion() >= (6, 5, 0):
				if self.SETTINGS.value("AllowDarkMode", default="enabled") == "disabled":
					QtGui.QGuiApplication.styleHints().setColorScheme(QtCore.Qt.ColorScheme.Light)
			if platform.system() == "Windows":
				qt_app.setStyle("fusion" if IsDarkMode() else "windowsvista")
		except:
			pass

		QtWidgets.QMainWindow.__init__(self)
		AppContext.CONFIG_PATH = args['config_path']
		AppContext.APP_PATH = args['app_path']

		self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
		self.setWindowTitle("{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION))
		# self.setContentsMargins(0, 0, 0, 0)
		self.TEXT_COLOR = QtGui.QPalette().color(QtGui.QPalette.Text).toTuple()

		# Create the QtWidgets.QVBoxLayout that lays out the whole form
		self.layout = QtWidgets.QGridLayout()
		self.layout_left = QtWidgets.QVBoxLayout()
		self.layout_right = QtWidgets.QVBoxLayout()

		# Cartridge Information GroupBox
		self.grpDMGCartridgeInfo = self.GuiCreateGroupBoxDMGCartInfo()
		self.grpAGBCartridgeInfo = self.GuiCreateGroupBoxAGBCartInfo()
		self.grpAGBCartridgeInfo.setVisible(False)
		self.layout_left.addWidget(self.grpDMGCartridgeInfo)
		self.layout_left.addWidget(self.grpAGBCartridgeInfo)

		# Actions
		self.grpActions = QtWidgets.QGroupBox()
		self.grpActionsLayout = QtWidgets.QVBoxLayout()
		self.grpActionsLayout.setContentsMargins(-1, 3, -1, -1)

		rowActionsMode = QtWidgets.QHBoxLayout()
		self.lblMode = QtWidgets.QLabel()
		rowActionsMode.addWidget(self.lblMode)
		self.optDMG = QtWidgets.QRadioButton()
		self.connect(self.optDMG, QtCore.SIGNAL("clicked()"), self.SetMode)
		self.optAGB = QtWidgets.QRadioButton()
		self.connect(self.optAGB, QtCore.SIGNAL("clicked()"), self.SetMode)
		rowActionsMode.addWidget(self.optDMG)
		rowActionsMode.addWidget(self.optAGB)

		rowActionsGeneral1 = QtWidgets.QHBoxLayout()
		self.btnHeaderRefresh = QtWidgets.QPushButton()
		self.btnHeaderRefresh.setMinimumHeight(25)
		self.btnHeaderRefresh.setMinimumWidth(140)
		self.connect(self.btnHeaderRefresh, QtCore.SIGNAL("clicked()"), self.ReadCartridge)
		rowActionsGeneral1.addWidget(self.btnHeaderRefresh)

		self.btnDetectCartridge = QtWidgets.QPushButton()
		self.btnDetectCartridge.setMinimumHeight(25)
		self.btnDetectCartridge.setMinimumWidth(140)
		self.connect(self.btnDetectCartridge, QtCore.SIGNAL("clicked()"), self.DetectCartridge)
		rowActionsGeneral1.addWidget(self.btnDetectCartridge)

		rowActionsGeneral2 = QtWidgets.QHBoxLayout()
		self.btnBackupROM = QtWidgets.QPushButton()
		self.btnBackupROM.setMinimumHeight(25)
		self.btnBackupROM.setMinimumWidth(140)
		self.connect(self.btnBackupROM, QtCore.SIGNAL("clicked()"), self.BackupROM)
		rowActionsGeneral2.addWidget(self.btnBackupROM)
		self.btnBackupRAM = QtWidgets.QPushButton()
		self.btnBackupRAM.setMinimumHeight(25)
		self.btnBackupRAM.setMinimumWidth(140)
		self.connect(self.btnBackupRAM, QtCore.SIGNAL("clicked()"), self.BackupRAM)
		rowActionsGeneral2.addWidget(self.btnBackupRAM)

		self.cmbDMGCartridgeTypeResult.currentIndexChanged.connect(self.CartridgeTypeChanged)
		self.cmbDMGHeaderMapperResult.currentIndexChanged.connect(self.DMGMapperTypeChanged)

		rowActionsGeneral3 = QtWidgets.QHBoxLayout()
		self.btnFlashROM = QtWidgets.QPushButton()
		self.btnFlashROM.setMinimumHeight(25)
		self.btnFlashROM.setMinimumWidth(140)
		self.connect(self.btnFlashROM, QtCore.SIGNAL("clicked()"), self.FlashROM)
		rowActionsGeneral3.addWidget(self.btnFlashROM)
		self.btnRestoreRAM = QtWidgets.QPushButton()
		self.mnuRestoreRAM = QtWidgets.QMenu()
		self.mnuRestoreRAM.addAction("", self.WriteRAM)
		self.mnuRestoreRAM.addAction("", lambda: self.WriteRAM(erase=True))
		self.mnuRestoreRAM.addSeparator()
		self.mnuRestoreRAM.addAction("", lambda: self.WriteRAM(test=True))
		self.btnRestoreRAM.setMenu(self.mnuRestoreRAM)
		self.btnRestoreRAM.setMinimumHeight(25)
		self.btnRestoreRAM.setMinimumWidth(140)
		rowActionsGeneral3.addWidget(self.btnRestoreRAM)

		self.grpActionsLayout.setSpacing(4)
		self.grpActionsLayout.addLayout(rowActionsMode)
		self.grpActionsLayout.addLayout(rowActionsGeneral1)
		self.grpActionsLayout.addLayout(rowActionsGeneral2)
		self.grpActionsLayout.addLayout(rowActionsGeneral3)
		self.grpActions.setLayout(self.grpActionsLayout)

		self.layout_right.addWidget(self.grpActions)

		# Transfer Status
		self.grpStatus = QtWidgets.QGroupBox()
		grpStatusLayout = QtWidgets.QVBoxLayout()
		grpStatusLayout.setContentsMargins(-1, 3, -1, -1)
		if platform.system() == "Linux":
			grpStatusLayout.setSpacing(4)

		rowStatus1a = QtWidgets.QHBoxLayout()
		self.lblStatus1a = QtWidgets.QLabel()
		rowStatus1a.addWidget(self.lblStatus1a)
		self.lblStatus1aResult = QtWidgets.QLabel("–")
		rowStatus1a.addWidget(self.lblStatus1aResult)
		grpStatusLayout.addLayout(rowStatus1a)
		rowStatus2a = QtWidgets.QHBoxLayout()
		self.lblStatus2a = QtWidgets.QLabel()
		rowStatus2a.addWidget(self.lblStatus2a)
		self.lblStatus2aResult = QtWidgets.QLabel("–")
		rowStatus2a.addWidget(self.lblStatus2aResult)
		grpStatusLayout.addLayout(rowStatus2a)
		rowStatus3a = QtWidgets.QHBoxLayout()
		self.lblStatus3a = QtWidgets.QLabel()
		rowStatus3a.addWidget(self.lblStatus3a)
		self.lblStatus3aResult = QtWidgets.QLabel("–")
		rowStatus3a.addWidget(self.lblStatus3aResult)
		grpStatusLayout.addLayout(rowStatus3a)
		rowStatus4a = QtWidgets.QHBoxLayout()
		self.lblStatus4a = QtWidgets.QLabel()
		self.lblStatus4a.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
		rowStatus4a.addWidget(self.lblStatus4a)
		self.lblStatus4aResult = QtWidgets.QLabel("")
		self.lblStatus4aResult.setVisible(False)
		rowStatus4a.addWidget(self.lblStatus4aResult)
		self.lblStatus5a = QtWidgets.QLabel("")
		self.lblStatus5a.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
		rowStatus4a.addWidget(self.lblStatus5a, 1)
		grpStatusLayout.addLayout(rowStatus4a)

		rowStatus2 = QtWidgets.QHBoxLayout()
		self.prgStatus = QtWidgets.QProgressBar()
		self.SetProgressBars(min=0, max=1, value=0)
		rowStatus2.addWidget(self.prgStatus)
		self.btnCancel = QtWidgets.QPushButton()
		self.btnCancel.setEnabled(False)
		self.connect(self.btnCancel, QtCore.SIGNAL("clicked()"), self.AbortOperation)
		rowStatus2.addWidget(self.btnCancel)

		grpStatusLayout.addLayout(rowStatus2)
		self.grpStatus.setLayout(grpStatusLayout)

		self.layout_right.addWidget(self.grpStatus)

		self.layout.addLayout(self.layout_left, 0, 0)
		self.layout.addLayout(self.layout_right, 0, 1)

		self.layout_devices = QtWidgets.QHBoxLayout()
		self.lblDevice = QtWidgets.QLabel()
		self.lblDevice.mousePressEvent = lambda event: [ self.WriteDebugLog(event, open_log=True) ]
		self.lblDevice.setToolTip("")
		self.lblDevice.setCursor(QtCore.Qt.PointingHandCursor)
		self.cmbDevice = QtWidgets.QComboBox()
		self.cmbDevice.setStyleSheet("QComboBox { border: 0; margin: 0; padding: 0; max-width: 0px; }")
		self.lblWarning = QtWidgets.QLabel("⚠️")
		self.lblWarning.mousePressEvent = lambda event: [ self.WriteDebugLog(event, open_log=True) ]
		self.lblWarning.setToolTip("")
		self.lblWarning.setCursor(QtCore.Qt.PointingHandCursor)
		self.lblWarning.setVisible(False)

		self.layout_devices.addWidget(self.lblDevice)
		self.layout_devices.addWidget(self.cmbDevice)
		self.layout_devices.addWidget(self.lblWarning)
		self.layout_devices.addStretch()

		self.mnuTools = QtWidgets.QMenu()
		self.mnuTools.addAction("", self.ShowPocketCameraWindow)
		self.mnuTools.addAction("", self.ShowInteractiveConsoleWindow)
		self.mnuTools.addSeparator()
		self.mnuTools.addAction("", self.ShowFirmwareUpdateWindow)
		self.mnuTools.actions()[1].setEnabled(False)

		self.mnuConfig = QtWidgets.QMenu()
		self.mnuConfig.addAction("", lambda: [ self.EnableUpdateCheck() ])
		self.mnuConfig.addAction("", lambda: self.SETTINGS.setValue("SaveFileNameAddDateTime", str(self.mnuConfig.actions()[1].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("", lambda: self.SETTINGS.setValue("PreferChipErase", str(self.mnuConfig.actions()[2].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("", lambda: self.SETTINGS.setValue("VerifyData", str(self.mnuConfig.actions()[3].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("", lambda: self.SETTINGS.setValue("AutoDetectLimitVoltage", str(self.mnuConfig.actions()[4].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("", lambda: [ self.SETTINGS.setValue("LimitBaudRate", str(self.mnuConfig.actions()[5].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")), self.SetLimitBaudRate() ])
		self.mnuConfig.addAction("", lambda: self.SETTINGS.setValue("GenerateDumpReports", str(self.mnuConfig.actions()[6].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("", lambda: self.SETTINGS.setValue("UseNoIntroFilenames", str(self.mnuConfig.actions()[7].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("", lambda: [ self.SETTINGS.setValue("AutoPowerOff", str(self.mnuConfig.actions()[8].isChecked()).lower().replace("true", "350").replace("false", "0")), self.SetAutoPowerOff() ])
		self.mnuConfig.addAction("", lambda: self.SETTINGS.setValue("CompareSectors", str(self.mnuConfig.actions()[9].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("", lambda: self.SETTINGS.setValue("ForceWrPullup", str(self.mnuConfig.actions()[10].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addSeparator()
		self.mnuConfigReadModeAGB = QtWidgets.QMenu()
		self.mnuConfigReadModeAGB.addAction("", lambda: [ self.SETTINGS.setValue("AGBReadMethod", str(self.mnuConfigReadModeAGB.actions()[1].isChecked()).lower().replace("true", "2")), self.SetAGBReadMethod() ])
		self.mnuConfigReadModeAGB.addAction("", lambda: [ self.SETTINGS.setValue("AGBReadMethod", str(self.mnuConfigReadModeAGB.actions()[0].isChecked()).lower().replace("true", "0")), self.SetAGBReadMethod() ])
		self.mnuConfigReadModeAGB.actions()[0].setCheckable(True)
		self.mnuConfigReadModeAGB.actions()[1].setCheckable(True)
		self.mnuConfigReadModeAGB.actions()[0].setChecked(self.SETTINGS.value("AGBReadMethod", default="2") == "2")
		self.mnuConfigReadModeAGB.actions()[1].setChecked(self.SETTINGS.value("AGBReadMethod", default="2") == "0")
		self.mnuConfigReadModeDMG = QtWidgets.QMenu()
		self.mnuConfigReadModeDMG.addAction("", lambda: [ self.SETTINGS.setValue("DMGReadMethod", str(self.mnuConfigReadModeDMG.actions()[0].isChecked()).lower().replace("true", "1")), self.SetDMGReadMethod() ])
		self.mnuConfigReadModeDMG.addAction("", lambda: [ self.SETTINGS.setValue("DMGReadMethod", str(self.mnuConfigReadModeDMG.actions()[1].isChecked()).lower().replace("true", "2")), self.SetDMGReadMethod() ])
		self.mnuConfigReadModeDMG.actions()[0].setCheckable(True)
		self.mnuConfigReadModeDMG.actions()[1].setCheckable(True)
		self.mnuConfigReadModeDMG.actions()[0].setChecked(self.SETTINGS.value("DMGReadMethod", default="1") == "1")
		self.mnuConfigReadModeDMG.actions()[1].setChecked(self.SETTINGS.value("DMGReadMethod", default="1") == "2")
		self.mnuConfig.addMenu(self.mnuConfigReadModeDMG)
		self.mnuConfig.addMenu(self.mnuConfigReadModeAGB)
		self.mnuConfig.addSeparator()
		self.mnuConfig.addAction("", self.ReEnableMessages)
		self.mnuConfig.actions()[0].setCheckable(True)
		self.mnuConfig.actions()[1].setCheckable(True)
		self.mnuConfig.actions()[2].setCheckable(True)
		self.mnuConfig.actions()[3].setCheckable(True)
		self.mnuConfig.actions()[4].setCheckable(True)
		self.mnuConfig.actions()[5].setCheckable(True)
		self.mnuConfig.actions()[6].setCheckable(True)
		self.mnuConfig.actions()[7].setCheckable(True)
		self.mnuConfig.actions()[8].setCheckable(True)
		self.mnuConfig.actions()[9].setCheckable(True)
		self.mnuConfig.actions()[10].setCheckable(True)
		self.mnuConfig.actions()[0].setChecked(self.SETTINGS.value("UpdateCheck") == "enabled")
		self.mnuConfig.actions()[1].setChecked(self.SETTINGS.value("SaveFileNameAddDateTime", default="disabled") == "enabled")
		self.mnuConfig.actions()[2].setChecked(self.SETTINGS.value("PreferChipErase", default="disabled") == "enabled")
		self.mnuConfig.actions()[3].setChecked(self.SETTINGS.value("VerifyData", default="enabled") == "enabled")
		self.mnuConfig.actions()[4].setChecked(self.SETTINGS.value("AutoDetectLimitVoltage", default="disabled") == "enabled")
		self.mnuConfig.actions()[5].setChecked(self.SETTINGS.value("LimitBaudRate", default="disabled") == "enabled")
		self.mnuConfig.actions()[6].setChecked(self.SETTINGS.value("GenerateDumpReports", default="disabled") == "enabled")
		self.mnuConfig.actions()[7].setChecked(self.SETTINGS.value("UseNoIntroFilenames", default="enabled") == "enabled")
		self.mnuConfig.actions()[8].setChecked(self.SETTINGS.value("AutoPowerOff", default="350") != "0")
		self.mnuConfig.actions()[9].setChecked(self.SETTINGS.value("CompareSectors", default="enabled") == "enabled")
		self.mnuConfig.actions()[10].setChecked(self.SETTINGS.value("ForceWrPullup", default="disabled") == "enabled")

		self.mnuLanguage = QtWidgets.QMenu()
		self.languageActionGroup = QActionGroup(self.mnuLanguage)
		self.languageActionGroup.setExclusive(True)
		for code, names in sorted(LANGUAGES.items()):
			if isinstance(names, tuple):
				native_name = names[1]
			else:
				native_name = names
			action = self.mnuLanguage.addAction(native_name + (" ({})".format(code)))
			action.setCheckable(True)
			action.triggered.connect(lambda _checked=False, lang=code: self.ChangeLanguage(lang))
			self.languageActionGroup.addAction(action)
			if code == CONFIGURED_LANGUAGE:
				action.setChecked(True)

		self.mnuThirdParty = QtWidgets.QMenu()
		self.mnuDeviceSupport = self.mnuThirdParty.addAction("", self.AboutConnectedDevice)
		self.mnuDeviceSupport.setVisible(False)
		self.mnuThirdParty.addAction("", lambda: [ QtWidgets.QMessageBox.aboutQt(None) ])
		self.mnuThirdParty.addAction("", self.AboutGameDB)
		self.mnuThirdParty.addAction("", lambda: [ self.OpenPath(AppContext.APP_PATH + os.sep + os.path.join("res", "Third Party Notices.md")) ])

		self.btnMainMenu = QtWidgets.QPushButton()
		self.mnuMainMenu = QtWidgets.QMenu()
		self.mnuMainMenu.addMenu(self.mnuConfig)
		self.mnuMainMenu.addMenu(self.mnuTools)
		self.mnuMainMenu.addMenu(self.mnuLanguage)
		self.mnuMainMenu.addSeparator()
		self.mnuMainMenu.addSeparator()
		self.mnuMainMenu.addAction("", self.OpenPath)
		self.mnuMainMenu.addSeparator()
		self.mnuMainMenu.addMenu(self.mnuThirdParty)
		self.mnuMainMenu.addAction("", self.AboutFlashGBX)
		self.btnMainMenu.setMenu(self.mnuMainMenu)

		self.btnConnect = QtWidgets.QPushButton()
		self.connect(self.btnConnect, QtCore.SIGNAL("clicked()"), self.ConnectDevice)
		self.layout_devices.addWidget(self.btnMainMenu)
		self.layout_devices.addWidget(self.btnConnect)
		
		if platform.system() == "Linux":
			self.layout.setHorizontalSpacing(8)
			self.layout.setVerticalSpacing(5)
			self.layout_left.setSpacing(5)
			self.layout_right.setSpacing(5)
			self.layout_devices.setSpacing(6)

		self.InitWidgetTexts()

		self.layout.addLayout(self.layout_devices, 1, 0, 1, 0)

		# Disable widgets
		self.optAGB.setEnabled(False)
		self.optDMG.setEnabled(False)
		self.btnHeaderRefresh.setEnabled(False)
		self.btnDetectCartridge.setEnabled(False)
		self.btnBackupROM.setEnabled(False)
		self.btnFlashROM.setEnabled(False)
		self.btnBackupRAM.setEnabled(False)
		self.btnRestoreRAM.setEnabled(False)
		self.btnConnect.setEnabled(False)
		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)

		# Set the main layout on a central widget for QMainWindow
		self.central_widget = QtWidgets.QWidget()
		self.central_widget.setContentsMargins(0, 0, 0, 0)
		self.central_widget.setLayout(self.layout)
		self.setCentralWidget(self.central_widget)

		# Show app window first, then do update check
		self.QT_APP = qt_app
		qt_app.processEvents()

		config_ret = args["config_ret"]
		for i in range(0, len(config_ret)):
			if config_ret[i][0] == 0:
				print(config_ret[i][1])
			elif config_ret[i][0] == 1:
				QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), config_ret[i][1], QtWidgets.QMessageBox.Ok)
			elif config_ret[i][0] == 2:
				QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), config_ret[i][1], QtWidgets.QMessageBox.Ok)
			elif config_ret[i][0] == 3:
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), config_ret[i][1], QtWidgets.QMessageBox.Ok)

		self.DEFAULT_STYLESHEET = self.lblDevice.styleSheet()

		if platform.system() == "Windows":
			# Warm up fallback font rendering to prevent lag on first use later
			l = QtGui.QTextLayout("⚠️")
			l.beginLayout()
			l.createLine()
			l.endLayout()

		QtCore.QTimer.singleShot(1, lambda: [ self.UpdateCheck(), self.FindDevices(port=args["argparsed"].device_port, firstRun=True) ])
		self.MSGBOX_TIMER = QtCore.QTimer()
		self.MSGBOX_TIMER.timeout.connect(self.MsgBoxCheck)
		self.MSGBOX_TIMER.start(200)
		self.LOG_ERROR_TIMER = QtCore.QTimer()
		self.LOG_ERROR_TIMER.timeout.connect(self.LogErrorCheck)
		self.LOG_ERROR_TIMER.start(200)

	def _GetAutoPlatformMode(self, conn=None, supported_modes=None):
		if conn is None:
			conn = self.CONN
		if conn is None:
			return None
		if supported_modes is None:
			supported_modes = conn.GetSupprtedModes()
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

	def _UpdatePlatformModeFromFirmware(self):
		if self.CONN is None:
			return
		if not (self.CONN.CanSetVoltageByAutoswitch() and not self.CONN.CanSetVoltageByCode()):
			return

		auto_mode = self._GetAutoPlatformMode(self.CONN)
		if auto_mode not in ("DMG", "AGB"):
			return
		if auto_mode == "DMG":
			self.optDMG.setChecked(True)
		else:
			self.optAGB.setChecked(True)
		self.SetMode()

	def MsgBoxCheck(self):
		if not self.MSGBOX_DISPLAYING and not self.MSGBOX_QUEUE.empty():
			self.MSGBOX_DISPLAYING = True
			msgbox = self.MSGBOX_QUEUE.get()
			dprint(f"Processing Message Box: {msgbox}")
			msgbox.exec()
			self.MSGBOX_DISPLAYING = False

	def LogErrorCheck(self):
		if isinstance(sys.stdout, Logger) and sys.stdout.LOG_ERROR is True:
			self.lblWarning.setVisible(True)

	def SetDMGPlatformBadge(self, data=None):
		base = "QLabel { border-radius: 4px; padding: 0px 6px; font-weight: bold; font-size: 10px; }"
		if data is None:
			self.lblDMGPlatformBadge.setText("")
			self.lblDMGPlatformBadge.setStyleSheet("")
			self.lblDMGPlatformBadge.setToolTip("")
			self.lblDMGPlatformBadge.setVisible(False)
			return
		cgb = data.get("cgb", 0)
		sgb = data.get("sgb", 0)
		old_lic = data.get("old_lic", 0)
		if cgb == 0xC0:
			text = "CGB"
			tooltip = __("Game Boy Color exclusive")
			style = (
				"QLabel {"
				" background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
				"  stop:0 rgba(255,60,60,115), stop:0.25 rgba(255,180,30,115),"
				"  stop:0.5 rgba(40,200,80,115), stop:0.75 rgba(50,140,255,115),"
				"  stop:1 rgba(160,70,255,115));"
				" color: #ffffff;"
				" border: 1px solid rgba(255,255,255,115);"
				" border-radius: 4px; padding: 0px 6px;"
				" font-weight: bold; font-size: 10px;"
				"}"
			)
		elif cgb == 0x80:
			text = "CGB"
			tooltip = __("Game Boy Color")
			style = base + (
				"QLabel {"
				" background-color: rgba(124, 92, 252, 51);"
				" color: #a78bfa;"
				" border: 1px solid rgba(124, 92, 252, 89);"
				"}"
			)
		elif old_lic == 0x33 and sgb == 0x03:
			text = "SGB"
			tooltip = __("Super Game Boy")
			style = base + (
				"QLabel {"
				" background-color: rgba(63, 220, 142, 38);"
				" color: #3fdc8e;"
				" border: 1px solid rgba(63, 220, 142, 76);"
				"}"
			)
		else:
			text = "DMG"
			tooltip = __("Original Game Boy")
			style = base + (
				"QLabel {"
				" background-color: rgba(148, 163, 184, 31);"
				" color: #94a3b8;"
				" border: 1px solid rgba(148, 163, 184, 64);"
				"}"
			)
		self.lblDMGPlatformBadge.setText(text)
		self.lblDMGPlatformBadge.setToolTip(tooltip)
		self.lblDMGPlatformBadge.setStyleSheet(style)
		self.lblDMGPlatformBadge.setVisible(True)
		self._UpdateDMGGameNameLayout()

	def SetDMGGameNameText(self, text):
		self._dmgGameNameFullText = text or ""
		self.lblDMGGameNameResult.setText(self._dmgGameNameFullText)
		self._UpdateDMGGameNameLayout()
		if self.lblDMGGameNameResult.text() != self._dmgGameNameFullText:
			self.lblDMGGameNameResult.setToolTip(self._dmgGameNameFullText)
		else:
			self.lblDMGGameNameResult.setToolTip("")

	def _UpdateDMGGameNameLayout(self):
		if not hasattr(self, "_rowDMGGameName"):
			return
		default_col_w = self._dmgGameNameDefaultColWidth
		if default_col_w <= 0:
			return
		row_w = self._rowDMGGameName.geometry().width()
		if row_w <= 0:
			return

		label = self.lblDMGGameName
		result = self.lblDMGGameNameResult
		badge = self.lblDMGPlatformBadge
		full_text = self._dmgGameNameFullText

		fm = result.fontMetrics()
		text_w = fm.horizontalAdvance(full_text)

		outer_spacing = self._rowDMGGameName.spacing()
		if outer_spacing < 0:
			outer_spacing = self.style().pixelMetric(QtWidgets.QStyle.PM_LayoutHorizontalSpacing)
			if outer_spacing < 0:
				outer_spacing = 6
		inner_spacing = max(self._resultDMGGameName.spacing(), 0)

		if badge.isVisible() and badge.text():
			badge_w = badge.sizeHint().width() + inner_spacing
		else:
			badge_w = 0

		# 2 px safety buffer for pixel rounding in text rendering
		reserved = outer_spacing + badge_w + 2

		table_avail = row_w - default_col_w - reserved
		if text_w <= table_avail:
			new_col_w = default_col_w
			elided = full_text
		else:
			label_fm = label.fontMetrics()
			margins = label.contentsMargins()
			natural_label_w = label_fm.horizontalAdvance(label.text()) + margins.left() + margins.right()
			natural_label_w = max(natural_label_w, 0)
			new_col_w = max(natural_label_w, row_w - reserved - text_w)
			new_col_w = min(new_col_w, default_col_w)
			avail = max(row_w - new_col_w - reserved, 0)
			elided = fm.elidedText(full_text, QtCore.Qt.ElideRight, avail) if text_w > avail else full_text

		if label.minimumWidth() != new_col_w or label.maximumWidth() != new_col_w:
			label.setMinimumWidth(new_col_w)
			label.setMaximumWidth(new_col_w)
		if result.text() != elided:
			result.setText(elided)

	def resizeEvent(self, event):
		super().resizeEvent(event)
		self._UpdateDMGGameNameLayout()

	def InitWidgetTexts(self):
		default_stylesheet = self.DEFAULT_STYLESHEET if self.DEFAULT_STYLESHEET is not None else ""
		for label in (
			self.lblDMGGameNameResult,
			self.lblDMGRomTitleResult,
			self.lblDMGGameCodeRevisionResult,
			self.lblDMGHeaderRtcResult,
			self.lblDMGHeaderBootlogoResult,
			self.lblDMGHeaderROMChecksumResult,
			self.lblAGBGameNameResult,
			self.lblAGBRomTitleResult,
			self.lblAGBHeaderGameCodeRevisionResult,
			self.lblAGBGpioRtcResult,
			self.lblAGBHeaderBootlogoResult,
			self.lblAGBHeaderChecksumResult,
			self.lblAGBHeaderROMChecksumResult,
		):
			label.clear()
			label.setStyleSheet(default_stylesheet)
			label.setToolTip("")
		self._dmgGameNameFullText = ""
		self._UpdateDMGGameNameLayout()
		self.lblDMGHeaderRtcResult.setCursor(QtCore.Qt.ArrowCursor)
		self.lblAGBGpioRtcResult.setCursor(QtCore.Qt.ArrowCursor)
		self.cmbDMGHeaderROMSizeResult.clear()
		self.cmbDMGHeaderSaveTypeResult.clear()
		self.cmbDMGHeaderMapperResult.clear()
		self.cmbDMGCartridgeTypeResult.clear()
		self.cmbAGBHeaderROMSizeResult.clear()
		self.cmbAGBSaveTypeResult.clear()
		self.cmbAGBCartridgeTypeResult.clear()
		self.lblStatus1aResult.setText("–")
		self.lblStatus2aResult.setText("–")
		self.lblStatus3aResult.setText("–")
		self.SetStatus4aResult("")
		self.SetDMGPlatformBadge(None)

		# DMG Cartridge Info
		self.grpDMGCartridgeInfo.setTitle(__("Game Boy Cartridge Information"))
		self.lblDMGGameName.setText(__("Game Name:"))
		self.lblDMGRomTitle.setText(__("ROM Title:"))
		self.lblDMGGameCodeRevision.setText(__("Game Code and Revision:"))
		self.lblDMGHeaderRtc.setText(__("Real Time Clock:"))
		self.lblDMGHeaderBootlogo.setText(__("Boot Logo:"))
		self.lblDMGHeaderROMChecksum.setText(__("ROM Checksum:"))
		self.lblDMGHeaderROMSize.setText(__("ROM Size:"))
		self.lblDMGHeaderSaveType.setText(__("Save Type:"))
		self.lblDMGHeaderMapper.setText(__("Mapper Type:"))
		self.lblDMGCartridgeType.setText(__("Profile:"))

		# AGB Cartridge Info
		self.grpAGBCartridgeInfo.setTitle(__("Game Boy Advance Cartridge Information"))
		self.lblAGBGameName.setText(__("Game Name:"))
		self.lblAGBRomTitle.setText(__("ROM Title:"))
		self.lblAGBHeaderGameCodeRevision.setText(__("Game Code and Revision:"))
		self.lblAGBGpioRtc.setText(__("Real Time Clock:"))
		self.lblAGBHeaderBootlogo.setText(__("Boot Logo:"))
		self.lblAGBHeaderChecksum.setText(__("Header Checksum:"))
		self.lblAGBHeaderROMChecksum.setText(__("ROM Checksum:"))
		self.lblAGBHeaderROMSize.setText(__("ROM Size:"))
		self.lblAGBHeaderSaveType.setText(__("Save Type:"))
		self.lblAGBCartridgeType.setText(__("Profile:"))

		# Actions
		self.grpActions.setTitle(__("Functions"))
		self.lblMode.setText(__("Plattform:") + " ")
		self.optDMG.setText(c__("Radio Button (& = Keyboard Shortcut)", "&Game Boy"))
		self.optAGB.setText(c__("Radio Button (& = Keyboard Shortcut)", "Game Boy &Advance"))
		self.btnHeaderRefresh.setText(c__("Button (& = Keyboard Shortcut)", "&Refresh"))
		self.btnDetectCartridge.setText(c__("Button (& = Keyboard Shortcut)", "Analyze &Flash Cart"))
		self.btnBackupROM.setText(c__("Button (& = Keyboard Shortcut)", "&Backup ROM"))
		self.btnBackupRAM.setText(c__("Button (& = Keyboard Shortcut)", "Backup &Save Data"))
		self.btnFlashROM.setText(c__("Button (& = Keyboard Shortcut)", "&Write ROM"))
		self.btnRestoreRAM.setText(c__("Button (& = Keyboard Shortcut)", "Writ&e Save Data"))
		self.mnuRestoreRAM.actions()[0].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Restore from save data file"))
		self.mnuRestoreRAM.actions()[1].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Erase cartridge save data"))
		self.mnuRestoreRAM.actions()[3].setText(c__("Menu Item (& = Keyboard Shortcut)", "Run stress &test"))

		# Transfer Status
		self.grpStatus.setTitle(__("Transfer Status"))
		self.lblStatus1a.setText(__("Data transferred:"))
		self.lblStatus2a.setText(__("Transfer rate:"))
		self.lblStatus3a.setText(__("Time elapsed:"))
		self.SetStatus4aText(__("Ready."))
		btnText = __("Stop")
		self.btnCancel.setText(btnText)
		btnWidth = self.btnCancel.fontMetrics().boundingRect(btnText).width() + 15
		if platform.system() == "Darwin": btnWidth += 12
		self.btnCancel.setMaximumWidth(btnWidth)

		# Device area
		self.lblDevice.setToolTip(__("Click here to generate a log file for debugging"))
		self.lblWarning.setToolTip(__("Click here to generate a log file for debugging"))

		# Tools menu
		self.mnuTools.setTitle(c__("Menu Item (& = Keyboard Shortcut)", "&Tools"))
		self.mnuTools.actions()[0].setText(c__("Menu Item (& = Keyboard Shortcut)", "Game Boy &Camera Album Viewer"))
		self.mnuTools.actions()[1].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Interactive Console"))
		self.mnuTools.actions()[3].setText(c__("Menu Item (& = Keyboard Shortcut)", "Firmware &Updater"))

		# Settings menu
		self.mnuConfig.setTitle(c__("Menu Item (& = Keyboard Shortcut)", "&Settings"))
		self.mnuConfig.actions()[0].setText(c__("Menu Item (& = Keyboard Shortcut)", "Check for &updates on application startup"))
		self.mnuConfig.actions()[1].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Append date && time to filename of save data backups"))
		self.mnuConfig.actions()[2].setText(c__("Menu Item (& = Keyboard Shortcut)", "Prefer full &chip erase"))
		self.mnuConfig.actions()[3].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Verify transferred data"))
		self.mnuConfig.actions()[4].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Limit voltage when analyzing Game Boy carts"))
		self.mnuConfig.actions()[5].setText(c__("Menu Item (& = Keyboard Shortcut)", "Limit &baud rate to 1Mbps"))
		self.mnuConfig.actions()[6].setText(c__("Menu Item (& = Keyboard Shortcut)", "Always &generate ROM dump reports"))
		self.mnuConfig.actions()[7].setText(c__("Menu Item (& = Keyboard Shortcut)", "Use &No-Intro file names"))
		self.mnuConfig.actions()[8].setText(c__("Menu Item (& = Keyboard Shortcut)", "Automatic cartridge &power off"))
		self.mnuConfig.actions()[9].setText(c__("Menu Item (& = Keyboard Shortcut)", "Skip writing matching ROM chunk&s"))
		self.mnuConfig.actions()[10].setText(c__("Menu Item (& = Keyboard Shortcut)", "Alternative address set mode (can fix or cause write &errors)"))
		self.mnuConfig.actions()[15].setText(c__("Menu Item (& = Keyboard Shortcut)", "Re-&enable suppressed messages"))

		# Read method sub-menus
		self.mnuConfigReadModeAGB.setTitle(c__("Menu Item (& = Keyboard Shortcut)", "&Read Method (Game Boy Advance)"))
		self.mnuConfigReadModeAGB.actions()[0].setText(c__("Menu Item (& = Keyboard Shortcut)", "S&tream"))
		self.mnuConfigReadModeAGB.actions()[1].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Single"))
		self.mnuConfigReadModeDMG.setTitle(c__("Menu Item (& = Keyboard Shortcut)", "&Read Method (Game Boy)"))
		self.mnuConfigReadModeDMG.actions()[0].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Normal"))
		self.mnuConfigReadModeDMG.actions()[1].setText(c__("Menu Item (& = Keyboard Shortcut)", "&Delayed"))

		# Language menu
		label_language = c__("Menu Item (& = Keyboard Shortcut)", "&Language")
		if label_language != "&Language":
			label_language = label_language.replace("&", "")
			label_language += " (&Language)"
		self.mnuLanguage.setTitle(label_language)

		# Third Party menu
		self.mnuThirdParty.setTitle(c__("Menu Item (& = Keyboard Shortcut)", "Third Party &Notices"))
		self.mnuThirdParty.actions()[1].setText(c__("Menu Item (& = Keyboard Shortcut)", "About &Qt"))
		self.mnuThirdParty.actions()[2].setText(c__("Menu Item (& = Keyboard Shortcut)", "About Game &Database"))
		self.mnuThirdParty.actions()[3].setText(c__("Menu Item (& = Keyboard Shortcut)", "Licenses"))
		self.UpdateThirdPartySupportAction()

		# Main menu actions
		self.mnuMainMenu.actions()[5].setText(c__("Menu Item (& = Keyboard Shortcut)", "Open &config folder"))
		self.mnuMainMenu.actions()[8].setText(c__("Menu Item (& = Keyboard Shortcut)", "About &FlashGBX"))

		# Options and Connect buttons
		btnText = c__("Button (& = Keyboard Shortcut)", "&Options")
		self.btnMainMenu.setText(btnText)
		btnWidth = self.btnMainMenu.fontMetrics().boundingRect(btnText).width() + 24
		if platform.system() == "Darwin": btnWidth += 12
		self.btnMainMenu.setMaximumWidth(btnWidth)
		self.btnConnect.setText(c__("Button (& = Keyboard Shortcut)", "&Connect"))
		self.ApplyInfoColumnWidths()

	def ApplyInfoColumnWidths(self):
		labels = (
			self.lblDMGGameName,
			self.lblDMGRomTitle,
			self.lblDMGGameCodeRevision,
			self.lblDMGHeaderRtc,
			self.lblDMGHeaderBootlogo,
			self.lblDMGHeaderROMChecksum,
			self.lblDMGHeaderROMSize,
			self.lblDMGHeaderSaveType,
			self.lblDMGHeaderMapper,
			#self.lblDMGCartridgeType,
			self.lblAGBGameName,
			self.lblAGBRomTitle,
			self.lblAGBHeaderGameCodeRevision,
			self.lblAGBGpioRtc,
			self.lblAGBHeaderBootlogo,
			self.lblAGBHeaderChecksum,
			self.lblAGBHeaderROMChecksum,
			self.lblAGBHeaderROMSize,
			self.lblAGBHeaderSaveType,
			#self.lblAGBCartridgeType,
		)
		max_width = max(label.sizeHint().width() for label in labels)
		for label in labels:
			label.setMinimumWidth(max_width)
			label.setMaximumWidth(max_width)
		self._dmgGameNameDefaultColWidth = max_width
		self._UpdateDMGGameNameLayout()

	def GuiCreateGroupBoxDMGCartInfo(self):
		self.grpDMGCartridgeInfo = QtWidgets.QGroupBox()
		self.grpDMGCartridgeInfo.setMinimumWidth(450 if platform.system() == "Linux" else 400)
		group_layout = QtWidgets.QVBoxLayout()
		group_layout.setContentsMargins(-1, 5, -1, -1)
		if platform.system() == "Linux":
			group_layout.setSpacing(4)

		rowDMGGameName = QtWidgets.QHBoxLayout()
		self.lblDMGGameName = QtWidgets.QLabel()
		self.lblDMGGameName.setContentsMargins(0, 1, 3, 1)
		rowDMGGameName.addWidget(self.lblDMGGameName)
		resultDMGGameName = QtWidgets.QHBoxLayout()
		resultDMGGameName.setContentsMargins(0, 0, 0, 0)
		resultDMGGameName.setSpacing(4)
		self.lblDMGGameNameResult = QtWidgets.QLabel("")
		self.lblDMGGameNameResult.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
		resultDMGGameName.addWidget(self.lblDMGGameNameResult, 1)
		self.lblDMGPlatformBadge = QtWidgets.QLabel("")
		self.lblDMGPlatformBadge.setAlignment(QtCore.Qt.AlignCenter)
		self.lblDMGPlatformBadge.setVisible(False)
		self.lblDMGPlatformBadge.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
		self.lblDMGPlatformBadge.setMaximumHeight(self.lblDMGGameNameResult.fontMetrics().height())
		resultDMGGameName.addWidget(self.lblDMGPlatformBadge, 0, QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
		rowDMGGameName.addLayout(resultDMGGameName)
		rowDMGGameName.setStretch(0, 9)
		rowDMGGameName.setStretch(1, 15)
		group_layout.addLayout(rowDMGGameName)
		self._rowDMGGameName = rowDMGGameName
		self._resultDMGGameName = resultDMGGameName
		self._dmgGameNameFullText = ""
		self._dmgGameNameDefaultColWidth = 0

		rowDMGRomTitle = QtWidgets.QHBoxLayout()
		self.lblDMGRomTitle = QtWidgets.QLabel()
		self.lblDMGRomTitle.setContentsMargins(0, 1, 3, 1)
		rowDMGRomTitle.addWidget(self.lblDMGRomTitle)
		resultDMGRomTitle = QtWidgets.QHBoxLayout()
		resultDMGRomTitle.setContentsMargins(0, 0, 0, 0)
		resultDMGRomTitle.setSpacing(0)
		self.lblDMGRomTitleResult = QtWidgets.QLabel("")
		resultDMGRomTitle.addWidget(self.lblDMGRomTitleResult)
		rowDMGRomTitle.addLayout(resultDMGRomTitle)
		rowDMGRomTitle.setStretch(0, 9)
		rowDMGRomTitle.setStretch(1, 15)
		group_layout.addLayout(rowDMGRomTitle)

		rowDMGGameCodeRevision = QtWidgets.QHBoxLayout()
		self.lblDMGGameCodeRevision = QtWidgets.QLabel()
		self.lblDMGGameCodeRevision.setContentsMargins(0, 1, 3, 1)
		rowDMGGameCodeRevision.addWidget(self.lblDMGGameCodeRevision)
		self.lblDMGGameCodeRevisionResult = QtWidgets.QLabel("")
		rowDMGGameCodeRevision.addWidget(self.lblDMGGameCodeRevisionResult)
		rowDMGGameCodeRevision.setStretch(0, 9)
		rowDMGGameCodeRevision.setStretch(1, 15)
		group_layout.addLayout(rowDMGGameCodeRevision)

		rowDMGHeaderRtc = QtWidgets.QHBoxLayout()
		self.lblDMGHeaderRtc = QtWidgets.QLabel()
		self.lblDMGHeaderRtc.setContentsMargins(0, 1, 3, 1)
		rowDMGHeaderRtc.addWidget(self.lblDMGHeaderRtc)
		self.lblDMGHeaderRtcResult = QtWidgets.QLabel("")
		self.lblDMGHeaderRtcResult.mousePressEvent = lambda event: [ self.EditRTC(event) ]
		rowDMGHeaderRtc.addWidget(self.lblDMGHeaderRtcResult)
		rowDMGHeaderRtc.setStretch(0, 9)
		rowDMGHeaderRtc.setStretch(1, 15)
		group_layout.addLayout(rowDMGHeaderRtc)

		rowDMGHeaderBootlogo = QtWidgets.QHBoxLayout()
		self.lblDMGHeaderBootlogo = QtWidgets.QLabel()
		self.lblDMGHeaderBootlogo.setContentsMargins(0, 1, 3, 1)
		rowDMGHeaderBootlogo.addWidget(self.lblDMGHeaderBootlogo)
		self.lblDMGHeaderBootlogoResult = QtWidgets.QLabel("")
		rowDMGHeaderBootlogo.addWidget(self.lblDMGHeaderBootlogoResult)
		rowDMGHeaderBootlogo.setStretch(0, 9)
		rowDMGHeaderBootlogo.setStretch(1, 15)
		group_layout.addLayout(rowDMGHeaderBootlogo)

		rowDMGHeaderROMChecksum = QtWidgets.QHBoxLayout()
		self.lblDMGHeaderROMChecksum = QtWidgets.QLabel()
		self.lblDMGHeaderROMChecksum.setContentsMargins(0, 1, 3, 1)
		rowDMGHeaderROMChecksum.addWidget(self.lblDMGHeaderROMChecksum)
		self.lblDMGHeaderROMChecksumResult = QtWidgets.QLabel("")
		rowDMGHeaderROMChecksum.addWidget(self.lblDMGHeaderROMChecksumResult)
		rowDMGHeaderROMChecksum.setStretch(0, 9)
		rowDMGHeaderROMChecksum.setStretch(1, 15)
		group_layout.addLayout(rowDMGHeaderROMChecksum)

		rowDMGHeaderROMSize = QtWidgets.QHBoxLayout()
		self.lblDMGHeaderROMSize = QtWidgets.QLabel()
		rowDMGHeaderROMSize.addWidget(self.lblDMGHeaderROMSize)
		self.cmbDMGHeaderROMSizeResult = QtWidgets.QComboBox()
		self.cmbDMGHeaderROMSizeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbDMGHeaderROMSizeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowDMGHeaderROMSize.addWidget(self.cmbDMGHeaderROMSizeResult)
		rowDMGHeaderROMSize.setStretch(0, 9)
		rowDMGHeaderROMSize.setStretch(1, 15)
		group_layout.addLayout(rowDMGHeaderROMSize)

		rowDMGHeaderSaveType = QtWidgets.QHBoxLayout()
		self.lblDMGHeaderSaveType = QtWidgets.QLabel()
		rowDMGHeaderSaveType.addWidget(self.lblDMGHeaderSaveType)
		self.cmbDMGHeaderSaveTypeResult = QtWidgets.QComboBox()
		self.cmbDMGHeaderSaveTypeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbDMGHeaderSaveTypeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowDMGHeaderSaveType.addWidget(self.cmbDMGHeaderSaveTypeResult)
		rowDMGHeaderSaveType.setStretch(0, 9)
		rowDMGHeaderSaveType.setStretch(1, 15)
		group_layout.addLayout(rowDMGHeaderSaveType)

		rowDMGHeaderMapper = QtWidgets.QHBoxLayout()
		self.lblDMGHeaderMapper = QtWidgets.QLabel()
		rowDMGHeaderMapper.addWidget(self.lblDMGHeaderMapper)
		self.cmbDMGHeaderMapperResult = QtWidgets.QComboBox()
		self.cmbDMGHeaderMapperResult.setStyleSheet("combobox-popup: 0;")
		self.cmbDMGHeaderMapperResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowDMGHeaderMapper.addWidget(self.cmbDMGHeaderMapperResult)
		rowDMGHeaderMapper.setStretch(0, 9)
		rowDMGHeaderMapper.setStretch(1, 15)
		group_layout.addLayout(rowDMGHeaderMapper)

		rowDMGCartridgeType = QtWidgets.QHBoxLayout()
		self.lblDMGCartridgeType = QtWidgets.QLabel()
		rowDMGCartridgeType.addWidget(self.lblDMGCartridgeType)
		self.cmbDMGCartridgeTypeResult = QtWidgets.QComboBox()
		self.cmbDMGCartridgeTypeResult.setStyleSheet("max-width: 260px;")
		self.cmbDMGCartridgeTypeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbDMGCartridgeTypeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowDMGCartridgeType.addWidget(self.cmbDMGCartridgeTypeResult)
		group_layout.addLayout(rowDMGCartridgeType)

		self.grpDMGCartridgeInfo.setLayout(group_layout)

		return self.grpDMGCartridgeInfo

	def GuiCreateGroupBoxAGBCartInfo(self):
		self.grpAGBCartridgeInfo = QtWidgets.QGroupBox()
		self.grpAGBCartridgeInfo.setMinimumWidth(432 if platform.system() == "Linux" else 400)
		group_layout = QtWidgets.QVBoxLayout()
		group_layout.setContentsMargins(-1, 5, -1, -1)
		if platform.system() == "Linux":
			group_layout.setSpacing(4)

		rowAGBGameName = QtWidgets.QHBoxLayout()
		self.lblAGBGameName = QtWidgets.QLabel()
		self.lblAGBGameName.setContentsMargins(0, 1, 3, 1)
		rowAGBGameName.addWidget(self.lblAGBGameName)
		self.lblAGBGameNameResult = QtWidgets.QLabel("")
		rowAGBGameName.addWidget(self.lblAGBGameNameResult)
		rowAGBGameName.setStretch(0, 9)
		rowAGBGameName.setStretch(1, 15)
		group_layout.addLayout(rowAGBGameName)

		rowAGBRomTitle = QtWidgets.QHBoxLayout()
		self.lblAGBRomTitle = QtWidgets.QLabel()
		self.lblAGBRomTitle.setContentsMargins(0, 1, 3, 1)
		rowAGBRomTitle.addWidget(self.lblAGBRomTitle)
		self.lblAGBRomTitleResult = QtWidgets.QLabel("")
		rowAGBRomTitle.addWidget(self.lblAGBRomTitleResult)
		rowAGBRomTitle.setStretch(0, 9)
		rowAGBRomTitle.setStretch(1, 15)
		group_layout.addLayout(rowAGBRomTitle)

		rowAGBHeaderGameCodeRevision = QtWidgets.QHBoxLayout()
		self.lblAGBHeaderGameCodeRevision = QtWidgets.QLabel()
		self.lblAGBHeaderGameCodeRevision.setContentsMargins(0, 1, 3, 1)
		rowAGBHeaderGameCodeRevision.addWidget(self.lblAGBHeaderGameCodeRevision)
		self.lblAGBHeaderGameCodeRevisionResult = QtWidgets.QLabel("")
		rowAGBHeaderGameCodeRevision.addWidget(self.lblAGBHeaderGameCodeRevisionResult)
		rowAGBHeaderGameCodeRevision.setStretch(0, 9)
		rowAGBHeaderGameCodeRevision.setStretch(1, 15)
		group_layout.addLayout(rowAGBHeaderGameCodeRevision)

		rowAGBGpioRtc = QtWidgets.QHBoxLayout()
		self.lblAGBGpioRtc = QtWidgets.QLabel()
		self.lblAGBGpioRtc.setContentsMargins(0, 1, 3, 1)
		rowAGBGpioRtc.addWidget(self.lblAGBGpioRtc)
		self.lblAGBGpioRtcResult = QtWidgets.QLabel("")
		self.lblAGBGpioRtcResult.mousePressEvent = lambda event: [ self.EditRTC(event) ]
		rowAGBGpioRtc.addWidget(self.lblAGBGpioRtcResult)
		rowAGBGpioRtc.setStretch(0, 9)
		rowAGBGpioRtc.setStretch(1, 15)
		group_layout.addLayout(rowAGBGpioRtc)

		rowAGBHeaderBootlogo = QtWidgets.QHBoxLayout()
		self.lblAGBHeaderBootlogo = QtWidgets.QLabel()
		self.lblAGBHeaderBootlogo.setContentsMargins(0, 1, 3, 1)
		rowAGBHeaderBootlogo.addWidget(self.lblAGBHeaderBootlogo)
		self.lblAGBHeaderBootlogoResult = QtWidgets.QLabel("")
		rowAGBHeaderBootlogo.addWidget(self.lblAGBHeaderBootlogoResult)
		rowAGBHeaderBootlogo.setStretch(0, 9)
		rowAGBHeaderBootlogo.setStretch(1, 15)
		group_layout.addLayout(rowAGBHeaderBootlogo)

		rowAGBHeaderChecksum = QtWidgets.QHBoxLayout()
		self.lblAGBHeaderChecksum = QtWidgets.QLabel()
		self.lblAGBHeaderChecksum.setContentsMargins(0, 1, 3, 1)
		rowAGBHeaderChecksum.addWidget(self.lblAGBHeaderChecksum)
		self.lblAGBHeaderChecksumResult = QtWidgets.QLabel("")
		rowAGBHeaderChecksum.addWidget(self.lblAGBHeaderChecksumResult)
		rowAGBHeaderChecksum.setStretch(0, 9)
		rowAGBHeaderChecksum.setStretch(1, 15)
		group_layout.addLayout(rowAGBHeaderChecksum)

		rowAGBHeaderROMChecksum = QtWidgets.QHBoxLayout()
		self.lblAGBHeaderROMChecksum = QtWidgets.QLabel()
		self.lblAGBHeaderROMChecksum.setContentsMargins(0, 1, 3, 1)
		rowAGBHeaderROMChecksum.addWidget(self.lblAGBHeaderROMChecksum)
		self.lblAGBHeaderROMChecksumResult = QtWidgets.QLabel("")
		rowAGBHeaderROMChecksum.addWidget(self.lblAGBHeaderROMChecksumResult)
		rowAGBHeaderROMChecksum.setStretch(0, 9)
		rowAGBHeaderROMChecksum.setStretch(1, 15)
		group_layout.addLayout(rowAGBHeaderROMChecksum)

		rowAGBHeaderROMSize = QtWidgets.QHBoxLayout()
		self.lblAGBHeaderROMSize = QtWidgets.QLabel()
		rowAGBHeaderROMSize.addWidget(self.lblAGBHeaderROMSize)
		self.cmbAGBHeaderROMSizeResult = QtWidgets.QComboBox()
		self.cmbAGBHeaderROMSizeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbAGBHeaderROMSizeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowAGBHeaderROMSize.addWidget(self.cmbAGBHeaderROMSizeResult)
		rowAGBHeaderROMSize.setStretch(0, 9)
		rowAGBHeaderROMSize.setStretch(1, 15)
		group_layout.addLayout(rowAGBHeaderROMSize)


		rowAGBHeaderSaveType = QtWidgets.QHBoxLayout()
		self.lblAGBHeaderSaveType = QtWidgets.QLabel()
		rowAGBHeaderSaveType.addWidget(self.lblAGBHeaderSaveType)
		self.cmbAGBSaveTypeResult = QtWidgets.QComboBox()
		self.cmbAGBSaveTypeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbAGBSaveTypeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowAGBHeaderSaveType.addWidget(self.cmbAGBSaveTypeResult)
		rowAGBHeaderSaveType.setStretch(0, 9)
		rowAGBHeaderSaveType.setStretch(1, 15)
		group_layout.addLayout(rowAGBHeaderSaveType)

		rowAGBCartridgeType = QtWidgets.QHBoxLayout()
		self.lblAGBCartridgeType = QtWidgets.QLabel()
		rowAGBCartridgeType.addWidget(self.lblAGBCartridgeType)
		self.cmbAGBCartridgeTypeResult = QtWidgets.QComboBox()
		self.cmbAGBCartridgeTypeResult.setStyleSheet("max-width: 260px;")
		self.cmbAGBCartridgeTypeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbAGBCartridgeTypeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.cmbAGBCartridgeTypeResult.currentIndexChanged.connect(self.CartridgeTypeChanged)
		rowAGBCartridgeType.addWidget(self.cmbAGBCartridgeTypeResult)
		group_layout.addLayout(rowAGBCartridgeType)

		self.grpAGBCartridgeInfo.setLayout(group_layout)
		return self.grpAGBCartridgeInfo

	def SetAutoPowerOff(self):
		if not self.CheckDeviceAlive(): return
		try:
			value = int(self.SETTINGS.value("AutoPowerOff", default="0"))
		except ValueError:
			value = 0
		self.CONN.SetAutoPowerOff(value=value)

	def SetDMGReadMethod(self):
		if not self.CheckDeviceAlive(): return
		try:
			method = int(self.SETTINGS.value("DMGReadMethod", "1"))
		except ValueError:
			method = 1
		self.CONN.SetDMGReadMethod(method)
		self.mnuConfigReadModeDMG.actions()[0].setChecked(False)
		self.mnuConfigReadModeDMG.actions()[1].setChecked(False)
		if method == 1:
			self.mnuConfigReadModeDMG.actions()[0].setChecked(True)
		elif method == 2:
			self.mnuConfigReadModeDMG.actions()[1].setChecked(True)

	def SetAGBReadMethod(self):
		if not self.CheckDeviceAlive(): return
		try:
			method = int(self.SETTINGS.value("AGBReadMethod", "2"))
		except ValueError:
			method = 2
		self.CONN.SetAGBReadMethod(method)
		self.mnuConfigReadModeAGB.actions()[0].setChecked(False)
		self.mnuConfigReadModeAGB.actions()[1].setChecked(False)
		if method == 2:
			self.mnuConfigReadModeAGB.actions()[0].setChecked(True)
		elif method == 0:
			self.mnuConfigReadModeAGB.actions()[1].setChecked(True)

	def SetLimitBaudRate(self):
		if not self.CheckDeviceAlive(): return
		mode = self.CONN.GetMode()
		limit_baudrate = self.SETTINGS.value("LimitBaudRate")
		if limit_baudrate == "enabled":
			self.CONN.ChangeBaudRate(baudrate=1000000)
		else:
			self.CONN.ChangeBaudRate(baudrate=2000000)
		self.DisconnectDevice()
		self.FindDevices(connectToFirst=True, mode=mode)

	def EnableUpdateCheck(self):
		update_check = self.SETTINGS.value("UpdateCheck")
		if update_check is None:
			self.UpdateCheck()
			return
		new_value = str(self.mnuConfig.actions()[0].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")
		if new_value == "enabled":
			answer = QtWidgets.QMessageBox.question(
				self,
				"{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION),
				__("Would you like to automatically check for new versions at application startup? This will make use of the GitHub API ({url}).", url='<a href="https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement">' + c__("GitHub API Link", "privacy policy") + '</a>'),
				QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
				QtWidgets.QMessageBox.No
			)
			if answer == QtWidgets.QMessageBox.Yes:
				self.SETTINGS.setValue("UpdateCheck", "enabled")
				self.mnuConfig.actions()[0].setChecked(True)
				update_check = "enabled"
				self.UpdateCheck()
			else:
				self.mnuConfig.actions()[0].setChecked(False)
				self.SETTINGS.setValue("UpdateCheck", "disabled")
		else:
			self.SETTINGS.setValue("UpdateCheck", "disabled")

	def ChangeLanguage(self, language_code):
		self.SETTINGS.setValue("Language", language_code)
		init_language(AppContext.CONFIG_PATH, override=language_code)
		loadQtTranslation(self.QT_APP, language=language_code)
		self.InitWidgetTexts()
		self.DisconnectDevice()

	def UpdateCheck(self):
		update_check = self.SETTINGS.value("UpdateCheck")
		if update_check is None:
			answer = QtWidgets.QMessageBox.question(
				self,
				"{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION),
				__("Welcome to {app} by {author}!", app=AppInfo.NAME + " " + AppInfo.VERSION, author="Lesserkuma") + "<br><br>" + __("Would you like to automatically check for new versions at application startup? This will make use of the GitHub API ({url}).", url='<a href="https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement">' + c__("GitHub API Link", "privacy policy") + '</a>'),
				QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
				QtWidgets.QMessageBox.Yes
			)
			if answer == QtWidgets.QMessageBox.Yes:
				self.SETTINGS.setValue("UpdateCheck", "enabled")
				self.mnuConfig.actions()[0].setChecked(True)
				update_check = "enabled"
			else:
				self.SETTINGS.setValue("UpdateCheck", "disabled")
			QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("General precautions:\n- Due to voltage differences, do not insert a Game Boy Advance cartridge while the platform mode is set to “Game Boy”.\n- Always keep the cartridge contacts as clean as possible to ensure a stable connection.").replace("\n", "<br>"), QtWidgets.QMessageBox.Ok)

		if update_check and update_check.lower() == "enabled":
			print("")
			url = "https://api.github.com/repos/Lesserkuma/FlashGBX/releases/latest"
			site = "https://github.com/Lesserkuma/FlashGBX/releases/latest"
			try:
				ret = requests.get(url, allow_redirects=True, timeout=1.5)
			except requests.exceptions.ConnectTimeout as e:
				print(__("Error: Update check failed due to a connection timeout. Please check your internet connection."), e, sep="\n")
				ret = False
			except requests.exceptions.ConnectionError as e:
				print(__("Error: Update check failed due to a connection error. Please check your network connection."), e, sep="\n")
				ret = False
			except Exception as e:
				print(__("Error: An unexpected error occured while querying the latest version information from GitHub."), e, sep="\n")
				ret = False
			if ret is not False and ret.status_code == 200:
				ret = ret.content
				try:
					ret = json.loads(ret)
					if 'tag_name' in ret:
						latest_version = str(ret['tag_name'])
						if version.parse(latest_version) == version.parse(AppInfo.VERSION_PEP440):
							print(__("You are using the latest version of FlashGBX."))
						elif version.parse(latest_version) > version.parse(AppInfo.VERSION_PEP440):
							msg_text = "A new version of FlashGBX has been released!\nVersion {:s} is now available.".format(latest_version)
							print(__("A new version of FlashGBX has been released!\nVersion {new_version} is now available.", new_version=latest_version))
							msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle=AppInfo.NAME + " " + __("Update Check"), text=msg_text)
							button_open = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Open release notes"), QtWidgets.QMessageBox.ActionRole)
							button_cancel = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Close"), QtWidgets.QMessageBox.RejectRole)
							msgbox.setDefaultButton(button_open)
							msgbox.setEscapeButton(button_cancel)
							answer = msgbox.exec()
							if msgbox.clickedButton() == button_open:
								self.OpenWebURL(site)
						else:
							print(__("This version of FlashGBX ({appver}) seems to be newer than the latest public release ({public_version}).", appver=AppInfo.VERSION_PEP440, public_version=latest_version))
					else:
						print(__("Error: Update check failed due to missing version information in JSON data from GitHub."))
				except json.decoder.JSONDecodeError:
					print(__("Error: Update check failed due to malformed JSON data from GitHub."))
				except Exception as e:
					print(__("Error: An unexpected error occured while querying the latest version information from GitHub."), e, sep="\n")
			elif ret is not False:
				if ret.status_code == 403 and "X-RateLimit-Remaining" in ret.headers and ret.headers["X-RateLimit-Remaining"] == '0':
					print(__("Error: Failed to check for updates (too many API requests). Try again later."))
				else:
					print(__("Error: Failed to check for updates (HTTP status {status_code}).", status_code=ret.status_code))

	def GetHostLauncherEnv(self):
		env = os.environ.copy()
		if platform.system() != "Linux":
			return env

		# Avoid leaking bundled AppImage libs into system launchers like xdg-open.
		if "LD_LIBRARY_PATH_ORIG" in env:
			env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
		else:
			env.pop("LD_LIBRARY_PATH", None)

		for var in ("APPDIR", "APPIMAGE", "ARGV0"):
			env.pop(var, None)
		return env

	def OpenWebURL(self, url):
		try:
			if platform.system() == "Linux":
				subprocess.Popen(["xdg-open", url], env=self.GetHostLauncherEnv())
			else:
				webbrowser.open(url)
		except:
			pass

	def DisconnectDevice(self):
		try:
			devname = self.CONN.GetFullNameExtended()
			self.CONN.Close(cartPowerOff=True)
			print(__("Disconnected from {device_name}", device_name=devname))
		except:
			pass

		self.DEVICES = {}
		self.cmbDevice.clear()
		self.CONN = None

		self.optAGB.setEnabled(False)
		self.optDMG.setEnabled(False)
		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.btnCancel.setEnabled(False)
		self.btnHeaderRefresh.setEnabled(False)
		self.btnDetectCartridge.setEnabled(False)
		self.btnBackupROM.setEnabled(False)
		self.btnFlashROM.setEnabled(False)
		self.btnBackupRAM.setEnabled(False)
		self.btnRestoreRAM.setEnabled(False)
		self.btnConnect.setText(c__("Button (& = Keyboard Shortcut)", "&Connect"))
		self.lblDevice.setText(__("Disconnected."))
		self.SetProgressBars(min=0, max=1, value=0)
		self.SetStatus4aText(__("Disconnected."))
		self.lblStatus1aResult.setText("–")
		self.lblStatus2aResult.setText("–")
		self.lblStatus3aResult.setText("–")
		self.SetStatus4aResult("")
		self.SetStatus4aText(__("Disconnected."))
		self.grpStatus.setTitle(__("Transfer Status"))
		self.mnuConfig.actions()[5].setVisible(True)
		self.mnuConfig.actions()[8].setVisible(True)
		self.mnuConfig.actions()[9].setVisible(True)
		self.mnuConfig.actions()[10].setVisible(False)
		self.mnuTools.actions()[3].setEnabled(True)
		self.mnuTools.actions()[1].setEnabled(False)
		self.mnuConfigReadModeAGB.setEnabled(True)
		self.mnuLanguage.setEnabled(True)
		self.UpdateThirdPartySupportAction()

	def ReEnableMessages(self):
		self.SETTINGS.setValue("AutoReconnect", "disabled")
		self.SETTINGS.setValue("SkipModeChangeWarning", "disabled")
		self.SETTINGS.setValue("SkipAutodetectMessage", "disabled")
		self.SETTINGS.setValue("SkipFinishMessage", "disabled")
		self.SETTINGS.setValue("SkipCameraSavePopup", "disabled")

	def AboutFlashGBX(self):
		from . import i18n
		msg = "This software is being developed by Lesserkuma as a hobby project. There is no affiliation with Nintendo or any other company. This software is provided as-is and the developer is not responsible for any damage that is caused by the use of it. Use at your own risk!<br><br>"
		msg += f"© 2020–{datetime.datetime.now().year} Lesserkuma<br>"
		msg += "<a href=\"https://github.com/Lesserkuma/FlashGBX\">https://github.com/Lesserkuma/FlashGBX</a><br>"
		msg += "<br>"
		if i18n.CONFIGURED_LANGUAGE and i18n.CONFIGURED_LANGUAGE != "en" and i18n.TRANSLATION_AUTHOR:
			lang_name = LANGUAGES.get(i18n.CONFIGURED_LANGUAGE, i18n.CONFIGURED_LANGUAGE)
			if isinstance(lang_name, tuple):
				lang_name = lang_name[0]
			msg += f"Translated to {lang_name} by {i18n.TRANSLATION_AUTHOR}<br><br>"
		msg += "Acknowledgments and Contributors:<br><small>2358, 90sFlav, AcoVanConis, AdmirtheSableye, AlexiG, ALXCO-Hardware, AndehX, antPL, aronson, Ausar, bbsan, BennVenn, Boeuffy, CaptainBean, ccs21, chobby, ClassicOldSong, Cliffback, CodyWick13, Corborg, Cristóbal, crizzlycruz, Crystal, Därk, Davidish, delibird_deals, DevDavisNunez, Diddy_Kong, djedditt, Dr-InSide, Duckman, dyf2007, easthighNerd, EchelonPrime, edo999, Eldram, Eli, Ell, EmperorOfTigers, endrift, Erba Verde, ethanstrax, eveningmoose, Falknör, FerrantePescara, frarees, fredemmott, Frost Clock, Gahr, gandalf1980, gboh, gekkio, Godan, Goon, Grender, HDR, Herax, Hiccup, hiks, howie0210, iamevn, Icesythe7, ide, infinest, inYourBackline, iyatemu, Jayro, Jenetrix, JFox, joyrider3774, jrharbort, JS7457, julgr, Kaede, kane159, Kelly, KOOORAY, kscheel, kyokohunter, Leitplanke, litlemoran, LovelyA72, Lu, Luca DS, LucentW, luxkiller65, manuelcm1, marv17, Merkin, metroid-maniac, Mr_V, Mufsta, numma_cway, olDirdey, orangeglo, orzgithub, paarongiroux, Paradoxical, Pese, Rairch, Raphaël BOICHOT, redalchemy, RetroGorek, RevZ, RibShark, s1cp, Satumox, Sgt.DoudouMiel, SH, Shinichi999, Sillyhatday, simonK, Sithdown, skite2001, Smelly-Ghost, Sonikks, Squiddy, Stitch, Super Maker, t5b6_de, Tauwasser, TheNFCookie, Timville, twitnic, velipso, Veund, voltagex, Voultar, Warez Waldo, wickawack, Winter1760, Wkr, x7l7j8cc, xactoes, xukkorz, yosoo, Zeii, Zelante, zipplet, Zoo, zvxr</small>"
		QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg, QtWidgets.QMessageBox.Ok)

	def AboutGameDB(self):
		msg = __("FlashGBX uses a game database that is based on the ongoing efforts of the No-Intro project. Visit {url} for more information.", url="<a href=\"https://no-intro.org/\">https://no-intro.org/</a>") + "<br><br>"
		msg += __("No-Intro databases referenced for this version of FlashGBX:") + "<br>"
		msg += "• Nintendo - Game Boy (20260828-172824)<br>• Nintendo - Game Boy Advance (20260828-013543)<br>• Nintendo - Game Boy Advance (Video) (20260522-144016)<br>• Nintendo - Game Boy Color (20260828-013644)" # No-Intro DBs
		QtWidgets.QMessageBox.information(self, "FlashGBX {:s}".format(AppInfo.VERSION), msg, QtWidgets.QMessageBox.Ok)

	def _GetDeviceSupportData(self):
		if self.CONN is None:
			return (None, None)
		message = self.CONN.GetSupportMessage()
		if message is None:
			return (None, None)
		device_name = self.CONN.GetName()
		return (device_name, message)

	def UpdateThirdPartySupportAction(self):
		device_name, support_message = self._GetDeviceSupportData()
		if device_name is None or support_message is None:
			self.mnuDeviceSupport.setVisible(False)
			return
		self.mnuDeviceSupport.setText(c__("Menu Item", "About {device_name}", device_name=device_name))
		self.mnuDeviceSupport.setVisible(True)

	def _ConvertUrlsToAnchors(self, text):
		escaped = html.escape(text)
		def repl(match):
			url = match.group(1)
			# url = "\u2060".join(url)
			return f'<a href="{url}">{url}</a>'
		return re.sub(r"(https?://[^\s<]+)", repl, escaped)

	def AboutConnectedDevice(self):
		device_name, support_message = self._GetDeviceSupportData()
		if device_name is None or support_message is None:
			return

		fw_version_text = __("Connected to {device_name}", device_name=self.CONN.GetFullName()) + "\n" + __("Firmware version: {fw_version}", fw_version=self.CONN.GetFirmwareVersion(more=True))
		msg = self._ConvertUrlsToAnchors(fw_version_text).replace("\n", "<br>") + "<br><br>"
		msg += self._ConvertUrlsToAnchors(support_message).replace("\n", "<br>")
		msgbox = QtWidgets.QMessageBox(
			parent=self,
			icon=QtWidgets.QMessageBox.Information,
			windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION),
			text=msg,
			standardButtons=QtWidgets.QMessageBox.Ok
		)
		msgbox.setTextFormat(QtCore.Qt.RichText)
		label = msgbox.findChild(QtWidgets.QLabel, "qt_msgbox_label")
		if label is not None:
			label.setOpenExternalLinks(True)
			label.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
		msgbox.exec()

	def OpenPath(self, path=None, select_file=False):
		if path is None:
			path = AppContext.CONFIG_PATH
			kbmod = QtWidgets.QApplication.keyboardModifiers()
			if kbmod != QtCore.Qt.ShiftModifier:
				self.WriteDebugLog()

		system = platform.system()
		env = self.GetHostLauncherEnv()
		try:
			if select_file and os.path.isfile(path):
				abs_path = os.path.abspath(path)
				if system == "Windows":
					subprocess.Popen(["explorer", "/select,", abs_path])
					return
				if system == "Darwin":
					subprocess.Popen(["open", "-R", abs_path], env=env)
					return
				try:
					file_uri = "file://" + urllib.parse.quote(abs_path)
					subprocess.check_call([
						"dbus-send", "--session", "--print-reply",
						"--dest=org.freedesktop.FileManager1",
						"--type=method_call",
						"/org/freedesktop/FileManager1",
						"org.freedesktop.FileManager1.ShowItems",
						"array:string:" + file_uri,
						"string:",
					], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
					return
				except Exception:
					path = os.path.dirname(abs_path)

			path_uri = 'file://{0:s}'.format(path)
			if system == "Windows":
				os.startfile(path_uri)
			elif system == "Darwin":
				subprocess.Popen(["open", path_uri], env=env)
			else:
				subprocess.Popen(["xdg-open", path_uri], env=env)
		except:
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("The file was not found.") + "\n\n" + str(path), QtWidgets.QMessageBox.Ok)

	def WriteDebugLog(self, event=None, open_log=False):
		if isinstance(event, QtGui.QMouseEvent):
			if event.button() in (QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.MouseButton.RightButton): return

		device = False
		try:
			device = self.CONN.GetFullNameExtended(more=True)
		except:
			pass

		Logger.write_debug_log(device)
		try:
			if open_log is True:
				fn = AppContext.CONFIG_PATH + os.sep + "debug.log"
				self.OpenPath(fn)
				self.lblWarning.setVisible(False)
				if isinstance(sys.stdout, Logger) and sys.stdout.LOG_ERROR is True:
					sys.stdout.LOG_ERROR = False
		except:
			pass

	def ConnectDevice(self):
		if self.CONN is not None:
			self.DisconnectDevice()
			return True
		else:
			self.CONN = None
			if self.cmbDevice.count() > 0:
				index = self.cmbDevice.currentText()
			else:
				index = self.lblDevice.text()

			if index not in self.DEVICES:
				self.FindDevices()
				return

			dev = self.DEVICES[index]
			port = dev.GetPort()
			if str(self.SETTINGS.value("LimitBaudRate", default="disabled")).lower() == "enabled":
				max_baud = 1000000
			else:
				max_baud = 2000000
			ret = dev.Initialize(self.FLASHCARTS, port=port, max_baud=max_baud)
			msg = ""

			if ret is False:
				self.CONN = None
				if self.cmbDevice.count() == 0: self.lblDevice.setText(__("No connection."))
				return False
			elif isinstance(ret, list):
				for i in range(0, len(ret)):
					status = ret[i][0]
					text = ret[i][1]
					if text in msg: continue
					if status == 0:
						msg += text + "\n"
					elif status == 1:
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Ok)
						if not '\n' in text: msgbox.setTextFormat(QtCore.Qt.RichText)
						msgbox.exec()
					elif status == 2:
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Ok)
						if not '\n' in text: msgbox.setTextFormat(QtCore.Qt.RichText)
						msgbox.exec()
					elif status == 3:
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Ok)
						if not '\n' in text: msgbox.setTextFormat(QtCore.Qt.RichText)
						msgbox.exec()
						self.CONN = None
						return False

			if dev.IsConnected():
				self.CONN = dev
				dev.SetWriteDelay(enable=str(self.SETTINGS.value("WriteDelay", default="disabled")).lower() == "enabled")
				self.SetAutoPowerOff()
				self.SetDMGReadMethod()
				self.SetAGBReadMethod()
				self.mnuConfig.actions()[5].setVisible(self.CONN.DEVICE_NAME == "GBxCart RW") # Limit Baud Rate
				self.mnuConfig.actions()[8].setVisible(self.CONN.CanPowerCycleCart() and self.CONN.CanPowerCycleCart() and self.CONN.FW["fw_ver"] >= 12) # Auto Power Off
				self.mnuConfig.actions()[9].setVisible(self.CONN.FW["fw_ver"] >= 12) # Skip writing matching ROM chunks
				self.mnuConfig.actions()[10].setVisible(self.CONN.DEVICE_NAME == "Joey Jr") # Force WR Pullup
				self.mnuConfigReadModeAGB.setEnabled(self.CONN.FW["fw_ver"] >= 12)
				self.mnuConfigReadModeDMG.setEnabled(self.CONN.FW["fw_ver"] >= 12)
				self.UpdateThirdPartySupportAction()

				self.CONN.SetTimeout(float(self.SETTINGS.value("SerialTimeout", default="1")))
				self.optDMG.setAutoExclusive(False)
				self.optAGB.setAutoExclusive(False)
				device_auto_switch_only = self.CONN.CanSetVoltageByAutoswitch() and not self.CONN.CanSetVoltageByCode()
				if "DMG" in self.CONN.GetSupprtedModes():
					self.optDMG.setEnabled(not device_auto_switch_only)
					self.optDMG.setChecked(False)
				if "AGB" in self.CONN.GetSupprtedModes():
					self.optAGB.setEnabled(not device_auto_switch_only)
					self.optAGB.setChecked(False)
				self.optAGB.setAutoExclusive(True)
				self.optDMG.setAutoExclusive(True)
				if len(self.CONN.GetSupprtedModes()) == 2:
					self.SetStatus4aText(__("Ready. Please select Platform Mode."))
				else:
					self.SetStatus4aText(__("Ready."))
				self.btnConnect.setText(c__("Button (& = Keyboard Shortcut)", "&Disconnect"))
				self.cmbDevice.setStyleSheet("QComboBox { border: 0; margin: 0; padding: 0; max-width: 0px; }")
				if dev.GetFWBuildDate() == "":
					self.lblDevice.setText(dev.GetFullNameLabel() + " [" + __("Legacy Mode") + "]")
				else:
					self.lblDevice.setText(dev.GetFullNameLabel())
				print("\n" + __("Connected to {device_name}", device_name=dev.GetFullNameExtended(more=True)))
				self.grpActions.setEnabled(True)
				self.mnuTools.setEnabled(True)
				self.mnuConfig.setEnabled(True)
				self.mnuLanguage.setEnabled(True)
				self.btnCancel.setEnabled(False)

				# Firmware Update Menu
				self.mnuTools.actions()[3].setEnabled(True)
				supports_firmware_updates = self.CONN.SupportsFirmwareUpdates()
				if supports_firmware_updates is False:
					self.mnuTools.actions()[3].setEnabled(False)

				# Interactive Console Menu
				self.mnuTools.actions()[1].setEnabled(self.CONN.GetMode() is not None)

				self.SetProgressBars(min=0, max=1, value=0)

				if self.CONN.GetMode() == "DMG":
					self.cmbDMGCartridgeTypeResult.clear()
					self.cmbDMGCartridgeTypeResult.addItems(self.CONN.GetSupportedCartridgesDMG()[0])
					self.grpAGBCartridgeInfo.setVisible(False)
					self.grpDMGCartridgeInfo.setVisible(True)
				elif self.CONN.GetMode() == "AGB":
					self.cmbAGBCartridgeTypeResult.clear()
					self.cmbAGBCartridgeTypeResult.addItems(self.CONN.GetSupportedCartridgesAGB()[0])
					self.grpDMGCartridgeInfo.setVisible(False)
					self.grpAGBCartridgeInfo.setVisible(True)

				print(msg, end="")

				if supports_firmware_updates:
					if dev.FirmwareUpdateAvailable():
						dontShowAgain = str(self.SETTINGS.value("SkipFirmwareUpdate", default="disabled")).lower() == "enabled"
						if not dontShowAgain or dev.FW_UPDATE_REQ:
							cb = None
							if dev.FW_UPDATE_REQ is True:
								text = __("A firmware update for your {device_name} is required to use this software. Do you want to update now?", device_name=dev.GetFullName())
								msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
							elif dev.FW_UPDATE_REQ == 2:
								text = __("Your {device_name} is no longer supported in this version of FlashGBX due to technical limitations. The last supported version is {url}.", device_name=dev.GetFullName(), url='<a href="https://github.com/Lesserkuma/FlashGBX/releases/tag/3.37">FlashGBX v3.37</a>') + "<br><br>" + __("The Firmware Updater can still be used, however any other functions are no longer available.") + "<br><br>" + __("Do you want to run the Firmware Updater now?")
								msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
							else:
								text = __("A firmware update for your {device_name} is available. Do you want to update now?", device_name=dev.GetFullName())
								msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
								cb = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Ignore firmware updates"), checked=dontShowAgain)
							answer = msgbox.exec()
							if dev.FW_UPDATE_REQ:
								if answer == QtWidgets.QMessageBox.Yes:
									self.ShowFirmwareUpdateWindow()
								if not AppContext.DEBUG:
									self.DisconnectDevice()
							else:
								if cb is not None:
									dontShowAgain = cb.isChecked()
									if dontShowAgain: self.SETTINGS.setValue("SkipFirmwareUpdate", "enabled")
								if answer == QtWidgets.QMessageBox.Yes:
									self.ShowFirmwareUpdateWindow()

				elif dev.FW_UPDATE_REQ:
					text = __("A firmware update for your {device_name} is required to use this software.", device_name=dev.GetFullName()) + "<br><br>" + __("Current firmware version: {fw_version}", fw_version=dev.GetFirmwareVersion())
					if not AppContext.DEBUG:
						self.DisconnectDevice()
					QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text, QtWidgets.QMessageBox.Ok)

				if dev.IsUnregistered():
					try:
						text = dev.GetRegisterInformation()
						QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text, QtWidgets.QMessageBox.Ok)
					except:
						pass

				if self.CONN is None:
					return False

				modes = self.CONN.GetSupprtedModes()
				auto_mode = self._GetAutoPlatformMode(self.CONN, modes)
				if auto_mode == "DMG":
					self.optDMG.setChecked(True)
					self.SetMode()
				elif auto_mode == "AGB":
					self.optAGB.setChecked(True)
					self.SetMode()
				return True

			return False

	def FindDevices(self, connectToFirst=False, port=None, mode=None, firstRun=False):
		if self.CONN is not None:
			self.DisconnectDevice()
		self.DEVICES = {}
		self.lblDevice.setText(__("Searching..."))
		self.btnConnect.setEnabled(False)
		qt_app.processEvents()

		messages = []

		for hw_device in HW_DEVICES:
			ports = []
			while True: # for finding other devices of the same type
				dev = hw_device.GbxDevice()
				if str(self.SETTINGS.value("LimitBaudRate", default="disabled")).lower() == "enabled":
					max_baud = 1000000
				else:
					max_baud = 2000000
				ret = dev.Initialize(self.FLASHCARTS, port=port, max_baud=max_baud)
				if ret is False or dev.CheckActive() is False:
					self.CONN = None
					break
				elif isinstance(ret, list):
					for i in range(0, len(ret)):
						status = ret[i][0]
						msg = ret[i][1]
						if msg in messages: # don’t show the same message twice
							continue
						if status == 3:
							messages.append(msg)
							self.CONN = None

				if dev.GetPort() in ports:
					break
				ports.append(dev.GetPort())

				if dev.IsConnected():
					self.DEVICES[dev.GetFullNameExtended()] = dev
					if dev.GetPort() in ports: break

		for dev in self.DEVICES.values():
			dev.Close()

		self.cmbDevice.setStyleSheet("QComboBox { border: 0; margin: 0; padding: 0; max-width: 0px; }")

		if len(self.DEVICES) == 0:
			if len(messages) > 0:
				msg = ""
				for message in messages:
					msg += message + "\n\n"
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg[:-2], QtWidgets.QMessageBox.Ok)
			elif not firstRun:
				compatible_devices = []
				for hw_device in HW_DEVICES:
					device_name = getattr(hw_device.GbxDevice, "DEVICE_NAME", None)
					if not device_name or device_name in compatible_devices:
						continue
					if device_name == "Joey Jr":
						device_name += " (" + c__("Joey Jr is compatible, but requires a firmware update", "firmware update required") + ")"
					compatible_devices.append(device_name)

				compatible_devices_text = ""
				for device_name in compatible_devices:
					compatible_devices_text += "- " + device_name + "\n"

				msg = (
					__("No compatible devices found. Please ensure the device is connected properly.") + "\n\n" + __("Compatible devices:")
					+ "\n"
					+ compatible_devices_text
					+ "\n"
					+ __(
						"Troubleshooting advice:\n"
						"- Re-connect the device with different USB cables and ports\n"
						"- Avoid battery charging cables and passive USB hubs\n"
						"- Perform a Firmware Update"
					)
				)
				if platform.system() == "Darwin":
					msg += "\n\n" + __("<b>For Joey Jr on macOS:</b>\nAn extra step is necessary to update the firmware: {url}", url='<a href="https://github.com/Lesserkuma/JoeyJr_FWUpdater">https://github.com/Lesserkuma/JoeyJr_FWUpdater</a>')
				elif platform.system() == "Linux":
					msg += "\n\n" + __("<b>For Linux users:</b>\nEnsure your user account has permissions to use the device. See the {readme} file for more information.", readme="<b>README.md</b>")

				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg.replace("\n", "<br>"))
				button_ok = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&OK"), QtWidgets.QMessageBox.ActionRole)
				button_fwupdate = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Firmware-Updater"), QtWidgets.QMessageBox.ActionRole)
				msgbox.setDefaultButton(button_ok)
				msgbox.setEscapeButton(button_ok)
				msgbox.exec()
				if msgbox.clickedButton() == button_fwupdate:
					self.ShowFirmwareUpdateWindow()

			self.lblDevice.setText(__("No devices found."))
			self.lblDevice.setStyleSheet("")
			self.cmbDevice.clear()

			self.btnConnect.setEnabled(False)
		elif len(self.DEVICES) == 1 or (connectToFirst and len(self.DEVICES) > 1):
			self.lblDevice.setText(list(self.DEVICES.keys())[0])
			self.lblDevice.setStyleSheet("")
			self.ConnectDevice()
			self.cmbDevice.clear()
			self.btnConnect.setEnabled(True)
		else:
			self.lblDevice.setText(__("Connect to:"))
			self.cmbDevice.clear()
			self.cmbDevice.addItems(self.DEVICES.keys())
			self.cmbDevice.setCurrentIndex(0)
			self.cmbDevice.setStyleSheet("")
			self.btnConnect.setEnabled(True)

		self.btnConnect.setEnabled(True)

		if len(self.DEVICES) == 0: return False

		if mode == "DMG":
			self.optDMG.setChecked(True)
			self.SetMode()
		elif mode == "AGB":
			self.optAGB.setChecked(True)
			self.SetMode()

		return True

	def AbortOperation(self):
		if "stresstest_running" in self.STATUS:
			del(self.STATUS["stresstest_running"])
		self.CONN.AbortOperation()
		self.SetStatus4aText(__("Stopping... Please wait."))
		self.SetStatus4aResult("")

	def FinishOperation(self):
		if self.lblStatus2aResult.text() == __("Pending..."): self.lblStatus2aResult.setText("–")
		self.SetStatus4aResult("")
		self.grpDMGCartridgeInfo.setEnabled(True)
		self.grpAGBCartridgeInfo.setEnabled(True)
		self.grpActions.setEnabled(True)
		self.mnuTools.setEnabled(True)
		self.mnuConfig.setEnabled(True)
		self.mnuLanguage.setEnabled(True)
		self.btnCancel.setEnabled(False)

		dontShowAgain = str(self.SETTINGS.value("SkipFinishMessage", default="disabled")).lower() == "enabled"
		msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("Operation complete!"), standardButtons=QtWidgets.QMessageBox.Ok)

		time_elapsed = None
		msg_te = ""
		speed = None
		if "time_start" in self.STATUS and self.STATUS["time_start"] > 0:
			time_elapsed = time.time() - self.STATUS["time_start"]
			msg_te = "\n\n" + __("Total time elapsed: {elapsed}", elapsed=Formatter.progress_time(time_elapsed, as_float=True))
			if "transferred" in self.CONN.INFO and time_elapsed > 0:
				speed = format_decimal((self.CONN.INFO["transferred"] / 1024.0) / time_elapsed, precision=2) + __(" KiB/s")
			self.STATUS["time_start"] = 0

		if self.CONN.INFO["last_action"] == 1: # Backup ROM
			self.CONN.INFO["last_action"] = 0
			dump_report = False
			button_dump_report = None
			dumpinfo_file = ""
			temp = str(self.SETTINGS.value("GenerateDumpReports", default="disabled")).lower() == "enabled"
			# try:
			dump_report = self.CONN.GetDumpReport()
			if dump_report is not False:
				if time_elapsed is not None and speed is not None:
					self.lblStatus2aResult.setText(speed)
					dump_report = dump_report.replace("%TRANSFER_RATE%", "{:.2f}".format((self.CONN.INFO["transferred"] / 1024.0) / time_elapsed) + " KiB/s")
					dump_report = dump_report.replace("%TIME_ELAPSED%", Formatter.progress_time(time_elapsed, localized=False))
				else:
					dump_report = dump_report.replace("%TRANSFER_RATE%", "N/A")
					dump_report = dump_report.replace("%TIME_ELAPSED%", "N/A")
				dumpinfo_file = os.path.splitext(self.STATUS["last_path"])[0] + ".txt"
			# except Exception as e:
			# 	print(__("Dump Report Error:") + " {:s}".format(str(e)))

			if dump_report is not False and dumpinfo_file != "" and temp is True:
				try:
					with open(dumpinfo_file, "wb") as f:
						f.write(bytearray([ 0xEF, 0xBB, 0xBF ])) # UTF-8 BOM
						f.write(dump_report.encode("UTF-8"))
					button_dump_report = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "Open Dump &Report"), QtWidgets.QMessageBox.ActionRole)
				except Exception as e:
					print(__("Error:") + " {:s}".format(str(e)))
			else:
				button_dump_report = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "Generate Dump &Report"), QtWidgets.QMessageBox.ActionRole)

			button_open_dir = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "Open Fol&der"), QtWidgets.QMessageBox.ActionRole)

			if self.CONN.GetMode() == "DMG":
				if self.CONN.INFO.get("rom_checksum", -1) == self.CONN.INFO.get("rom_checksum_calc", -2):
					self.lblDMGHeaderROMChecksumResult.setText(c__("Game Data", "Valid") + " (0x{:04X})".format(self.CONN.INFO.get("rom_checksum", 0)))
					self.lblDMGHeaderROMChecksumResult.setStyleSheet("QLabel { color: green; }")
					self.SetStatus4aText(__("Done!"))
					msg = __("The ROM backup is complete and the checksum was verified successfully!")
					msgbox.setText(msg + msg_te)
					msgbox.exec()
				else:
					self.SetStatus4aText(__("Done!"))
					if "mapper_raw" in self.CONN.INFO and self.CONN.INFO["mapper_raw"] in (0x202, 0x203, 0x205):
						msg = __("The ROM backup is complete.")
						msgbox.setText(msg + msg_te)
						msgbox.exec()
					else:
						self.lblDMGHeaderROMChecksumResult.setText(c__("Game Data", "Invalid") + " (0x{:04X}≠0x{:04X})".format(self.CONN.INFO.get("rom_checksum_calc", 0), self.CONN.INFO.get("rom_checksum", 0)))
						self.lblDMGHeaderROMChecksumResult.setStyleSheet("QLabel { color: red; }")
						msg = __("The ROM was dumped, but the checksum is not correct.")
						button_gmmc1 = None
						if self.CONN.INFO["loop_detected"] is not False:
							msg += "\n\n" + __("A data loop was detected in the ROM backup at position {pos} ({size}). This may indicate a bad dump or overdump.", pos="0x{:X}".format(self.CONN.INFO["loop_detected"]), size=Formatter.file_size(self.CONN.INFO["loop_detected"], as_int=True))
						else:
							msg += " " + __("This may indicate a bad dump, however this can be normal for some reproduction cartridges, unlicensed games, prototypes, patched games and intentional overdumps.") + " " + c__("Advice when ROM backup was bad", "You can also try to change the read mode in the options.")
							if self.CONN.GetMode() == "DMG" and self.cmbDMGHeaderMapperResult.currentText() == "MBC1":
								msg += "\n\n" + __("If this is a “{gb_memory_cartridge}”, try the “{label}” option.", gb_memory_cartridge="GB-Memory Cartridge", label=__("Retry with {mapper}", mapper="G-MMC1"))
								button_gmmc1 = msgbox.addButton(__("Retry with {mapper}", mapper="G-MMC1"), QtWidgets.QMessageBox.ActionRole)
						msgbox.setText(msg + msg_te)
						msgbox.setIcon(QtWidgets.QMessageBox.Warning)
						msgbox.exec()
						if msgbox.clickedButton() == button_gmmc1:
							if self.CheckDeviceAlive():
								self.cmbDMGHeaderMapperResult.setCurrentIndex(ConvertMapperToMapperType(0x105)[2])
								self.cmbDMGHeaderROMSizeResult.setCurrentIndex(5)
								cart_type = 0
								cart_types = self.CONN.GetSupportedCartridgesDMG()
								for i in range(0, len(cart_types[0])):
									if "dmg-mmsa-jpn" in cart_types[1][i]:
										self.cmbDMGCartridgeTypeResult.setCurrentIndex(i)
										cart_type = i
								self.STATUS["args"]["mbc"] = 0x105
								self.STATUS["args"]["rom_size"] = 1048576
								self.STATUS["args"]["cart_type"] = cart_type
								self.STATUS["time_start"] = time.time()
								QtCore.QTimer.singleShot(1, lambda: [ self.CONN.BackupROM(fncSetProgress=self.PROGRESS.SetProgress, args=self.STATUS["args"]) ])
								return
			elif self.CONN.GetMode() == "AGB":
				if "db" in self.CONN.INFO and self.CONN.INFO["db"] is not None:
					if self.CONN.INFO["db"]["rc"] == self.CONN.INFO.get("file_crc32"):
						self.lblAGBHeaderROMChecksumResult.setText(c__("Game Data", "Valid") + " (0x{:06X})".format(self.CONN.INFO["db"]["rc"]))
						self.lblAGBHeaderROMChecksumResult.setStyleSheet("QLabel { color: green; }")
						self.SetStatus4aText(__("Done!"))
						msg = __("The ROM backup is complete and the checksum was verified successfully!")
						msgbox.setText(msg + msg_te)
						msgbox.exec()
					else:
						self.lblAGBHeaderROMChecksumResult.setText(c__("Game Data", "Invalid") + " (0x{:06X}≠0x{:06X})".format(self.CONN.INFO.get("file_crc32", 0), self.CONN.INFO["db"]["rc"]))
						self.lblAGBHeaderROMChecksumResult.setStyleSheet("QLabel { color: red; }")
						self.SetStatus4aText(__("Done!"))
						msg = __("The ROM backup is complete, but the checksum doesn’t match the known database entry.")
						if self.CONN.INFO["loop_detected"] is not False:
							msg += "\n\n" + __("A data loop was detected in the ROM backup at position {pos} ({size}). This may indicate a bad dump or overdump.", pos="0x{:X}".format(self.CONN.INFO["loop_detected"]), size=Formatter.file_size(self.CONN.INFO["loop_detected"], as_int=True))
						else:
							msg += " " + __("This may indicate a bad dump, however this can be normal for some reproduction cartridges, unlicensed games, prototypes, patched games and intentional overdumps.")
						msgbox.setText(msg + msg_te)
						msgbox.setIcon(QtWidgets.QMessageBox.Warning)
						msgbox.exec()
				else:
					self.lblAGBHeaderROMChecksumResult.setText("0x{:06X}".format(self.CONN.INFO.get("file_crc32", 0)))
					self.lblAGBHeaderROMChecksumResult.setStyleSheet(self.DEFAULT_STYLESHEET)
					self.SetStatus4aText(__("Done!"))
					msg = __("The ROM backup is complete! As there is no known checksum for this ROM in the database, verification was skipped.")
					if self.CONN.INFO["loop_detected"] is not False:
						msg += "\n\n" + __("A data loop was detected in the ROM backup at position {pos} ({size}). This may indicate a bad dump or overdump.", pos="0x{:X}".format(self.CONN.INFO["loop_detected"]), size=Formatter.file_size(self.CONN.INFO["loop_detected"], as_int=True))
						msgbox.setIcon(QtWidgets.QMessageBox.Warning)
					msgbox.setText(msg + msg_te)
					msgbox.exec()

			if msgbox.clickedButton() == button_dump_report:
				if not (dump_report is not False and dumpinfo_file != "" and temp is True):
					try:
						with open(dumpinfo_file, "wb") as f:
							f.write(bytearray([ 0xEF, 0xBB, 0xBF ])) # UTF-8 BOM
							f.write(dump_report.encode("UTF-8"))
					except Exception as e:
						print("Error: {:s}".format(str(e)))
				self.OpenPath(dumpinfo_file)
			elif msgbox.clickedButton() == button_open_dir:
				self.OpenPath(self.STATUS["last_path"], select_file=True)

		elif self.CONN.INFO["last_action"] == 2: # Backup RAM
			self.SetStatus4aText(__("Done!"))
			self.CONN.INFO["last_action"] = 0

			dontShowAgainCameraSavePopup = str(self.SETTINGS.value("SkipCameraSavePopup", default="disabled")).lower() == "enabled"
			if not dontShowAgainCameraSavePopup:
				if self.CONN.GetMode() == "DMG" and self.CONN.INFO["mapper_raw"] == 252:
					# Pocket Camera
					if self.CONN.INFO["transferred"] == 0x20000 or (self.CONN.INFO["transferred"] == 0x100000 and "Unlicensed Photo!" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()):
						cbCameraSavePopup = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Don’t show this message again"), checked=dontShowAgain)
						msgboxCameraPopup = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("Would you like to load your save data with the GB Camera Viewer now?"))
						msgboxCameraPopup.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
						msgboxCameraPopup.setDefaultButton(QtWidgets.QMessageBox.Yes)
						msgboxCameraPopup.setCheckBox(cbCameraSavePopup)
						answer = msgboxCameraPopup.exec()
						dontShowAgainCameraSavePopup = cbCameraSavePopup.isChecked()
						if dontShowAgainCameraSavePopup: self.SETTINGS.setValue("SkipCameraSavePopup", "enabled")
						if answer == QtWidgets.QMessageBox.Yes:
							self.CAMWIN = None
							self.CAMWIN = PocketCameraWindow(self, icon=self.windowIcon(), file=self.CONN.INFO["last_path"], config_path=AppContext.CONFIG_PATH, app_path=AppContext.APP_PATH)
							self.CAMWIN.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
							self.CAMWIN.setModal(True)
							self.CAMWIN.run()
							return

			if "last_path" in self.CONN.INFO:
				button_open_dir = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "Open Fol&der"), QtWidgets.QMessageBox.ActionRole)
			msgbox.setText(__("The save data backup is complete!") + msg_te)
			msgbox.exec()
			if "last_path" in self.CONN.INFO and msgbox.clickedButton() == button_open_dir:
				self.OpenPath(self.CONN.INFO["last_path"], select_file=True)

		elif self.CONN.INFO["last_action"] == 3: # Restore RAM
			self.SetStatus4aText(__("Done!"))
			self.CONN.INFO["last_action"] = 0
			if "save_erase" in self.CONN.INFO and self.CONN.INFO["save_erase"]:
				msg_text = __("The save data was erased.")
				del(self.CONN.INFO["save_erase"])
			elif "verified" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["verified"] == True:
				msg_text = __("The save data was written and verified successfully!")
			else:
				msg_text = __("Save data writing complete!")
			msgbox.setText(msg_text + msg_te)
			msgbox.exec()

		elif self.CONN.INFO["last_action"] == 4: # Flash ROM
			if "broken_sectors" in self.CONN.INFO:
				s = ""
				sc = 0
				for sector in self.CONN.INFO["broken_sectors"]:
					sc += 1
					if sc > 10:
						s += c__("Shortened list of Broken Sectors (e.g. 0x0000~0x07FF and others)", "and others") + "  "
						break
					s += "0x{:X}~0x{:X}, ".format(sector[0], sector[0]+sector[1]-1)
				msg_v = ___("The ROM was written completely, but verification of written data failed in the following sector: {sectors}.", "The ROM was written completely, but verification of written data failed in the following sectors: {sectors}.", n=sc, sectors=s[:-2])
				if "verify_error_params" in self.CONN.INFO:
					if self.CONN.GetMode() == "DMG":
						cart_types = self.CONN.GetSupportedCartridgesDMG()[0]
					elif self.CONN.GetMode() == "AGB":
						cart_types = self.CONN.GetSupportedCartridgesAGB()[0]
					cart_type_str = " ({:s})".format(cart_types[self.CONN.INFO["dump_info"]["cart_type"]])
					msg_v += "\n\n" + __(
						"Troubleshooting advice:\n"
						"- Clean cartridge contacts\n"
						"- Check soldering if it’s a DIY cartridge\n"
						"- Avoid passive USB hubs and try different USB ports/cables\n"
						"- Check flashcart profile selection"
					) + cart_type_str + "\n" + __("- Check cartridge ROM storage size (at least {rom_size} is required)", rom_size=Formatter.file_size(self.CONN.INFO["verify_error_params"]["rom_size"]))
					if "mapper_selection_type" in self.CONN.INFO["verify_error_params"]:
						if self.CONN.INFO["verify_error_params"]["mapper_selection_type"] == 1: # manual
							msg_v += "\n" + __("- Check mapper type used:") + " " + self.CONN.INFO["verify_error_params"]["mapper_name"] + " (" + c__("Mapper Type", "manual selection") + ")"
						elif self.CONN.INFO["verify_error_params"]["mapper_selection_type"] == 2: # forced by cart type
							msg_v += "\n" + __("- Check mapper type used:") + " " + self.CONN.INFO["verify_error_params"]["mapper_name"] + " (" + c__("Mapper Type", "forced by selected flashcart profile") + ")"
						if self.CONN.INFO["verify_error_params"]["rom_size"] > self.CONN.INFO["verify_error_params"]["mapper_max_size"]:
							msg_v += "\n" + __("- Check mapper type ROM size limit: likely up to {max_size}", max_size=Formatter.file_size(self.CONN.INFO["verify_error_params"]["mapper_max_size"]))
				msg_v += "\n\n" + __("Do you want to write the sectors again that failed verification?")

				answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg_v, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
				if answer == QtWidgets.QMessageBox.Yes:
					args = self.STATUS["args"]
					args.update({"flash_sectors":self.CONN.INFO["broken_sectors"]})
					self.CONN.FlashROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
					return

			self.CONN.INFO["last_action"] = 0
			self.SetStatus4aText(__("Done!"))
			if "verified" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["verified"] == True:
				msg = __("The ROM was written and verified successfully!")
			else:
				msg = __("ROM writing complete!")

			msgbox.setText(msg + msg_te)
			msgbox.exec()

			if self.CONN.GetMode() == "AGB" and "Batteryless SRAM" in AgbSaveTypes().GetStringList()[self.cmbAGBSaveTypeResult.currentIndex()]:
				temp1 = self.cmbAGBCartridgeTypeResult.currentIndex()
				temp2 = self.cmbAGBSaveTypeResult.currentIndex()
				if "batteryless_sram" in self.CONN.INFO["dump_info"]:
					temp3 = self.CONN.INFO["dump_info"]["batteryless_sram"]
				self.ReadCartridge(resetStatus=False)
				self.cmbAGBCartridgeTypeResult.setCurrentIndex(temp1)
				self.cmbAGBSaveTypeResult.setCurrentIndex(temp2)
				if "batteryless_sram" in self.CONN.INFO["dump_info"]:
					self.CONN.INFO["dump_info"]["batteryless_sram"] = temp3
			else:
				self.ReadCartridge(resetStatus=False)

		elif self.CONN.INFO["last_action"] == 6: # Detect Cartridge
			self.SetStatus4aText(__("Ready."))
			self.CONN.INFO["last_action"] = 0
			self.FinishDetectCartridge(self.CONN.INFO.get("detect_cart", False))

		else:
			self.SetStatus4aText(__("Ready."))
			self.CONN.INFO["last_action"] = 0

		if dontShowAgain: self.SETTINGS.setValue("SkipFinishMessage", "enabled")
		# if self.CONN is not None and self.CONN.CanPowerCycleCart(): self.CONN.CartPowerOff()
		self.SetProgressBars(min=0, max=1, value=1)

	def DMGMapperTypeChanged(self, index):
		if index in (-1, 0): return

	def SetDMGMapperResult(self, cart_type):
		mbc = 0
		if "mbc" in cart_type:
			if isinstance(cart_type["mbc"], int):
				mbc = cart_type["mbc"]
			elif self.cmbDMGHeaderMapperResult.currentIndex() > 0:
				mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
			self.cmbDMGHeaderMapperResult.setCurrentIndex(ConvertMapperToMapperType(mbc)[2])

	def CartridgeTypeChanged(self, index):
		self.STATUS["cart_type"] = {}
		if index in (-1, 0): return
		if "detect_cartridge_args" in self.STATUS: return
		if self.CONN.GetMode() == "DMG":
			cart_types = self.CONN.GetSupportedCartridgesDMG()
			if cart_types[1][index] == "RETAIL": # special keyword
				pass
			else:
				if "flash_size" in cart_types[1][index] and not "dmg-mmsa-jpn" in cart_types[1][index]:
					if cart_types[1][index]["flash_size"] in RomSizes():
						self.cmbDMGHeaderROMSizeResult.setCurrentIndex(RomSizes().GetIndex(cart_types[1][index]["flash_size"]))
				self.STATUS["cart_type"] = cart_types[1][index]
				self.SetDMGMapperResult(cart_types[1][index])

		elif self.CONN.GetMode() == "AGB":
			cart_types = self.CONN.GetSupportedCartridgesAGB()
			if cart_types[1][index] == "RETAIL": # special keyword
				pass
			else:
				if "flash_size" in cart_types[1][index] and cart_types[1][index]["flash_size"] in RomSizes():
					self.cmbAGBHeaderROMSizeResult.setCurrentIndex(RomSizes().GetIndex(cart_types[1][index]["flash_size"]))
				self.STATUS["cart_type"] = cart_types[1][index]

	def CheckHeader(self):
		if "dump_info" not in self.CONN.INFO or "header" not in self.CONN.INFO["dump_info"]:
			return True
		data = self.CONN.INFO["dump_info"]["header"]
		if not (self.CONN.GetMode() == "DMG" and data["mapper_raw"] in (0x203, 0x204, 0x205)) and not data['logo_correct'] and not data["header_checksum_correct"] and data['empty'] == False:
			msg = __("ROM header checksum and boot logo checks failed. Please ensure that the cartridge contacts are clean.") + "\n\n" + __("Do you still want to continue?")
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
			if answer == QtWidgets.QMessageBox.No: return False
		return True

	def BackupROM(self):
		if not self.CheckDeviceAlive(): return
		if not self.CheckHeader(): return

		mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())

		rom_size = 0
		cart_type = 0
		path = generate_filename(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=self.SETTINGS)
		if self.CONN.GetMode() == "DMG":
			setting_name = "LastDirRomDMG"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)

			path = QtWidgets.QFileDialog.getSaveFileName(self, __("Backup ROM"), last_dir + os.sep + path, __("Game Boy ROM File") + " (" + " ".join("*" + e for e in ROM_EXTS_DMG_READ) + ");;" + __("All Files") + " (*.*)")[0]
			cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()
			rom_size = RomSizes().GetSize(self.cmbDMGHeaderROMSizeResult.currentIndex())

		elif self.CONN.GetMode() == "AGB":
			setting_name = "LastDirRomAGB"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)

			rom_size = RomSizes().GetSize(self.cmbAGBHeaderROMSizeResult.currentIndex())
			path = QtWidgets.QFileDialog.getSaveFileName(self, __("Backup ROM"), last_dir + os.sep + path, __("Game Boy Advance ROM File") + " (" + " ".join("*" + e for e in ROM_EXTS_AGB) + ");;" + __("All Files") + " (*.*)")[0]
			cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()

		if (path == ""): return

		self.SETTINGS.setValue(setting_name, os.path.dirname(path))
		self.lblDMGHeaderROMChecksumResult.setStyleSheet(self.DEFAULT_STYLESHEET)
		self.lblAGBHeaderROMChecksumResult.setStyleSheet(self.DEFAULT_STYLESHEET)

		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.grpActions.setEnabled(False)
		self.mnuTools.setEnabled(False)
		self.mnuConfig.setEnabled(False)
		self.mnuLanguage.setEnabled(False)
		self.SetStatus4aText(__("Preparing..."))
		qt_app.processEvents()
		args = { "path":path, "mbc":mbc, "rom_size":rom_size, "agb_rom_size":rom_size, "fast_read_mode":True, "cart_type":cart_type, "settings":self.SETTINGS }
		self.CONN.BackupROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
		self.grpStatus.setTitle(__("Transfer Status"))
		self.STATUS["time_start"] = time.time()
		self.STATUS["last_path"] = path
		self.STATUS["args"] = args

	def FlashROM(self, dpath=""):
		if not self.CheckDeviceAlive(): return

		just_erase = False
		path = ""
		if dpath != "":
			ext = os.path.splitext(dpath)[1]
			if ext.lower() == ".isx":
				text = __("The following ISX file will now be converted to a regular ROM file and then written to the flash cartridge:") + "\n" + dpath
			else:
				text = __("The following ROM file will now be written to the flash cartridge:") + "\n" + dpath
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
			if answer == QtWidgets.QMessageBox.Cancel:
				if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])
				return
			path = dpath

		if self.CONN.GetMode() == "DMG":
			setting_name = "LastDirRomDMG"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			carts = self.CONN.GetSupportedCartridgesDMG()[1]
			cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()
		elif self.CONN.GetMode() == "AGB":
			setting_name = "LastDirRomAGB"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			carts = self.CONN.GetSupportedCartridgesAGB()[1]
			cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()
		else:
			return

		if cart_type == 0:
			if "detected_cart_type" not in self.STATUS: self.STATUS["detected_cart_type"] = ""
			if self.STATUS["detected_cart_type"] == "":
				self.STATUS["detected_cart_type"] = "WAITING_FLASH"
				self.STATUS["detect_cartridge_args"] = { "dpath":path }
				self.STATUS["can_skip_message"] = True
				self.DetectCartridge(checkSaveType=False)
				return
			cart_type = self.STATUS["detected_cart_type"]
			if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

			if cart_type is False: # clicked Cancel button
				return
			elif cart_type is None or cart_type == 0 or not isinstance(cart_type, int):
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("A compatible flashcart profile could not be auto-detected."), QtWidgets.QMessageBox.Ok)
				return

			if self.CONN.GetMode() == "DMG":
				self.cmbDMGCartridgeTypeResult.setCurrentIndex(cart_type)
			elif self.CONN.GetMode() == "AGB":
				self.cmbAGBCartridgeTypeResult.setCurrentIndex(cart_type)

		if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

		if self.CONN.GetMode() == "DMG":
			self.SetDMGMapperResult(carts[cart_type])
			mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
		else:
			mbc = 0

		if (path == ""):
			if self.CONN.GetMode() == "DMG":
				path = QtWidgets.QFileDialog.getOpenFileName(self, __("Write ROM"), last_dir, __("Game Boy ROM File") + " (" + " ".join("*" + e for e in ROM_EXTS_DMG) + ");;" + __("All Files") + " (*.*)")[0]
			elif self.CONN.GetMode() == "AGB":
				path = QtWidgets.QFileDialog.getOpenFileName(self, __("Write ROM"), last_dir, __("Game Boy Advance ROM File") + " (" + " ".join("*" + e for e in ROM_EXTS_AGB) + ");;" + __("All Files") + " (*.*)")[0]

		if (path == ""):
			msg = __("No ROM file was selected. Do you want to wipe the ROM contents of the cartridge instead?")
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
			if answer == QtWidgets.QMessageBox.No: return
			just_erase = True
			path = False
			buffer = bytearray()

		if not just_erase:
			self.SETTINGS.setValue(setting_name, os.path.dirname(path))
			if os.path.getsize(path) == 0:
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("The selected ROM file is empty."), QtWidgets.QMessageBox.Ok)
				return
			if os.path.getsize(path) > 0x20000000: # reject too large files to avoid exploding RAM
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("ROM files bigger than 512{mib} are not supported.", mib=__(" MiB")), QtWidgets.QMessageBox.Ok)
				return

			with open(path, "rb") as file:
				ext = os.path.splitext(path)[1]
				if ext.lower() == ".isx":
					buffer = bytearray(file.read())
					buffer = from_isx(buffer)
				else:
					buffer = bytearray(file.read(0x1000))
			rom_size = os.stat(path).st_size
			if "flash_size" in carts[cart_type]:
				if rom_size > carts[cart_type]['flash_size']:
					msg = __("The selected flashcart profile seems to support ROMs that are up to {max_size} in size, but the file you selected is {file_size}.", max_size=Formatter.file_size(carts[cart_type]['flash_size']), file_size=Formatter.file_size(os.path.getsize(path)))
					msg += " " + __("You can still give it a try, but it’s possible that it’s too large which may cause the ROM writing to fail.")
					answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
					if answer == QtWidgets.QMessageBox.Cancel: return

		override_voltage = False
		voltage_fallback = False
		ask_voltage_fallback = False
		device_voltage_locked = self.CONN.CanSetVoltageByAutoswitch() and not self.CONN.CanSetVoltageByCode()
		if not device_voltage_locked:
			if 'voltage_variants' in carts[cart_type] and carts[cart_type]['voltage'] == 3.3:
				override_voltage = 3.3
				voltage_fallback = 5
				ask_voltage_fallback = True
			elif carts[cart_type].get('voltage') == 5 and has_3v_compatible_profile(carts, cart_type):
				# Some PCBs share the same flash chip but need 3.3V; try 3.3V silently first,
				# ask before falling back to 5V if writing fails.
				override_voltage = 3.3
				voltage_fallback = 5
				ask_voltage_fallback = True

		prefer_chip_erase = self.SETTINGS.value("PreferChipErase", default="disabled")
		if prefer_chip_erase and prefer_chip_erase.lower() == "enabled":
			prefer_chip_erase = True
		else:
			prefer_chip_erase = False

		verify_write = self.SETTINGS.value("VerifyData", default="enabled")
		if verify_write and verify_write.lower() == "enabled":
			verify_write = True
		else:
			verify_write = False

		fix_bootlogo = False
		fix_header = False
		if not just_erase and len(buffer) >= 0x1000:
			if self.CONN.GetMode() == "DMG":
				hdr = RomFileDMG(buffer).GetHeader()

				if not compare_mbc(hdr["mapper_raw"], mbc):
					mbc1 = get_mbc_name(mbc)
					mbc2 = get_mbc_name(hdr["mapper_raw"])
					compatible_mbc = [ "None", "MBC2", "MBC3", "MBC30", "MBC5", "MBC7", "MAC-GBD", "G-MMC1", "HuC-1", "HuC-3", "Unlicensed MBCX Mapper", "Unlicensed 256M Multi Cart Mapper" ]
					if (mbc2 == "None") or (mbc1 == "G-MMC1" and mbc2 == "MBC1") or (mbc2 == "G-MMC1" and mbc1 == "MBC1"):
						pass
					elif mbc2 != "None" and not (mbc1 in compatible_mbc and mbc2 in compatible_mbc):
						if "mbc" in carts[cart_type] and carts[cart_type]["mbc"] == "manual":
							msg_text = __("The ROM file you selected uses a different mapper type than your current selection. What mapper should be used when writing the ROM?") + "\n\n" + __("Selected mapper type:") + " " + mbc1 + "\n" + __("ROM mapper type:") + " " + mbc2
							msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg_text)
							if mbc == 0: mbc1 = "MBC5"
							button_1 = msgbox.addButton("{:s}".format(mbc1), QtWidgets.QMessageBox.ActionRole)
							button_2 = msgbox.addButton("{:s}".format(mbc2), QtWidgets.QMessageBox.ActionRole)
							button_cancel = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Cancel"), QtWidgets.QMessageBox.RejectRole)
							msgbox.setDefaultButton(button_1)
							msgbox.setEscapeButton(button_cancel)
							msgbox.exec()
							if msgbox.clickedButton() == button_cancel:
								return
							elif msgbox.clickedButton() == button_2:
								mbc = hdr["mapper_raw"]
						else:
							if mbc1 == "None": mbc1 = c__("Mapper Type", c__("Mapper Type", "None/Unknown"))
							msg_text = __("Warning: The ROM file you selected uses a different mapper type than your flashcart profile. The ROM file may be incompatible with your cartridge.") + "\n\n" + __("Selected mapper type:") + " " + mbc1 + "\n" + __("ROM mapper type:") + " " + mbc2
							answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg_text, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
							if answer == QtWidgets.QMessageBox.Cancel: return
			elif self.CONN.GetMode() == "AGB":
				hdr = RomFileAGB(buffer).GetHeader()

			if not hdr["logo_correct"] and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and mbc not in (0x203, 0x205))):
				msg_text = __("Warning: The ROM file you selected will not boot on actual hardware due to invalid boot logo data.")
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
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg_text)
					button_1 = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Fix and Continue"), QtWidgets.QMessageBox.ActionRole)
					button_2 = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "Continue &without fixing"), QtWidgets.QMessageBox.ActionRole)
					button_cancel = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Cancel"), QtWidgets.QMessageBox.RejectRole)
					msgbox.setDefaultButton(button_1)
					msgbox.setEscapeButton(button_cancel)
					msgbox.exec()
					if msgbox.clickedButton() == button_1:
						fix_bootlogo = bootlogo
					elif msgbox.clickedButton() == button_cancel:
						return
					elif msgbox.clickedButton() == button_2:
						pass
				else:
					dprint("Couldn’t find boot logo file in configuration folder")
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg_text)
					msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&OK"), QtWidgets.QMessageBox.ActionRole)
					button_cancel = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Cancel"), QtWidgets.QMessageBox.RejectRole)
					msgbox.setDefaultButton(button_cancel)
					msgbox.setEscapeButton(button_cancel)
					retval = msgbox.exec()
					if retval == QtWidgets.QMessageBox.Cancel:
						return
					else:
						pass

			if not hdr["header_checksum_correct"] and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and mbc not in (0x203, 0x205))):
				msg_text = __("Warning: The ROM file you selected will not boot on actual hardware due to an invalid header checksum (expected {calc} instead of {actual}).", calc=f"0x{hdr['header_checksum_calc']:02X}", actual=f"0x{hdr['header_checksum']:02X}")
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg_text)
				button_1 = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Fix and Continue"), QtWidgets.QMessageBox.ActionRole)
				button_2 = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "Continue &without fixing"), QtWidgets.QMessageBox.ActionRole)
				button_cancel = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Cancel"), QtWidgets.QMessageBox.RejectRole)
				msgbox.setDefaultButton(button_1)
				msgbox.setEscapeButton(button_cancel)
				msgbox.exec()
				if msgbox.clickedButton() == button_1:
					fix_header = True
				elif msgbox.clickedButton() == button_cancel:
					return
				elif msgbox.clickedButton() == button_2:
					pass

		flash_offset = 0
		force_wr_pullup = self.SETTINGS.value("ForceWrPullup", default="disabled").lower() == "enabled"

		effective_voltage = override_voltage if override_voltage is not False else carts[cart_type].get("voltage")
		if (effective_voltage == 3.3 or 'voltage_variants' in carts[cart_type]) and device_voltage_locked and self.CONN.GetMode() == "DMG":
			msg_text = __("Warning: A 3.3V flashcart profile is selected, but your device is fixed to a 5V supply in Game Boy mode. Writing to a 3.3V flash chip at 5V may cause overvoltage issues.") + "\n" + __("Do you want to continue?")
			answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg_text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
			if answer == QtWidgets.QMessageBox.Cancel: return

		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.grpActions.setEnabled(False)
		self.mnuTools.setEnabled(False)
		self.mnuConfig.setEnabled(False)
		self.mnuLanguage.setEnabled(False)
		self.SetStatus4aText(__("Preparing..."))
		qt_app.processEvents()
		if len(buffer) > 0x1000 or just_erase:
			if just_erase:
				prefer_chip_erase = True
				verify_write = False
			args = { "path":"", "buffer":buffer, "cart_type":cart_type, "override_voltage":override_voltage, "prefer_chip_erase":prefer_chip_erase, "fast_read_mode":True, "verify_write":verify_write, "fix_header":fix_header, "fix_bootlogo":fix_bootlogo, "mbc":mbc, "voltage_fallback":voltage_fallback, "ask_voltage_fallback":ask_voltage_fallback }
		else:
			args = { "path":path, "cart_type":cart_type, "override_voltage":override_voltage, "prefer_chip_erase":prefer_chip_erase, "fast_read_mode":True, "verify_write":verify_write, "fix_header":fix_header, "fix_bootlogo":fix_bootlogo, "mbc":mbc, "flash_offset":flash_offset, "force_wr_pullup":force_wr_pullup, "voltage_fallback":voltage_fallback, "ask_voltage_fallback":ask_voltage_fallback }
		args["compare_sectors"] = self.SETTINGS.value("CompareSectors", default="disabled").lower() == "enabled"
		self.CONN.FlashROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
		#self.CONN._FlashROM(args=args)
		self.grpStatus.setTitle(__("Transfer Status"))
		buffer = None
		self.STATUS["time_start"] = time.time()
		self.STATUS["last_path"] = path
		self.STATUS["args"] = args

	def BackupRAM(self, dpath=""):
		if not self.CheckDeviceAlive(): return

		rtc = False
		path = ""

		# Detect Cartridge needed?
		if \
			(self.CONN.GetMode() == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < AgbSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in AgbSaveTypes().GetStringList()[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(self.CONN.GetMode() == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < DmgSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()) or \
			(self.CONN.GetMode() == "DMG" and "Unlicensed Photo!" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()) \
		:
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("This feature is not supported in Legacy Mode."), standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return

			if self.CONN.GetMode() == "AGB":
				cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()
			elif self.CONN.GetMode() == "DMG":
				cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()
			if cart_type == 0 or ("dump_info" not in self.CONN.INFO or "batteryless_sram" not in self.CONN.INFO["dump_info"]):
				if "detected_cart_type" not in self.STATUS: self.STATUS["detected_cart_type"] = ""
				if self.STATUS["detected_cart_type"] == "":
					self.STATUS["detected_cart_type"] = "WAITING_SAVE_READ"
					self.STATUS["detect_cartridge_args"] = { "dpath":path }
					self.STATUS["can_skip_message"] = True
					self.DetectCartridge(checkSaveType=True)
					return
				cart_type = self.STATUS["detected_cart_type"]
				if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

				if cart_type is False: # clicked Cancel button
					return
				elif cart_type is None or cart_type == 0 or not isinstance(cart_type, int):
					QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("A compatible flashcart profile could not be auto-detected."), QtWidgets.QMessageBox.Ok)
					return
				if self.CONN.GetMode() == "AGB":
					self.cmbAGBCartridgeTypeResult.setCurrentIndex(cart_type)
				elif self.CONN.GetMode() == "DMG":
					self.cmbDMGCartridgeTypeResult.setCurrentIndex(cart_type)

		cart_type = 0
		if self.CONN.GetMode() == "DMG":
			setting_name = "LastDirSaveDataDMG"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
			save_type = DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetMbc()
			if save_type == 0:
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("No save type was selected."), QtWidgets.QMessageBox.Ok)
				return
			cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()

		elif self.CONN.GetMode() == "AGB":
			setting_name = "LastDirSaveDataAGB"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			mbc = 0
			save_type = self.cmbAGBSaveTypeResult.currentIndex()
			if save_type == 0:
				QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("No save type was selected."), QtWidgets.QMessageBox.Ok)
				return
			cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()
		else:
			return

		if not self.CheckHeader(): return
		if dpath == "":
			path = generate_filename(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=self.SETTINGS)
			path = os.path.splitext(path)[0]

			add_date_time = self.SETTINGS.value("SaveFileNameAddDateTime", default="disabled")
			if len(path) > 0 and add_date_time and add_date_time.lower() == "enabled":
				path += "_{:s}".format(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

			path += ".sav"
			path = QtWidgets.QFileDialog.getSaveFileName(self, "Backup Save Data", last_dir + os.sep + path, "Save Data File (" + " ".join("*" + e for e in SAVE_EXTS) + ");;All Files (*.*)")[0]
			if (path == ""): return
		else:
			path = dpath

		verify_read = self.SETTINGS.value("VerifyData", default="enabled")
		if verify_read and verify_read.lower() == "enabled":
			verify_read = True
		else:
			verify_read = False

		rtc = False
		if self.CONN.INFO["has_rtc"] is True:
			if self.CONN.GetMode() == "DMG" and mbc in (0x10, 0x110) and not self.CONN.IsClkConnected():
				rtc = False
			else:
				msg = __("A Real Time Clock cartridge was detected. Do you want the cartridge’s Real Time Clock register values also to be saved?")
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.Cancel: return
				rtc = (answer == QtWidgets.QMessageBox.Yes)

		bl_args = {}
		if \
			(self.CONN.GetMode() == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < AgbSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in AgbSaveTypes().GetStringList()[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(self.CONN.GetMode() == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < DmgSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()) \
		:
			if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

			if "dump_info" in self.CONN.INFO and "batteryless_sram" in self.CONN.INFO["dump_info"]:
				detected = self.CONN.INFO["dump_info"]["batteryless_sram"]
			else:
				detected = False

			if self.CONN.GetMode() == "AGB":
				rom_size = RomSizes().GetSize(self.cmbAGBHeaderROMSizeResult.currentIndex())
			elif self.CONN.GetMode() == "DMG":
				rom_size = RomSizes().GetSize(self.cmbDMGHeaderROMSizeResult.currentIndex())
			bl_args = self.GetBLArgs(rom_size=rom_size, detected=detected)
			if bl_args is False: return

		self.SETTINGS.setValue(setting_name, os.path.dirname(path))

		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.grpActions.setEnabled(False)
		self.mnuTools.setEnabled(False)
		self.mnuConfig.setEnabled(False)
		self.mnuLanguage.setEnabled(False)
		self.SetStatus4aText(__("Preparing..."))
		qt_app.processEvents()

		if len(bl_args) > 0:
			args = { "path":path, "mbc":mbc, "rom_size":bl_args["bl_size"], "agb_rom_size":bl_args["bl_size"], "fast_read_mode":True, "cart_type":cart_type }
			args.update(bl_args)
			self.CONN.BackupROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
		else:
			args = { "path":path, "mbc":mbc, "save_type":save_type, "rtc":rtc, "verify_read":verify_read, "cart_type":cart_type }
			self.CONN.BackupRAM(fncSetProgress=self.PROGRESS.SetProgress, args=args)

		self.grpStatus.setTitle(__("Transfer Status"))
		self.STATUS["time_start"] = time.time()
		self.STATUS["last_path"] = path
		self.STATUS["args"] = args

	def WriteRAM(self, dpath="", erase=False, test=False, skip_warning=False):
		if not self.CheckDeviceAlive(): return
		mode = self.CONN.GetMode()

		path = ""
		if erase is True:
			dpath = ""

		# Detect Cartridge needed?
		if not test and ( \
			(mode == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < AgbSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in AgbSaveTypes().GetStringList()[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(mode == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < DmgSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()) or \
			(mode == "DMG" and "Unlicensed Photo!" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()) \
		):
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("This feature is not supported in Legacy Mode."), standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return

			if mode == "AGB":
				cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()
			elif mode == "DMG":
				cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()
			if cart_type == 0 or ("dump_info" not in self.CONN.INFO or "batteryless_sram" not in self.CONN.INFO["dump_info"]):
				if "detected_cart_type" not in self.STATUS: self.STATUS["detected_cart_type"] = ""
				if self.STATUS["detected_cart_type"] == "":
					self.STATUS["detected_cart_type"] = "WAITING_SAVE_WRITE"
					self.STATUS["detect_cartridge_args"] = { "dpath":dpath, "erase":erase }
					self.STATUS["can_skip_message"] = True
					self.DetectCartridge(checkSaveType=True)
					return
				cart_type = self.STATUS["detected_cart_type"]
				if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

				if cart_type is False: # clicked Cancel button
					return
				elif cart_type is None or cart_type == 0 or not isinstance(cart_type, int):
					QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("A compatible flashcart profile could not be auto-detected."), QtWidgets.QMessageBox.Ok)
					return
				if mode == "AGB":
					self.cmbAGBCartridgeTypeResult.setCurrentIndex(cart_type)
				elif mode == "DMG":
					self.cmbDMGCartridgeTypeResult.setCurrentIndex(cart_type)

		if mode == "DMG":
			setting_name = "LastDirSaveDataDMG"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
			save_type = DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetMbc()
			if save_type == 0:
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("No save type was selected."), QtWidgets.QMessageBox.Ok)
				return
			cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()

		elif mode == "AGB":
			setting_name = "LastDirSaveDataAGB"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			mbc = 0
			save_type = self.cmbAGBSaveTypeResult.currentIndex()
			if save_type == 0:
				QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("No save type was selected."), QtWidgets.QMessageBox.Ok)
				return
			cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()
		else:
			return
		if not self.CheckHeader(): return

		filesize = 0
		if dpath != "":
			if not skip_warning:
				text = __("The following save data file will now be written to the cartridge:") + "\n" + dpath
				answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
				if answer == QtWidgets.QMessageBox.Cancel: return
			path = dpath
			self.SETTINGS.setValue(setting_name, os.path.dirname(path))
		elif erase:
			if not skip_warning:
				answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("The save data on your cartridge will now be erased."), QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
				if answer == QtWidgets.QMessageBox.Cancel: return
		elif test:
			path = None
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("This feature is not supported in Legacy Mode."), standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return

			if (mode == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < AgbSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in AgbSaveTypes().GetStringList()[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(mode == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < DmgSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()) or \
			(mode == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < DmgSaveTypes().GetNumberOfTypes() and "Unlicensed Photo!" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()) or \
			("8M DACS" in AgbSaveTypes().GetStringList()[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(mode == "AGB" and "ereader" in self.CONN.INFO and self.CONN.INFO["ereader"] is True) or \
			(mode == "DMG" and "256M Multi Cart" in self.cmbDMGHeaderMapperResult.currentText() and not self.CONN.CanPowerCycleCart()):
				QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("Stress test is not supported for this save type."), QtWidgets.QMessageBox.Ok)
				return
			msg = __("The cartridge’s save chip will be tested for potential problems as follows:\n- Read the same data multiple times\n- Writing and reading different test patterns\n\nPlease ensure the cartridge pins are freshly cleaned and the save data is backed up before proceeding.")
			if not self.CONN.CanPowerCycleCart() and (mode == "AGB" and "SRAM" in self.cmbAGBSaveTypeResult.currentText() or (mode == "DMG" and "SRAM" in self.cmbDMGHeaderSaveTypeResult.currentText())):
				msg += "\n\n" + __("Note: Your {device_name} does not support automatic power cycling, so some tests may be skipped.", device_name=self.CONN.GetName())
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
			if answer == QtWidgets.QMessageBox.Cancel: return
		else:
			if path == "":
				path = generate_filename(mode=mode, header=self.CONN.INFO, settings=self.SETTINGS)
				path = os.path.splitext(path)[0]
				path += ".sav"
			path = QtWidgets.QFileDialog.getOpenFileName(self, __("Restore Save Data"), last_dir + os.sep + path, __("Save Data File") + " (" + " ".join("*" + e for e in SAVE_EXTS) + ");;" + __("All Files") + " (*.*)")[0]
			if not path == "": self.SETTINGS.setValue(setting_name, os.path.dirname(path))
			if (path == ""): return

		if not erase and not test and len(path) > 0:
			filesize = os.path.getsize(path)
			if filesize == 0 or filesize > 0x200000: # reject too large files to avoid exploding RAM
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("The size of this file is not supported."), QtWidgets.QMessageBox.Ok)
				return

		buffer = None
		if mode == "AGB" and "ereader" in self.CONN.INFO and self.CONN.INFO["ereader"] is True:
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("This cartridge is not supported in Legacy Mode."), standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text="")
			button_keep = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Keep existing calibration data"), QtWidgets.QMessageBox.ActionRole)
			self.CONN.ReadHeader()
			cart_name = "e-Reader"
			if self.CONN.INFO["db"] is not None:
				cart_name = self.CONN.INFO["db"]["gn"]
			if "ereader_calibration" in self.CONN.INFO:
				if erase:
					buffer = bytearray([0xFF] * 0x20000)
					msg_text = __("This {cart_name} cartridge currently has calibration data in place. It is strongly recommended to keep the existing calibration data.", cart_name=cart_name) + "\n\n" + __("How do you want to proceed?")
					button_overwrite = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Erase everything"), QtWidgets.QMessageBox.ActionRole)
				else:
					with open(path, "rb") as f: buffer = bytearray(f.read())
					msg_text = __("This {cart_name} cartridge currently has calibration data in place that is different from this save file’s data. It is strongly recommended to keep the existing calibration data unless you actually need to restore it from a previous backup.", cart_name=cart_name) + "\n\n" + __("Would you like to keep the existing calibration data, or overwrite it with data from the file you selected?")
					button_overwrite = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Restore from save data"), QtWidgets.QMessageBox.ActionRole)
				button_cancel = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Cancel"), QtWidgets.QMessageBox.RejectRole)
				msgbox.setText(msg_text)
				msgbox.setDefaultButton(button_keep)
				msgbox.setEscapeButton(button_cancel)

				if buffer[0xD000:0xF000] != self.CONN.INFO["ereader_calibration"]:
					answer = msgbox.exec()
					if msgbox.clickedButton() == button_cancel:
						return
					elif msgbox.clickedButton() == button_keep:
						buffer[0xD000:0xF000] = self.CONN.INFO["ereader_calibration"]
					elif msgbox.clickedButton() == button_overwrite:
						pass
			else:
				msg_text = __("Warning: This {cart_name} cartridge may currently have calibration data in place. Erasing or overwriting this data may render the “{feature_name}” feature unusable. It is strongly recommended to create a backup of the original save data first and store it in a safe place. That way the calibration data can be restored later.", cart_name=cart_name, feature_name="Scan Card") + "\n\n" + __("Do you still want to continue?")
				answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg_text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
				if answer == QtWidgets.QMessageBox.No: return

		elif mode == "DMG" and self.CONN.INFO.get("dump_info", {}).get("header", {}).get("mapper_raw") == 0xFC:
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("This cartridge is not supported in Legacy Mode."), standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text="")
			button_keep = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Keep existing calibration data"), QtWidgets.QMessageBox.ActionRole)
			if "Unlicensed Photo!" not in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString():
				button_reset = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Force recalibration"), QtWidgets.QMessageBox.ActionRole)
			else:
				button_reset = None
			self.CONN.ReadHeader()
			cart_name = "Game Boy Camera"
			if self.CONN.INFO["db"] is not None:
				cart_name = self.CONN.INFO["db"]["gn"]
			if not test:
				if "gbcamera_calibration1" in self.CONN.INFO:
					if erase:
						buffer = bytearray([0x00] * 0x20000)
						if "Unlicensed Photo!" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString():
							buffer += bytearray([0xFF] * 0xE0000)
						msg_text = __("This {cart_name} cartridge currently has calibration data in place.\n\nHow do you want to proceed?", cart_name=cart_name) + "\n\n" + __("It is recommended to keep the existing calibration data, but you can also choose to erase it or overwrite it with data from the file you selected.")
						button_overwrite = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Erase everything"), QtWidgets.QMessageBox.ActionRole)
					else:
						with open(path, "rb") as f: buffer = bytearray(f.read())
						msg_text = __("This {cart_name} cartridge currently has calibration data in place that is different from this save file’s data.\n\nHow do you want to proceed?", cart_name=cart_name)
						button_overwrite = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Restore from save data"), QtWidgets.QMessageBox.ActionRole)
					button_cancel = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Cancel"), QtWidgets.QMessageBox.RejectRole)
					msgbox.setText(msg_text)
					msgbox.setDefaultButton(button_keep)
					msgbox.setEscapeButton(button_cancel)

					if buffer[0x4FF2:0x5000] != self.CONN.INFO["gbcamera_calibration1"] or buffer[0x11FF2:0x12000] != self.CONN.INFO["gbcamera_calibration2"]:
						answer = msgbox.exec()
						if msgbox.clickedButton() == button_cancel:
							return
						elif msgbox.clickedButton() == button_keep:
							buffer[0x4FF2:0x5000] = self.CONN.INFO["gbcamera_calibration1"]
							buffer[0x11FF2:0x12000] = self.CONN.INFO["gbcamera_calibration2"]
						elif msgbox.clickedButton() == button_reset:
							buffer[0x4FF2:0x5000] = bytearray([0xAA] * 0xE)
							buffer[0x11FF2:0x12000] = bytearray([0xAA] * 0xE)
						elif msgbox.clickedButton() == button_overwrite:
							pass
				else:
					msg_text = __("Warning: This {cart_name} cartridge may currently have calibration data in place. It is recommended to create a backup of the original save data first and store it in a safe place. That way the calibration data can be restored later.", cart_name=cart_name) + "\n\n" + __("Do you still want to continue?")
					answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg_text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
					if answer == QtWidgets.QMessageBox.No: return


		verify_write = self.SETTINGS.value("VerifyData", default="enabled")
		if verify_write and verify_write.lower() == "enabled":
			verify_write = True
		else:
			verify_write = False

		rtc = False
		rtc_advance = False

		if not test and self.CONN.INFO["has_rtc"] is True:
			if mode == "DMG" and mbc in (0x10, 0x110) and not self.CONN.IsClkConnected():
				rtc = False
			elif erase or save_size_includes_rtc(mode=mode, mbc=mbc, save_size=filesize, save_type=save_type):
				msg = __("A Real Time Clock cartridge was detected. Do you want the Real Time Clock register values to be written as well?")
				cb = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Adjust RTC"), checked=True)
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
				if erase:
					cb.setChecked(True)
				else:
					msgbox.setCheckBox(cb)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.Cancel: return
				rtc_advance = cb.isChecked()
				rtc = (answer == QtWidgets.QMessageBox.Yes)

		if test:
			self.grpDMGCartridgeInfo.setEnabled(False)
			self.grpAGBCartridgeInfo.setEnabled(False)
			self.grpActions.setEnabled(False)
			self.mnuTools.setEnabled(False)
			self.mnuConfig.setEnabled(False)
			self.mnuLanguage.setEnabled(False)
			self.SetStatus4aText(__("Preparing..."))
			self.grpStatus.setTitle(__("Transfer Status"))
			self.lblStatus1aResult.setText("–")
			self.lblStatus2aResult.setText("–")
			self.lblStatus3aResult.setText("–")
			self.SetStatus4aResult("")
			self.btnCancel.setEnabled(True)
			self.STATUS["stresstest_running"] = True
			qt_app.processEvents()

			test_patterns = [
				bytearray(os.urandom(128*1024)),
				bytearray([ 0x00, 0x00, 0x00, 0x00 ] * 32768),
				bytearray([ 0x55, 0xAA, 0xAA, 0x55 ] * 32768),
				bytearray([ 0x00, 0xFF, 0xFF, 0x00 ] * 32768),
				bytearray([ 0xFF, 0xFF, 0xFF, 0xFF ] * 32768),
			]
			inc = bytearray()
			dec = bytearray()
			for i in range(0, 256):
				inc.append(i)
				dec.append(255-i)
			test_patterns.append(inc)
			test_patterns.append(dec)

			if get_mbc_name(mbc) == "MBC2":
				for j in range(0, len(test_patterns)):
					for i in range(0, len(test_patterns[j])):
						test_patterns[j][i] = test_patterns[j][i] & 0x0F

			test_patterns_names = [
				c__("Stress Test Pattern", "reading twice"),
				c__("Stress Test Pattern", "writing random values"),
				c__("Stress Test Pattern", "writing {pattern}", pattern="00, 00, 00, 00"),
				c__("Stress Test Pattern", "writing {pattern}", pattern="55, AA, AA, 55"),
				c__("Stress Test Pattern", "writing {pattern}", pattern="00, FF, FF, 00"),
				c__("Stress Test Pattern", "writing {pattern}", pattern="FF, FF, FF, FF"),
				c__("Stress Test Pattern", "writing incrementing values"),
				c__("Stress Test Pattern", "writing decrementing values"),
			]
			#if AppContext.DEBUG: test_patterns = [ test_patterns[0], test_patterns[1], test_patterns[4] ]

			time_start = time.time()
			test_ok = 0
			save1 = bytearray([0])
			save2 = bytearray([1])
			backup_fn = AppContext.CONFIG_PATH + os.sep + "backup_stress_test.bin"

			try:
				self.SetStatus4aText(__("Testing ({pattern} 1/2)...", pattern=test_patterns_names[0]))
				self.SetProgressBars(min=0, max=len(test_patterns)+3, value=0)
				qt_app.processEvents()
				args = { "mode":2, "path":path, "mbc":mbc, "save_type":save_type, "rtc":False, "cart_type":cart_type }
				t = threading.Thread(target=lambda a: self.CONN.TransferData(args=a, signal=None), args=[args])
				t.start()
				while t.is_alive():
					qt_app.processEvents()
					time.sleep(0.02)
				t.join()
				save1 = self.CONN.INFO["data"]
				if self.CONN.CanPowerCycleCart():
					self.CONN.CartPowerOff()
					self.SetProgressBars(min=0, max=len(test_patterns)+3, value=1)
					for i in range(5, 0, -1):
						self.SetStatus4aText(__("Waiting for power cycle ({countdown})...", countdown=i))
						qt_app.processEvents()
						time.sleep(1)
						if "stresstest_running" not in self.STATUS: break
					self.CONN.CartPowerOn()
				else:
					time.sleep(1)
				self.SetStatus4aText(__("Testing ({pattern} 2/2)...", pattern=test_patterns_names[0]))
				qt_app.processEvents()
				t = threading.Thread(target=lambda a: self.CONN.TransferData(args=a, signal=None), args=[args])
				t.start()
				while t.is_alive():
					qt_app.processEvents()
					time.sleep(0.02)
				t.join()
				save2 = self.CONN.INFO["data"]
			except KeyError:
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("An error occured. Please ensure you selected the correct save type."), standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				save1 = None

			stop = False
			if (save1 is not None and save1 != save2) and "stresstest_running" in self.STATUS:
				with open(AppContext.CONFIG_PATH + os.sep + "debug_stress_test_1.bin", "wb") as f: f.write(save1)
				with open(AppContext.CONFIG_PATH + os.sep + "debug_stress_test_2.bin", "wb") as f: f.write(save2)
				msg = __("Test {num} ({pattern}) failed!", num=test_ok+1, pattern=test_patterns_names[test_ok]) + "\n" + __("Note: SRAM requires a working battery to retain save data.") + "\n\n" + __("Continue anyway?")
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.No:
					stop = True

			if not stop and save1 is not None:
				with open(backup_fn, "wb") as f: f.write(save1)
				test_ok += 1
				for i in range(0, len(test_patterns)):
					if "stresstest_running" not in self.STATUS: break
					self.SetStatus4aText(__("Testing ({pattern})...", pattern=test_patterns_names[i+1]))
					self.SetProgressBars(min=0, max=len(test_patterns)+3, value=i+2)
					qt_app.processEvents()
					towrite = test_patterns[i]
					args = { "mode":3, "path":path, "mbc":mbc, "save_type":save_type, "rtc":False, "rtc_advance":rtc_advance, "erase":erase, "verify_write":False, "buffer":towrite, "cart_type":cart_type }
					t = threading.Thread(target=lambda a: self.CONN.TransferData(args=a, signal=None), args=[args])
					t.start()
					while t.is_alive():
						qt_app.processEvents()
						time.sleep(0.02)
					t.join()
					if i == 0 \
					and not (save1 != save2): # user "continued anyway"
						self.CONN.CartPowerOff()
						time.sleep(0.5)
						self.CONN.CartPowerOn()
					args = { "mode":2, "path":path, "mbc":mbc, "save_type":save_type, "rtc":False, "cart_type":cart_type }
					t = threading.Thread(target=lambda a: self.CONN.TransferData(args=a, signal=None), args=[args])
					t.start()
					while t.is_alive():
						qt_app.processEvents()
						time.sleep(0.02)
					t.join()
					readback = self.CONN.INFO["data"]
					if towrite[:len(readback)] != readback:
						break
					test_ok += 1

				self.btnCancel.setEnabled(False)
				self.SetStatus4aText(__("Restoring original save data..."))
				self.SetProgressBars(min=0, max=len(test_patterns)+3, value=len(test_patterns)+2)
				qt_app.processEvents()
				args = { "mode":3, "path":path, "mbc":mbc, "save_type":save_type, "rtc":False, "rtc_advance":rtc_advance, "erase":erase, "verify_write":False, "buffer":save1, "cart_type":cart_type }
				t = threading.Thread(target=lambda a: self.CONN.TransferData(args=a, signal=None), args=[args])
				t.start()
				while t.is_alive():
					qt_app.processEvents()
					time.sleep(0.02)
				t.join()
				args = { "mode":2, "path":path, "mbc":mbc, "save_type":save_type, "rtc":False, "cart_type":cart_type }
				t = threading.Thread(target=lambda a: self.CONN.TransferData(args=a, signal=None), args=[args])
				t.start()
				while t.is_alive():
					qt_app.processEvents()
					time.sleep(0.02)
				t.join()

			time_elapsed = time.time() - time_start
			msg_te = "\n\n" + __("Total time elapsed: {elapsed}", elapsed=Formatter.progress_time(time_elapsed, as_float=True))

			self.SetProgressBars(min=0, max=100, value=100)
			self.SetStatus4aText(__("Done!"))
			qt_app.processEvents()

			if "stresstest_running" in self.STATUS:
				if test_ok == len(test_patterns)+1:
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("All tests completed successfully!") + msg_te, standardButtons=QtWidgets.QMessageBox.Ok)
					msgbox.exec()
				else:
					try:
						if test_ok == 0:
							towrite = save1
							readback = save2
						with open(AppContext.CONFIG_PATH + os.sep + "debug_stress_test_1.bin", "wb") as f: f.write(towrite[:len(readback)])
						with open(AppContext.CONFIG_PATH + os.sep + "debug_stress_test_2.bin", "wb") as f: f.write(readback)
					except:
						pass
					if test_ok > 0:
						msg = __("Test {num} ({pattern}) failed!", num=test_ok+1, pattern=test_patterns_names[test_ok])
						msg += msg_te
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Ok)
						msgbox.exec()
			else:
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("The stress test process was cancelled."), standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()

			self.grpDMGCartridgeInfo.setEnabled(True)
			self.grpAGBCartridgeInfo.setEnabled(True)
			self.grpActions.setEnabled(True)
			self.mnuTools.setEnabled(True)
			self.mnuConfig.setEnabled(True)
			self.mnuLanguage.setEnabled(True)
			self.btnCancel.setEnabled(False)

			if not self.CONN.IsConnected(): self.DisconnectDevice()

		else:
			bl_args = {}
			if \
				(mode == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < AgbSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in AgbSaveTypes().GetStringList()[self.cmbAGBSaveTypeResult.currentIndex()]) or \
				(mode == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < DmgSaveTypes().GetNumberOfTypes() and "Batteryless SRAM" in DmgSaveTypes(index=self.cmbDMGHeaderSaveTypeResult.currentIndex()).GetString()) \
			:
				if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

				if "dump_info" in self.CONN.INFO and "batteryless_sram" in self.CONN.INFO["dump_info"]:
					detected = self.CONN.INFO["dump_info"]["batteryless_sram"]
				else:
					detected = False
				bl_args = self.GetBLArgs(rom_size=RomSizes().GetSize(self.cmbAGBHeaderROMSizeResult.currentIndex()), detected=detected)
				if bl_args is False: return

				if mode == "DMG" and self.CONN.CanSetVoltageByAutoswitch() and not self.CONN.CanSetVoltageByCode():
					bl_carts = self.CONN.GetSupportedCartridgesDMG()[1]
					if isinstance(bl_carts[cart_type], dict) and (bl_carts[cart_type].get("voltage") == 3.3 or 'voltage_variants' in bl_carts[cart_type]):
						msg_text = __("Warning: A 3.3V flashcart profile is selected, but your device is fixed to a 5V supply in Game Boy mode. Writing to a 3.3V flash chip at 5V may cause overvoltage issues.") + "\n" + __("Do you want to continue?")
						answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg_text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
						if answer == QtWidgets.QMessageBox.Cancel: return

				args = { "path":path, "cart_type":cart_type, "override_voltage":False, "prefer_chip_erase":False, "fast_read_mode":True, "verify_write":verify_write, "fix_header":False, "fix_bootlogo":False, "mbc":mbc }
				args.update(bl_args)
				args.update({"bl_save":True, "flash_offset":bl_args["bl_offset"], "flash_size":bl_args["bl_size"]})
				if erase:
					args["path"] = ""
					args["buffer"] = bytearray([0xFF] * bl_args["bl_size"])
				self.STATUS["args"] = args
				self.CONN.FlashROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
				#self.CONN._FlashROM(args=args)

			else:
				args = { "path":path, "mbc":mbc, "save_type":save_type, "rtc":rtc, "rtc_advance":rtc_advance, "erase":erase, "verify_write":verify_write, "cart_type":cart_type }
				if buffer is not None:
					args["buffer"] = buffer
					args["path"] = None
					args["erase"] = False
				self.STATUS["args"] = args
				self.CONN.RestoreRAM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
				#args = { "mode":3, "path":path, "mbc":mbc, "save_type":save_type, "rtc":rtc, "rtc_advance":rtc_advance, "erase":erase, "verify_write":verify_write }
				#self.CONN._BackupRestoreRAM(args=args)

			self.STATUS["time_start"] = time.time()
			self.STATUS["last_path"] = path
			self.STATUS["args"] = args
			self.grpDMGCartridgeInfo.setEnabled(False)
			self.grpAGBCartridgeInfo.setEnabled(False)
			self.grpActions.setEnabled(False)
			self.mnuTools.setEnabled(False)
			self.mnuConfig.setEnabled(False)
			self.mnuLanguage.setEnabled(False)
			self.SetStatus4aText(__("Preparing..."))
			self.grpStatus.setTitle(__("Transfer Status"))
			self.lblStatus1aResult.setText("–")
			self.lblStatus2aResult.setText("–")
			self.lblStatus3aResult.setText("–")
			self.SetStatus4aResult("")
			qt_app.processEvents()

	def GetBLArgs(self, rom_size, detected=False):
		mode = self.CONN.GetMode()
		if mode == "AGB":
			locs = [ 0x3C0000, 0x7C0000, 0xFC0000, 0x1FC0000 ]
			lens = [ 0x200, 0x2000, 0x8000, 0x10000, 0x20000 ]
		elif mode == "DMG":
			locs = [ 0xD0000, 0x100000, 0x110000, 0x1D0000, 0x1E0000, 0x210000, 0x3D0000 ]
			lens = [ 0x2000, 0x8000, 0x10000, 0x20000 ]

		temp = self.SETTINGS.value("BatterylessSramLocations{:s}".format(mode), "[]")
		loc_index = None
		len_index = None
		lay_index = None

		try:
			temp = json.loads(temp)
			locs.extend(temp)
			if detected is not False:
				locs.append(detected["bl_offset"])
			locs = list(set(locs))
			locs.sort()
		except:
			pass

		intro_msg = ""
		if detected is not False:
			try:
				loc_index = locs.index(detected["bl_offset"])
				len_index = lens.index(detected["bl_size"])
				intro_msg = __("In order to access Batteryless SRAM save data, its ROM location and size must be specified.") + "\n\n" + __("The previously detected parameters have been pre-selected. Please adjust if necessary, then click “OK” to continue.")
			except:
				detected = False
		if detected is False:
			intro_msg = __("In order to access Batteryless SRAM save data, its ROM location and size must be specified.") + "\n\n"
			intro_msg2 = __("⚠️ The required parameters could not be auto-detected. Please enter the ROM location and size manually below.") + " " + __("Note that wrong values can corrupt your game when writing, so having a full ROM backup is recommended.")

			if mode == "DMG":
				try:
					header = self.CONN.INFO["dump_info"]["header"]
					preselect = header.get("batteryless_sram") or RomFileDMG.GetBatterylessSramConfig(header)
					if preselect is not None:
						game_title_raw = header.get("game_title_raw", header.get("game_title", "")).replace("\x00", "").rstrip()
						loc_index = locs.index(preselect["bl_offset"])
						len_index = lens.index(preselect["bl_size"])
						lay_index = preselect.get("bl_layout")
						intro_msg2 = __("The required parameters were pre-selected based on the ROM title “{game_title}”. These may still be inaccurate, so you can adjust them below if necessary.") + " " + __("Note that wrong values can corrupt your game when writing, so having a full ROM backup is recommended.", game_title=game_title_raw)
				except:
					pass

			intro_msg += intro_msg2

		try:
			if loc_index is None:
				loc_index = locs.index(int(self.SETTINGS.value("BatterylessSramLastLocation{:s}".format(mode))))
		except:
			pass

		bl_args = {}
		if loc_index is None:
			loc_index = 0
			for l in locs:
				if l + 0x40000 >= rom_size: break
				loc_index += 1
			if loc_index >= len(locs): loc_index = len(locs) - 1
		if len_index is None:
			if mode == "AGB":
				len_index = 2
			elif mode == "DMG":
				len_index = 1
		if lay_index is None:
			lay_index = 2

		dlg_args = {
			"title":__("{batteryless_sram} Parameters", batteryless_sram="Batteryless SRAM"),
			"intro":intro_msg.replace("\n", "<br>"),
			"params": [
				# ID, Type, Value(s), Default Index
				[ "loc", "cmb_e", __("Location:"), [ "0x{:X}".format(l) for l in locs ], loc_index ],
				[ "len", "cmb", __("Size:"), [ Formatter.file_size(s, as_int=True) for s in lens ], len_index ],
			]
		}
		if mode == "DMG":
			dlg_args["params"].append(
				[ "layout", "cmb", __("Layout:"), [ __("Continuous"), __("First half of ROM bank"), __("Second half of ROM bank") ], lay_index ]
			)

		dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
		if dlg.exec_() == 1:
			result = dlg.GetResult()
			if result["loc"].currentText() not in [ "0x{:X}".format(l) for l in locs ]:
				try:
					if "0x" in result["loc"].currentText():
						bl_args["bl_offset"] = int(result["loc"].currentText()[2:], 16)
					else:
						bl_args["bl_offset"] = int(result["loc"].currentText(), 16)
				except ValueError:
					bl_args["bl_offset"] = 0
			else:
				bl_args["bl_offset"] = locs[result["loc"].currentIndex()]
			bl_args["bl_size"] = lens[result["len"].currentIndex()]
			if mode == "DMG":
				bl_args["bl_layout"] = result["layout"].currentIndex()

			locs.append(bl_args["bl_offset"])
			self.SETTINGS.setValue("BatterylessSramLocations{:s}".format(mode), json.dumps(locs))
			self.SETTINGS.setValue("BatterylessSramLastLocation{:s}".format(mode), json.dumps(bl_args["bl_offset"]))
			ret = bl_args
		else:
			ret = False
		del(dlg)
		return ret

	def EditRTC(self, _):
		if not self.CheckDeviceAlive(): return
		if not self.CheckHeader(): return

		data = self.CONN.INFO
		if "dump_info" not in data: return
		if "has_rtc" not in data or data["has_rtc"] is not True: return
		if "rtc_dict" not in data or len(data["rtc_dict"]) == 0: return
		rtc_data = data["rtc_dict"]

		if self.CONN.GetMode() == "DMG":
			mbc = get_mbc_name(ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex()))
			if mbc in ("MBC3", "MBC30", "Unlicensed MBCX Mapper"):
				dlg_args = {
					"title": __("{mapper} Real Time Clock Editor", mapper="MBC3/MBC30"),
					"intro": __("Enter the number of days, hours, minutes and seconds that passed since the RTC initially started.") + "\n\n" + __("Please note that all values are internal values. The game may use these only as a relative reference."),
					"params": [
						# ID, Type, Value(s), Default Index
						[ "rtc_d", "spb", c__("Real Time Clock Setting", "Days:"), (0, 511), rtc_data.get("rtc_d") or 0 ],
						[ "rtc_h", "spb", c__("Real Time Clock Setting", "Hours:"), (0, 23), rtc_data.get("rtc_h") or 0 ],
						[ "rtc_m", "spb", c__("Real Time Clock Setting", "Minutes:"), (0, 59), rtc_data.get("rtc_m") or 0 ],
						[ "rtc_s", "spb", c__("Real Time Clock Setting", "Seconds:"), (0, 59), rtc_data.get("rtc_s") or 0 ],
						[ "current", "chk", c__("Real Time Clock Setting", "Ignore above time values and use the system time instead"), None, False ],
					]
				}
				dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
				if dlg.exec_() == 1:
					result = dlg.GetResult()
					rtc_dict = {}
					for key, value in result.items():
						if isinstance(value, QtWidgets.QSpinBox):
							rtc_dict[key] = value.value()
						elif isinstance(value, QtWidgets.QCheckBox):
							rtc_dict[key] = value.isChecked()
					if result["current"].isChecked():
						dt = datetime.datetime.now() + datetime.timedelta(seconds=1)
						rtc_dict.update({
							"rtc_h":dt.hour,
							"rtc_m":dt.minute,
							"rtc_s":dt.second,
						})
					mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
					args = { "mbc":mbc, "rtc_dict":rtc_dict }
				else:
					return False

			elif mbc in ("HuC-3"):
				dlg_args = {
					"title": __("{mapper} Real Time Clock Editor", mapper="HuC-3"),
					"intro": __("Enter the number of days since your last play, and the current time.") + "\n\n" + __("Please note that the day value is an internal value. The game may use it only as a relative reference."),
					"params": [
						# ID, Type, Value(s), Default Index
						[ "rtc_d", "spb", c__("Real Time Clock Setting", "Days:"), (0, 4095), rtc_data.get("rtc_d") or 0 ],
						[ "rtc_h", "spb", c__("Real Time Clock Setting", "Hours:"), (0, 23), rtc_data.get("rtc_h") or 0 ],
						[ "rtc_m", "spb", c__("Real Time Clock Setting", "Minutes:"), (0, 59), rtc_data.get("rtc_m") or 0 ],
						[ "current", "chk", c__("Real Time Clock Setting", "Ignore above time values and use the system time instead"), None, False ],
					]
				}
				dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
				if dlg.exec_() == 1:
					result = dlg.GetResult()
					rtc_dict = {}
					for key, value in result.items():
						if isinstance(value, QtWidgets.QSpinBox):
							rtc_dict[key] = value.value()
						elif isinstance(value, QtWidgets.QCheckBox):
							rtc_dict[key] = value.isChecked()
					if result["current"].isChecked():
						dt = datetime.datetime.now()
						rtc_dict.update({
							"rtc_h":dt.hour,
							"rtc_m":dt.minute
						})
					mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
					args = { "mbc":mbc, "rtc_dict":rtc_dict }
				else:
					return False

			elif mbc in ("TAMA5"):
				dlg_args = {
					"title": __("{mapper} Real Time Clock Editor", mapper="TAMA5"),
					"intro": __("Enter the date and time used in the game.") + "\n\n" + __("Please note that the day value is an internal value. The game may use it only as a relative reference."),
					"params": [
						# ID, Type, Value(s), Default Index
						[ "rtc_y", "spb", c__("Real Time Clock Setting", "Years passed:"), (0, 80), (rtc_data.get("rtc_y") or 19) - 19 ], # 19–99
						[ "rtc_leap_year_state", "spb", c__("Real Time Clock Setting", "Years since last leap year:"), (0, 3), rtc_data.get("rtc_leap_year_state") or 0 ],
						[ "rtc_m", "spb", c__("Real Time Clock Setting", "Month:"), (1, 12), rtc_data.get("rtc_m") or 1 ],
						[ "rtc_d", "spb", c__("Real Time Clock Setting", "Day:"), (1, 31), rtc_data.get("rtc_d") or 1 ],
						[ "rtc_h", "spb", c__("Real Time Clock Setting", "Hours:"), (0, 23), rtc_data.get("rtc_h") or 0 ],
						[ "rtc_i", "spb", c__("Real Time Clock Setting", "Minutes:"), (0, 59), rtc_data.get("rtc_i") or 0 ],
						[ "rtc_s", "spb", c__("Real Time Clock Setting", "Seconds:"), (0, 59), rtc_data.get("rtc_s") or 0 ],
						[ "current", "chk", c__("Real Time Clock Setting", "Ignore above values and use the system time instead"), None, False ],
					]
				}
				dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
				if dlg.exec_() == 1:
					result = dlg.GetResult()
					rtc_dict = {}
					for key, value in result.items():
						if isinstance(value, QtWidgets.QSpinBox):
							rtc_dict[key] = value.value()
						elif isinstance(value, QtWidgets.QCheckBox):
							rtc_dict[key] = value.isChecked()
					if result["current"].isChecked():
						dt = datetime.datetime.now() + datetime.timedelta(seconds=2)
						rtc_dict.update({
							"rtc_m":dt.month,
							"rtc_d":dt.day,
							"rtc_h":dt.hour,
							"rtc_i":dt.minute,
							"rtc_s":dt.second,
						})
						for y in range(dt.year, 0, -1):
							if (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0):
								rtc_dict["rtc_leap_year_state"] = dt.year - y
								break
					mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
					rtc_dict["rtc_y"] += 19
					rtc_dict["rtc_buffer"] = rtc_data["rtc_buffer"]
					args = { "mbc":mbc, "rtc_dict":rtc_dict }
				else:
					return False

		elif self.CONN.GetMode() == "AGB":
			dlg_args = {
				"title": __("GBA Real Time Clock Editor"),
				"intro": __("Enter the date and time for the Real Time Clock.") + "\n\n" + __("Please note that all values are internal values. The game may use these only as a relative reference."),
				"params": [
					# ID, Type, Value(s), Default Index
					[ "rtc_y", "spb", c__("Real Time Clock Setting", "Year:"), (2000, 2099), (rtc_data.get("rtc_y") or 0) + 2000 ],
					[ "rtc_m", "spb", c__("Real Time Clock Setting", "Month:"), (1, 12), rtc_data.get("rtc_m") or 1 ],
					[ "rtc_d", "spb", c__("Real Time Clock Setting", "Day:"), (1, 31), rtc_data.get("rtc_d") or 1 ],
					[ "rtc_h", "spb", c__("Real Time Clock Setting", "Hours:"), (0, 23), rtc_data.get("rtc_h") or 0 ],
					[ "rtc_i", "spb", c__("Real Time Clock Setting", "Minutes:"), (0, 59), rtc_data.get("rtc_i") or 0 ],
					[ "rtc_s", "spb", c__("Real Time Clock Setting", "Seconds:"), (0, 59), rtc_data.get("rtc_s") or 0 ],
					[ "rtc_w", "cmb", c__("Real Time Clock Setting", "Weekday:"), [__(d) for d in list(calendar.day_name)], ((rtc_data.get("rtc_w") or 1) - 1) % 7 ],
					[ "current", "chk", c__("Real Time Clock Setting", "Ignore above values and use the system time instead"), None, False ],
				]
			}
			dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
			if dlg.exec_() == 1:
				result = dlg.GetResult()
				rtc_dict = {}
				for key, value in result.items():
					if isinstance(value, QtWidgets.QSpinBox):
						rtc_dict[key] = value.value()
					elif isinstance(value, QtWidgets.QComboBox):
						rtc_dict[key] = value.currentIndex()
				if result["current"].isChecked():
					dt = datetime.datetime.now() + datetime.timedelta(seconds=1)
					rtc_dict.update({
						"rtc_y":dt.year,
						"rtc_m":dt.month,
						"rtc_d":dt.day,
						"rtc_w":dt.isoweekday() % 7,
						"rtc_h":dt.hour,
						"rtc_i":dt.minute,
						"rtc_s":dt.second,
					})
				else:
					# GUI order is Monday=0..Sunday=6; GBA RTC stores Sunday=0..Saturday=6.
					rtc_dict["rtc_w"] = (rtc_dict["rtc_w"] + 1) % 7
				rtc_dict["rtc_y"] -= 2000
				mbc = ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
				args = { "rtc_dict":rtc_dict }
			else:
				return False

		self.STATUS["args"] = args
		ret = self.CONN.WriteRTC(args=args)
		self.ReadCartridge(resetStatus=False)
		if ret:
			QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("The Real Time Clock register values have been updated."), QtWidgets.QMessageBox.Ok)
			return True
		else:
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("An error occured while updating the Real Time Clock register values."), QtWidgets.QMessageBox.Ok)
			return False

	def CheckDeviceAlive(self, setMode=False):
		_ = setMode
		if self.CONN is not None:
			mode = self.CONN.GetMode()
			if self.CONN.DEVICE is None:
				self.DisconnectDevice()
			else:
				if not self.CONN.IsConnected():
					self.DisconnectDevice()
					self.CONN = None
					self.DEVICES = {}
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("The connection to the device was lost!\n\nThis can be happen in one of the following cases:\n- The USB cable was unplugged or is faulty\n- The inserted cartridge may draw too much peak power (try re-connecting a few times or try hotswapping the cartridge after connecting)\n- The inserted cartrdige may induce a short circuit (check for bad soldering)") + "\n\n" + __("Do you want to try and reconnect to the device?"), standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
					msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
					answer = msgbox.exec()
					if answer == QtWidgets.QMessageBox.No:
						self.DisconnectDevice()
						return False

					QtCore.QTimer.singleShot(500, lambda: [ self.FindDevices(connectToFirst=True, mode=mode) ])
					return False
				else:
					return True
		return False

	def SetMode(self):
		setTo = False
		mode = self.CONN.GetMode()
		if mode == "DMG":
			if self.optDMG.isChecked(): return
			setTo = "AGB"
		elif mode == "AGB":
			if self.optAGB.isChecked(): return
			setTo = "DMG"
		else: # mode not set yet
			if self.optDMG.isChecked():
				setTo = "DMG"
			elif self.optAGB.isChecked():
				setTo = "AGB"

		voltageWarning = ""
		device_auto_switch_only = self.CONN.CanSetVoltageByAutoswitch() and not self.CONN.CanSetVoltageByCode()
		if device_auto_switch_only:
			dontShowAgain = True
		elif self.CONN.CanSetVoltageByCode() or self.CONN.CanSetVoltageByAutoswitch(): # device can switch in software or automatically based on a switch near the cartridge slot
			dontShowAgain = str(self.SETTINGS.value("SkipModeChangeWarning", default="disabled")).lower() == "enabled"
		elif self.CONN.CanSetVoltageBySwitch(): # device has a physical switch
			voltageWarning = "\n\n" + __("Important: Also make sure your device is set to the correct voltage!")
			dontShowAgain = False
		else: # no voltage switching supported
			dontShowAgain = False

		if not dontShowAgain and mode is not None:
			cb = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Don’t show this message again"), checked=False)
			if setTo == "DMG":
				modeWarning = "\n\n" + __("Caution: Game Boy Advance cartridges must not be inserted in Game Boy mode. Doing so can break the cartridge, so please be careful.")
			else:
				modeWarning = ""
			msg = __("The platform mode will now be changed to {mode} mode.", mode={"DMG":__("Game Boy"), "AGB":__("Game Boy Advance")}[setTo]) + modeWarning + voltageWarning
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
			msgbox.setDefaultButton(QtWidgets.QMessageBox.Ok)
			if self.CONN.CanSetVoltageByCode() or self.CONN.CanSetVoltageByAutoswitch(): msgbox.setCheckBox(cb)
			answer = msgbox.exec()
			dontShowAgain = cb.isChecked()
			if answer == QtWidgets.QMessageBox.Cancel:
				if mode == "DMG": self.optDMG.setChecked(True)
				if mode == "AGB": self.optAGB.setChecked(True)
				return False
			if not device_auto_switch_only and dontShowAgain: self.SETTINGS.setValue("SkipModeChangeWarning", "enabled")

		if not self.CheckDeviceAlive(setMode=setTo): return

		try:
			if self.optDMG.isChecked() and (mode == "AGB" or mode == None):
				self.CONN.SetMode("DMG")
			elif self.optAGB.isChecked() and (mode == "DMG" or mode == None):
				self.CONN.SetMode("AGB")
			if self.CONN.GetMode() is not None:
				self.mnuTools.actions()[1].setEnabled(True)
		except (BrokenPipeError, SerialException):
			msg = __("Failed to turn on the cartridge power.") + "\n" + __("The “{setting}” setting has therefore been disabled.", setting=__("Automatic cartridge &power off").replace("&", "")) + "\n\n" + __("Workaround advice:\n1. Eject the cartridge.\n2. Re-connect the USB cable.\n3. Click “{button_connect}” and select Platform mode.\n4. Insert the cartridge and click “{button_refresh}”.", button_connect=__("&Connect").replace("&", ""), button_refresh=__("&Refresh").replace("&", ""))
			self.mnuConfig.actions()[8].setChecked(False)
			self.SETTINGS.setValue("AutoPowerOff", "0")
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), msg, QtWidgets.QMessageBox.Ok)
			self.DisconnectDevice()
			return False

		ok = self.ReadCartridge()
		qt_app.processEvents()
		if ok not in (False, None):
			self.btnHeaderRefresh.setEnabled(True)
			self.btnDetectCartridge.setEnabled(True)
			self.btnBackupROM.setEnabled(True)
			self.btnFlashROM.setEnabled(True)
			self.btnBackupRAM.setEnabled(True)
			self.btnRestoreRAM.setEnabled(True)
			self.grpDMGCartridgeInfo.setEnabled(True)
			self.grpAGBCartridgeInfo.setEnabled(True)

	def ReadCartridge(self, resetStatus=True):
		if self.CheckDeviceAlive() is not True: return
		self._UpdatePlatformModeFromFirmware()
		if resetStatus:
			self.btnHeaderRefresh.setEnabled(False)
			self.btnDetectCartridge.setEnabled(False)
			self.btnBackupROM.setEnabled(False)
			self.btnFlashROM.setEnabled(False)
			self.btnBackupRAM.setEnabled(False)
			self.btnRestoreRAM.setEnabled(False)
			self.SetStatus4aText(__("Reading cartridge data..."))
			self.SetProgressBars(min=0, max=0, value=1)
			qt_app.processEvents()

		try:
			data = self.CONN.ReadHeader()
		except (BrokenPipeError, SerialException):
			self.LimitBaudRateGBxCartRW()
			self.DisconnectDevice()
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("The connection to the device was lost while trying to read the ROM header. This may happen if the inserted cartridge issues a short circuit or its peak power draw is too high.\n\nAs a potential workaround for the latter, you can try hotswapping the cartridge:\n1. Remove the cartridge from the device.\n2. Reconnect the device and select platform mode.\n3. Then insert the cartridge and click “{button}”.", button=self.btnHeaderRefresh.text().replace("&", "")), QtWidgets.QMessageBox.Ok)
			return False

		if data == False or len(data) == 0:
			self.LimitBaudRateGBxCartRW()
			self.DisconnectDevice()
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("Invalid response from the device. Please re-connect the USB cable."), QtWidgets.QMessageBox.Ok)
			return False

		if self.CONN.CheckROMStable() is False and resetStatus:
			try:
				if data != bytearray(data[0] * len(data)):
					QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("The cartridge connection is unstable!") + "\n" + __("Please clean the cartridge pins, carefully realign the cartridge and then try again."), QtWidgets.QMessageBox.Ok)
			except:
				pass

		if self.CONN.GetMode() == "DMG":
			if self.cmbDMGHeaderMapperResult.count() == 0:
				self.cmbDMGHeaderMapperResult.addItems(DMG_Mapper().GetAllMapperTypes())
				self.cmbDMGHeaderMapperResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
			if self.cmbDMGCartridgeTypeResult.count() == 0:
				self.cmbDMGCartridgeTypeResult.addItems(self.CONN.GetSupportedCartridgesDMG()[0])
				self.cmbDMGCartridgeTypeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
			if "flash_type" in data:
				self.cmbDMGCartridgeTypeResult.setCurrentIndex(data["flash_type"])
			else:
				self.cmbDMGCartridgeTypeResult.setCurrentIndex(0)
			if self.cmbDMGHeaderROMSizeResult.count() == 0:
				self.cmbDMGHeaderROMSizeResult.addItems(RomSizes().GetStringList(mode="DMG"))
				self.cmbDMGHeaderROMSizeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
			if self.cmbDMGHeaderSaveTypeResult.count() == 0:
				self.cmbDMGHeaderSaveTypeResult.addItems(DmgSaveTypes().GetStringList())
				self.cmbDMGHeaderSaveTypeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)

			self.lblDMGRomTitleResult.setText(Formatter.title(data['game_title']))
			self.lblDMGGameCodeRevision.setText(__("Game Code and Revision:"))
			self.lblDMGGameNameResult.setToolTip("")
			if data["logo_correct"] is False:
				self.SetDMGPlatformBadge(None)
			else:
				self.SetDMGPlatformBadge(data)
			if data["db"] is not None:
				self.lblDMGGameCodeRevisionResult.setText("{:s}-{:s}".format(data["db"]["gc"], str(data["version"])))
				self.SetDMGGameNameText(data["db"]["gn"])
			else:
				self.SetDMGGameNameText(c__("Game Data", "(No database entry)"))
				if len(data['game_code']) > 0:
					self.lblDMGGameCodeRevisionResult.setText("{:s}-{:s}".format(Formatter.title(data["game_code"]), str(data["version"])))
				else:
					self.lblDMGGameCodeRevision.setText("Revision:")
					self.lblDMGGameCodeRevisionResult.setText(str(data['version']))

			if data["has_rtc"] is True and len(data["rtc_dict"]) > 0 and "rtc_valid" in data["rtc_dict"] and data["rtc_dict"]["rtc_valid"] is True:
				self.lblDMGHeaderRtcResult.setText(data["rtc_string"] + " ⚙️")
				self.lblDMGHeaderRtcResult.setCursor(QtCore.Qt.PointingHandCursor)
				self.lblDMGHeaderRtcResult.setToolTip(__("Click here to edit the Real Time Clock register values"))
			else:
				self.lblDMGHeaderRtcResult.setText(data["rtc_string"])
				self.lblDMGHeaderRtcResult.setCursor(QtCore.Qt.ArrowCursor)
				self.lblDMGHeaderRtcResult.setToolTip("")

			if data['logo_correct'] and data['header_checksum_correct']:
				self.lblDMGHeaderBootlogoResult.setText(c__("Game Data", "OK"))
				self.lblDMGHeaderBootlogoResult.setStyleSheet(self.DEFAULT_STYLESHEET)
				if not os.path.exists(AppContext.CONFIG_PATH + os.sep + "bootlogo_dmg.bin"):
					with open(AppContext.CONFIG_PATH + os.sep + "bootlogo_dmg.bin", "wb") as f:
						f.write(data['raw'][0x104:0x134])
			else:
				self.lblDMGHeaderBootlogoResult.setText(c__("Game Data", "Invalid"))
				self.lblDMGHeaderBootlogoResult.setStyleSheet("QLabel { color: red; }")

			self.lblDMGHeaderROMChecksumResult.setText("0x{:04X}".format(data['rom_checksum']))
			self.lblDMGHeaderROMChecksumResult.setStyleSheet(self.DEFAULT_STYLESHEET)
			self.cmbDMGHeaderROMSizeResult.setCurrentIndex(data["rom_size_raw"])
			for i in range(0, DmgSaveTypes().GetNumberOfTypes()):
				if data["ram_size_raw"] == DmgSaveTypes(index=i).GetMbc():
					self.cmbDMGHeaderSaveTypeResult.setCurrentIndex(i)
			temp = ConvertMapperToMapperType(data["mapper_raw"])
			mapper_type = temp[2]
			self.cmbDMGHeaderMapperResult.setCurrentIndex(mapper_type)

			if data['empty'] == True: # defaults
				if data['empty_nocart'] == True:
					self.SetDMGGameNameText("(" + __("No cartridge connected") + ")")
				else:
					self.SetDMGGameNameText("(" + __("No ROM data detected") + ")")
				self.lblDMGGameNameResult.setStyleSheet("QLabel { color: red; }")
				self.cmbDMGHeaderROMSizeResult.setCurrentIndex(0)
				self.cmbDMGHeaderSaveTypeResult.setCurrentIndex(0)
				self.cmbDMGHeaderMapperResult.setCurrentIndex(0)
			else:
				self.lblDMGGameNameResult.setStyleSheet(self.DEFAULT_STYLESHEET)

				# if data['logo_correct'] and not self.CONN.IsSupportedMbc(data["mapper_raw"]) and resetStatus:
				# 	QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("This cartridge uses a mapper that may not be completely supported by FlashGBX using your {device_name}.", device_name=self.CONN.GetFullName()), QtWidgets.QMessageBox.Ok)
				if data['logo_correct'] and data['game_title'] in ("NP M-MENU MENU", "DMG MULTI MENU ", "GBMEM-MENU MMSA"):
					cart_types = self.CONN.GetSupportedCartridgesDMG()
					for i in range(0, len(cart_types[0])):
						if "dmg-mmsa-jpn" in cart_types[1][i]:
							self.cmbDMGCartridgeTypeResult.setCurrentIndex(i)

			if data["mapper_raw"] == 0x203: # Xploder GB
				self.lblDMGHeaderRtcResult.setText("")
				self.lblDMGHeaderBootlogoResult.setText("")
				self.lblDMGHeaderBootlogoResult.setStyleSheet(self.DEFAULT_STYLESHEET)
				self.lblDMGHeaderROMChecksumResult.setText("")
				self.lblDMGHeaderROMChecksumResult.setStyleSheet(self.DEFAULT_STYLESHEET)
			elif data["mapper_raw"] == 0x205: # Datel
				self.lblDMGHeaderRtcResult.setText("")
				self.lblDMGHeaderBootlogoResult.setText("")
				self.lblDMGHeaderBootlogoResult.setStyleSheet(self.DEFAULT_STYLESHEET)
				self.lblDMGGameCodeRevisionResult.setText("")
				self.lblDMGGameCodeRevisionResult.setStyleSheet(self.DEFAULT_STYLESHEET)
				self.lblDMGHeaderROMChecksumResult.setText("")
				self.lblDMGHeaderROMChecksumResult.setStyleSheet(self.DEFAULT_STYLESHEET)
			elif data["mapper_raw"] == 0x204: # Sachen
				self.SetDMGGameNameText(Formatter.title(data["game_title"]))
				self.lblDMGHeaderRtcResult.setText("")
				self.lblDMGRomTitleResult.setText("")
				self.lblDMGGameCodeRevisionResult.setText("")
				self.lblDMGHeaderBootlogoResult.setText("")
				self.lblDMGHeaderBootlogoResult.setStyleSheet(self.DEFAULT_STYLESHEET)
				if "logo_sachen" in data:
					data["logo_sachen"].putpalette([ 255, 255, 255, 128, 128, 128 ])
					try:
						self.lblDMGHeaderBootlogoResult.setPixmap(bitmap2pixmap(data["logo_sachen"]))
					except:
						pass
			else:
				if "logo" in data:
					if data['logo_correct']:
						rgb = ( self.TEXT_COLOR[0], self.TEXT_COLOR[1], self.TEXT_COLOR[2] ) # GUI font color
						rgb = tuple(min(255, int(c + (127.5 - c) * 0.25)) if c < 127.5 else max(0, int(c - (c - 127.5) * 0.25)) for c in rgb)
						data["logo"].putpalette([ 255, 255, 255, rgb[0], rgb[1], rgb[2] ])
					else:
						data["logo"].putpalette([ 255, 255, 255, 251, 0, 24 ])
					try:
						self.lblDMGHeaderBootlogoResult.setPixmap(bitmap2pixmap(data["logo"]))
					except:
						pass

			self.grpAGBCartridgeInfo.setVisible(False)
			self.grpDMGCartridgeInfo.setVisible(True)

		elif self.CONN.GetMode() == "AGB":
			if resetStatus:
				self.cmbAGBCartridgeTypeResult.clear()
				self.cmbAGBCartridgeTypeResult.addItems(self.CONN.GetSupportedCartridgesAGB()[0])
				self.cmbAGBCartridgeTypeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
				if "flash_type" in data:
					self.cmbAGBCartridgeTypeResult.setCurrentIndex(data["flash_type"])
				else:
					self.cmbAGBCartridgeTypeResult.setCurrentIndex(0)
			if self.cmbAGBHeaderROMSizeResult.count() == 0:
				self.cmbAGBHeaderROMSizeResult.addItems(RomSizes().GetStringList())
				self.cmbAGBHeaderROMSizeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
				self.cmbAGBHeaderROMSizeResult.setCurrentIndex(self.cmbAGBHeaderROMSizeResult.count() - 1)
			if self.cmbAGBSaveTypeResult.count() == 0:
				self.cmbAGBSaveTypeResult.addItems(AgbSaveTypes().GetStringList())
				self.cmbAGBSaveTypeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
				self.cmbAGBSaveTypeResult.setCurrentIndex(self.cmbAGBSaveTypeResult.count() - 1)

			self.lblAGBRomTitleResult.setText(Formatter.title(data['game_title']))
			self.lblAGBGameNameResult.setToolTip("")
			if data["db"] is not None:
				self.lblAGBHeaderGameCodeRevisionResult.setText("{:s}-{:s}".format(data["db"]["gc"], str(data["version"])))
				temp = data["db"]["gn"]
				self.lblAGBGameNameResult.setText(temp)
				while self.lblAGBGameNameResult.fontMetrics().boundingRect(self.lblAGBGameNameResult.text()).width() > 240:
					temp = temp[:-1]
					self.lblAGBGameNameResult.setText(temp + "…")
				if temp != data["db"]["gn"]:
					self.lblAGBGameNameResult.setToolTip(data["db"]["gn"])
			else:
				if len(data["game_code"]) > 0:
					self.lblAGBHeaderGameCodeRevisionResult.setText("{:s}-{:s}".format(Formatter.title(data["game_code"]), str(data["version"])))
				else:
					self.lblAGBHeaderGameCodeRevisionResult.setText("")
				self.lblAGBGameNameResult.setText(c__("Game Data", "(No database entry)"))

			if data['logo_correct']:
				self.lblAGBHeaderBootlogoResult.setText("OK")
				self.lblAGBHeaderBootlogoResult.setStyleSheet(self.lblAGBRomTitleResult.styleSheet())
				if not os.path.exists(AppContext.CONFIG_PATH + os.sep + "bootlogo_agb.bin"):
					with open(AppContext.CONFIG_PATH + os.sep + "bootlogo_agb.bin", "wb") as f:
						f.write(data['raw'][0x04:0xA0])
			else:
				self.lblAGBHeaderBootlogoResult.setText(c__("Game Data", "Invalid"))
				self.lblAGBHeaderBootlogoResult.setStyleSheet("QLabel { color: red; }")

			if data["has_rtc"] is True and len(data["rtc_dict"]) > 0 and "rtc_valid" in data["rtc_dict"] and data["rtc_dict"]["rtc_valid"] is True:
				self.lblAGBGpioRtcResult.setText(data["rtc_string"] + " ⚙️")
				self.lblAGBGpioRtcResult.setCursor(QtCore.Qt.PointingHandCursor)
				self.lblAGBGpioRtcResult.setToolTip(__("Click here to edit the Real Time Clock register values"))
			else:
				self.lblAGBGpioRtcResult.setText(data["rtc_string"])
				self.lblAGBGpioRtcResult.setCursor(QtCore.Qt.ArrowCursor)
				self.lblAGBGpioRtcResult.setToolTip("")

			if data['header_checksum_correct']:
				self.lblAGBHeaderChecksumResult.setText(c__("Game Data", "Valid") + " (0x{:02X})".format(data['header_checksum']))
				self.lblAGBHeaderChecksumResult.setStyleSheet(self.lblAGBRomTitleResult.styleSheet())
			else:
				self.lblAGBHeaderChecksumResult.setText(c__("Game Data", "Invalid") + " (0x{:02X})".format(data['header_checksum']))
				self.lblAGBHeaderChecksumResult.setStyleSheet("QLabel { color: red; }")

			self.lblAGBHeaderROMChecksumResult.setStyleSheet(self.DEFAULT_STYLESHEET)
			self.lblAGBHeaderROMChecksumResult.setText("Not available")

			if data["db"] is None:
				self.lblAGBHeaderROMChecksumResult.setText(c__("Game Data", "(No database entry)"))
			if data["db"] != None:
				self.cmbAGBHeaderROMSizeResult.setCurrentIndex(RomSizes().GetIndex(data["db"]['rs']))
				if data["rom_size_calc"] < 0x400000:
					self.lblAGBHeaderROMChecksumResult.setText(c__("Game Data", "In database") + " (0x{:06X})".format(data["db"]['rc']))
			elif data["rom_size"] != 0:
				if data["rom_size"] not in RomSizes():
					data["rom_size"] = 0x2000000
				self.cmbAGBHeaderROMSizeResult.setCurrentIndex(RomSizes().GetIndex(data["rom_size"]))
			else:
				self.cmbAGBHeaderROMSizeResult.setCurrentIndex(0)

			if data["save_type"] == None:
				self.cmbAGBSaveTypeResult.setCurrentIndex(0)
				if data["db"] != None:
					if data["db"]['st'] < AgbSaveTypes().GetNumberOfTypes():
						self.cmbAGBSaveTypeResult.setCurrentIndex(data["db"]['st'])
			elif data["save_type"] < AgbSaveTypes().GetNumberOfTypes():
				self.cmbAGBSaveTypeResult.setCurrentIndex(data["save_type"])

			if data['empty'] == True: # defaults
				if data['empty_nocart'] == True:
					self.lblAGBGameNameResult.setText("(" + __("No cartridge connected") + ")")
				else:
					self.lblAGBGameNameResult.setText("(" + __("No ROM data detected") + ")")
				self.lblAGBGameNameResult.setStyleSheet("QLabel { color: red; }")
				self.cmbAGBSaveTypeResult.setCurrentIndex(0)
			else:
				self.lblAGBGameNameResult.setStyleSheet(self.DEFAULT_STYLESHEET)
				if data['logo_correct']:
					cart_types = self.CONN.GetSupportedCartridgesAGB()
					for i in range(0, len(cart_types[0])):
						if ((data['3d_memory'] is True and "3d_memory" in cart_types[1][i]) or
							(data['vast_fame'] is True and "vast_fame" in cart_types[1][i])):
							self.cmbAGBCartridgeTypeResult.setCurrentIndex(i)

			if data["dacs_8m"] is True:
				self.cmbAGBSaveTypeResult.setCurrentIndex(6)

			self.grpDMGCartridgeInfo.setVisible(False)
			self.grpAGBCartridgeInfo.setVisible(True)

			if data['logo_correct'] and isinstance(data["db"], dict) and "rs" in data["db"] and data["db"]['rs'] == 0x4000000 and not self.CONN.IsSupported3dMemory() and resetStatus:
				QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("This cartridge uses a mapper that may not be completely supported by the firmware of the {device_name}. Check for firmware updates.", device_name=self.CONN.GetFullName()), QtWidgets.QMessageBox.Ok)

			if "logo" in data:
				if data['logo_correct']:
					rgb = ( self.TEXT_COLOR[0], self.TEXT_COLOR[1], self.TEXT_COLOR[2] ) # GUI font color
					rgb = tuple(min(255, int(c + (127.5 - c) * 0.25)) if c < 127.5 else max(0, int(c - (c - 127.5) * 0.25)) for c in rgb)
					data["logo"].putpalette([ 255, 255, 255, rgb[0], rgb[1], rgb[2] ])
				else:
					data["logo"].putpalette([ 255, 255, 255, 251, 0, 24 ])
				try:
					self.lblAGBHeaderBootlogoResult.setPixmap(bitmap2pixmap(data["logo"]))
				except:
					pass

		if resetStatus:
			self.lblStatus1aResult.setText("–")
			self.lblStatus2aResult.setText("–")
			self.lblStatus3aResult.setText("–")
			self.SetStatus4aText(__("Ready."))
			self.grpStatus.setTitle(__("Transfer Status"))
			self.FinishOperation()
			self.btnHeaderRefresh.setEnabled(True)
			self.btnDetectCartridge.setEnabled(True)
			self.btnBackupROM.setEnabled(True)
			self.btnFlashROM.setEnabled(True)
			self.btnBackupRAM.setEnabled(True)
			self.btnRestoreRAM.setEnabled(True)
			self.btnHeaderRefresh.setFocus()
			self.SetProgressBars(min=0, max=100, value=0)
			qt_app.processEvents()

		if data['game_title'][:11] == "YJencrypted" and resetStatus:
			QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("This cartridge may be protected against reading or writing a ROM. If you don’t want to risk this cartridge to render itself unusable, please do not try to write a new ROM to it."), QtWidgets.QMessageBox.Ok)

	def LimitBaudRateGBxCartRW(self):
		if self.CONN.GetName() == "GBxCart RW" and str(self.SETTINGS.value("AutoLimitBaudRate", default="enabled")).lower() == "enabled" and str(self.SETTINGS.value("LimitBaudRate", default="disabled")).lower() == "disabled":
			dprint("Setting “" + self.mnuConfig.actions()[5].text().replace("&", "") + "” to “enabled”")
			self.mnuConfig.actions()[5].setChecked(True)
			self.SETTINGS.setValue("LimitBaudRate", "enabled")
			dprint("Setting “" + self.mnuConfig.actions()[8].text().replace("&", "") + "” to “0”")
			self.mnuConfig.actions()[8].setChecked(False)
			self.SETTINGS.setValue("AutoPowerOff", "0")
			try:
				self.CONN.ChangeBaudRate(baudrate=1000000)
			except:
				try:
					self.DisconnectDevice()
				except:
					pass

	def DetectCartridge(self, checkSaveType=True):
		if not self.CheckDeviceAlive(): return
		if not self.CONN.CheckROMStable():
			answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("The cartridge connection is unstable!") + "\n" + __("Please clean the cartridge pins, carefully realign the cartridge for best results.") + "\n\n" + __("Continue anyway?"), QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
			if answer == QtWidgets.QMessageBox.No: return
		self.btnHeaderRefresh.setEnabled(False)
		self.btnDetectCartridge.setEnabled(False)
		self.btnBackupROM.setEnabled(False)
		self.btnFlashROM.setEnabled(False)
		self.btnBackupRAM.setEnabled(False)
		self.btnRestoreRAM.setEnabled(False)
		self.grpStatus.setTitle(__("Transfer Status"))
		self.lblStatus1aResult.setText("–")
		self.lblStatus2aResult.setText("–")
		self.lblStatus3aResult.setText("–")
		self.SetStatus4aResult("")
		# self.SetStatus4aText("Analyzing Cartridge...")
		self.SetProgressBars(min=0, max=0, value=1)
		qt_app.processEvents()

		if "can_skip_message" not in self.STATUS: self.STATUS["can_skip_message"] = False
		limitVoltage = str(self.SETTINGS.value("AutoDetectLimitVoltage", default="disabled")).lower() == "enabled"
		self.CONN.DetectCartridge(fncSetProgress=self.PROGRESS.SetProgress, args={"limitVoltage":limitVoltage, "checkSaveType":checkSaveType})

	def FinishDetectCartridge(self, ret):
		self.lblStatus1aResult.setText("–")
		self.lblStatus2aResult.setText("–")
		self.lblStatus3aResult.setText("–")

		limitVoltage = str(self.SETTINGS.value("AutoDetectLimitVoltage", default="disabled")).lower() == "enabled"
		if ret is False or not isinstance(ret, (list, tuple)) or len(ret) < 11:
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("An error occured while trying to analyze the cartridge and you may need to physically reconnect the device.") + "\n\n" + __("This cartridge may not be auto-detectable, please select the flashcart profile manually."), QtWidgets.QMessageBox.Ok)
			self.LimitBaudRateGBxCartRW()
			self.DisconnectDevice()
			cart_type = None
		else:
			(header, save_size, save_type, save_chip, sram_unstable, cart_types, cart_type_id, cfi_s, _, flash_id, detected_size) = ret

			# Save Type
			if not self.STATUS["can_skip_message"]:
				try:
					if save_type is not None and save_type is not False:
						if self.CONN.GetMode() == "DMG":
							self.cmbDMGHeaderSaveTypeResult.setCurrentIndex(DmgSaveTypes(mbc=save_type).GetIndex())
						elif self.CONN.GetMode() == "AGB":
							self.cmbAGBSaveTypeResult.setCurrentIndex(save_type)
				except:
					pass

			# Cart Type
			try:
				cart_type = None
				msg_cart_type = ""
				msg_cart_type_used = ""
				if self.CONN.GetMode() == "DMG":
					supp_cart_types = self.CONN.GetSupportedCartridgesDMG()
				elif self.CONN.GetMode() == "AGB":
					supp_cart_types = self.CONN.GetSupportedCartridgesAGB()
				else:
					raise NotImplementedError
			except Exception as e:
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=__("An unknown error occured. Please try again.") + "\n\n" + str(e), standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				self.LimitBaudRateGBxCartRW()
				return

			try:
				if len(cart_types) > 0:
					cart_type = cart_type_id
					if self.CONN.GetMode() == "DMG":
						self.cmbDMGCartridgeTypeResult.setCurrentIndex(0)
						self.cmbDMGCartridgeTypeResult.setCurrentIndex(cart_type)
					elif self.CONN.GetMode() == "AGB":
						self.cmbAGBCartridgeTypeResult.setCurrentIndex(0)
						self.cmbAGBCartridgeTypeResult.setCurrentIndex(cart_type)
					self.STATUS["cart_type"] = supp_cart_types[1][cart_type]
					for i in range(0, len(cart_types)):
						if cart_types[i] == cart_type_id:
							msg_cart_type += "- {:s} ← {:s}<br>".format(supp_cart_types[0][cart_types[i]], c__("Flashcart Profile List “- PROFILE NAME ← selected”", "selected"))
							msg_cart_type_used = supp_cart_types[0][cart_types[i]]
						else:
							msg_cart_type += "- {:s}<br>".format(supp_cart_types[0][cart_types[i]])
					msg_cart_type = msg_cart_type[:-4]

			except:
				pass

			# Messages
			# Header
			msg_header_s = "<b>" + __("ROM Title:") + "</b> {:s}<br>".format(Formatter.title(header["game_title"]))

			# Save Type
			msg_save_type_s = ""
			temp = ""
			if not self.STATUS["can_skip_message"] and save_type is not False and save_type is not None:
				if save_chip is not None:
					if save_type == 5 and save_chip is not None and "Unlicensed" in save_chip and "data" in self.CONN.INFO and self.CONN.INFO["data"] == bytearray([0xFF] * len(self.CONN.INFO["data"])):
						temp = "{:s} or {:s} ({:s})".format(AgbSaveTypes().GetStringList()[4], AgbSaveTypes().GetStringList()[5], save_chip)
					else:
						temp = "{:s} ({:s})".format(AgbSaveTypes().GetStringList()[save_type], save_chip)
				else:
					if self.CONN.GetMode() == "DMG":
						try:
							temp = "{:s}".format(DmgSaveTypes(mbc=save_type).GetString())
						except:
							temp = "Unknown"
					elif self.CONN.GetMode() == "AGB":
						temp = "{:s}".format(AgbSaveTypes().GetStringList()[save_type])
						try:
							if "Batteryless SRAM" in AgbSaveTypes().GetStringList()[save_type]:
								if save_size == 0:
									temp += " (" + __("unknown size") + ")<br><b>" + __("{batteryless_sram} Location:", batteryless_sram="Batteryless SRAM") + "</b> 0x{:X}–0x{:X} ({:s})".format(header["batteryless_sram"]["bl_offset"], header["batteryless_sram"]["bl_offset"]+header["batteryless_sram"]["bl_size"]-1, Formatter.file_size(header["batteryless_sram"]["bl_size"], as_int=True))
								elif save_size == header["batteryless_sram"]["bl_size"]:
									temp += " ({:s})<br><b>" + __("{batteryless_sram} Location:", batteryless_sram="Batteryless SRAM") + "</b> 0x{:X}–0x{:X} ({:s})".format(Formatter.file_size(save_size, as_int=True), header["batteryless_sram"]["bl_offset"], header["batteryless_sram"]["bl_offset"]+header["batteryless_sram"]["bl_size"]-1, Formatter.file_size(header["batteryless_sram"]["bl_size"], as_int=True))
								else:
									temp += " ({:s})<br><b>" + __("{batteryless_sram} Location:", batteryless_sram="Batteryless SRAM") + "</b> 0x{:X}–0x{:X} ({:s})".format(Formatter.file_size(save_size, as_int=True), header["batteryless_sram"]["bl_offset"], header["batteryless_sram"]["bl_offset"]+header["batteryless_sram"]["bl_size"]-1, Formatter.file_size(header["batteryless_sram"]["bl_size"], as_int=True))
						except:
							pass

				if save_type == 0:
					if save_chip and "Unknown" not in save_chip:
						msg_save_type_s = "<b>" + __("Save Type:") + "</b> {:s}<br>".format(save_chip)
					else:
						msg_save_type_s = "<b>" + __("Save Type:") + "</b> " + c__("Save Type", "None or unknown (no save data detected)") + "<br>"
				else:
					if sram_unstable and "SRAM" in temp:
						msg_save_type_s = "<b>" + __("Save Type:") + "</b> {:s} <span style=\"color: red;\">(" + c__("Save Data Access", "not stable or not battery-backed") + ")</span><br>".format(temp)
					else:
						msg_save_type_s = "<b>" + __("Save Type:") + "</b> {:s}<br>".format(temp)

			# Cart Type
			msg_cart_type_s = ""
			msg_cart_type_s_detail = ""
			msg_flash_size_s = ""
			msg_flash_id_s = ""
			msg_cfi_s = ""
			msg_flash_mapper_s = ""
			try_this = None
			found_supported = False
			is_generic = False
			if cart_type is not None:
				if len(cart_types) > 1:
					msg_cart_type_s = "<b>" + __("Flashcart Profile:") + "</b> {:s} (".format(msg_cart_type_used) + c__("Flashcart Profile: PROFILE NAME (or compatble)", "or compatible") + ")<br>"
				else:
					msg_cart_type_s = "<b>" + __("Flashcart Profile:") + "</b> {:s}<br>".format(msg_cart_type_used)
				msg_cart_type_s_detail = "<b>" + __("Compatible Flashcart Profiles:") + "</b><br>{:s}<br>".format(msg_cart_type)
				found_supported = True

				if detected_size > 0:
					size = detected_size
					msg_flash_size_s = "<b>" + __("ROM Size:") + "</b> {:s}<br>".format(Formatter.file_size(size, as_int=True))
				elif "flash_size" in supp_cart_types[1][cart_type_id]:
					size = supp_cart_types[1][cart_type_id]["flash_size"]
					msg_flash_size_s = "<b>" + __("ROM Size:") + "</b> {:s}<br>".format(Formatter.file_size(size, as_int=True))

				if self.CONN.GetMode() == "DMG":
					if "mbc" in supp_cart_types[1][cart_type_id]:
						if supp_cart_types[1][cart_type_id]["mbc"] == "manual":
							msg_flash_mapper_s = "<b>" + __("Mapper Type:") + "</b> <i>" + __("Manual selection") + "</i><br>"
						elif supp_cart_types[1][cart_type_id]["mbc"] in DMG_Mapper().GetAllMapperIds():
							msg_flash_mapper_s = "<b>" + __("Mapper Type:") + "</b> {:s}<br>".format(DMG_Mapper().GetMapperType(supp_cart_types[1][cart_type_id]["mbc"]))
					else:
						msg_flash_mapper_s = "<b>" + __("Mapper Type:") + "</b> " + c__("Mapper Type", "Default") + " (MBC5)" + "<br>"

			else:
				if (len(flash_id.split("\n")) > 2) and ((self.CONN.GetMode() == "DMG") or ("dacs_8m" in header and header["dacs_8m"] is not True)):
					msg_cart_type_s = "<b>" + __("Flashcart Profile:") + "</b> " + __("Unknown flash cartridge")
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
						msg_cart_type_s += " " + __("For ROM writing, you can give the option called “{option}” a try at your own risk.", option=try_this)
					msg_cart_type_s += "<br>"
				else:
					msg_cart_type_s = "<b>" + __("Flashcart Profile:") + "</b> " + "Generic ROM Cartridge" + " (" + __("not rewritable or not auto-detectable") + ")" + "<br>"
					is_generic = True

			if (len(flash_id.split("\n")) > 2):
				if limitVoltage:
					msg_flash_id_title = __("Flash ID Check (limited voltage):")
				else:
					msg_flash_id_title = __("Flash ID Check:")
				msg_flash_id_s = "<br><b>" + msg_flash_id_title + "</b><pre style=\"font-size: 8pt; margin: 0;\">{:s}</pre>".format(flash_id[:-1])
			if not is_generic:
				if cfi_s != "":
					msg_cfi_s = "<br><b>" + __("{common_flash_interface} Data:", common_flash_interface="Common Flash Interface") + "</b><br>{:s}<br><br>".format(cfi_s.replace("\n", "<br>"))
				else:
					msg_cfi_s = "<br><b>" + __("{common_flash_interface} Data:", common_flash_interface="Common Flash Interface") + "</b> " + c__("Common Flash Interface Data", "Not available") + "<br><br>"

			if msg_cart_type_s_detail == "": msg_cart_type_s_detail = msg_cart_type_s
			self.SetProgressBars(min=0, max=100, value=100)
			show_details = False

			msg_gbmem = ""
			if "gbmem_parsed" in header and header["gbmem_parsed"] is not None:
				msg_gbmem = "<br><b>" + __("{gb_memory_cartridge} Data:", gb_memory_cartridge="GB-Memory Cartridge") + "</b><br>"
				if isinstance(header["gbmem_parsed"], list):
					msg_gbmem += "" \
						"- " + __("Write Timestamp:") + " {timestamp:s}<br>".format(timestamp=header["gbmem_parsed"][0]["timestamp"].replace("\0", "")) + \
						"- " + __("Write Kiosk ID:") + " {kiosk_id:s}<br>".format(kiosk_id=header["gbmem_parsed"][0]["kiosk_id"].replace("\0", "")) + \
						"- " + __("Number of Games:") + " {num_games:d}<br>".format(num_games=header["gbmem_parsed"][0]["num_games"]) + \
						"- " + __("Write Counter:") + " {write_count:d}<br>".format(write_count=header["gbmem_parsed"][0]["write_count"]) + \
						"- " + __("Cartridge ID:") + " {cart_id:s}<br>".format(cart_id=header["gbmem_parsed"][0]["cart_id"].replace("\0", ""))
					for i in range(1, len(header["gbmem_parsed"])):
						if header["gbmem_parsed"][i]["menu_index"] == 0xFF: continue
						if i == 1:
							msg_gbmem += "- " + __("Menu ROM:") + " {:s}<br>".format(header["gbmem_parsed"][i]["title"].replace("\0", ""))
						else:
							msg_gbmem += "- " + __("Game {number}:", number=i - 1) + " {:s}<br>".format(header["gbmem_parsed"][i]["title"].replace("\0", ""))
				else:
					msg_gbmem += "" \
						"- " + __("Write Timestamp:") + " {timestamp:s}<br>".format(timestamp=header["gbmem_parsed"]["timestamp"].replace("\0", "")) + \
						"- " + __("Write Kiosk ID:") + " {kiosk_id:s}<br>".format(kiosk_id=header["gbmem_parsed"]["kiosk_id"].replace("\0", "")) + \
						"- " + __("Write Counter:") + " {write_count:d}<br>".format(write_count=header["gbmem_parsed"]["write_count"]) + \
						"- " + __("Cartridge ID:") + " {cart_id:s}<br>".format(cart_id=header["gbmem_parsed"]["cart_id"].replace("\0", "")) + \
						"- " + __("Game Title:") + " {game_title:s}<br>".format(game_title=header["gbmem_parsed"]["title"].replace("\0", ""))

			msg = __("The following cartridge configuration was detected:") + "<br><br>"
			if found_supported:
				dontShowAgain = str(self.SETTINGS.value("SkipAutodetectMessage", default="disabled")).lower() == "enabled"
				if not dontShowAgain or not self.STATUS["can_skip_message"]:
					temp = "{:s}{:s}{:s}{:s}{:s}{:s}".format(msg, msg_flash_size_s, msg_save_type_s, msg_flash_mapper_s, msg_cart_type_s, msg_gbmem)
					temp = temp[:-4]
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s} | {:s}".format(AppInfo.NAME, AppInfo.VERSION, self.CONN.GetFullNameLabel()), text=temp)
					msgbox.setTextFormat(QtCore.Qt.RichText)
					button_ok = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&OK"), QtWidgets.QMessageBox.ActionRole)
					button_details = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Details"), QtWidgets.QMessageBox.ActionRole)
					button_cancel = None
					msgbox.setDefaultButton(button_ok)
					cb = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Always skip this message"), checked=False)
					if self.STATUS["can_skip_message"]:
						button_cancel = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Cancel"), QtWidgets.QMessageBox.RejectRole)
						msgbox.setEscapeButton(button_cancel)
						msgbox.setCheckBox(cb)
					else:
						msgbox.setEscapeButton(button_ok)

					msgbox.exec()
					dontShowAgain = cb.isChecked()
					if dontShowAgain and self.STATUS["can_skip_message"]: self.SETTINGS.setValue("SkipAutodetectMessage", "enabled")

					if msgbox.clickedButton() == button_details:
						show_details = True
						msg = ""
					elif msgbox.clickedButton() == button_cancel:
						self.btnHeaderRefresh.setEnabled(True)
						self.btnDetectCartridge.setEnabled(True)
						self.btnBackupROM.setEnabled(True)
						self.btnFlashROM.setEnabled(True)
						self.btnBackupRAM.setEnabled(True)
						self.btnRestoreRAM.setEnabled(True)
						self.btnHeaderRefresh.setFocus()
						self.SetProgressBars(min=0, max=100, value=0)
						self.SetStatus4aText(__("Ready."))
						self.STATUS["can_skip_message"] = False
						if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])
						return

			if not found_supported or show_details is True:
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s} | {:s}".format(AppInfo.NAME, AppInfo.VERSION, self.CONN.GetFullNameLabel()))
				button_ok = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&OK"), QtWidgets.QMessageBox.ActionRole)
				msgbox.setDefaultButton(button_ok)
				msgbox.setEscapeButton(button_ok)
				if try_this is not None:
					button_try = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Try “{generic_type}”", generic_type="Generic Type"), QtWidgets.QMessageBox.ActionRole)
					button_try.setToolTip("{:s}".format(try_this))
				else:
					button_try = None

				if not is_generic:
					msg_fw = "<br><span style=\"font-size: 8pt;\"><i>{:s} {:s} | {:s}</i></span><br>".format(AppInfo.NAME, AppInfo.VERSION, self.CONN.GetFullNameExtended())
					button_clipboard = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "&Copy to Clipboard"), QtWidgets.QMessageBox.ActionRole)
				else:
					msg_fw = ""
					button_clipboard = None

				if self.CONN.GetMode() == "DMG" and limitVoltage and (is_generic or not found_supported):
					text = __("No known flashcart profile could be detected. The option “{limit_voltage}” has been enabled which can cause auto-detection to fail. As it is usually not recommended to enable this option, do you now want to disable it and try again?", limit_voltage=__("&Limit voltage when analyzing Game Boy carts").replace("&", ""))
					answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
					if answer == QtWidgets.QMessageBox.Yes:
						self.SETTINGS.setValue("AutoDetectLimitVoltage", "disabled")
						self.mnuConfig.actions()[4].setChecked(False)
						self.STATUS["can_skip_message"] = False
						self.DetectCartridge()
						return

				temp = "{:s}{:s}{:s}{:s}{:s}{:s}{:s}{:s}{:s}{:s}".format(msg, msg_header_s, msg_flash_size_s, msg_save_type_s, msg_flash_mapper_s, msg_flash_id_s, msg_cfi_s, msg_cart_type_s_detail, msg_gbmem, msg_fw)
				temp = temp[:-4]
				msgbox.setText(temp)
				msgbox.setTextFormat(QtCore.Qt.RichText)
				msgbox.exec()
				if msgbox.clickedButton() == button_clipboard:
					clipboard = QtWidgets.QApplication.clipboard()
					doc = QtGui.QTextDocument()
					doc.setHtml(temp)
					temp = doc.toPlainText()
					clipboard.setText(temp)
				elif msgbox.clickedButton() == button_try:
					if try_this in supp_cart_types[0]:
						cart_type = supp_cart_types[0].index(try_this)
					if self.CONN.GetMode() == "DMG":
						self.cmbDMGCartridgeTypeResult.setCurrentIndex(cart_type)
					elif self.CONN.GetMode() == "AGB":
						self.cmbAGBCartridgeTypeResult.setCurrentIndex(cart_type)

		self.btnHeaderRefresh.setEnabled(True)
		self.btnDetectCartridge.setEnabled(True)
		self.btnBackupROM.setEnabled(True)
		self.btnFlashROM.setEnabled(True)
		self.btnBackupRAM.setEnabled(True)
		self.btnRestoreRAM.setEnabled(True)
		self.btnHeaderRefresh.setFocus()
		self.SetProgressBars(min=0, max=100, value=0)
		self.SetStatus4aText(__("Ready."))

		waiting = None
		if "detected_cart_type" in self.STATUS and self.STATUS["detected_cart_type"] in ("WAITING_FLASH", "WAITING_SAVE_READ", "WAITING_SAVE_WRITE"):
			waiting = self.STATUS["detected_cart_type"]
			self.STATUS["detected_cart_type"] = cart_type
		self.STATUS["can_skip_message"] = False

		if waiting == "WAITING_FLASH":
			if "detect_cartridge_args" in self.STATUS:
				self.FlashROM(dpath=self.STATUS["detect_cartridge_args"]["dpath"])
				del(self.STATUS["detect_cartridge_args"])
			else:
				self.FlashROM()
		elif waiting == "WAITING_SAVE_READ":
			if "detect_cartridge_args" in self.STATUS:
				self.BackupRAM(dpath=self.STATUS["detect_cartridge_args"]["dpath"])
				del(self.STATUS["detect_cartridge_args"])
			else:
				self.BackupRAM()
		elif waiting == "WAITING_SAVE_WRITE":
			if "detect_cartridge_args" in self.STATUS:
				self.WriteRAM(dpath=self.STATUS["detect_cartridge_args"]["dpath"], erase=self.STATUS["detect_cartridge_args"]["erase"], skip_warning=True)
				del(self.STATUS["detect_cartridge_args"])
			else:
				self.WriteRAM()

	def WaitProgress(self, args):
		if args["user_action"] == "REINSERT_CART":
			title = "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION)
			if "title" in args:
				title += " – " + args["title"]
			msg = args["msg"]
			answer = QtWidgets.QMessageBox.warning(self, title, msg, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
			if answer == QtWidgets.QMessageBox.Ok:
				self.CONN.USER_ANSWER = True
			else:
				self.CONN.USER_ANSWER = False
		elif args["user_action"] == "RETRY_5V":
			title = "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION)
			if "title" in args:
				title += " – " + args["title"]
			msg = args["msg"]
			answer = QtWidgets.QMessageBox.question(self, title, msg, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
			if answer == QtWidgets.QMessageBox.Yes:
				self.CONN.USER_ANSWER = True
			else:
				self.CONN.USER_ANSWER = False

	def UpdateProgress(self, args):
		if args is None: return
		if self.CONN is None: return

		if "method" in args:
			voltage_suffix = ""
			if "voltage" in args and args["voltage"] in (3.3, 5):
				voltage_suffix = " " + __("at {voltage}V", voltage=format_decimal(args["voltage"], precision=1))
			if args["method"] == "ROM_READ":
				self.grpStatus.setTitle(__("Transfer Status") + " (" + __("Backup ROM") + ")")
			elif args["method"] == "ROM_WRITE":
				self.grpStatus.setTitle(__("Transfer Status") + " (" + __("Write ROM") + voltage_suffix + ")")
			elif args["method"] == "ROM_WRITE_VERIFY":
				self.grpStatus.setTitle(__("Transfer Status") + " (" + __("Verify Flash") + ")")
			elif args["method"] == "SAVE_READ":
				self.grpStatus.setTitle(__("Transfer Status") + " (" + __("Backup Save Data") + ")")
			elif args["method"] == "SAVE_WRITE":
				self.grpStatus.setTitle(__("Transfer Status") + " (" + __("Write Save Data") + ")")
			elif args["method"] == "SAVE_WRITE_VERIFY":
				self.grpStatus.setTitle(__("Transfer Status") + " (" + __("Verify Save Data") + ")")
			elif args["method"] == "DETECT_CART":
				self.grpStatus.setTitle(__("Transfer Status") + " (" + __("Analyze Cartridge") + ")")

		if "error" in args:
			self.SetStatus4aText(__("Failed!"))
			self.grpDMGCartridgeInfo.setEnabled(True)
			self.grpAGBCartridgeInfo.setEnabled(True)
			self.grpActions.setEnabled(True)
			self.mnuTools.setEnabled(True)
			self.mnuConfig.setEnabled(True)
			self.mnuLanguage.setEnabled(True)
			self.btnCancel.setEnabled(False)
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=str(args["error"]), standardButtons=QtWidgets.QMessageBox.Ok)
			if not '\n' in str(args["error"]): msgbox.setTextFormat(QtCore.Qt.RichText)
			msgbox.exec()
			self.LimitBaudRateGBxCartRW()
			return

		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.grpActions.setEnabled(False)
		self.mnuTools.setEnabled(False)
		self.mnuConfig.setEnabled(False)
		self.mnuLanguage.setEnabled(False)

		pos = 0
		size = 0
		speed = 0
		elapsed = 0
		left = 0
		estimated = 0
		if "pos" in args: pos = args["pos"]
		if "size" in args: size = args["size"]
		if "speed" in args: speed = args["speed"]
		if "time_elapsed" in args: elapsed = args["time_elapsed"]
		if "time_left" in args: left = args["time_left"]
		if "time_estimated" in args: estimated = args["time_estimated"]

		if "action" in args:
			if args["action"] == "ERASE":
				self.lblStatus1aResult.setText(__("Pending..."))
				self.lblStatus2aResult.setText(__("Pending..."))
				self.lblStatus3aResult.setText(Formatter.progress_time(elapsed))
				if estimated != 0:
					self.SetStatus4aText(__("Erasing... This may take up to {seconds} seconds.", seconds=estimated))
				else:
					self.SetStatus4aText(__("Erasing... This may take some time."))
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "UNLOCK":
				self.lblStatus1aResult.setText(__("Pending..."))
				self.lblStatus2aResult.setText(__("Pending..."))
				self.lblStatus3aResult.setText(__("Pending..."))
				self.SetStatus4aText(__("Unlocking flash..."))
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "UPDATE_RTC":
				self.lblStatus1aResult.setText(__("Pending..."))
				self.lblStatus2aResult.setText(__("Pending..."))
				self.lblStatus3aResult.setText(__("Pending..."))
				self.SetStatus4aText(__("Updating Real Time Clock..."))
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(False)
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "CALC_CHECKSUMS":
				self.lblStatus1aResult.setText(__("Pending..."))
				self.lblStatus2aResult.setText(__("Pending..."))
				self.lblStatus3aResult.setText(__("Pending..."))
				if "type" in args and len(str(args["type"])) > 0:
					self.SetStatus4aText(__("Calculating {checksum_type}...", checksum_type=args["type"]))
				else:
					self.SetStatus4aText(__("Calculating checksums..."))
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(False)
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "SECTOR_ERASE":
				if elapsed >= 1:
					self.lblStatus3aResult.setText(Formatter.progress_time(elapsed))
				self.SetStatus4aText(__("Erasing sector at address {address}...", address="0x{:X}".format(args["sector_pos"])))
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "ABORTING":
				self.lblStatus1aResult.setText("–")
				self.lblStatus2aResult.setText("–")
				self.lblStatus3aResult.setText("–")
				self.SetStatus4aText(__("Stopping... Please wait."))
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "ERROR":
				self.lblStatus2aResult.setText(__("Pending..."))
				self.lblStatus3aResult.setText(__("Pending..."))
				self.SetStatus4aText("<span style=\"color: red;\">{:s}</span>".format(args["text"]))
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "UPDATE_INFO":
				self.SetStatus4aText(args["text"])
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "FINISHED":
				if pos > 0:
					self.lblStatus1aResult.setText(Formatter.file_size(pos))
				self.FinishOperation()
			elif args["action"] == "ABORT":
				wd = 10
				try:
					while self.CONN.WORKER.isRunning():
						time.sleep(0.1)
						wd -= 1
						if wd == 0: break
				except AttributeError as _:
					return
				self.CONN.CANCEL = False
				self.CONN.ERROR = False
				self.grpDMGCartridgeInfo.setEnabled(True)
				self.grpAGBCartridgeInfo.setEnabled(True)
				self.grpActions.setEnabled(True)
				self.mnuTools.setEnabled(True)
				self.mnuConfig.setEnabled(True)
				self.mnuLanguage.setEnabled(True)
				self.grpStatus.setTitle(__("Transfer Status"))
				self.lblStatus1aResult.setText("–")
				self.lblStatus2aResult.setText("–")
				self.lblStatus3aResult.setText("–")
				self.SetStatus4aText(__("Stopped."))
				self.SetStatus4aResult("")
				self.btnCancel.setEnabled(False)
				self.SetProgressBars(min=0, max=1, value=0)
				self.btnCancel.setEnabled(False)

				if "info_type" in args.keys() and "info_msg" in args.keys():
					if args["info_type"] == "msgbox_critical":
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=args["info_msg"], standardButtons=QtWidgets.QMessageBox.Ok)
						dprint("Queueing Message Box {:s}:\n----\n{:s} {:s}\n----\n{:s}\n----".format(str(msgbox), AppInfo.NAME, AppInfo.VERSION, args["info_msg"]))
						if not '\n' in args["info_msg"]: msgbox.setTextFormat(QtCore.Qt.RichText)
						self.MSGBOX_QUEUE.put(msgbox)
						self.WriteDebugLog()
						if "fatal" in args:
							self.LimitBaudRateGBxCartRW()
							self.DisconnectDevice()
					elif args["info_type"] == "msgbox_information":
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), text=args["info_msg"], standardButtons=QtWidgets.QMessageBox.Ok)
						dprint("Queueing Message Box {:s}:\n----\n{:s} {:s}\n----\n{:s}\n----".format(str(msgbox), AppInfo.NAME, AppInfo.VERSION, args["info_msg"]))
						if not '\n' in args["info_msg"]: msgbox.setTextFormat(QtCore.Qt.RichText)
						#msgbox.exec()
						self.MSGBOX_QUEUE.put(msgbox)
					elif args["info_type"] == "label":
						self.SetStatus4aText(args["info_msg"])

				QtCore.QTimer.singleShot(1, lambda: [ self.ReadCartridge(resetStatus=False) ])
				return

			elif args["action"] == "PROGRESS":
				self.SetProgressBars(min=0, max=size, value=pos)
				if "abortable" in args:
					self.btnCancel.setEnabled(args["abortable"])
				else:
					self.btnCancel.setEnabled(True)
				self.lblStatus1aResult.setText("{:s}".format(Formatter.file_size(pos)))
				if speed > 0:
					self.lblStatus2aResult.setText(format_decimal(speed, precision=2) + __(" KiB/s"))
				else:
					self.lblStatus2aResult.setText(__("Pending..."))
				self.SetStatus4aText(__("Time left:"))
				if left > 0:
					self.SetStatus4aResult(Formatter.progress_time(left))
				else:
					self.SetStatus4aResult(__("Pending..."))
				if elapsed > 0:
					self.lblStatus3aResult.setText(Formatter.progress_time(elapsed))

				if speed == 0 and "skipping" in args and args["skipping"] is True:
					self.SetStatus4aResult(__("Pending..."))

	def SetStatus4aText(self, text):
		self.lblStatus4a.setText(text)
		self.lblStatus5a.setText(text)

	def SetStatus4aResult(self, text):
		if text:
			self.lblStatus4aResult.setText(text)
			self.lblStatus4a.setVisible(True)
			self.lblStatus4aResult.setVisible(True)
			self.lblStatus5a.setVisible(False)
		else:
			self.lblStatus4aResult.clear()
			self.lblStatus4a.setVisible(False)
			self.lblStatus4aResult.setVisible(False)
			self.lblStatus5a.setVisible(True)

	def SetProgressBars(self, min=0, max=100, value=0, setPause=None):
		self.prgStatus.setMinimum(min)
		self.prgStatus.setMaximum(max)
		self.prgStatus.setValue(value)
		if self.TBPROG is not None:
			if not value > max:
				self.TBPROG.setRange(min, max)
				self.TBPROG.setValue(value)
				if value != min and value != max:
					self.TBPROG.setVisible(True)
				else:
					self.TBPROG.setVisible(False)
			if setPause is not None:
				self.TBPROG.setPaused(setPause)
			else:
				self.TBPROG.setPaused(False)

	def ShowFirmwareUpdateWindow(self):
		if self.CONN is None:
			try:
				dev_types = {
					hw_mod.GbxDevice.DEVICE_LABEL_LONG: hw_mod.GbxDevice.GetFirmwareUpdaterClass(None)
					for hw_mod in HW_DEVICES
					if hw_mod.GbxDevice().SupportsFirmwareUpdates()
				}
				dlg_args = {
					"title": __("Firmware Updater"),
					"intro": __("Please select your device."),
					"params": [
						# ID, Type, Value(s), Default Index
						[ "dev_type", "cmb", __("Device Type:"), dev_types.keys(), 0 ]
					]
				}
				dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
				if dlg.exec_() == 1:
					result = dlg.GetResult()
					FirmwareUpdater = list(dev_types.values())[result["dev_type"].currentIndex()][1]
				else:
					return False
			except KeyError:
				return False
		else:
			if not self.CONN.SupportsFirmwareUpdates():
				QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("FlashGBX currently does not support updating the firmware of your device."), QtWidgets.QMessageBox.Ok)
				return False
			else:
				FirmwareUpdater = self.CONN.GetFirmwareUpdaterClass()[1]

		self.FWUPWIN = None
		self.FWUPWIN = FirmwareUpdater(self, app_path=AppContext.APP_PATH, icon=self.windowIcon(), device=self.CONN)
		self.FWUPWIN.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
		self.FWUPWIN.setModal(True)
		self.FWUPWIN.run()

	def ShowPocketCameraWindow(self):
		data = None
		if self.CONN is not None:
			if self.CONN.GetMode() is None and "DMG" in self.CONN.GetSupprtedModes():
				answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("Is a Game Boy Camera cartridge currently inserted?"), QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
				if answer == QtWidgets.QMessageBox.Yes:
					self.optDMG.setChecked(True)
					self.SetMode()
			if self.CONN.GetMode() == "DMG":
				header = self.CONN.ReadHeader()
				if header["mapper_raw"] == 252: # GBD
					args = { "path":None, "mbc":252, "save_type":header["ram_size_raw"], "rtc":False }
					self.SetStatus4aText(__("Loading data, please wait..."))
					qt_app.processEvents()
					self.CONN.BackupRAM(fncSetProgress=False, args=args)
					data = self.CONN.INFO["data"]
					self.SetStatus4aText(__("Ready."))

		self.CAMWIN = None
		self.CAMWIN = PocketCameraWindow(self, icon=self.windowIcon(), file=data, config_path=AppContext.CONFIG_PATH, app_path=AppContext.APP_PATH)
		self.CAMWIN.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
		self.CAMWIN.setModal(True)
		self.CAMWIN.run()

	def ShowInteractiveConsoleWindow(self):
		if self.CONN is None:
			QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("Please connect to a device first."), QtWidgets.QMessageBox.Ok)
			return False
		if self.CONN.GetMode() not in ("DMG", "AGB"):
			QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(AppInfo.NAME, AppInfo.VERSION), __("Please select a platform mode (Game Boy or Game Boy Advance) first."), QtWidgets.QMessageBox.Ok)
			return False

		self.INTWIN = None
		self.INTWIN = InteractiveConsoleWindow(self, icon=self.windowIcon())
		self.INTWIN.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
		self.INTWIN.setModal(True)
		self.INTWIN.run()

	def dragEnterEvent(self, e):
		if self._dragEventHover(e):
			e.accept()
		else:
			e.ignore()

	def dragMoveEvent(self, e):
		if self._dragEventHover(e):
			e.accept()
		else:
			e.ignore()

	def _dragEventHover(self, e):
		if self.btnHeaderRefresh.isEnabled() and self.grpActions.isEnabled() and e.mimeData().hasUrls:
			for url in e.mimeData().urls():
				fn = str(url.toLocalFile())
				if fn == "":
					fn = urllib.parse.unquote(str(QtCore.QUrl(str(url.toString())).toLocalFile() or url.path()))

				fn_split = os.path.splitext(os.path.abspath(fn))
				ext = fn_split[1].lower()
				if ext in SAVE_EXTS:
					return True
				elif self.CONN.GetMode() == "DMG" and ext in ROM_EXTS_DMG:
					return True
				elif self.CONN.GetMode() == "AGB" and ext in ROM_EXTS_AGB:
					return True
				else:
					return False
		return False

	def dropEvent(self, e):
		if self.btnHeaderRefresh.isEnabled() and self.grpActions.isEnabled() and e.mimeData().hasUrls:
			e.setDropAction(QtCore.Qt.CopyAction)
			e.accept()
			for url in e.mimeData().urls():
				fn = str(url.toLocalFile())
				if fn == "":
					fn = urllib.parse.unquote(str(QtCore.QUrl(str(url.toString())).toLocalFile() or url.path()))

				fn_split = os.path.splitext(os.path.abspath(fn))
				ext = fn_split[1].lower()
				if ext in DROP_ROM_EXTS_ALL:
					self.FlashROM(fn)
				elif ext in SAVE_EXTS:
					self.WriteRAM(fn)
		else:
			e.ignore()

	def closeEvent(self, event):
		self.DisconnectDevice()

		self.MSGBOX_TIMER.stop()
		self.MSGBOX_DISPLAYING = True
		with self.MSGBOX_QUEUE.mutex:
			self.MSGBOX_QUEUE.queue.clear()
		event.accept()

	def run(self):
		self.layout.update()
		self.layout.activate()
		self.adjustSize()
		fixed_size = self.size()
		screen = self.screen() or QtGui.QGuiApplication.primaryScreen()
		screen_geometry = screen.availableGeometry()
		frame_geometry = self.frameGeometry()
		frame_geometry.moveCenter(screen_geometry.center())
		self.move(frame_geometry.topLeft())
		self.setAcceptDrops(True)
		icon_filename = "icon.png" if platform.system() == "Linux" else "icon.ico"
		app_icon = QtGui.QIcon(AppContext.APP_PATH + os.sep + os.path.join("res", icon_filename))
		qt_app.setWindowIcon(app_icon)
		self.setWindowIcon(app_icon)
		self.setWindowFlag(QtCore.Qt.WindowMaximizeButtonHint, False)
		if platform.system() == "Windows":
			self.setWindowFlag(QtCore.Qt.MSWindowsFixedSizeDialogHint, True)
		self.show()
		self.setFixedSize(fixed_size)
		sys.stdout = Logger()

		# Taskbar Progress on Windows and Linux (Unity Launcher API)
		if platform.system() in ("Windows", "Linux"):
			try:
				from .pyside import QtWinExtras
				if platform.system() == "Windows":
					myappid = 'Lesserkuma.FlashGBX'
					QtWinExtras.QtWin.setCurrentProcessExplicitAppUserModelID(myappid)
				taskbar_button = QtWinExtras.QWinTaskbarButton()
				self.TBPROG = taskbar_button.progress()
				self.TBPROG.setRange(0, 100)
				taskbar_button.setWindow(self.windowHandle())
				self.TBPROG.setVisible(False)
			except (ImportError, AttributeError, RuntimeError):
				pass

		qt_app.exec()
		sys.stdout = sys.__stdout__

qt_app = QApplication(sys.argv)
if platform.system() == "Linux":
	try:
		desktop_id = AppInfo.NAME.lower()
		os.environ["FLASHGBX_DESKTOP_FILE"] = desktop_id + ".desktop"
		QtGui.QGuiApplication.setDesktopFileName(desktop_id)
		qt_app.setApplicationName(desktop_id)
		qt_app.setApplicationDisplayName(AppInfo.NAME)
	except (AttributeError, TypeError):
		qt_app.setApplicationName(AppInfo.NAME)
else:
	qt_app.setApplicationName(AppInfo.NAME)
loadQtTranslation(qt_app)

