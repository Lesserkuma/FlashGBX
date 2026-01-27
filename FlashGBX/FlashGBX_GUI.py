# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import sys, os, time, datetime, json, platform, subprocess, requests, webbrowser, threading, calendar, queue
from .pyside import QtCore, QtWidgets, QtGui, QApplication
from PIL.ImageQt import ImageQt
from PIL import Image
from serial import SerialException
from packaging import version
from .RomFileDMG import RomFileDMG
from .RomFileAGB import RomFileAGB
from .PocketCameraWindow import PocketCameraWindow
from .UserInputDialog import UserInputDialog
from .Util import APPNAME, VERSION, VERSION_PEP440
from . import Util
from . import hw_GBxCartRW, hw_GBFlash, hw_JoeyJr
hw_devices = [hw_GBxCartRW, hw_GBFlash, hw_JoeyJr]

class FlashGBX_GUI(QtWidgets.QWidget):
	CONN = None
	SETTINGS = None
	DEVICES = {}
	FLASHCARTS = { "DMG":{}, "AGB":{} }
	APP_PATH = ""
	CONFIG_PATH = ""
	TBPROG = None # Windows 7+ Taskbar Progress Bar
	PROGRESS = None
	CAMWIN = None
	FWUPWIN = None
	STATUS = {}
	TEXT_COLOR = (0, 0, 0, 255)
	MSGBOX_QUEUE = queue.Queue()
	MSGBOX_DISPLAYING = False
	
	def __init__(self, args):
		sys.excepthook = Util.exception_hook

		QtWidgets.QWidget.__init__(self)
		Util.CONFIG_PATH = args['config_path']
		Util.APP_PATH = args['app_path']
		self.SETTINGS = Util.IniSettings(path=args["config_path"] + "/settings.ini")
		self.FLASHCARTS = args["flashcarts"]
		self.PROGRESS = Util.Progress(self.UpdateProgress, self.WaitProgress)
		
		self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
		self.setWindowIcon(QtGui.QIcon(Util.APP_PATH + "/res/icon.ico"))
		self.setWindowTitle("{:s} {:s}".format(APPNAME, VERSION))
		self.setWindowFlags(self.windowFlags() | QtCore.Qt.MSWindowsFixedSizeDialogHint)
		self.TEXT_COLOR = QtGui.QPalette().color(QtGui.QPalette.Text).toTuple()
		
		# Create the QtWidgets.QVBoxLayout that lays out the whole form
		self.layout = QtWidgets.QGridLayout()
		self.layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
		self.layout_left = QtWidgets.QVBoxLayout()
		self.layout_right = QtWidgets.QVBoxLayout()
		self.layout.setContentsMargins(-1, 8, -1, 8)

		# Cartridge Information GroupBox
		self.grpDMGCartridgeInfo = self.GuiCreateGroupBoxDMGCartInfo()
		self.grpAGBCartridgeInfo = self.GuiCreateGroupBoxAGBCartInfo()
		self.grpAGBCartridgeInfo.setVisible(False)
		self.layout_left.addWidget(self.grpDMGCartridgeInfo)
		self.layout_left.addWidget(self.grpAGBCartridgeInfo)

		# Actions
		self.grpActions = QtWidgets.QGroupBox("Functions")
		self.grpActionsLayout = QtWidgets.QVBoxLayout()
		self.grpActionsLayout.setContentsMargins(-1, 3, -1, -1)
		
		rowActionsMode = QtWidgets.QHBoxLayout()
		self.lblMode = QtWidgets.QLabel("Mode: ")
		rowActionsMode.addWidget(self.lblMode)
		self.optDMG = QtWidgets.QRadioButton("&Game Boy")
		self.connect(self.optDMG, QtCore.SIGNAL("clicked()"), self.SetMode)
		self.optAGB = QtWidgets.QRadioButton("Game Boy &Advance")
		self.connect(self.optAGB, QtCore.SIGNAL("clicked()"), self.SetMode)
		rowActionsMode.addWidget(self.optDMG)
		rowActionsMode.addWidget(self.optAGB)
		
		rowActionsGeneral1 = QtWidgets.QHBoxLayout()
		self.btnHeaderRefresh = QtWidgets.QPushButton("&Refresh")
		self.btnHeaderRefresh.setMinimumHeight(25)
		self.connect(self.btnHeaderRefresh, QtCore.SIGNAL("clicked()"), self.ReadCartridge)
		rowActionsGeneral1.addWidget(self.btnHeaderRefresh)

		self.btnDetectCartridge = QtWidgets.QPushButton("Analyze &Flash Cart")
		self.btnDetectCartridge.setMinimumHeight(25)
		self.connect(self.btnDetectCartridge, QtCore.SIGNAL("clicked()"), self.DetectCartridge)
		rowActionsGeneral1.addWidget(self.btnDetectCartridge)

		rowActionsGeneral2 = QtWidgets.QHBoxLayout()
		self.btnBackupROM = QtWidgets.QPushButton("&Backup ROM")
		self.btnBackupROM.setMinimumHeight(25)
		self.connect(self.btnBackupROM, QtCore.SIGNAL("clicked()"), self.BackupROM)
		rowActionsGeneral2.addWidget(self.btnBackupROM)
		self.btnBackupRAM = QtWidgets.QPushButton("Backup &Save Data")
		self.btnBackupRAM.setMinimumHeight(25)
		self.connect(self.btnBackupRAM, QtCore.SIGNAL("clicked()"), self.BackupRAM)
		rowActionsGeneral2.addWidget(self.btnBackupRAM)
		
		self.cmbDMGCartridgeTypeResult.currentIndexChanged.connect(self.CartridgeTypeChanged)
		self.cmbDMGHeaderMapperResult.currentIndexChanged.connect(self.DMGMapperTypeChanged)
		
		rowActionsGeneral3 = QtWidgets.QHBoxLayout()
		self.btnFlashROM = QtWidgets.QPushButton("&Write ROM")
		self.btnFlashROM.setMinimumHeight(25)
		self.connect(self.btnFlashROM, QtCore.SIGNAL("clicked()"), self.FlashROM)
		rowActionsGeneral3.addWidget(self.btnFlashROM)
		self.btnRestoreRAM = QtWidgets.QPushButton("Writ&e Save Data")
		self.mnuRestoreRAM = QtWidgets.QMenu()
		self.mnuRestoreRAM.addAction("&Restore from save data file", self.WriteRAM)
		self.mnuRestoreRAM.addAction("&Erase cartridge save data", lambda: self.WriteRAM(erase=True))
		self.mnuRestoreRAM.addSeparator()
		self.mnuRestoreRAM.addAction("Run stress &test", lambda: self.WriteRAM(test=True))
		self.btnRestoreRAM.setMenu(self.mnuRestoreRAM)
		self.btnRestoreRAM.setMinimumHeight(25)
		rowActionsGeneral3.addWidget(self.btnRestoreRAM)

		self.grpActionsLayout.setSpacing(4)
		self.grpActionsLayout.addLayout(rowActionsMode)
		self.grpActionsLayout.addLayout(rowActionsGeneral1)
		self.grpActionsLayout.addLayout(rowActionsGeneral2)
		self.grpActionsLayout.addLayout(rowActionsGeneral3)
		self.grpActions.setLayout(self.grpActionsLayout)

		self.layout_right.addWidget(self.grpActions)

		# Transfer Status
		self.grpStatus = QtWidgets.QGroupBox("Transfer Status")
		grpStatusLayout = QtWidgets.QVBoxLayout()
		grpStatusLayout.setContentsMargins(-1, 3, -1, -1)

		rowStatus1a = QtWidgets.QHBoxLayout()
		self.lblStatus1a = QtWidgets.QLabel("Data transferred:")
		rowStatus1a.addWidget(self.lblStatus1a)
		self.lblStatus1aResult = QtWidgets.QLabel("–")
		rowStatus1a.addWidget(self.lblStatus1aResult)
		grpStatusLayout.addLayout(rowStatus1a)
		rowStatus2a = QtWidgets.QHBoxLayout()
		self.lblStatus2a = QtWidgets.QLabel("Transfer rate:")
		rowStatus2a.addWidget(self.lblStatus2a)
		self.lblStatus2aResult = QtWidgets.QLabel("–")
		rowStatus2a.addWidget(self.lblStatus2aResult)
		grpStatusLayout.addLayout(rowStatus2a)
		rowStatus3a = QtWidgets.QHBoxLayout()
		self.lblStatus3a = QtWidgets.QLabel("Time elapsed:")
		rowStatus3a.addWidget(self.lblStatus3a)
		self.lblStatus3aResult = QtWidgets.QLabel("–")
		rowStatus3a.addWidget(self.lblStatus3aResult)
		grpStatusLayout.addLayout(rowStatus3a)
		rowStatus4a = QtWidgets.QHBoxLayout()
		self.lblStatus4a = QtWidgets.QLabel("Ready.")
		rowStatus4a.addWidget(self.lblStatus4a)
		self.lblStatus4aResult = QtWidgets.QLabel("")
		rowStatus4a.addWidget(self.lblStatus4aResult)
		grpStatusLayout.addLayout(rowStatus4a)

		rowStatus2 = QtWidgets.QHBoxLayout()
		self.prgStatus = QtWidgets.QProgressBar()
		self.SetProgressBars(min=0, max=1, value=0)
		rowStatus2.addWidget(self.prgStatus)
		btnText = "Stop"
		self.btnCancel = QtWidgets.QPushButton(btnText)
		self.btnCancel.setEnabled(False)
		btnWidth = self.btnCancel.fontMetrics().boundingRect(btnText).width() + 15
		if platform.system() == "Darwin": btnWidth += 12
		self.btnCancel.setMaximumWidth(btnWidth)
		self.connect(self.btnCancel, QtCore.SIGNAL("clicked()"), self.AbortOperation)
		rowStatus2.addWidget(self.btnCancel)

		grpStatusLayout.addLayout(rowStatus2)
		self.grpStatus.setLayout(grpStatusLayout)

		self.layout_right.addWidget(self.grpStatus)

		self.layout.addLayout(self.layout_left, 0, 0)
		self.layout.addLayout(self.layout_right, 0, 1)
		
		# List devices
		self.layout_devices = QtWidgets.QHBoxLayout()
		self.lblDevice = QtWidgets.QLabel()
		self.lblDevice.mousePressEvent = lambda event: [ self.WriteDebugLog(event, open_log=True) ]
		self.lblDevice.setToolTip("Click here to generate a log file for debugging")
		self.lblDevice.setCursor(QtCore.Qt.PointingHandCursor)
		self.cmbDevice = QtWidgets.QComboBox()
		self.cmbDevice.setStyleSheet("QComboBox { border: 0; margin: 0; padding: 0; max-width: 0px; }")
		self.layout_devices.addWidget(self.lblDevice)
		self.layout_devices.addWidget(self.cmbDevice)
		self.layout_devices.addStretch()

		self.mnuTools = QtWidgets.QMenu("&Tools")
		self.mnuTools.addAction("Game Boy &Camera Album Viewer", self.ShowPocketCameraWindow)
		self.mnuTools.addSeparator()
		self.mnuTools.addAction("Firmware &Updater", self.ShowFirmwareUpdateWindow)

		self.mnuConfig = QtWidgets.QMenu("&Settings")
		self.mnuConfig.addAction("Check for &updates on application startup", lambda: [ self.EnableUpdateCheck() ])
		self.mnuConfig.addAction("&Append date && time to filename of save data backups", lambda: self.SETTINGS.setValue("SaveFileNameAddDateTime", str(self.mnuConfig.actions()[1].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("Prefer full &chip erase", lambda: self.SETTINGS.setValue("PreferChipErase", str(self.mnuConfig.actions()[2].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("&Verify transferred data", lambda: self.SETTINGS.setValue("VerifyData", str(self.mnuConfig.actions()[3].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("&Limit voltage when analyzing Game Boy carts", lambda: self.SETTINGS.setValue("AutoDetectLimitVoltage", str(self.mnuConfig.actions()[4].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("Limit &baud rate to 1Mbps", lambda: [ self.SETTINGS.setValue("LimitBaudRate", str(self.mnuConfig.actions()[5].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")), self.SetLimitBaudRate() ])
		self.mnuConfig.addAction("Always &generate ROM dump reports", lambda: self.SETTINGS.setValue("GenerateDumpReports", str(self.mnuConfig.actions()[6].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("Use &No-Intro file names", lambda: self.SETTINGS.setValue("UseNoIntroFilenames", str(self.mnuConfig.actions()[7].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("Automatic cartridge &power off", lambda: [ self.SETTINGS.setValue("AutoPowerOff", str(self.mnuConfig.actions()[8].isChecked()).lower().replace("true", "350").replace("false", "0")), self.SetAutoPowerOff() ])
		self.mnuConfig.addAction("Skip writing matching ROM chunk&s", lambda: self.SETTINGS.setValue("CompareSectors", str(self.mnuConfig.actions()[9].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addAction("Alternate address set mode (can fix or cause write errors)", lambda: self.SETTINGS.setValue("ForceWrPullup", str(self.mnuConfig.actions()[10].isChecked()).lower().replace("true", "enabled").replace("false", "disabled")))
		self.mnuConfig.addSeparator()
		self.mnuConfigReadModeAGB = QtWidgets.QMenu("&Read Method (Game Boy Advance)")
		self.mnuConfigReadModeAGB.addAction("S&tream", lambda: [ self.SETTINGS.setValue("AGBReadMethod", str(self.mnuConfigReadModeAGB.actions()[1].isChecked()).lower().replace("true", "2")), self.SetAGBReadMethod() ])
		self.mnuConfigReadModeAGB.addAction("&Single", lambda: [ self.SETTINGS.setValue("AGBReadMethod", str(self.mnuConfigReadModeAGB.actions()[0].isChecked()).lower().replace("true", "0")), self.SetAGBReadMethod() ])
		self.mnuConfigReadModeAGB.actions()[0].setCheckable(True)
		self.mnuConfigReadModeAGB.actions()[1].setCheckable(True)
		self.mnuConfigReadModeAGB.actions()[0].setChecked(self.SETTINGS.value("AGBReadMethod", default="2") == "2")
		self.mnuConfigReadModeAGB.actions()[1].setChecked(self.SETTINGS.value("AGBReadMethod", default="2") == "0")
		self.mnuConfigReadModeDMG = QtWidgets.QMenu("&Read Method (Game Boy)")
		self.mnuConfigReadModeDMG.addAction("&Normal", lambda: [ self.SETTINGS.setValue("DMGReadMethod", str(self.mnuConfigReadModeAGB.actions()[1].isChecked()).lower().replace("true", "1")), self.SetDMGReadMethod() ])
		self.mnuConfigReadModeDMG.addAction("&Delayed", lambda: [ self.SETTINGS.setValue("DMGReadMethod", str(self.mnuConfigReadModeAGB.actions()[0].isChecked()).lower().replace("true", "2")), self.SetDMGReadMethod() ])
		self.mnuConfigReadModeDMG.actions()[0].setCheckable(True)
		self.mnuConfigReadModeDMG.actions()[1].setCheckable(True)
		self.mnuConfigReadModeDMG.actions()[0].setChecked(self.SETTINGS.value("DMGReadMethod", default="1") == "1")
		self.mnuConfigReadModeDMG.actions()[1].setChecked(self.SETTINGS.value("DMGReadMethod", default="1") == "2")
		self.mnuConfig.addMenu(self.mnuConfigReadModeDMG)
		self.mnuConfig.addMenu(self.mnuConfigReadModeAGB)
		self.mnuConfig.addSeparator()
		self.mnuConfig.addAction("Re-&enable suppressed messages", self.ReEnableMessages)
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

		self.mnuThirdParty = QtWidgets.QMenu("Third Party &Notices")
		self.mnuThirdParty.addAction("About &Qt", lambda: [ QtWidgets.QMessageBox.aboutQt(None) ])
		self.mnuThirdParty.addAction("About Game &Database", self.AboutGameDB)
		self.mnuThirdParty.addAction("Licenses", lambda: [ self.OpenPath(Util.APP_PATH + "/res/Third Party Notices.md") ])

		btnText = "&Options"
		self.btnMainMenu = QtWidgets.QPushButton(btnText)
		btnWidth = self.btnMainMenu.fontMetrics().boundingRect(btnText).width() + 24
		if platform.system() == "Darwin": btnWidth += 12
		self.btnMainMenu.setMaximumWidth(btnWidth)
		self.mnuMainMenu = QtWidgets.QMenu()
		self.mnuMainMenu.addMenu(self.mnuConfig)
		self.mnuMainMenu.addMenu(self.mnuTools)
		self.mnuMainMenu.addSeparator()
		self.mnuMainMenu.addSeparator()
		self.mnuMainMenu.addAction("Open &config folder", self.OpenPath)
		self.mnuMainMenu.addSeparator()
		self.mnuMainMenu.addMenu(self.mnuThirdParty)
		self.mnuMainMenu.addAction("About &FlashGBX", self.AboutFlashGBX)
		self.btnMainMenu.setMenu(self.mnuMainMenu)

		self.btnConnect = QtWidgets.QPushButton("&Connect")
		self.connect(self.btnConnect, QtCore.SIGNAL("clicked()"), self.ConnectDevice)
		self.layout_devices.addWidget(self.btnMainMenu)
		self.layout_devices.addWidget(self.btnConnect)

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
		
		# Set the VBox layout as the window's main layout
		self.setLayout(self.layout)
		
		# Show app window first, then do update check
		self.QT_APP = qt_app
		qt_app.processEvents()
		
		config_ret = args["config_ret"]
		for i in range(0, len(config_ret)):
			if config_ret[i][0] == 0:
				print(config_ret[i][1])
			elif config_ret[i][0] == 1:
				QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(APPNAME, VERSION), config_ret[i][1], QtWidgets.QMessageBox.Ok)
			elif config_ret[i][0] == 2:
				QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), config_ret[i][1], QtWidgets.QMessageBox.Ok)
			elif config_ret[i][0] == 3:
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), config_ret[i][1], QtWidgets.QMessageBox.Ok)

		QtCore.QTimer.singleShot(1, lambda: [ self.UpdateCheck(), self.FindDevices(port=args["argparsed"].device_port, firstRun=True) ])
		self.MSGBOX_TIMER = QtCore.QTimer()
		self.MSGBOX_TIMER.timeout.connect(self.MsgBoxCheck)
		self.MSGBOX_TIMER.start(200)
	

	def MsgBoxCheck(self):
		if not self.MSGBOX_DISPLAYING and not self.MSGBOX_QUEUE.empty():
			self.MSGBOX_DISPLAYING = True
			msgbox = self.MSGBOX_QUEUE.get()
			Util.dprint(f"Processing Message Box: {msgbox}")
			msgbox.exec()
			self.MSGBOX_DISPLAYING = False
	
	def GuiCreateGroupBoxDMGCartInfo(self):
		self.grpDMGCartridgeInfo = QtWidgets.QGroupBox("Game Boy Cartridge Information")
		self.grpDMGCartridgeInfo.setMinimumWidth(400)
		group_layout = QtWidgets.QVBoxLayout()
		group_layout.setContentsMargins(-1, 5, -1, -1)

		rowDMGGameName = QtWidgets.QHBoxLayout()
		self.lblDMGGameName = QtWidgets.QLabel("Game Name:")
		self.lblDMGGameName.setContentsMargins(0, 1, 0, 1)
		rowDMGGameName.addWidget(self.lblDMGGameName)
		self.lblDMGGameNameResult = QtWidgets.QLabel("")
		rowDMGGameName.addWidget(self.lblDMGGameNameResult)
		rowDMGGameName.setStretch(0, 9)
		rowDMGGameName.setStretch(1, 12)
		group_layout.addLayout(rowDMGGameName)

		rowDMGRomTitle = QtWidgets.QHBoxLayout()
		self.lblDMGRomTitle = QtWidgets.QLabel("ROM Title:")
		self.lblDMGRomTitle.setContentsMargins(0, 1, 0, 1)
		rowDMGRomTitle.addWidget(self.lblDMGRomTitle)
		self.lblDMGRomTitleResult = QtWidgets.QLabel("")
		rowDMGRomTitle.addWidget(self.lblDMGRomTitleResult)
		rowDMGRomTitle.setStretch(0, 9)
		rowDMGRomTitle.setStretch(1, 12)
		group_layout.addLayout(rowDMGRomTitle)

		rowDMGGameCodeRevision = QtWidgets.QHBoxLayout()
		self.lblDMGGameCodeRevision = QtWidgets.QLabel("Game Code and Revision:")
		self.lblDMGGameCodeRevision.setContentsMargins(0, 1, 0, 1)
		rowDMGGameCodeRevision.addWidget(self.lblDMGGameCodeRevision)
		self.lblDMGGameCodeRevisionResult = QtWidgets.QLabel("")
		rowDMGGameCodeRevision.addWidget(self.lblDMGGameCodeRevisionResult)
		rowDMGGameCodeRevision.setStretch(0, 9)
		rowDMGGameCodeRevision.setStretch(1, 12)
		group_layout.addLayout(rowDMGGameCodeRevision)

		rowDMGHeaderRtc = QtWidgets.QHBoxLayout()
		lblDMGHeaderRtc = QtWidgets.QLabel("Real Time Clock:")
		lblDMGHeaderRtc.setContentsMargins(0, 1, 0, 1)
		rowDMGHeaderRtc.addWidget(lblDMGHeaderRtc)
		self.lblDMGHeaderRtcResult = QtWidgets.QLabel("")
		self.lblDMGHeaderRtcResult.mousePressEvent = lambda event: [ self.EditRTC(event) ]
		rowDMGHeaderRtc.addWidget(self.lblDMGHeaderRtcResult)
		rowDMGHeaderRtc.setStretch(0, 9)
		rowDMGHeaderRtc.setStretch(1, 12)
		group_layout.addLayout(rowDMGHeaderRtc)

		rowDMGHeaderBootlogo = QtWidgets.QHBoxLayout()
		lblDMGHeaderBootlogo = QtWidgets.QLabel("Boot Logo:")
		lblDMGHeaderBootlogo.setContentsMargins(0, 1, 0, 1)
		rowDMGHeaderBootlogo.addWidget(lblDMGHeaderBootlogo)
		self.lblDMGHeaderBootlogoResult = QtWidgets.QLabel("")
		rowDMGHeaderBootlogo.addWidget(self.lblDMGHeaderBootlogoResult)
		rowDMGHeaderBootlogo.setStretch(0, 9)
		rowDMGHeaderBootlogo.setStretch(1, 12)
		group_layout.addLayout(rowDMGHeaderBootlogo)

		rowDMGHeaderROMChecksum = QtWidgets.QHBoxLayout()
		lblDMGHeaderROMChecksum = QtWidgets.QLabel("ROM Checksum:")
		lblDMGHeaderROMChecksum.setContentsMargins(0, 1, 0, 1)
		rowDMGHeaderROMChecksum.addWidget(lblDMGHeaderROMChecksum)
		self.lblDMGHeaderROMChecksumResult = QtWidgets.QLabel("")
		rowDMGHeaderROMChecksum.addWidget(self.lblDMGHeaderROMChecksumResult)
		rowDMGHeaderROMChecksum.setStretch(0, 9)
		rowDMGHeaderROMChecksum.setStretch(1, 12)
		group_layout.addLayout(rowDMGHeaderROMChecksum)

		rowDMGHeaderROMSize = QtWidgets.QHBoxLayout()
		lblDMGHeaderROMSize = QtWidgets.QLabel("ROM Size:")
		rowDMGHeaderROMSize.addWidget(lblDMGHeaderROMSize)
		self.cmbDMGHeaderROMSizeResult = QtWidgets.QComboBox()
		self.cmbDMGHeaderROMSizeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbDMGHeaderROMSizeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowDMGHeaderROMSize.addWidget(self.cmbDMGHeaderROMSizeResult)
		rowDMGHeaderROMSize.setStretch(0, 9)
		rowDMGHeaderROMSize.setStretch(1, 12)
		group_layout.addLayout(rowDMGHeaderROMSize)

		rowDMGHeaderSaveType = QtWidgets.QHBoxLayout()
		lblDMGHeaderSaveType = QtWidgets.QLabel("Save Type:")
		rowDMGHeaderSaveType.addWidget(lblDMGHeaderSaveType)
		self.cmbDMGHeaderSaveTypeResult = QtWidgets.QComboBox()
		self.cmbDMGHeaderSaveTypeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbDMGHeaderSaveTypeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowDMGHeaderSaveType.addWidget(self.cmbDMGHeaderSaveTypeResult)
		rowDMGHeaderSaveType.setStretch(0, 9)
		rowDMGHeaderSaveType.setStretch(1, 12)
		group_layout.addLayout(rowDMGHeaderSaveType)

		rowDMGHeaderMapper = QtWidgets.QHBoxLayout()
		lblDMGHeaderMapper = QtWidgets.QLabel("Mapper Type:")
		rowDMGHeaderMapper.addWidget(lblDMGHeaderMapper)
		self.cmbDMGHeaderMapperResult = QtWidgets.QComboBox()
		self.cmbDMGHeaderMapperResult.setStyleSheet("combobox-popup: 0;")
		self.cmbDMGHeaderMapperResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowDMGHeaderMapper.addWidget(self.cmbDMGHeaderMapperResult)
		rowDMGHeaderMapper.setStretch(0, 9)
		rowDMGHeaderMapper.setStretch(1, 12)
		group_layout.addLayout(rowDMGHeaderMapper)

		rowDMGCartridgeType = QtWidgets.QHBoxLayout()
		lblDMGCartridgeType = QtWidgets.QLabel("Profile:")
		rowDMGCartridgeType.addWidget(lblDMGCartridgeType)
		self.cmbDMGCartridgeTypeResult = QtWidgets.QComboBox()
		self.cmbDMGCartridgeTypeResult.setStyleSheet("max-width: 260px;")
		self.cmbDMGCartridgeTypeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbDMGCartridgeTypeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		rowDMGCartridgeType.addWidget(self.cmbDMGCartridgeTypeResult)
		group_layout.addLayout(rowDMGCartridgeType)

		self.grpDMGCartridgeInfo.setLayout(group_layout)
		
		return self.grpDMGCartridgeInfo
	
	def GuiCreateGroupBoxAGBCartInfo(self):
		self.grpAGBCartridgeInfo = QtWidgets.QGroupBox("Game Boy Advance Cartridge Information")
		self.grpAGBCartridgeInfo.setMinimumWidth(400)
		group_layout = QtWidgets.QVBoxLayout()
		group_layout.setContentsMargins(-1, 5, -1, -1)

		rowAGBGameName = QtWidgets.QHBoxLayout()
		lblAGBGameName = QtWidgets.QLabel("Game Name:")
		lblAGBGameName.setContentsMargins(0, 1, 0, 1)
		rowAGBGameName.addWidget(lblAGBGameName)
		self.lblAGBGameNameResult = QtWidgets.QLabel("")
		rowAGBGameName.addWidget(self.lblAGBGameNameResult)
		rowAGBGameName.setStretch(0, 9)
		rowAGBGameName.setStretch(1, 12)
		group_layout.addLayout(rowAGBGameName)

		rowAGBRomTitle = QtWidgets.QHBoxLayout()
		lblAGBRomTitle = QtWidgets.QLabel("ROM Title:")
		lblAGBRomTitle.setContentsMargins(0, 1, 0, 1)
		rowAGBRomTitle.addWidget(lblAGBRomTitle)
		self.lblAGBRomTitleResult = QtWidgets.QLabel("")
		rowAGBRomTitle.addWidget(self.lblAGBRomTitleResult)
		rowAGBRomTitle.setStretch(0, 9)
		rowAGBRomTitle.setStretch(1, 12)
		group_layout.addLayout(rowAGBRomTitle)

		rowAGBHeaderGameCodeRevision = QtWidgets.QHBoxLayout()
		lblAGBHeaderGameCodeRevision = QtWidgets.QLabel("Game Code and Revision:")
		lblAGBHeaderGameCodeRevision.setContentsMargins(0, 1, 0, 1)
		rowAGBHeaderGameCodeRevision.addWidget(lblAGBHeaderGameCodeRevision)
		self.lblAGBHeaderGameCodeRevisionResult = QtWidgets.QLabel("")
		rowAGBHeaderGameCodeRevision.addWidget(self.lblAGBHeaderGameCodeRevisionResult)
		rowAGBHeaderGameCodeRevision.setStretch(0, 9)
		rowAGBHeaderGameCodeRevision.setStretch(1, 12)
		group_layout.addLayout(rowAGBHeaderGameCodeRevision)

		rowAGBGpioRtc = QtWidgets.QHBoxLayout()
		lblAGBGpioRtc = QtWidgets.QLabel("Real Time Clock:")
		lblAGBGpioRtc.setContentsMargins(0, 1, 0, 1)
		rowAGBGpioRtc.addWidget(lblAGBGpioRtc)
		self.lblAGBGpioRtcResult = QtWidgets.QLabel("")
		self.lblAGBGpioRtcResult.mousePressEvent = lambda event: [ self.EditRTC(event) ]
		rowAGBGpioRtc.addWidget(self.lblAGBGpioRtcResult)
		rowAGBGpioRtc.setStretch(0, 9)
		rowAGBGpioRtc.setStretch(1, 12)
		group_layout.addLayout(rowAGBGpioRtc)

		rowAGBHeaderBootlogo = QtWidgets.QHBoxLayout()
		lblAGBHeaderBootlogo = QtWidgets.QLabel("Boot Logo:")
		lblAGBHeaderBootlogo.setContentsMargins(0, 1, 0, 1)
		rowAGBHeaderBootlogo.addWidget(lblAGBHeaderBootlogo)
		self.lblAGBHeaderBootlogoResult = QtWidgets.QLabel("")
		rowAGBHeaderBootlogo.addWidget(self.lblAGBHeaderBootlogoResult)
		rowAGBHeaderBootlogo.setStretch(0, 9)
		rowAGBHeaderBootlogo.setStretch(1, 12)
		group_layout.addLayout(rowAGBHeaderBootlogo)

		rowAGBHeaderChecksum = QtWidgets.QHBoxLayout()
		lblAGBHeaderChecksum = QtWidgets.QLabel("Header Checksum:")
		lblAGBHeaderChecksum.setContentsMargins(0, 1, 0, 1)
		rowAGBHeaderChecksum.addWidget(lblAGBHeaderChecksum)
		self.lblAGBHeaderChecksumResult = QtWidgets.QLabel("")
		rowAGBHeaderChecksum.addWidget(self.lblAGBHeaderChecksumResult)
		rowAGBHeaderChecksum.setStretch(0, 9)
		rowAGBHeaderChecksum.setStretch(1, 12)
		group_layout.addLayout(rowAGBHeaderChecksum)

		rowAGBHeaderROMChecksum = QtWidgets.QHBoxLayout()
		lblAGBHeaderROMChecksum = QtWidgets.QLabel("ROM Checksum:")
		lblAGBHeaderROMChecksum.setContentsMargins(0, 1, 0, 1)
		rowAGBHeaderROMChecksum.addWidget(lblAGBHeaderROMChecksum)
		self.lblAGBHeaderROMChecksumResult = QtWidgets.QLabel("")
		rowAGBHeaderROMChecksum.addWidget(self.lblAGBHeaderROMChecksumResult)
		rowAGBHeaderROMChecksum.setStretch(0, 9)
		rowAGBHeaderROMChecksum.setStretch(1, 12)
		group_layout.addLayout(rowAGBHeaderROMChecksum)
		
		rowAGBHeaderROMSize = QtWidgets.QHBoxLayout()
		lblAGBHeaderROMSize = QtWidgets.QLabel("ROM Size:")
		rowAGBHeaderROMSize.addWidget(lblAGBHeaderROMSize)
		self.cmbAGBHeaderROMSizeResult = QtWidgets.QComboBox()
		self.cmbAGBHeaderROMSizeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbAGBHeaderROMSizeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.cmbAGBHeaderROMSizeResult.addItems(Util.AGB_Header_ROM_Sizes)
		self.cmbAGBHeaderROMSizeResult.setCurrentIndex(self.cmbAGBHeaderROMSizeResult.count() - 1)
		rowAGBHeaderROMSize.addWidget(self.cmbAGBHeaderROMSizeResult)
		rowAGBHeaderROMSize.setStretch(0, 9)
		rowAGBHeaderROMSize.setStretch(1, 12)
		group_layout.addLayout(rowAGBHeaderROMSize)
		
		rowAGBHeaderSaveType = QtWidgets.QHBoxLayout()
		lblAGBHeaderSaveType = QtWidgets.QLabel("Save Type:")
		rowAGBHeaderSaveType.addWidget(lblAGBHeaderSaveType)
		self.cmbAGBSaveTypeResult = QtWidgets.QComboBox()
		self.cmbAGBSaveTypeResult.setStyleSheet("combobox-popup: 0;")
		self.cmbAGBSaveTypeResult.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.cmbAGBSaveTypeResult.addItems(Util.AGB_Header_Save_Types)
		self.cmbAGBSaveTypeResult.setCurrentIndex(self.cmbAGBSaveTypeResult.count() - 1)
		rowAGBHeaderSaveType.addWidget(self.cmbAGBSaveTypeResult)
		rowAGBHeaderSaveType.setStretch(0, 9)
		rowAGBHeaderSaveType.setStretch(1, 12)
		group_layout.addLayout(rowAGBHeaderSaveType)
		
		rowAGBCartridgeType = QtWidgets.QHBoxLayout()
		lblAGBCartridgeType = QtWidgets.QLabel("Profile:")
		rowAGBCartridgeType.addWidget(lblAGBCartridgeType)
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
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(APPNAME, VERSION), "Would you like to automatically check for new versions at application startup? This will make use of the GitHub API (<a href=\"https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement\">privacy policy</a>).", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
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

	def UpdateCheck(self):
		update_check = self.SETTINGS.value("UpdateCheck")
		if update_check is None:
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(APPNAME, VERSION), "Welcome to {:s} {:s} by Lesserkuma!<br><br>".format(APPNAME, VERSION) + "Would you like to automatically check for new versions at application startup? This will make use of the GitHub API (<a href=\"https://docs.github.com/en/site-policy/privacy-policies/github-privacy-statement\">privacy policy</a>).", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
			if answer == QtWidgets.QMessageBox.Yes:
				self.SETTINGS.setValue("UpdateCheck", "enabled")
				self.mnuConfig.actions()[0].setChecked(True)
				update_check = "enabled"
			else:
				self.SETTINGS.setValue("UpdateCheck", "disabled")
		if update_check and update_check.lower() == "enabled":
			print("")
			url = "https://api.github.com/repos/Lesserkuma/FlashGBX/releases/latest"
			site = "https://github.com/Lesserkuma/FlashGBX/releases/latest"
			try:
				ret = requests.get(url, allow_redirects=True, timeout=1.5)
			except requests.exceptions.ConnectTimeout as e:
				print("ERROR: Update check failed due to a connection timeout. Please check your internet connection.", e, sep="\n")
				ret = False
			except requests.exceptions.ConnectionError as e:
				print("ERROR: Update check failed due to a connection error. Please check your network connection.", e, sep="\n")
				ret = False
			except Exception as e:
				print("ERROR: An unexpected error occured while querying the latest version information from GitHub.", e, sep="\n")
				ret = False
			if ret is not False and ret.status_code == 200:
				ret = ret.content
				try:
					ret = json.loads(ret)
					if 'tag_name' in ret:
						latest_version = str(ret['tag_name'])
						if version.parse(latest_version) == version.parse(VERSION_PEP440):
							print("You are using the latest version of {:s}.".format(APPNAME))
						elif version.parse(latest_version) > version.parse(VERSION_PEP440):
							msg_text = "A new version of {:s} has been released!\nVersion {:s} is now available.".format(APPNAME, latest_version)
							print(msg_text)
							msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} Update Check".format(APPNAME), text=msg_text)
							button_open = msgbox.addButton("  &Open release notes  ", QtWidgets.QMessageBox.ActionRole)
							button_cancel = msgbox.addButton("&Close", QtWidgets.QMessageBox.RejectRole)
							msgbox.setDefaultButton(button_open)
							msgbox.setEscapeButton(button_cancel)
							answer = msgbox.exec()
							if msgbox.clickedButton() == button_open:
								webbrowser.open(site)
						else:
							print("This version of {:s} ({:s}) seems to be newer than the latest public release ({:s}).".format(APPNAME, VERSION_PEP440, latest_version))
					else:
						print("Error: Update check failed due to missing version information in JSON data from GitHub.")
				except json.decoder.JSONDecodeError:
					print("Error: Update check failed due to malformed JSON data from GitHub.")
				except Exception as e:
					print("Error: An unexpected error occured while querying the latest version information from GitHub.", e, sep="\n")
			elif ret is not False:
				if ret.status_code == 403 and "X-RateLimit-Remaining" in ret.headers and ret.headers["X-RateLimit-Remaining"] == '0':
					print("Error: Failed to check for updates (too many API requests). Try again later.")
				else:
					print("Error: Failed to check for updates (HTTP status {:d}).".format(ret.status_code))

	def DisconnectDevice(self):
		try:
			devname = self.CONN.GetFullNameExtended()
			self.CONN.Close(cartPowerOff=True)
			print("Disconnected from {:s}".format(devname))
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
		self.btnConnect.setText("&Connect")
		self.lblDevice.setText("Disconnected.")
		self.SetProgressBars(min=0, max=1, value=0)
		self.lblStatus4a.setText("Disconnected.")
		self.lblStatus1aResult.setText("–")
		self.lblStatus2aResult.setText("–")
		self.lblStatus3aResult.setText("–")
		self.lblStatus4aResult.setText("")
		self.lblStatus4a.setText("Disconnected.")
		self.grpStatus.setTitle("Transfer Status")
		self.mnuConfig.actions()[5].setVisible(True)
		self.mnuConfig.actions()[8].setVisible(True)
		self.mnuConfig.actions()[9].setVisible(True)
		self.mnuConfig.actions()[10].setVisible(False)
		self.mnuTools.actions()[2].setEnabled(True)
		self.mnuConfigReadModeAGB.setEnabled(True)
	
	def ReEnableMessages(self):
		self.SETTINGS.setValue("AutoReconnect", "disabled")
		self.SETTINGS.setValue("SkipModeChangeWarning", "disabled")
		self.SETTINGS.setValue("SkipAutodetectMessage", "disabled")
		self.SETTINGS.setValue("SkipFinishMessage", "disabled")
		self.SETTINGS.setValue("SkipCameraSavePopup", "disabled")

	def AboutFlashGBX(self):
		msg = "This software is being developed by Lesserkuma as a hobby project. There is no affiliation with Nintendo or any other company. This software is provided as-is and the developer is not responsible for any damage that is caused by the use of it. Use at your own risk!<br><br>"
		msg += f"© 2020–{datetime.datetime.now().year} Lesserkuma<br>"
		msg += "• Website: <a href=\"https://github.com/Lesserkuma/FlashGBX\">https://github.com/Lesserkuma/FlashGBX</a><br><br>"
		msg += "Acknowledgments and Contributors:<br>2358, 90sFlav, AcoVanConis, AdmirtheSableye, AlexiG, ALXCO-Hardware, AndehX, antPL, aronson, Ausar, bbsan, BennVenn, ccs21, chobby, ClassicOldSong, Cliffback, CodyWick13, Corborg, Cristóbal, crizzlycruz, Crystal, Därk, Davidish, delibird_deals, DevDavisNunez, Diddy_Kong, djedditt, Dr-InSide, dyf2007, easthighNerd, EchelonPrime, edo999, Eldram, Ell, EmperorOfTigers, endrift, Erba Verde, ethanstrax, eveningmoose, Falknör, FerrantePescara, frarees, Frost Clock, Gahr, gandalf1980, gboh, gekkio, Godan, Grender, HDR, Herax, Hiccup, hiks, howie0210, iamevn, Icesythe7, ide, infinest, inYourBackline, iyatemu, Jayro, Jenetrix, JFox, joyrider3774, jrharbort, JS7457, julgr, Kaede, kane159, KOOORAY, kscheel, kyokohunter, Leitplanke, litlemoran, LovelyA72, Lu, Luca DS, LucentW, luxkiller65, manuelcm1, marv17, Merkin, metroid-maniac, Mr_V, Mufsta, olDirdey, orangeglo, paarongiroux, Paradoxical, Pese, Rairch, Raphaël BOICHOT, redalchemy, RetroGorek, RevZ, RibShark, s1cp, Satumox, Sgt.DoudouMiel, SH, Shinichi999, Sillyhatday, simonK, Sithdown, skite2001, Smelly-Ghost, Sonikks, Squiddy, Stitch, Super Maker, t5b6_de, Tauwasser, TheNFCookie, Timville, twitnic, velipso, Veund, voltagex, Voultar, Warez Waldo, wickawack, Winter1760, Wkr, x7l7j8cc, xactoes, xukkorz, yosoo, Zeii, Zelante, zipplet, Zoo, zvxr"
		QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(APPNAME, VERSION), msg, QtWidgets.QMessageBox.Ok)

	def AboutGameDB(self):
		msg = f"{APPNAME} uses a game database that is based on the ongoing efforts of the No-Intro project. Visit <a href=\"https://no-intro.org/\">https://no-intro.org/</a> for more information.<br><br>"
		msg += f"No-Intro databases referenced for this version of {APPNAME}:<br>"
		msg += "• Nintendo - Game Boy (20260113-102506)<br>• Nintendo - Game Boy Advance (20260124-113814)<br>• Nintendo - Game Boy Advance (Video) (20251114-101831)<br>• Nintendo - Game Boy Color (20260110-131928)" # No-Intro DBs
		QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(APPNAME, VERSION), msg, QtWidgets.QMessageBox.Ok)

	def OpenPath(self, path=None):
		if path is None:
			path = Util.CONFIG_PATH
			kbmod = QtWidgets.QApplication.keyboardModifiers()
			if kbmod != QtCore.Qt.ShiftModifier:
				self.WriteDebugLog()
		path = 'file://{0:s}'.format(path)
		try:
			if platform.system() == "Windows":
				os.startfile(path)
			elif platform.system() == "Darwin":
				subprocess.Popen(["open", path])
			else:
				subprocess.Popen(["xdg-open", path])
		except:
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "The file was not found.\n\n{:s}".format(path), QtWidgets.QMessageBox.Ok)

	def WriteDebugLog(self, event=None, open_log=False):
		if isinstance(event, QtGui.QMouseEvent):
			if event.button() in (QtCore.Qt.MouseButton.MiddleButton, QtCore.Qt.MouseButton.RightButton): return

		device = False
		try:
			device = self.CONN.GetFullNameExtended(more=True)
		except:
			pass
		
		Util.write_debug_log(device)
		try:
			if open_log is True:
				fn = Util.CONFIG_PATH + "/debug.log"
				self.OpenPath(fn)
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
				if self.cmbDevice.count() == 0: self.lblDevice.setText("No connection.")
				return False
			elif isinstance(ret, list):
				for i in range(0, len(ret)):
					status = ret[i][0]
					text = ret[i][1]
					if text in msg: continue
					if status == 0:
						msg += text + "\n"
					elif status == 1:
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Ok)
						if not '\n' in text: msgbox.setTextFormat(QtCore.Qt.RichText)
						msgbox.exec()
					elif status == 2:
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Ok)
						if not '\n' in text: msgbox.setTextFormat(QtCore.Qt.RichText)
						msgbox.exec()
					elif status == 3:
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Ok)
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
				
				self.CONN.SetTimeout(float(self.SETTINGS.value("SerialTimeout", default="1")))
				self.optDMG.setAutoExclusive(False)
				self.optAGB.setAutoExclusive(False)
				if "DMG" in self.CONN.GetSupprtedModes():
					self.optDMG.setEnabled(True)
					self.optDMG.setChecked(False)
				if "AGB" in self.CONN.GetSupprtedModes():
					self.optAGB.setEnabled(True)
					self.optAGB.setChecked(False)
				self.optAGB.setAutoExclusive(True)
				self.optDMG.setAutoExclusive(True)
				self.lblStatus4a.setText("Ready.")
				self.btnConnect.setText("&Disconnect")
				self.cmbDevice.setStyleSheet("QComboBox { border: 0; margin: 0; padding: 0; max-width: 0px; }")
				if dev.GetFWBuildDate() == "":
					self.lblDevice.setText(dev.GetFullNameLabel() + " [Legacy Mode]")
				else:
					self.lblDevice.setText(dev.GetFullNameLabel())
				print("\nConnected to {:s}".format(dev.GetFullNameExtended(more=True)))
				self.grpActions.setEnabled(True)
				self.mnuTools.setEnabled(True)
				self.mnuConfig.setEnabled(True)
				self.btnCancel.setEnabled(False)

				# Firmware Update Menu
				self.mnuTools.actions()[2].setEnabled(True)
				supports_firmware_updates = self.CONN.SupportsFirmwareUpdates()
				if supports_firmware_updates is False:
					self.mnuTools.actions()[2].setEnabled(False)

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
								text = "A firmware update for your {:s} device is required to use this software. Do you want to update now?".format(dev.GetFullName())
								msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
							elif dev.FW_UPDATE_REQ == 2:
								text = "Your {:s} device is no longer supported in this version of FlashGBX due to technical limitations. The last supported version is <a href=\"https://github.com/Lesserkuma/FlashGBX/releases/tag/3.37\">FlashGBX v3.37</a>.\n\nYou can still use the Firmware Updater, however any other functions are no longer available.\n\nDo you want to run the Firmware Updater now?".format(dev.GetFullName()).replace("\n", "<br>")
								msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
							else:
								text = "A firmware update for your {:s} device is available. Do you want to update now?".format(dev.GetFullName())
								msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, defaultButton=QtWidgets.QMessageBox.Yes)
								cb = QtWidgets.QCheckBox("Ignore firmware updates", checked=dontShowAgain)
							answer = msgbox.exec()
							if dev.FW_UPDATE_REQ:
								if answer == QtWidgets.QMessageBox.Yes:
									self.ShowFirmwareUpdateWindow()
								if not Util.DEBUG:
									self.DisconnectDevice()
							else:
								if cb is not None:
									dontShowAgain = cb.isChecked()
									if dontShowAgain: self.SETTINGS.setValue("SkipFirmwareUpdate", "enabled")
								if answer == QtWidgets.QMessageBox.Yes:
									self.ShowFirmwareUpdateWindow()
				
				elif dev.FW_UPDATE_REQ:
					text = "A firmware update for your {:s} device is required to use this software.<br><br>Current firmware version: {:s}".format(dev.GetFullName(), dev.GetFirmwareVersion())
					if not Util.DEBUG:
						self.DisconnectDevice()
					QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), text, QtWidgets.QMessageBox.Ok)
				
				if dev.IsUnregistered():
					try:
						text = dev.GetRegisterInformation()
						QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), text, QtWidgets.QMessageBox.Ok)
					except:
						pass

				return True

			return False
	
	def FindDevices(self, connectToFirst=False, port=None, mode=None, firstRun=False):
		if self.CONN is not None:
			self.DisconnectDevice()
		self.lblDevice.setText("Searching...")
		self.btnConnect.setEnabled(False)
		qt_app.processEvents()
		
		messages = []

		# pylint: disable=global-variable-not-assigned
		global hw_devices
		for hw_device in hw_devices:
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
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), msg[:-2], QtWidgets.QMessageBox.Ok)
			elif not firstRun:
				msg = \
					"No compatible devices found. Please ensure the device is connected properly.\n\n" \
					"Compatible devices:\n" \
					"- insideGadgets GBxCart RW\n" \
					"- Geeksimon GBFlash\n" \
					"- BennVenn Joey Jr (requires firmware update)\n\n" \
					"Troubleshooting advice:\n" \
					"- Reconnect the device, try different USB ports/cables, avoid passive USB hubs\n" \
					"- Use a USB data cable (battery charging cables may not work)\n" \
					"- Check if the operating system detects the device (if not, reboot your machine)\n" \
					"- Update the firmware through Options → Tools → Firmware Updater"
				if platform.system() == "Darwin":
					msg += "\n   - <b>For Joey Jr on macOS:</b> Use the dedicated <a href=\"https://github.com/Lesserkuma/JoeyJr_FWUpdater\">Firmware Updater for Joey Jr</a>"
				elif platform.system() == "Linux":
					msg += "\n- <b>For Linux users:</b> Ensure your user account has permissions to use the device (try adding yourself to user groups “dialout” or “uucp”)"

				QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg.replace("\n", "<br>"), standardButtons=QtWidgets.QMessageBox.Ok).exec()
			
			self.lblDevice.setText("No devices found.")
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
			self.lblDevice.setText("Connect to:")
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
		self.lblStatus4a.setText("Stopping... Please wait.")
		self.lblStatus4aResult.setText("")
	
	def FinishOperation(self):
		if self.lblStatus2aResult.text() == "Pending...": self.lblStatus2aResult.setText("–")
		self.lblStatus4aResult.setText("")
		self.grpDMGCartridgeInfo.setEnabled(True)
		self.grpAGBCartridgeInfo.setEnabled(True)
		self.grpActions.setEnabled(True)
		self.mnuTools.setEnabled(True)
		self.mnuConfig.setEnabled(True)
		self.btnCancel.setEnabled(False)
		
		dontShowAgain = str(self.SETTINGS.value("SkipFinishMessage", default="disabled")).lower() == "enabled"
		msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="Operation complete!", standardButtons=QtWidgets.QMessageBox.Ok)
		
		time_elapsed = None
		msg_te = ""
		speed = None
		if "time_start" in self.STATUS and self.STATUS["time_start"] > 0:
			time_elapsed = time.time() - self.STATUS["time_start"]
			msg_te = "\n\nTotal time elapsed: {:s}".format(Util.formatProgressTime(time_elapsed, asFloat=True))
			if "transferred" in self.CONN.INFO:
				speed = "{:.2f} KiB/s".format((self.CONN.INFO["transferred"] / 1024.0) / time_elapsed)
			self.STATUS["time_start"] = 0
		
		if self.CONN.INFO["last_action"] == 1: # Backup ROM
			self.CONN.INFO["last_action"] = 0
			dump_report = False
			button_dump_report = None
			dumpinfo_file = ""
			temp = str(self.SETTINGS.value("GenerateDumpReports", default="disabled")).lower() == "enabled"
			try:
				dump_report = self.CONN.GetDumpReport()
				if dump_report is not False:
					if time_elapsed is not None and speed is not None:
						self.lblStatus2aResult.setText(speed)
						dump_report = dump_report.replace("%TRANSFER_RATE%", speed)
						dump_report = dump_report.replace("%TIME_ELAPSED%", Util.formatProgressTime(time_elapsed))
					else:
						dump_report = dump_report.replace("%TRANSFER_RATE%", "N/A")
						dump_report = dump_report.replace("%TIME_ELAPSED%", "N/A")
					dumpinfo_file = os.path.splitext(self.STATUS["last_path"])[0] + ".txt"
			except Exception as e:
				print("ERROR: {:s}".format(str(e)))
			
			if dump_report is not False and dumpinfo_file != "" and temp is True:
				try:
					with open(dumpinfo_file, "wb") as f:
						f.write(bytearray([ 0xEF, 0xBB, 0xBF ])) # UTF-8 BOM
						f.write(dump_report.encode("UTF-8"))
					button_dump_report = msgbox.addButton("  Open Dump &Report  ", QtWidgets.QMessageBox.ActionRole)
				except Exception as e:
					print("ERROR: {:s}".format(str(e)))
			else:
				button_dump_report = msgbox.addButton("  Generate Dump &Report  ", QtWidgets.QMessageBox.ActionRole)
			
			button_open_dir = msgbox.addButton("  Open Fol&der  ", QtWidgets.QMessageBox.ActionRole)

			if self.CONN.GetMode() == "DMG":
				if self.CONN.INFO["rom_checksum"] == self.CONN.INFO["rom_checksum_calc"]:
					self.lblDMGHeaderROMChecksumResult.setText("Valid (0x{:04X})".format(self.CONN.INFO["rom_checksum"]))
					self.lblDMGHeaderROMChecksumResult.setStyleSheet("QLabel { color: green; }")
					self.lblStatus4a.setText("Done!")
					msg = "The ROM backup is complete and the checksum was verified successfully!"
					msgbox.setText(msg + msg_te)
					msgbox.exec()
				else:
					self.lblStatus4a.setText("Done.")
					if "mapper_raw" in self.CONN.INFO and self.CONN.INFO["mapper_raw"] in (0x202, 0x203, 0x205):
						msg = "The ROM backup is complete."
						msgbox.setText(msg + msg_te)
						msgbox.exec()
					else:
						self.lblDMGHeaderROMChecksumResult.setText("Invalid (0x{:04X}≠0x{:04X})".format(self.CONN.INFO["rom_checksum_calc"], self.CONN.INFO["rom_checksum"]))
						self.lblDMGHeaderROMChecksumResult.setStyleSheet("QLabel { color: red; }")
						msg = "The ROM was dumped, but the checksum is not correct."
						button_gmmc1 = None
						if self.CONN.INFO["loop_detected"] is not False:
							msg += "\n\nA data loop was detected in the ROM backup at position 0x{:X} ({:s}). This may indicate a bad dump or overdump.".format(self.CONN.INFO["loop_detected"], Util.formatFileSize(size=self.CONN.INFO["loop_detected"], asInt=True))
						else:
							msg += " This may indicate a bad dump, however this can be normal for some reproduction cartridges, unlicensed games, prototypes, patched games and intentional overdumps. You can also try to change the read mode in the options."
							if self.CONN.GetMode() == "DMG" and self.cmbDMGHeaderMapperResult.currentText() == "MBC1":
								msg += "\n\nIf this is a NP GB-Memory Cartridge, try the “Retry as G-MMC1” option."
								button_gmmc1 = msgbox.addButton("  Retry as G-MMC1  ", QtWidgets.QMessageBox.ActionRole)
						msgbox.setText(msg + msg_te)
						msgbox.setIcon(QtWidgets.QMessageBox.Warning)
						msgbox.exec()
						if msgbox.clickedButton() == button_gmmc1:
							if self.CheckDeviceAlive():
								self.cmbDMGHeaderMapperResult.setCurrentIndex(Util.ConvertMapperToMapperType(0x105)[2])
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
					if self.CONN.INFO["db"]["rc"] == self.CONN.INFO["file_crc32"]:
						self.lblAGBHeaderROMChecksumResult.setText("Valid (0x{:06X})".format(self.CONN.INFO["db"]["rc"]))
						self.lblAGBHeaderROMChecksumResult.setStyleSheet("QLabel { color: green; }")
						self.lblStatus4a.setText("Done!")
						msg = "The ROM backup is complete and the checksum was verified successfully!"
						msgbox.setText(msg + msg_te)
						msgbox.exec()
					else:
						self.lblAGBHeaderROMChecksumResult.setText("Invalid (0x{:06X}≠0x{:06X})".format(self.CONN.INFO["file_crc32"], self.CONN.INFO["db"]["rc"]))
						self.lblAGBHeaderROMChecksumResult.setStyleSheet("QLabel { color: red; }")
						self.lblStatus4a.setText("Done.")
						msg = "The ROM backup is complete, but the checksum doesn’t match the known database entry."
						if self.CONN.INFO["loop_detected"] is not False:
							msg += "\n\nA data loop was detected in the ROM backup at position 0x{:X} ({:s}). This may indicate a bad dump or overdump.".format(self.CONN.INFO["loop_detected"], Util.formatFileSize(size=self.CONN.INFO["loop_detected"], asInt=True))
						else:
							msg += " This may indicate a bad dump, however this can be normal for some reproduction cartridges, unlicensed games, prototypes, patched games and intentional overdumps."
						msgbox.setText(msg + msg_te)
						msgbox.setIcon(QtWidgets.QMessageBox.Warning)
						msgbox.exec()
				else:
					self.lblAGBHeaderROMChecksumResult.setText("0x{:06X}".format(self.CONN.INFO["file_crc32"]))
					self.lblAGBHeaderROMChecksumResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
					self.lblStatus4a.setText("Done!")
					msg = "The ROM backup is complete! As there is no known checksum for this ROM in the database, verification was skipped."
					if self.CONN.INFO["loop_detected"] is not False:
						msg += "\n\nNOTE: A data loop was detected in the ROM backup at position 0x{:X} ({:s}). This may indicate a bad dump or overdump.".format(self.CONN.INFO["loop_detected"], Util.formatFileSize(size=self.CONN.INFO["loop_detected"], asInt=True))
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
						print("ERROR: {:s}".format(str(e)))
				self.OpenPath(dumpinfo_file)
			elif msgbox.clickedButton() == button_open_dir:
				self.OpenPath(os.path.split(dumpinfo_file)[0])
		
		elif self.CONN.INFO["last_action"] == 2: # Backup RAM
			self.lblStatus4a.setText("Done!")
			self.CONN.INFO["last_action"] = 0

			dontShowAgainCameraSavePopup = str(self.SETTINGS.value("SkipCameraSavePopup", default="disabled")).lower() == "enabled"
			if not dontShowAgainCameraSavePopup:
				if self.CONN.GetMode() == "DMG" and self.CONN.INFO["mapper_raw"] == 252:
					# Pocket Camera
					if self.CONN.INFO["transferred"] == 0x20000 or (self.CONN.INFO["transferred"] == 0x100000 and "Unlicensed Photo!" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]):
						cbCameraSavePopup = QtWidgets.QCheckBox("Don’t show this message again", checked=dontShowAgain)
						msgboxCameraPopup = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="Would you like to load your save data with the GB Camera Viewer now?")
						msgboxCameraPopup.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
						msgboxCameraPopup.setDefaultButton(QtWidgets.QMessageBox.Yes)
						msgboxCameraPopup.setCheckBox(cbCameraSavePopup)
						answer = msgboxCameraPopup.exec()
						dontShowAgainCameraSavePopup = cbCameraSavePopup.isChecked()
						if dontShowAgainCameraSavePopup: self.SETTINGS.setValue("SkipCameraSavePopup", "enabled")
						if answer == QtWidgets.QMessageBox.Yes:
							self.CAMWIN = None
							self.CAMWIN = PocketCameraWindow(self, icon=self.windowIcon(), file=self.CONN.INFO["last_path"], config_path=Util.CONFIG_PATH, app_path=Util.APP_PATH)
							self.CAMWIN.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
							self.CAMWIN.setModal(True)
							self.CAMWIN.run()
							return
			
			if "last_path" in self.CONN.INFO:
				button_open_dir = msgbox.addButton("  Open Fol&der  ", QtWidgets.QMessageBox.ActionRole)
			msgbox.setText("The save data backup is complete!" + msg_te)
			msgbox.exec()
			if "last_path" in self.CONN.INFO and msgbox.clickedButton() == button_open_dir:
				self.OpenPath(os.path.split(self.CONN.INFO["last_path"])[0])
		
		elif self.CONN.INFO["last_action"] == 3: # Restore RAM
			self.lblStatus4a.setText("Done!")
			self.CONN.INFO["last_action"] = 0
			if "save_erase" in self.CONN.INFO and self.CONN.INFO["save_erase"]:
				msg_text = "The save data was erased."
				del(self.CONN.INFO["save_erase"])
			elif "verified" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["verified"] == True:
				msg_text = "The save data was written and verified successfully!"
			else:
				msg_text = "Save data writing complete!"
			msgbox.setText(msg_text + msg_te)
			msgbox.exec()
		
		elif self.CONN.INFO["last_action"] == 4: # Flash ROM
			if "broken_sectors" in self.CONN.INFO:
				s = ""
				sc = 0
				for sector in self.CONN.INFO["broken_sectors"]:
					sc += 1
					if sc > 10:
						s += "and others  "
						break
					s += "0x{:X}~0x{:X}, ".format(sector[0], sector[0]+sector[1]-1)
				msg_v = "The ROM was written completely, but verification of written data failed in the following sector(s): {:s}.".format(s[:-2])
				if "verify_error_params" in self.CONN.INFO:
					if self.CONN.GetMode() == "DMG":
						cart_types = self.CONN.GetSupportedCartridgesDMG()[0]
					elif self.CONN.GetMode() == "AGB":
						cart_types = self.CONN.GetSupportedCartridgesAGB()[0]
					cart_type_str = " ({:s})".format(cart_types[self.CONN.INFO["dump_info"]["cart_type"]])
					msg_v += "\n\nTips:\n- Clean cartridge contacts\n- Check soldering if it’s a DIY cartridge\n- Avoid passive USB hubs and try different USB ports/cables\n- Check cartridge type selection{:s}\n- Check cartridge ROM storage size (at least {:s} is required)".format(cart_type_str, Util.formatFileSize(size=self.CONN.INFO["verify_error_params"]["rom_size"]))
					if "mapper_selection_type" in self.CONN.INFO["verify_error_params"]:
						if self.CONN.INFO["verify_error_params"]["mapper_selection_type"] == 1: # manual
							msg_v += "\n- Check mapper type used: {:s} (manual selection)".format(self.CONN.INFO["verify_error_params"]["mapper_name"])
						elif self.CONN.INFO["verify_error_params"]["mapper_selection_type"] == 2: # forced by cart type
							msg_v += "\n- Check mapper type used: {:s} (forced by selected cartridge type)".format(self.CONN.INFO["verify_error_params"]["mapper_name"])
						if self.CONN.INFO["verify_error_params"]["rom_size"] > self.CONN.INFO["verify_error_params"]["mapper_max_size"]:
							msg_v += "\n- Check mapper type ROM size limit: likely up to {:s}".format(Util.formatFileSize(size=self.CONN.INFO["verify_error_params"]["mapper_max_size"]))
				msg_v += "\n\nDo you want to try and write the sectors again that failed verification?"
				
				answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), msg_v, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
				if answer == QtWidgets.QMessageBox.Yes:
					args = self.STATUS["args"]
					args.update({"flash_sectors":self.CONN.INFO["broken_sectors"]})
					self.CONN.FlashROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
					return
			
			self.CONN.INFO["last_action"] = 0
			self.lblStatus4a.setText("Done!")
			if "verified" in self.PROGRESS.PROGRESS and self.PROGRESS.PROGRESS["verified"] == True:
				msg = "The ROM was written and verified successfully!"
			else:
				msg = "ROM writing complete!"

			msgbox.setText(msg + msg_te)
			msgbox.exec()
			
			if self.CONN.GetMode() == "AGB" and "Batteryless SRAM" in Util.AGB_Header_Save_Types[self.cmbAGBSaveTypeResult.currentIndex()]:
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
			self.lblStatus4a.setText("Ready.")
			self.CONN.INFO["last_action"] = 0
			self.FinishDetectCartridge(self.CONN.INFO["detect_cart"])

		else:
			self.lblStatus4a.setText("Ready.")
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
				mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
			self.cmbDMGHeaderMapperResult.setCurrentIndex(Util.ConvertMapperToMapperType(mbc)[2])
	
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
					for i in range(0, len(Util.DMG_Header_ROM_Sizes_Flasher_Map)):
						if cart_types[1][index]["flash_size"] == (Util.DMG_Header_ROM_Sizes_Flasher_Map[i]):
							self.cmbDMGHeaderROMSizeResult.setCurrentIndex(i)
				self.STATUS["cart_type"] = cart_types[1][index]
				self.SetDMGMapperResult(cart_types[1][index])
		
		elif self.CONN.GetMode() == "AGB":
			cart_types = self.CONN.GetSupportedCartridgesAGB()
			if cart_types[1][index] == "RETAIL": # special keyword
				pass
			else:
				if "flash_size" in cart_types[1][index] and cart_types[1][index]["flash_size"] in Util.AGB_Header_ROM_Sizes_Map:
					self.cmbAGBHeaderROMSizeResult.setCurrentIndex(Util.AGB_Header_ROM_Sizes_Map.index(cart_types[1][index]["flash_size"]))
				self.STATUS["cart_type"] = cart_types[1][index]
	
	def CheckHeader(self):
		data = self.CONN.INFO["dump_info"]["header"]
		if not (self.CONN.GetMode() == "DMG" and data["mapper_raw"] in (0x203, 0x204, 0x205)) and not data['logo_correct'] and not data["header_checksum_correct"] and data['empty'] == False:
			msg = "ROM header checksum and boot logo checks failed. Please ensure that the cartridge contacts are clean.\n\nDo you still want to continue?"
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(APPNAME, VERSION), msg, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
			if answer == QtWidgets.QMessageBox.No: return False
		return True
	
	def BackupROM(self):
		if not self.CheckDeviceAlive(): return
		if not self.CheckHeader(): return
		
		mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
		
		rom_size = 0
		cart_type = 0
		path = Util.GenerateFileName(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=self.SETTINGS)
		if self.CONN.GetMode() == "DMG":
			setting_name = "LastDirRomDMG"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)

			path = QtWidgets.QFileDialog.getSaveFileName(self, "Backup ROM", last_dir + "/" + path, "Game Boy ROM File (*.gb *.sgb *.gbc);;All Files (*.*)")[0]
			cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()
			rom_size = Util.DMG_Header_ROM_Sizes_Flasher_Map[self.cmbDMGHeaderROMSizeResult.currentIndex()]
		
		elif self.CONN.GetMode() == "AGB":
			setting_name = "LastDirRomAGB"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)

			rom_size = Util.AGB_Header_ROM_Sizes_Map[self.cmbAGBHeaderROMSizeResult.currentIndex()]
			path = QtWidgets.QFileDialog.getSaveFileName(self, "Backup ROM", last_dir + "/" + path, "Game Boy Advance ROM File (*.gba *.srl);;All Files (*.*)")[0]
			cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()

		if (path == ""): return
		
		self.SETTINGS.setValue(setting_name, os.path.dirname(path))
		self.lblDMGHeaderROMChecksumResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
		self.lblAGBHeaderROMChecksumResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
		
		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.grpActions.setEnabled(False)
		self.mnuTools.setEnabled(False)
		self.mnuConfig.setEnabled(False)
		self.lblStatus4a.setText("Preparing...")
		qt_app.processEvents()
		args = { "path":path, "mbc":mbc, "rom_size":rom_size, "agb_rom_size":rom_size, "fast_read_mode":True, "cart_type":cart_type, "settings":self.SETTINGS }
		self.CONN.BackupROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
		self.grpStatus.setTitle("Transfer Status")
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
				text = "The following ISX file will now be converted to a regular ROM file and then written to the flash cartridge:\n" + dpath
			else:
				text = "The following ROM file will now be written to the flash cartridge:\n" + dpath
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(APPNAME, VERSION), text, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
			if answer == QtWidgets.QMessageBox.Cancel: return
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
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "A compatible flash cartridge profile could not be auto-detected.", QtWidgets.QMessageBox.Ok)
				return
			
			if self.CONN.GetMode() == "DMG":
				self.cmbDMGCartridgeTypeResult.setCurrentIndex(cart_type)
			elif self.CONN.GetMode() == "AGB":
				self.cmbAGBCartridgeTypeResult.setCurrentIndex(cart_type)
		
		if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

		if self.CONN.GetMode() == "DMG":
			self.SetDMGMapperResult(carts[cart_type])
			mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
		else:
			mbc = 0
		
		if (path == ""):
			if self.CONN.GetMode() == "DMG":
				path = QtWidgets.QFileDialog.getOpenFileName(self, "Write ROM", last_dir, "Game Boy ROM File (*.gb *.gbc *.sgb *.bin *.isx);;All Files (*.*)")[0]
			elif self.CONN.GetMode() == "AGB":
				path = QtWidgets.QFileDialog.getOpenFileName(self, "Write ROM", last_dir, "Game Boy Advance ROM File (*.gba *.srl *.bin);;All Files (*.*)")[0]
		
		if (path == ""):
			msg = "No ROM file was selected. Do you want to wipe the ROM contents of the cartridge instead?"
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(APPNAME, VERSION), msg, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
			if answer == QtWidgets.QMessageBox.No: return
			just_erase = True
			path = False
			buffer = bytearray()
		
		if not just_erase:
			self.SETTINGS.setValue(setting_name, os.path.dirname(path))
			if os.path.getsize(path) == 0:
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "The selected ROM file is empty.", QtWidgets.QMessageBox.Ok)
				return
			if os.path.getsize(path) > 0x20000000: # reject too large files to avoid exploding RAM
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "ROM files bigger than 512 MiB are not supported.", QtWidgets.QMessageBox.Ok)
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
					answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), msg, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
					if answer == QtWidgets.QMessageBox.Cancel: return
		
		override_voltage = False
		if 'voltage_variants' in carts[cart_type] and carts[cart_type]['voltage'] == 3.3:
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="Some cartridges of this type can be flashed at 3.3V, others may require 5V. Which mode should be used?")
			button_3_3v = msgbox.addButton("Use &3.3V", QtWidgets.QMessageBox.ActionRole)
			button_5v = msgbox.addButton("Use &5V", QtWidgets.QMessageBox.ActionRole)
			button_cancel = msgbox.addButton("&Cancel", QtWidgets.QMessageBox.RejectRole)
			msgbox.setDefaultButton(button_3_3v)
			msgbox.setEscapeButton(button_cancel)
			answer = msgbox.exec()
			if msgbox.clickedButton() == button_5v:
				override_voltage = 5
			elif msgbox.clickedButton() == button_cancel: return
		
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

				if not Util.compare_mbc(hdr["mapper_raw"], mbc):
					mbc1 = Util.get_mbc_name(mbc)
					mbc2 = Util.get_mbc_name(hdr["mapper_raw"])
					compatible_mbc = [ "None", "MBC2", "MBC3", "MBC30", "MBC5", "MBC7", "MAC-GBD", "G-MMC1", "HuC-1", "HuC-3", "Unlicensed MBCX Mapper" ]
					if (mbc2 == "None") or (mbc1 == "G-MMC1" and mbc2 == "MBC1") or (mbc2 == "G-MMC1" and mbc1 == "MBC1"):
						pass
					elif mbc2 != "None" and not (mbc1 in compatible_mbc and mbc2 in compatible_mbc):
						if "mbc" in carts[cart_type] and carts[cart_type]["mbc"] == "manual":
							msg_text = "The ROM file you selected uses a different mapper type than your current selection. What mapper should be used when writing the ROM?\n\nSelected mapper type: {:s}\nROM mapper type: {:s}".format(mbc1, mbc2)
							msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg_text)
							if mbc == 0: mbc1 = "MBC5"
							button_1 = msgbox.addButton("  {:s}  ".format(mbc1), QtWidgets.QMessageBox.ActionRole)
							button_2 = msgbox.addButton("  {:s}  ".format(mbc2), QtWidgets.QMessageBox.ActionRole)
							button_cancel = msgbox.addButton("&Cancel", QtWidgets.QMessageBox.RejectRole)
							msgbox.setDefaultButton(button_1)
							msgbox.setEscapeButton(button_cancel)
							msgbox.exec()
							if msgbox.clickedButton() == button_cancel:
								return
							elif msgbox.clickedButton() == button_2:
								mbc = hdr["mapper_raw"]
						else:
							if mbc1 == "None": mbc1 = "None/Unknown"
							msg_text = "Warning: The ROM file you selected uses a different mapper type than your cartridge type. The ROM file may be incompatible with your cartridge.\n\nSelected mapper type: {:s}\nROM mapper type: {:s}".format(mbc1, mbc2)
							answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), msg_text, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
							if answer == QtWidgets.QMessageBox.Cancel: return
			elif self.CONN.GetMode() == "AGB":
				hdr = RomFileAGB(buffer).GetHeader()
			
			if not hdr["logo_correct"] and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and mbc not in (0x203, 0x205))):
				msg_text = "Warning: The ROM file you selected will not boot on actual hardware due to invalid boot logo data."
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
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg_text)
					button_1 = msgbox.addButton("  &Fix and Continue  ", QtWidgets.QMessageBox.ActionRole)
					button_2 = msgbox.addButton("  Continue &without fixing  ", QtWidgets.QMessageBox.ActionRole)
					button_cancel = msgbox.addButton("&Cancel", QtWidgets.QMessageBox.RejectRole)
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
					Util.dprint("Couldn’t find boot logo file in configuration folder")
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg_text)
					msgbox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
					msgbox.setDefaultButton(QtWidgets.QMessageBox.Cancel)
					msgbox.setEscapeButton(QtWidgets.QMessageBox.Cancel)
					retval = msgbox.exec()
					if retval == QtWidgets.QMessageBox.Cancel:
						return
					else:
						pass
			
			if not hdr["header_checksum_correct"] and (self.CONN.GetMode() == "AGB" or (self.CONN.GetMode() == "DMG" and mbc not in (0x203, 0x205))):
				msg_text = "Warning: The ROM file you selected will not boot on actual hardware due to an invalid header checksum (expected 0x{:02X} instead of 0x{:02X}).".format(hdr["header_checksum_calc"], hdr["header_checksum"])
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg_text)
				button_1 = msgbox.addButton("  &Fix and Continue  ", QtWidgets.QMessageBox.ActionRole)
				button_2 = msgbox.addButton("  Continue &without fixing  ", QtWidgets.QMessageBox.ActionRole)
				button_cancel = msgbox.addButton("&Cancel", QtWidgets.QMessageBox.RejectRole)
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

		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.grpActions.setEnabled(False)
		self.mnuTools.setEnabled(False)
		self.mnuConfig.setEnabled(False)
		self.lblStatus4a.setText("Preparing...")
		qt_app.processEvents()
		if len(buffer) > 0x1000 or just_erase:
			if just_erase:
				prefer_chip_erase = True
				verify_write = False
			args = { "path":"", "buffer":buffer, "cart_type":cart_type, "override_voltage":override_voltage, "prefer_chip_erase":prefer_chip_erase, "fast_read_mode":True, "verify_write":verify_write, "fix_header":fix_header, "fix_bootlogo":fix_bootlogo, "mbc":mbc }
		else:
			args = { "path":path, "cart_type":cart_type, "override_voltage":override_voltage, "prefer_chip_erase":prefer_chip_erase, "fast_read_mode":True, "verify_write":verify_write, "fix_header":fix_header, "fix_bootlogo":fix_bootlogo, "mbc":mbc, "flash_offset":flash_offset, "force_wr_pullup":force_wr_pullup }
		args["compare_sectors"] = self.SETTINGS.value("CompareSectors", default="disabled").lower() == "enabled"
		self.CONN.FlashROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
		#self.CONN._FlashROM(args=args)
		self.grpStatus.setTitle("Transfer Status")
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
			(self.CONN.GetMode() == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < len(Util.AGB_Header_Save_Types) and "Batteryless SRAM" in Util.AGB_Header_Save_Types[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(self.CONN.GetMode() == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < len(Util.DMG_Header_RAM_Sizes) and "Batteryless SRAM" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]) or \
			(self.CONN.GetMode() == "DMG" and "Unlicensed Photo!" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]) \
		:
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="This feature is not supported in Legacy Mode.", standardButtons=QtWidgets.QMessageBox.Ok)
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
					QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "A compatible flash cartridge profile could not be auto-detected.", QtWidgets.QMessageBox.Ok)
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
			mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
			save_type = Util.DMG_Header_RAM_Sizes_Map[self.cmbDMGHeaderSaveTypeResult.currentIndex()]
			if save_type == 0:
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "No save type was selected.", QtWidgets.QMessageBox.Ok)
				return
			cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()
		
		elif self.CONN.GetMode() == "AGB":
			setting_name = "LastDirSaveDataAGB"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			mbc = 0
			save_type = self.cmbAGBSaveTypeResult.currentIndex()
			if save_type == 0:
				QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), "No save type was selected.", QtWidgets.QMessageBox.Ok)
				return
			cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()
		else:
			return
		
		if not self.CheckHeader(): return
		if dpath == "":
			path = Util.GenerateFileName(mode=self.CONN.GetMode(), header=self.CONN.INFO, settings=self.SETTINGS)
			path = os.path.splitext(path)[0]
			
			add_date_time = self.SETTINGS.value("SaveFileNameAddDateTime", default="disabled")
			if len(path) > 0 and add_date_time and add_date_time.lower() == "enabled":
				path += "_{:s}".format(datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"))

			path += ".sav"
			path = QtWidgets.QFileDialog.getSaveFileName(self, "Backup Save Data", last_dir + "/" + path, "Save Data File (*.sav *.srm *.fla *.eep);;All Files (*.*)")[0]
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
				msg = "A Real Time Clock cartridge was detected. Do you want the cartridge’s Real Time Clock register values also to be saved?"
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.Cancel: return
				rtc = (answer == QtWidgets.QMessageBox.Yes)

		bl_args = {}
		if \
			(self.CONN.GetMode() == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < len(Util.AGB_Header_Save_Types) and "Batteryless SRAM" in Util.AGB_Header_Save_Types[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(self.CONN.GetMode() == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < len(Util.DMG_Header_RAM_Sizes) and "Batteryless SRAM" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]) \
		:
			if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

			if "dump_info" in self.CONN.INFO and "batteryless_sram" in self.CONN.INFO["dump_info"]:
				detected = self.CONN.INFO["dump_info"]["batteryless_sram"]
			else:
				detected = False
			
			if self.CONN.GetMode() == "AGB":
				rom_size = Util.AGB_Header_ROM_Sizes_Map[self.cmbAGBHeaderROMSizeResult.currentIndex()]
			elif self.CONN.GetMode() == "DMG":
				rom_size = Util.DMG_Header_ROM_Sizes_Map[self.cmbDMGHeaderROMSizeResult.currentIndex()]
			bl_args = self.GetBLArgs(rom_size=rom_size, detected=detected)
			if bl_args is False: return
		
		self.SETTINGS.setValue(setting_name, os.path.dirname(path))

		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.grpActions.setEnabled(False)
		self.mnuTools.setEnabled(False)
		self.mnuConfig.setEnabled(False)
		self.lblStatus4a.setText("Preparing...")
		qt_app.processEvents()

		if len(bl_args) > 0:
			args = { "path":path, "mbc":mbc, "rom_size":bl_args["bl_size"], "agb_rom_size":bl_args["bl_size"], "fast_read_mode":True, "cart_type":cart_type }
			args.update(bl_args)
			self.CONN.BackupROM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
		else:
			args = { "path":path, "mbc":mbc, "save_type":save_type, "rtc":rtc, "verify_read":verify_read, "cart_type":cart_type }
			self.CONN.BackupRAM(fncSetProgress=self.PROGRESS.SetProgress, args=args)
		
		self.grpStatus.setTitle("Transfer Status")
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
			(mode == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < len(Util.AGB_Header_Save_Types) and "Batteryless SRAM" in Util.AGB_Header_Save_Types[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(mode == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < len(Util.DMG_Header_RAM_Sizes) and "Batteryless SRAM" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]) or \
			(mode == "DMG" and "Unlicensed Photo!" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]) \
		):
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="This feature is not supported in Legacy Mode.", standardButtons=QtWidgets.QMessageBox.Ok)
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
					QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "A compatible flash cartridge profile could not be auto-detected.", QtWidgets.QMessageBox.Ok)
					return
				if mode == "AGB":
					self.cmbAGBCartridgeTypeResult.setCurrentIndex(cart_type)
				elif mode == "DMG":
					self.cmbDMGCartridgeTypeResult.setCurrentIndex(cart_type)

		if mode == "DMG":
			setting_name = "LastDirSaveDataDMG"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
			save_type = Util.DMG_Header_RAM_Sizes_Map[self.cmbDMGHeaderSaveTypeResult.currentIndex()]
			if save_type == 0:
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "No save type was selected.", QtWidgets.QMessageBox.Ok)
				return
			cart_type = self.cmbDMGCartridgeTypeResult.currentIndex()

		elif mode == "AGB":
			setting_name = "LastDirSaveDataAGB"
			last_dir = self.SETTINGS.value(setting_name)
			if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
			mbc = 0
			save_type = self.cmbAGBSaveTypeResult.currentIndex()
			if save_type == 0:
				QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), "No save type was selected.", QtWidgets.QMessageBox.Ok)
				return
			cart_type = self.cmbAGBCartridgeTypeResult.currentIndex()
		else:
			return
		if not self.CheckHeader(): return
		
		filesize = 0
		if dpath != "":
			if not skip_warning:
				text = "The following save data file will now be written to the cartridge:\n" + dpath
				answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(APPNAME, VERSION), text, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
				if answer == QtWidgets.QMessageBox.Cancel: return
			path = dpath
			self.SETTINGS.setValue(setting_name, os.path.dirname(path))
		elif erase:
			if not skip_warning:
				answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), "The save data on your cartridge will now be erased.", QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
				if answer == QtWidgets.QMessageBox.Cancel: return
		elif test:
			path = None
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="This feature is not supported in Legacy Mode.", standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return
			elif not self.CONN.CanPowerCycleCart():
				if (mode == "AGB" and "SRAM" in self.cmbAGBSaveTypeResult.currentText()) or (mode == "DMG" and "SRAM" in self.cmbDMGHeaderSaveTypeResult.currentText()):
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="Your device does not support automatic power cycling, so some tests may be skipped.", standardButtons=QtWidgets.QMessageBox.Ok)
					msgbox.exec()
			
			if (mode == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < len(Util.AGB_Header_Save_Types) and "Batteryless SRAM" in Util.AGB_Header_Save_Types[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(mode == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < len(Util.DMG_Header_RAM_Sizes) and "Batteryless SRAM" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]) or \
			(mode == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < len(Util.DMG_Header_RAM_Sizes) and "Unlicensed Photo!" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]) or \
			("8M DACS" in Util.AGB_Header_Save_Types[self.cmbAGBSaveTypeResult.currentIndex()]) or \
			(mode == "AGB" and "ereader" in self.CONN.INFO and self.CONN.INFO["ereader"] is True) or \
			(mode == "DMG" and "256M Multi Cart" in self.cmbDMGHeaderMapperResult.currentText() and not self.CONN.CanPowerCycleCart()):
				QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(APPNAME, VERSION), "Stress test is not supported for this save type.", QtWidgets.QMessageBox.Ok)
				return
			answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(APPNAME, VERSION), "The cartridge’s save chip will be tested for potential problems as follows:\n- Read the same data multiple times\n- Writing and reading different test patterns\n\nPlease ensure the cartridge pins are freshly cleaned and the save data is backed up before proceeding.", QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
			if answer == QtWidgets.QMessageBox.Cancel: return
		else:
			if path == "":
				path = Util.GenerateFileName(mode=mode, header=self.CONN.INFO, settings=self.SETTINGS)
				path = os.path.splitext(path)[0]
				path += ".sav"
			path = QtWidgets.QFileDialog.getOpenFileName(self, "Restore Save Data", last_dir + "/" + path, "Save Data File (*.sav *.srm *.fla *.eep);;All Files (*.*)")[0]
			if not path == "": self.SETTINGS.setValue(setting_name, os.path.dirname(path))
			if (path == ""): return
		
		if not erase and not test and len(path) > 0:
			filesize = os.path.getsize(path)
			if filesize == 0 or filesize > 0x200000: # reject too large files to avoid exploding RAM
				QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "The size of this file is not supported.", QtWidgets.QMessageBox.Ok)
				return
		
		buffer = None
		if mode == "AGB" and "ereader" in self.CONN.INFO and self.CONN.INFO["ereader"] is True:
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="This cartridge is not supported in Legacy Mode.", standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="")
			button_keep = msgbox.addButton("  &Keep existing calibration data  ", QtWidgets.QMessageBox.ActionRole)
			self.CONN.ReadInfo()
			cart_name = "e-Reader"
			if self.CONN.INFO["db"] is not None:
				cart_name = self.CONN.INFO["db"]["gn"]
			if "ereader_calibration" in self.CONN.INFO:
				if erase:
					buffer = bytearray([0xFF] * 0x20000)
					msg_text = "This {:s} cartridge currently has calibration data in place. It is strongly recommended to keep the existing calibration data.\n\nHow do you want to proceed?".format(cart_name)
					button_overwrite = msgbox.addButton("  &Erase everything  ", QtWidgets.QMessageBox.ActionRole)
				else:
					with open(path, "rb") as f: buffer = bytearray(f.read())
					msg_text = "This {:s} cartridge currently has calibration data in place that is different from this save file’s data. It is strongly recommended to keep the existing calibration data unless you actually need to restore it from a previous backup.\n\nWould you like to keep the existing calibration data, or overwrite it with data from the file you selected?".format(cart_name)
					button_overwrite = msgbox.addButton("  &Restore from save data  ", QtWidgets.QMessageBox.ActionRole)
				button_cancel = msgbox.addButton("&Cancel", QtWidgets.QMessageBox.RejectRole)
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
				msg_text = "Warning: This {:s} cartridge may currently have calibration data in place. Erasing or overwriting this data may render the “Scan Card” feature unusable. It is strongly recommended to create a backup of the original save data first and store it in a safe place. That way the calibration data can be restored later.\n\nDo you still want to continue?".format(cart_name)
				answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), msg_text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
				if answer == QtWidgets.QMessageBox.No: return
		
		elif mode == "DMG" and self.CONN.INFO["dump_info"]["header"]["mapper_raw"] == 0xFC:
			if self.CONN.GetFWBuildDate() == "": # Legacy Mode
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="This cartridge is not supported in Legacy Mode.", standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="")
			button_keep = msgbox.addButton("  &Keep existing calibration data  ", QtWidgets.QMessageBox.ActionRole)
			if "Unlicensed Photo!" not in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]:
				button_reset = msgbox.addButton("  &Force recalibration  ", QtWidgets.QMessageBox.ActionRole)
			else:
				button_reset = None
			self.CONN.ReadInfo()
			cart_name = "Game Boy Camera"
			if self.CONN.INFO["db"] is not None:
				cart_name = self.CONN.INFO["db"]["gn"]
			if not test:
				if "gbcamera_calibration1" in self.CONN.INFO:
					if erase:
						buffer = bytearray([0x00] * 0x20000)
						if "Unlicensed Photo!" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]:
							buffer += bytearray([0xFF] * 0xE0000)
						msg_text = "This {:s} cartridge currently has calibration data in place.\n\nHow would you like to proceed?".format(cart_name)
						button_overwrite = msgbox.addButton("  &Erase everything  ", QtWidgets.QMessageBox.ActionRole)
					else:
						with open(path, "rb") as f: buffer = bytearray(f.read())
						msg_text = "This {:s} cartridge currently has calibration data in place that is different from this save file’s data.\n\nHow would you like to proceed?".format(cart_name)
						button_overwrite = msgbox.addButton("  &Restore from save data  ", QtWidgets.QMessageBox.ActionRole)
					button_cancel = msgbox.addButton("&Cancel", QtWidgets.QMessageBox.RejectRole)
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
					msg_text = "Warning: This {:s} cartridge may currently have calibration data in place. It is recommended to create a backup of the original save data first and store it in a safe place. That way the calibration data can be restored later.\n\nDo you still want to continue?".format(cart_name)
					answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), msg_text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
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
			elif erase or Util.save_size_includes_rtc(mode=mode, mbc=mbc, save_size=filesize, save_type=save_type):
				msg = "A Real Time Clock cartridge was detected. Do you want the Real Time Clock register values to be written as well?"
				cb = QtWidgets.QCheckBox("&Adjust RTC", checked=True)
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Cancel)
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
			self.lblStatus4a.setText("Preparing...")
			self.grpStatus.setTitle("Transfer Status")
			self.lblStatus1aResult.setText("–")
			self.lblStatus2aResult.setText("–")
			self.lblStatus3aResult.setText("–")
			self.lblStatus4aResult.setText("")
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

			if Util.get_mbc_name(mbc) == "MBC2":
				for j in range(0, len(test_patterns)):
					for i in range(0, len(test_patterns[j])):
						test_patterns[j][i] = test_patterns[j][i] & 0x0F
			
			test_patterns_names = [
				"reading twice",
				"writing random values",
				"writing 00, 00, 00, 00",
				"writing 55, AA, AA, 55",
				"writing 00, FF, FF, 00",
				"writing FF, FF, FF, FF",
				"writing incrementing values",
				"writing decrementing values",
			]
			#if Util.DEBUG: test_patterns = [ test_patterns[0], test_patterns[1], test_patterns[4] ]
			
			time_start = time.time()
			test_ok = 0
			save1 = bytearray([0])
			save2 = bytearray([1])
			backup_fn = Util.CONFIG_PATH + "/backup_stress_test.bin"
			
			try:
				self.lblStatus4a.setText("Testing ({:s} 1/2)...".format(test_patterns_names[0]))
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
						self.lblStatus4a.setText("Waiting for power cycle ({:d})...".format(i))
						qt_app.processEvents()
						time.sleep(1)
						if "stresstest_running" not in self.STATUS: break
					self.CONN.CartPowerOn()
				else:
					time.sleep(1)
				self.lblStatus4a.setText("Testing ({:s} 2/2)...".format(test_patterns_names[0]))
				qt_app.processEvents()
				t = threading.Thread(target=lambda a: self.CONN.TransferData(args=a, signal=None), args=[args])
				t.start()
				while t.is_alive():
					qt_app.processEvents()
					time.sleep(0.02)
				t.join()
				save2 = self.CONN.INFO["data"]
			except KeyError:
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="An error occured. Please ensure you selected the correct save type.", standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				save1 = None
			
			stop = False
			if (save1 is not None and save1 != save2) and "stresstest_running" in self.STATUS:
				with open(Util.CONFIG_PATH + "/debug_stress_test_1.bin", "wb") as f: f.write(save1)
				with open(Util.CONFIG_PATH + "/debug_stress_test_2.bin", "wb") as f: f.write(save2)
				msg = "Test {:d} ({:s}) failed!\nNote: SRAM requires a working battery to retain save data.\n\nContinue anyway?".format(test_ok+1, test_patterns_names[test_ok])
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.No:
					stop = True
			
			if not stop and save1 is not None:
				with open(backup_fn, "wb") as f: f.write(save1)
				test_ok += 1
				for i in range(0, len(test_patterns)):
					if "stresstest_running" not in self.STATUS: break
					self.lblStatus4a.setText("Testing ({:s})...".format(test_patterns_names[i+1]))
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
				self.lblStatus4a.setText("Restoring original save data...")
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
			msg_te = "\n\nTotal time elapsed: {:s}".format(Util.formatProgressTime(time_elapsed, asFloat=True))

			self.SetProgressBars(min=0, max=100, value=100)
			self.lblStatus4a.setText("Done.")
			qt_app.processEvents()

			if "stresstest_running" in self.STATUS:
				if test_ok == len(test_patterns)+1:
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="All tests completed successfully!" + msg_te, standardButtons=QtWidgets.QMessageBox.Ok)
					msgbox.exec()
				else:
					try:
						if test_ok == 0:
							towrite = save1
							readback = save2
						with open(Util.CONFIG_PATH + "/debug_stress_test_1.bin", "wb") as f: f.write(towrite[:len(readback)])
						with open(Util.CONFIG_PATH + "/debug_stress_test_2.bin", "wb") as f: f.write(readback)
					except:
						pass
					if test_ok > 0:
						msg = "Test {:d} ({:s}) failed!".format(test_ok+1, test_patterns_names[test_ok])
						msg += msg_te
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=msg, standardButtons=QtWidgets.QMessageBox.Ok)
						msgbox.exec()
			else:
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="The stress test process was cancelled.", standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				
			self.grpDMGCartridgeInfo.setEnabled(True)
			self.grpAGBCartridgeInfo.setEnabled(True)
			self.grpActions.setEnabled(True)
			self.mnuTools.setEnabled(True)
			self.mnuConfig.setEnabled(True)
			self.btnCancel.setEnabled(False)

			if not self.CONN.IsConnected(): self.DisconnectDevice()

		else:
			bl_args = {}
			if \
				(mode == "AGB" and self.cmbAGBSaveTypeResult.currentIndex() < len(Util.AGB_Header_Save_Types) and "Batteryless SRAM" in Util.AGB_Header_Save_Types[self.cmbAGBSaveTypeResult.currentIndex()]) or \
				(mode == "DMG" and self.cmbDMGHeaderSaveTypeResult.currentIndex() < len(Util.DMG_Header_RAM_Sizes) and "Batteryless SRAM" in Util.DMG_Header_RAM_Sizes[self.cmbDMGHeaderSaveTypeResult.currentIndex()]) \
			:
				if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])

				if "dump_info" in self.CONN.INFO and "batteryless_sram" in self.CONN.INFO["dump_info"]:
					detected = self.CONN.INFO["dump_info"]["batteryless_sram"]
				else:
					detected = False
				bl_args = self.GetBLArgs(rom_size=Util.AGB_Header_ROM_Sizes_Map[self.cmbAGBHeaderROMSizeResult.currentIndex()], detected=detected)
				if bl_args is False: return

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
			self.lblStatus4a.setText("Preparing...")
			self.grpStatus.setTitle("Transfer Status")
			self.lblStatus1aResult.setText("–")
			self.lblStatus2aResult.setText("–")
			self.lblStatus3aResult.setText("–")
			self.lblStatus4aResult.setText("")
			qt_app.processEvents()

	def GetBLArgs(self, rom_size, detected=False):
		mode = self.CONN.GetMode()
		if mode == "AGB":
			locs = [ 0x3C0000, 0x7C0000, 0xFC0000, 0x1FC0000 ]
			lens = [ 0x2000, 0x8000, 0x10000, 0x20000 ]
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
				intro_msg = "In order to access Batteryless SRAM save data, its ROM location and size must be specified.\n\nThe previously detected parameters have been pre-selected. Please adjust if necessary, then click “OK” to continue."
			except:
				detected = False
		if detected is False:
			intro_msg = "In order to access Batteryless SRAM save data, its ROM location and size must be specified.\n\n"
			# if mode == "AGB":
			# 	max_size = self.cmbAGBHeaderROMSizeResult.currentText().replace(" ", " ")
			# elif mode == "DMG":
			# 	max_size = self.cmbDMGHeaderROMSizeResult.currentText().replace(" ", " ")
			intro_msg2 = "⚠️ The required parameters could not be auto-detected. Please enter the ROM location and size manually below. Note that wrong values can corrupt your game upon writing, so having a full ROM backup is recommended."

			if mode == "DMG":
				# Load database of observed configurations from various bootlegs
				preselect = {}
				if os.path.exists(Util.CONFIG_PATH + "/db_DMG_bl.json"):
					with open(Util.CONFIG_PATH + "/db_DMG_bl.json", "r") as f:
						try:
							preselect = json.loads(f.read())
						except Exception as e:
							print("ERROR: Couldn’t load the database of batteryless SRAM configurations.", e, sep="\n")

				try:
					if self.CONN.INFO["dump_info"]["header"]["game_title"] in list(preselect.keys()):
						loc_index = locs.index(preselect[self.CONN.INFO["dump_info"]["header"]["game_title"]][0])
						len_index = lens.index(preselect[self.CONN.INFO["dump_info"]["header"]["game_title"]][1])
						lay_index = preselect[self.CONN.INFO["dump_info"]["header"]["game_title"]][2]
						intro_msg2 = "The required parameters were pre-selected based on the ROM title “" + self.CONN.INFO["dump_info"]["header"]["game_title"] + "”. These may still be inaccurate, so you can adjust them below if necessary. Note that wrong values can corrupt your game when writing, so having a full " + max_size + " ROM backup is recommended."
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
			"title":"Batteryless SRAM Parameters",
			"intro":intro_msg.replace("\n", "<br>"),
			"params": [
				# ID, Type, Value(s), Default Index
				[ "loc", "cmb_e", "Location:", [ "0x{:X}".format(l) for l in locs ], loc_index ],
				[ "len", "cmb", "Size:", [ Util.formatFileSize(size=s, asInt=True) for s in lens ], len_index ],
			]
		}
		if mode == "DMG":
			dlg_args["params"].append(
				[ "layout", "cmb", "Layout:", [ "Continuous", "First half of ROM bank", "Second half of ROM bank" ], lay_index ]
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
		data = self.CONN.INFO
		if "dump_info" not in data: return
		if "has_rtc" not in data or data["has_rtc"] is not True: return
		if "rtc_dict" not in data or len(data["rtc_dict"]) == 0: return
		rtc_data = data["rtc_dict"]

		if self.CONN.GetMode() == "DMG":
			mbc = Util.get_mbc_name(Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex()))
			if mbc in ("MBC3", "MBC30", "Unlicensed MBCX Mapper"):
				dlg_args = {
					"title":"MBC3/MBC30 Real Time Clock Editor",
					"intro":"Enter the number of days, hours, minutes and seconds that passed since the RTC initially started.\n\nPlease note that all values are internal values. The game may use these only as a relative reference.",
					"params": [
						# ID, Type, Value(s), Default Index
						[ "rtc_d", "spb", "Days:", (0, 511), rtc_data["rtc_d"] ],
						[ "rtc_h", "spb", "Hours:", (0, 23), rtc_data["rtc_h"] ],
						[ "rtc_m", "spb", "Minutes:", (0, 59), rtc_data["rtc_m"] ],
						[ "rtc_s", "spb", "Seconds:", (0, 59), rtc_data["rtc_s"] ],
						[ "current", "chk", "Ignore above time values and use the current time instead", None, False ],
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
					mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
					args = { "mbc":mbc, "rtc_dict":rtc_dict }
				else:
					return False
			
			elif mbc in ("HuC-3"):
				dlg_args = {
					"title":"HuC-3 Real Time Clock Editor",
					"intro":"Enter the number of days since your last play, and the current time.\n\nPlease note that the day value is an internal value. The game may use it only as a relative reference.",
					"params": [
						# ID, Type, Value(s), Default Index
						[ "rtc_d", "spb", "Days:", (0, 4095), rtc_data["rtc_d"] ],
						[ "rtc_h", "spb", "Hours:", (0, 23), rtc_data["rtc_h"] ],
						[ "rtc_m", "spb", "Minutes:", (0, 59), rtc_data["rtc_m"] ],
						[ "current", "chk", "Ignore above time values and use the current time instead", None, False ],
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
					mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
					args = { "mbc":mbc, "rtc_dict":rtc_dict }
				else:
					return False

			elif mbc in ("TAMA5"):
				dlg_args = {
					"title":"TAMA5 Real Time Clock Editor",
					"intro":"Enter the date and time used in the game.\n\nPlease note that the day value is an internal value. The game may use it only as a relative reference.",
					"params": [
						# ID, Type, Value(s), Default Index
						[ "rtc_y", "spb", "Years passed:", (0, 80), rtc_data["rtc_y"] - 19 ], # 19–99
						[ "rtc_leap_year_state", "spb", "Years since last leap year:", (0, 3), rtc_data["rtc_leap_year_state"] ],
						[ "rtc_m", "spb", "Month:", (1, 12), rtc_data["rtc_m"] ],
						[ "rtc_d", "spb", "Day:", (1, 31), rtc_data["rtc_d"] ],
						[ "rtc_h", "spb", "Hours:", (0, 23), rtc_data["rtc_h"] ],
						[ "rtc_i", "spb", "Minutes:", (0, 59), rtc_data["rtc_i"] ],
						[ "rtc_s", "spb", "Seconds:", (0, 59), rtc_data["rtc_s"] ],
						[ "current", "chk", "Ignore above values and use the current date and time instead", None, False ],
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
					mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
					rtc_dict["rtc_y"] += 19
					rtc_dict["rtc_buffer"] = rtc_data["rtc_buffer"]
					args = { "mbc":mbc, "rtc_dict":rtc_dict }
				else:
					return False

		elif self.CONN.GetMode() == "AGB":
			dlg_args = {
				"title":"GBA Real Time Clock Editor",
				"intro":"Enter the date and time for the Real Time Clock.\n\nPlease note that all values are internal values. The game may use these only as a relative reference.",
				"params": [
					# ID, Type, Value(s), Default Index
					[ "rtc_y", "spb", "Year:", (2000, 2099), rtc_data["rtc_y"] + 2000 ],
					[ "rtc_m", "spb", "Month:", (1, 12), rtc_data["rtc_m"] ],
					[ "rtc_d", "spb", "Day:", (1, 31), rtc_data["rtc_d"] ],
					[ "rtc_h", "spb", "Hours:", (0, 23), rtc_data["rtc_h"] ],
					[ "rtc_i", "spb", "Minutes:", (0, 59), rtc_data["rtc_i"] ],
					[ "rtc_s", "spb", "Seconds:", (0, 59), rtc_data["rtc_s"] ],
					[ "rtc_w", "cmb", "Weekday:", list(calendar.day_name), rtc_data["rtc_w"] ],
					[ "current", "chk", "Ignore above values and use the current date and time instead", None, False ],
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
						"rtc_w":dt.weekday(),
						"rtc_h":dt.hour,
						"rtc_i":dt.minute,
						"rtc_s":dt.second,
					})
				rtc_dict["rtc_y"] -= 2000
				mbc = Util.ConvertMapperTypeToMapper(self.cmbDMGHeaderMapperResult.currentIndex())
				args = { "rtc_dict":rtc_dict }
			else:
				return False

		self.STATUS["args"] = args
		ret = self.CONN.WriteRTC(args=args)
		self.ReadCartridge(resetStatus=False)
		if ret:
			QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(APPNAME, VERSION), "The Real Time Clock register values have been updated.", QtWidgets.QMessageBox.Ok)
			return True
		else:
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "An error occured while updating the Real Time Clock register values.", QtWidgets.QMessageBox.Ok)
			return False

	def CheckDeviceAlive(self, setMode=False):
		if self.CONN is not None:
			mode = self.CONN.GetMode()
			if self.CONN.DEVICE is None:
				self.DisconnectDevice()
			else:
				if not self.CONN.IsConnected():
					self.DisconnectDevice()
					self.CONN = None
					self.DEVICES = {}
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="The connection to the device was lost!\n\nThis can be happen in one of the following cases:\n- The USB cable was unplugged or is faulty\n- The inserted cartridge may draw too much peak power (try re-connecting a few times or try hotswapping the cartridge after connecting)\n- The inserted cartrdige may induce a short circuit (check for bad soldering)\n\nDo you want to try and reconnect to the device?", standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
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
		if self.CONN.CanSetVoltageAutomatically(): # device can switch in software
			dontShowAgain = str(self.SETTINGS.value("SkipModeChangeWarning", default="disabled")).lower() == "enabled"
		elif self.CONN.CanSetVoltageManually(): # device has a physical switch
			voltageWarning = "\n\nImportant: Also make sure your device is set to the correct voltage!"
			dontShowAgain = False
		else: # no voltage switching supported
			dontShowAgain = False
		
		if not dontShowAgain and mode is not None:
			cb = QtWidgets.QCheckBox("Don’t show this message again", checked=False)
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="The mode will now be changed to " + {"DMG":"Game Boy", "AGB":"Game Boy Advance"}[setTo] + " mode. To be safe, cartridges should only be exchanged while they are not receiving power by the device." + voltageWarning, standardButtons=QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
			msgbox.setDefaultButton(QtWidgets.QMessageBox.Ok)
			if self.CONN.CanSetVoltageAutomatically(): msgbox.setCheckBox(cb)
			answer = msgbox.exec()
			dontShowAgain = cb.isChecked()
			if answer == QtWidgets.QMessageBox.Cancel:
				if mode == "DMG": self.optDMG.setChecked(True)
				if mode == "AGB": self.optAGB.setChecked(True)
				return False
			if dontShowAgain: self.SETTINGS.setValue("SkipModeChangeWarning", "enabled")
		
		if not self.CheckDeviceAlive(setMode=setTo): return
		
		try:
			if self.optDMG.isChecked() and (mode == "AGB" or mode == None):
				self.CONN.SetMode("DMG")
			elif self.optAGB.isChecked() and (mode == "DMG" or mode == None):
				self.CONN.SetMode("AGB")
		except (BrokenPipeError, SerialException):
			msg = "Failed to turn on the cartridge power.\n\nThe “Automatic cartridge power off” setting has therefore been disabled. Please re-connect the device and try again."
			self.mnuConfig.actions()[5].setChecked(False)
			self.SETTINGS.setValue("AutoPowerOff", "0")
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), msg, QtWidgets.QMessageBox.Ok)
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
		if resetStatus:
			self.btnHeaderRefresh.setEnabled(False)
			self.btnDetectCartridge.setEnabled(False)
			self.btnBackupROM.setEnabled(False)
			self.btnFlashROM.setEnabled(False)
			self.btnBackupRAM.setEnabled(False)
			self.btnRestoreRAM.setEnabled(False)
			self.lblStatus4a.setText("Reading cartridge data...")
			self.SetProgressBars(min=0, max=0, value=1)
			qt_app.processEvents()
		
		try:
			data = self.CONN.ReadInfo(setPinsAsInputs=True)
		except (BrokenPipeError, SerialException):
			self.LimitBaudRateGBxCartRW()
			self.DisconnectDevice()
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "The connection to the device was lost while trying to read the ROM header. This may happen if the inserted cartridge issues a short circuit or its peak power draw is too high.\n\nAs a potential workaround for the latter, you can try hotswapping the cartridge:\n1. Remove the cartridge from the device.\n2. Reconnect the device and select mode.\n3. Then insert the cartridge and click “{:s}”.".format(self.btnHeaderRefresh.text().replace("&", "")), QtWidgets.QMessageBox.Ok)
			return False
		
		if data == False or len(data) == 0:
			self.LimitBaudRateGBxCartRW()
			self.DisconnectDevice()
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "Invalid response from the device. Please re-connect the USB cable.", QtWidgets.QMessageBox.Ok)
			return False
		
		if self.CONN.CheckROMStable() is False and resetStatus:
			try:
				if data != bytearray(data[0] * len(data)):
					QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "The cartridge connection is unstable!\nPlease clean the cartridge pins, carefully realign the cartridge and then try again.", QtWidgets.QMessageBox.Ok)
			except:
				pass
		
		if self.CONN.GetMode() == "DMG":
			self.cmbDMGHeaderMapperResult.clear()
			self.cmbDMGHeaderMapperResult.addItems(list(Util.DMG_Mapper_Types.keys()))
			self.cmbDMGHeaderMapperResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
			self.cmbDMGCartridgeTypeResult.clear()
			self.cmbDMGCartridgeTypeResult.addItems(self.CONN.GetSupportedCartridgesDMG()[0])
			self.cmbDMGCartridgeTypeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
			if "flash_type" in data:
				self.cmbDMGCartridgeTypeResult.setCurrentIndex(data["flash_type"])
			self.cmbDMGHeaderROMSizeResult.clear()
			self.cmbDMGHeaderROMSizeResult.addItems(Util.DMG_Header_ROM_Sizes)
			self.cmbDMGHeaderROMSizeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
			self.cmbDMGHeaderSaveTypeResult.clear()
			self.cmbDMGHeaderSaveTypeResult.addItems(Util.DMG_Header_RAM_Sizes)
			self.cmbDMGHeaderSaveTypeResult.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
			
			self.lblDMGRomTitleResult.setText(data['game_title'])
			self.lblDMGGameCodeRevision.setText("Game Code and Revision:")
			self.lblDMGGameNameResult.setToolTip("")
			if data["db"] is not None:
				self.lblDMGGameCodeRevisionResult.setText("{:s}-{:s}".format(data["db"]["gc"], str(data["version"])))
				temp = data["db"]["gn"]
				self.lblDMGGameNameResult.setText(temp)
				while self.lblDMGGameNameResult.fontMetrics().boundingRect(self.lblDMGGameNameResult.text()).width() > 240:
					temp = temp[:-1]
					self.lblDMGGameNameResult.setText(temp + "…")
				if temp != data["db"]["gn"]:
					self.lblDMGGameNameResult.setToolTip(data["db"]["gn"])
			else:
				self.lblDMGGameNameResult.setText("(Not in database)")
				if len(data['game_code']) > 0:
					self.lblDMGGameCodeRevisionResult.setText("{:s}-{:s}".format(data["game_code"], str(data["version"])))
				else:
					self.lblDMGGameCodeRevision.setText("Revision:")
					self.lblDMGGameCodeRevisionResult.setText(str(data['version']))

			self.lblDMGHeaderRtcResult.setText(data["rtc_string"])
			if data["has_rtc"] is True and len(data["rtc_dict"]) > 0 and "rtc_valid" in data["rtc_dict"] and data["rtc_dict"]["rtc_valid"] is True:
				self.lblDMGHeaderRtcResult.setCursor(QtCore.Qt.PointingHandCursor)
				self.lblDMGHeaderRtcResult.setToolTip("Click here to edit the Real Time Clock register values")
			else:
				self.lblDMGHeaderRtcResult.setCursor(QtCore.Qt.ArrowCursor)
				self.lblDMGHeaderRtcResult.setToolTip("")
			
			if data['logo_correct'] and data['header_checksum_correct']:
				self.lblDMGHeaderBootlogoResult.setText("OK")
				self.lblDMGHeaderBootlogoResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
				if not os.path.exists(Util.CONFIG_PATH + "/bootlogo_dmg.bin"):
					with open(Util.CONFIG_PATH + "/bootlogo_dmg.bin", "wb") as f:
						f.write(data['raw'][0x104:0x134])
			else:
				self.lblDMGHeaderBootlogoResult.setText("Invalid")
				self.lblDMGHeaderBootlogoResult.setStyleSheet("QLabel { color: red; }")

			self.lblDMGHeaderROMChecksumResult.setText("0x{:04X}".format(data['rom_checksum']))
			self.lblDMGHeaderROMChecksumResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
			self.cmbDMGHeaderROMSizeResult.setCurrentIndex(data["rom_size_raw"])
			for i in range(0, len(Util.DMG_Header_RAM_Sizes_Map)):
				if data["ram_size_raw"] == Util.DMG_Header_RAM_Sizes_Map[i]:
					self.cmbDMGHeaderSaveTypeResult.setCurrentIndex(i)
			temp = Util.ConvertMapperToMapperType(data["mapper_raw"])
			mapper_type = temp[2]
			self.cmbDMGHeaderMapperResult.setCurrentIndex(mapper_type)

			if data['empty'] == True: # defaults
				if data['empty_nocart'] == True:
					self.lblDMGGameNameResult.setText("(No cartridge connected)")
				else:
					self.lblDMGGameNameResult.setText("(No ROM data detected)")
				self.lblDMGGameNameResult.setStyleSheet("QLabel { color: red; }")
				self.cmbDMGHeaderROMSizeResult.setCurrentIndex(0)
				self.cmbDMGHeaderSaveTypeResult.setCurrentIndex(0)
				self.cmbDMGHeaderMapperResult.setCurrentIndex(0)
			else:
				self.lblDMGGameNameResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
				
				if data['logo_correct'] and not self.CONN.IsSupportedMbc(data["mapper_raw"]) and resetStatus:
					QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), "This cartridge uses a mapper that may not be completely supported by {:s} using your {:s} device.".format(APPNAME, self.CONN.GetFullName()), QtWidgets.QMessageBox.Ok)
				if data['logo_correct'] and data['game_title'] in ("NP M-MENU MENU", "DMG MULTI MENU "):
					cart_types = self.CONN.GetSupportedCartridgesDMG()
					for i in range(0, len(cart_types[0])):
						if "dmg-mmsa-jpn" in cart_types[1][i]:
							self.cmbDMGCartridgeTypeResult.setCurrentIndex(i)
			
			if data["mapper_raw"] == 0x203: # Xploder GB
				self.lblDMGHeaderRtcResult.setText("")
				self.lblDMGHeaderBootlogoResult.setText("")
				self.lblDMGHeaderBootlogoResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
				self.lblDMGHeaderROMChecksumResult.setText("")
				self.lblDMGHeaderROMChecksumResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
			elif data["mapper_raw"] == 0x205: # Datel
				self.lblDMGHeaderRtcResult.setText("")
				self.lblDMGHeaderBootlogoResult.setText("")
				self.lblDMGHeaderBootlogoResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
				self.lblDMGGameCodeRevisionResult.setText("")
				self.lblDMGGameCodeRevisionResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
				self.lblDMGHeaderROMChecksumResult.setText("")
				self.lblDMGHeaderROMChecksumResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
			elif data["mapper_raw"] == 0x204: # Sachen
				self.lblDMGGameNameResult.setText(data["game_title"])
				self.lblDMGHeaderRtcResult.setText("")
				self.lblDMGRomTitleResult.setText("")
				self.lblDMGGameCodeRevisionResult.setText("")
				self.lblDMGHeaderBootlogoResult.setText("")
				self.lblDMGHeaderBootlogoResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
				if "logo_sachen" in data:
					data["logo_sachen"].putpalette([ 255, 255, 255, 128, 128, 128 ])
					try:
						self.lblDMGHeaderBootlogoResult.setPixmap(Util.bitmap2pixmap(data["logo_sachen"]))
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
						self.lblDMGHeaderBootlogoResult.setPixmap(Util.bitmap2pixmap(data["logo"]))
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

			self.lblAGBRomTitleResult.setText(data['game_title'])
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
					self.lblAGBHeaderGameCodeRevisionResult.setText("{:s}-{:s}".format(data['game_code'], str(data['version'])))
				else:
					self.lblAGBHeaderGameCodeRevisionResult.setText("")
				self.lblAGBGameNameResult.setText("(Not in database)")
			
			if data['logo_correct']:
				self.lblAGBHeaderBootlogoResult.setText("OK")
				self.lblAGBHeaderBootlogoResult.setStyleSheet(self.lblAGBRomTitleResult.styleSheet())
				if not os.path.exists(Util.CONFIG_PATH + "/bootlogo_agb.bin"):
					with open(Util.CONFIG_PATH + "/bootlogo_agb.bin", "wb") as f:
						f.write(data['raw'][0x04:0xA0])
			else:
				self.lblAGBHeaderBootlogoResult.setText("Invalid")
				self.lblAGBHeaderBootlogoResult.setStyleSheet("QLabel { color: red; }")

			self.lblAGBGpioRtcResult.setText(data["rtc_string"])
			if data["has_rtc"] is True and len(data["rtc_dict"]) > 0 and "rtc_valid" in data["rtc_dict"] and data["rtc_dict"]["rtc_valid"] is True:
				self.lblAGBGpioRtcResult.setCursor(QtCore.Qt.PointingHandCursor)
				self.lblAGBGpioRtcResult.setToolTip("Click here to edit the Real Time Clock register values")
			else:
				self.lblAGBGpioRtcResult.setCursor(QtCore.Qt.ArrowCursor)
				self.lblAGBGpioRtcResult.setToolTip("")
			
			if data['header_checksum_correct']:
				self.lblAGBHeaderChecksumResult.setText("Valid (0x{:02X})".format(data['header_checksum']))
				self.lblAGBHeaderChecksumResult.setStyleSheet(self.lblAGBRomTitleResult.styleSheet())
			else:
				self.lblAGBHeaderChecksumResult.setText("Invalid (0x{:02X})".format(data['header_checksum']))
				self.lblAGBHeaderChecksumResult.setStyleSheet("QLabel { color: red; }")
			
			self.lblAGBHeaderROMChecksumResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
			self.lblAGBHeaderROMChecksumResult.setText("Not available")
			
			if data["db"] is None:
				self.lblAGBHeaderROMChecksumResult.setText("(Not in database)")
			if data["db"] != None:
				self.cmbAGBHeaderROMSizeResult.setCurrentIndex(Util.AGB_Header_ROM_Sizes_Map.index(data["db"]['rs']))
				if data["rom_size_calc"] < 0x400000:
					self.lblAGBHeaderROMChecksumResult.setText("In database (0x{:06X})".format(data["db"]['rc']))
			elif data["rom_size"] != 0:
				if not data["rom_size"] in Util.AGB_Header_ROM_Sizes_Map:
					data["rom_size"] = 0x2000000
				self.cmbAGBHeaderROMSizeResult.setCurrentIndex(Util.AGB_Header_ROM_Sizes_Map.index(data["rom_size"]))
			else:
				self.cmbAGBHeaderROMSizeResult.setCurrentIndex(0)
			
			if data["save_type"] == None:
				self.cmbAGBSaveTypeResult.setCurrentIndex(0)
				if data["db"] != None:
					if data["db"]['st'] < len(Util.AGB_Header_Save_Types):
						self.cmbAGBSaveTypeResult.setCurrentIndex(data["db"]['st'])

			if data['empty'] == True: # defaults
				if data['empty_nocart'] == True:
					self.lblAGBGameNameResult.setText("(No cartridge connected)")
				else:
					self.lblAGBGameNameResult.setText("(No ROM data detected)")
				self.lblAGBGameNameResult.setStyleSheet("QLabel { color: red; }")
				self.cmbAGBSaveTypeResult.setCurrentIndex(0)
			else:
				self.lblAGBGameNameResult.setStyleSheet(self.lblDMGRomTitleResult.styleSheet())
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
				QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), "This cartridge uses a Memory Bank Controller that may not be completely supported by the firmware of the {:s} device. Please check for firmware updates in the Tools menu or the maker’s website.".format(self.CONN.GetFullName()), QtWidgets.QMessageBox.Ok)
			
			if "logo" in data:
				if data['logo_correct']:
					rgb = ( self.TEXT_COLOR[0], self.TEXT_COLOR[1], self.TEXT_COLOR[2] ) # GUI font color
					rgb = tuple(min(255, int(c + (127.5 - c) * 0.25)) if c < 127.5 else max(0, int(c - (c - 127.5) * 0.25)) for c in rgb)
					data["logo"].putpalette([ 255, 255, 255, rgb[0], rgb[1], rgb[2] ])
				else:
					data["logo"].putpalette([ 255, 255, 255, 251, 0, 24 ])
				try:
					self.lblAGBHeaderBootlogoResult.setPixmap(Util.bitmap2pixmap(data["logo"]))
				except:
					pass

		if resetStatus:
			self.lblStatus1aResult.setText("–")
			self.lblStatus2aResult.setText("–")
			self.lblStatus3aResult.setText("–")
			self.lblStatus4a.setText("Ready.")
			self.grpStatus.setTitle("Transfer Status")
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
			QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), "This cartridge may be protected against reading or writing a ROM. If you don’t want to risk this cartridge to render itself unusable, please do not try to write a new ROM to it.", QtWidgets.QMessageBox.Ok)
	
	def LimitBaudRateGBxCartRW(self):
		if self.CONN.GetName() == "GBxCart RW" and str(self.SETTINGS.value("AutoLimitBaudRate", default="enabled")).lower() == "enabled" and str(self.SETTINGS.value("LimitBaudRate", default="disabled")).lower() == "disabled":
			Util.dprint("Setting “" + self.mnuConfig.actions()[5].text().replace("&", "") + "” to “enabled”")
			self.mnuConfig.actions()[5].setChecked(True)
			self.SETTINGS.setValue("LimitBaudRate", "enabled")
			Util.dprint("Setting “" + self.mnuConfig.actions()[8].text().replace("&", "") + "” to “0”")
			self.mnuConfig.actions()[5].setChecked(False)
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
			answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), "The cartridge connection is unstable!\nPlease clean the cartridge pins, carefully realign the cartridge for best results.\n\nContinue anyway?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
			if answer == QtWidgets.QMessageBox.No: return
		self.btnHeaderRefresh.setEnabled(False)
		self.btnDetectCartridge.setEnabled(False)
		self.btnBackupROM.setEnabled(False)
		self.btnFlashROM.setEnabled(False)
		self.btnBackupRAM.setEnabled(False)
		self.btnRestoreRAM.setEnabled(False)
		self.grpStatus.setTitle("Transfer Status")
		self.lblStatus1aResult.setText("–")
		self.lblStatus2aResult.setText("–")
		self.lblStatus3aResult.setText("–")
		self.lblStatus4aResult.setText("")
		# self.lblStatus4a.setText("Analyzing Cartridge...")
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
		if ret is False:
			QtWidgets.QMessageBox.critical(self, "{:s} {:s}".format(APPNAME, VERSION), "An error occured while trying to analyze the cartridge and you may need to physically reconnect the device.\n\nThis cartridge may not be auto-detectable, please select the cartridge type manually.", QtWidgets.QMessageBox.Ok)
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
							self.cmbDMGHeaderSaveTypeResult.setCurrentIndex(Util.DMG_Header_RAM_Sizes_Map.index(save_type))
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
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text="An unknown error occured. Please try again.\n\n" + str(e), standardButtons=QtWidgets.QMessageBox.Ok)
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
							msg_cart_type += "- {:s}*<br>".format(supp_cart_types[0][cart_types[i]])
							msg_cart_type_used = supp_cart_types[0][cart_types[i]]
						else:
							msg_cart_type += "- {:s}<br>".format(supp_cart_types[0][cart_types[i]])
					msg_cart_type = msg_cart_type[:-4]
			
			except:
				pass
			
			# Messages
			# Header
			msg_header_s = "<b>ROM Title:</b> {:s}<br>".format(header["game_title"])
			
			# Save Type
			msg_save_type_s = ""
			temp = ""
			if not self.STATUS["can_skip_message"] and save_type is not False and save_type is not None:
				if save_chip is not None:
					if save_type == 5 and "Unlicensed" in save_chip and "data" in self.CONN.INFO and self.CONN.INFO["data"] == bytearray([0xFF] * len(self.CONN.INFO["data"])):
						temp = "{:s} or {:s} ({:s})".format(Util.AGB_Header_Save_Types[4], Util.AGB_Header_Save_Types[5], save_chip)
					else:
						temp = "{:s} ({:s})".format(Util.AGB_Header_Save_Types[save_type], save_chip)
				else:
					if self.CONN.GetMode() == "DMG":
						try:
							temp = "{:s}".format(Util.DMG_Header_RAM_Sizes[Util.DMG_Header_RAM_Sizes_Map.index(save_type)])
						except:
							temp = "Unknown"
					elif self.CONN.GetMode() == "AGB":
						temp = "{:s}".format(Util.AGB_Header_Save_Types[save_type])
						try:
							if "Batteryless SRAM" in Util.AGB_Header_Save_Types[save_type]:
								if save_size == 0:
									temp += " (unknown size)<br><b>Batteryless SRAM Location:</b> 0x{:X}–0x{:X} ({:s})".format(header["batteryless_sram"]["bl_offset"], header["batteryless_sram"]["bl_offset"]+header["batteryless_sram"]["bl_size"]-1, Util.formatFileSize(size=header["batteryless_sram"]["bl_size"], asInt=True))
								elif save_size == header["batteryless_sram"]["bl_size"]:
									temp += " ({:s})<br><b>Batteryless SRAM Location:</b> 0x{:X}–0x{:X} ({:s})".format(Util.formatFileSize(size=save_size, asInt=True), header["batteryless_sram"]["bl_offset"], header["batteryless_sram"]["bl_offset"]+header["batteryless_sram"]["bl_size"]-1, Util.formatFileSize(size=header["batteryless_sram"]["bl_size"], asInt=True))
								else:
									temp += " ({:s})<br><b>Batteryless SRAM Location:</b> 0x{:X}–0x{:X} ({:s})".format(Util.formatFileSize(size=save_size, asInt=True), header["batteryless_sram"]["bl_offset"], header["batteryless_sram"]["bl_offset"]+header["batteryless_sram"]["bl_size"]-1, Util.formatFileSize(size=header["batteryless_sram"]["bl_size"], asInt=True))
						except:
							pass

				if save_type == 0:
					if "Unknown" in save_chip:
						msg_save_type_s = "<b>Save Type:</b> {:s}<br>".format(save_chip)
					else:
						msg_save_type_s = "<b>Save Type:</b> None or unknown (no save data detected)<br>"
				else:
					if sram_unstable and "SRAM" in temp:
						msg_save_type_s = "<b>Save Type:</b> {:s} <span style=\"color: red;\">(not stable or not battery-backed)</span><br>".format(temp)
					else:
						msg_save_type_s = "<b>Save Type:</b> {:s}<br>".format(temp)
			
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
					msg_cart_type_s = "<b>Cartridge Type:</b> {:s} (or compatible)<br>".format(msg_cart_type_used)
				else:
					msg_cart_type_s = "<b>Cartridge Type:</b> {:s}<br>".format(msg_cart_type_used)
				msg_cart_type_s_detail = "<b>Compatible Cartridge Types:</b><br>{:s}<br>".format(msg_cart_type)
				found_supported = True

				if detected_size > 0:
					size = detected_size
					msg_flash_size_s = "<b>ROM Size:</b> {:s}<br>".format(Util.formatFileSize(size=size, asInt=True))
				elif "flash_size" in supp_cart_types[1][cart_type_id]:
					size = supp_cart_types[1][cart_type_id]["flash_size"]
					msg_flash_size_s = "<b>ROM Size:</b> {:s}<br>".format(Util.formatFileSize(size=size, asInt=True))
				
				if self.CONN.GetMode() == "DMG":
					if "mbc" in supp_cart_types[1][cart_type_id]:
						if supp_cart_types[1][cart_type_id]["mbc"] == "manual":
							msg_flash_mapper_s = "<b>Mapper Type:</b> <i>Manual selection</i><br>"
						elif supp_cart_types[1][cart_type_id]["mbc"] in Util.DMG_Header_Mapper.keys():
							msg_flash_mapper_s = "<b>Mapper Type:</b> {:s}<br>".format(Util.DMG_Header_Mapper[supp_cart_types[1][cart_type_id]["mbc"]])
					else:
						msg_flash_mapper_s = "<b>Mapper Type:</b> Default (MBC5)<br>"
			
			else:
				if (len(flash_id.split("\n")) > 2) and ((self.CONN.GetMode() == "DMG") or ("dacs_8m" in header and header["dacs_8m"] is not True)):
					msg_cart_type_s = "<b>Cartridge Type:</b> Unknown flash cartridge"
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
					msg_cart_type_s += "<br>"
				else:
					msg_cart_type_s = "<b>Cartridge Type:</b> Generic ROM Cartridge (not rewritable or not auto-detectable)<br>"
					is_generic = True
			
			if (len(flash_id.split("\n")) > 2):
				if limitVoltage:
					msg_flash_id_s_limit = " (voltage limited)"
				else:
					msg_flash_id_s_limit = ""
				msg_flash_id_s = "<br><b>Flash ID Check{:s}:</b><pre style=\"font-size: 8pt; margin: 0;\">{:s}</pre>".format(msg_flash_id_s_limit, flash_id[:-1])
			if not is_generic:
				if cfi_s != "":
					msg_cfi_s = "<br><b>Common Flash Interface Data:</b><br>{:s}<br><br>".format(cfi_s.replace("\n", "<br>"))
				else:
					msg_cfi_s = "<br><b>Common Flash Interface Data:</b> Not available<br><br>"
			
			if msg_cart_type_s_detail == "": msg_cart_type_s_detail = msg_cart_type_s
			self.SetProgressBars(min=0, max=100, value=100)
			show_details = False
			
			msg_gbmem = ""
			if "gbmem_parsed" in header and header["gbmem_parsed"] is not None:
				msg_gbmem = "<br><b>NP GB-Memory Cartridge Data:</b><br>"
				if isinstance(header["gbmem_parsed"], list):
					msg_gbmem += "" \
						"- Write Timestamp: {timestamp:s}<br>" \
						"- Write Kiosk ID: {kiosk_id:s}<br>" \
						"- Number of Games: {num_games:d}<br>" \
						"- Write Counter: {write_count:d}<br>" \
						"- Cartridge ID: {cart_id:s}<br>" \
					.format(
						timestamp=header["gbmem_parsed"][0]["timestamp"].replace("\0", ""),
						kiosk_id=header["gbmem_parsed"][0]["kiosk_id"].replace("\0", ""),
						cart_id=header["gbmem_parsed"][0]["cart_id"].replace("\0", ""),
						write_count=header["gbmem_parsed"][0]["write_count"],
						num_games=header["gbmem_parsed"][0]["num_games"],
					)
					for i in range(1, len(header["gbmem_parsed"])):
						if header["gbmem_parsed"][i]["menu_index"] == 0xFF: continue
						if i == 1:
							msg_gbmem += "- Menu ROM: {:s}<br>".format(header["gbmem_parsed"][i]["title"].replace("\0", ""))
						else:
							msg_gbmem += "- Game {:d}: {:s}<br>".format(i - 1, header["gbmem_parsed"][i]["title"].replace("\0", ""))
				else:
					msg_gbmem += "" \
						"- Write Timestamp: {timestamp:s}<br>" \
						"- Write Kiosk ID: {kiosk_id:s}<br>" \
						"- Write Counter: {write_count:d}<br>" \
						"- Cartridge ID: {cart_id:s}<br>" \
						"- Game Title: {game_title:s}<br>" \
					.format(
						timestamp=header["gbmem_parsed"]["timestamp"].replace("\0", ""),
						kiosk_id=header["gbmem_parsed"]["kiosk_id"].replace("\0", ""),
						cart_id=header["gbmem_parsed"]["cart_id"].replace("\0", ""),
						write_count=header["gbmem_parsed"]["write_count"],
						game_title=header["gbmem_parsed"]["title"],
					)
			
			msg = "The following cartridge configuration was detected:<br><br>"
			if found_supported:
				dontShowAgain = str(self.SETTINGS.value("SkipAutodetectMessage", default="disabled")).lower() == "enabled"
				if not dontShowAgain or not self.STATUS["can_skip_message"]:
					temp = "{:s}{:s}{:s}{:s}{:s}{:s}".format(msg, msg_flash_size_s, msg_save_type_s, msg_flash_mapper_s, msg_cart_type_s, msg_gbmem)
					temp = temp[:-4]
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s} | {:s}".format(APPNAME, VERSION, self.CONN.GetFullNameLabel()), text=temp)
					msgbox.setTextFormat(QtCore.Qt.RichText)
					button_ok = msgbox.addButton("&OK", QtWidgets.QMessageBox.ActionRole)
					button_details = msgbox.addButton("&Details", QtWidgets.QMessageBox.ActionRole)
					button_cancel = None
					msgbox.setDefaultButton(button_ok)
					cb = QtWidgets.QCheckBox("Always skip this message", checked=False)
					if self.STATUS["can_skip_message"]:
						button_cancel = msgbox.addButton("&Cancel", QtWidgets.QMessageBox.RejectRole)
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
						self.lblStatus4a.setText("Ready.")
						self.STATUS["can_skip_message"] = False
						if "detected_cart_type" in self.STATUS: del(self.STATUS["detected_cart_type"])
						return

			if not found_supported or show_details is True:
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s} | {:s}".format(APPNAME, VERSION, self.CONN.GetFullNameLabel()))
				button_ok = msgbox.addButton("&OK", QtWidgets.QMessageBox.ActionRole)
				msgbox.setDefaultButton(button_ok)
				msgbox.setEscapeButton(button_ok)
				if try_this is not None:
					button_try = msgbox.addButton("  &Try Generic Type  ", QtWidgets.QMessageBox.ActionRole)
					button_try.setToolTip("{:s}".format(try_this))
				else:
					button_try = None
				
				if not is_generic:
					msg_fw = "<br><span style=\"font-size: 8pt;\"><i>{:s} {:s} | {:s}</i></span><br>".format(APPNAME, VERSION, self.CONN.GetFullNameExtended())
					button_clipboard = msgbox.addButton("  &Copy to Clipboard  ", QtWidgets.QMessageBox.ActionRole)
				else:
					msg_fw = ""
					button_clipboard = None
				
				if self.CONN.GetMode() == "DMG" and limitVoltage and (is_generic or not found_supported):
					text = "No known flash cartridge type could be detected. The option “Limit voltage to 3.3V when detecting Game Boy flash cartridges” has been enabled which can cause auto-detection to fail. As it is usually not recommended to enable this option, do you now want to disable it and try again?"
					answer = QtWidgets.QMessageBox.warning(self, "{:s} {:s}".format(APPNAME, VERSION), text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
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
		self.lblStatus4a.setText("Ready.")
		
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
			title = "{:s} {:s}".format(APPNAME, VERSION)
			if "title" in args:
				title += " – " + args["title"]
			msg = args["msg"]
			answer = QtWidgets.QMessageBox.warning(self, title, msg, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
			if answer == QtWidgets.QMessageBox.Ok:
				self.CONN.USER_ANSWER = True
			else:
				self.CONN.USER_ANSWER = False

	def UpdateProgress(self, args):
		if args is None: return
		if self.CONN is None: return
		
		if "method" in args:
			if args["method"] == "ROM_READ":
				self.grpStatus.setTitle("Transfer Status (Backup ROM)")
			elif args["method"] == "ROM_WRITE":
				self.grpStatus.setTitle("Transfer Status (Write ROM)")
			elif args["method"] == "ROM_WRITE_VERIFY":
				self.grpStatus.setTitle("Transfer Status (Verify Flash)")
			elif args["method"] == "SAVE_READ":
				self.grpStatus.setTitle("Transfer Status (Backup Save Data)")
			elif args["method"] == "SAVE_WRITE":
				self.grpStatus.setTitle("Transfer Status (Write Save Data)")
			elif args["method"] == "SAVE_WRITE_VERIFY":
				self.grpStatus.setTitle("Transfer Status (Verify Save Data)")
			elif args["method"] == "DETECT_CART":
				self.grpStatus.setTitle("Transfer Status (Analyze Cartridge)")
		
		if "error" in args:
			self.lblStatus4a.setText("Failed!")
			self.grpDMGCartridgeInfo.setEnabled(True)
			self.grpAGBCartridgeInfo.setEnabled(True)
			self.grpActions.setEnabled(True)
			self.mnuTools.setEnabled(True)
			self.mnuConfig.setEnabled(True)
			self.btnCancel.setEnabled(False)
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=str(args["error"]), standardButtons=QtWidgets.QMessageBox.Ok)
			if not '\n' in str(args["error"]): msgbox.setTextFormat(QtCore.Qt.RichText)
			msgbox.exec()
			self.LimitBaudRateGBxCartRW()
			return
		
		self.grpDMGCartridgeInfo.setEnabled(False)
		self.grpAGBCartridgeInfo.setEnabled(False)
		self.grpActions.setEnabled(False)
		self.mnuTools.setEnabled(False)
		self.mnuConfig.setEnabled(False)
		
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
				self.lblStatus1aResult.setText("Pending...")
				self.lblStatus2aResult.setText("Pending...")
				self.lblStatus3aResult.setText(Util.formatProgressTime(elapsed))
				if estimated != 0:
					self.lblStatus4a.setText("Erasing... This may take up to {:d} seconds.".format(estimated))
				else:
					self.lblStatus4a.setText("Erasing... This may take some time.")
				self.lblStatus4aResult.setText("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "UNLOCK":
				self.lblStatus1aResult.setText("Pending...")
				self.lblStatus2aResult.setText("Pending...")
				self.lblStatus3aResult.setText("Pending...")
				self.lblStatus4a.setText("Unlocking flash...")
				self.lblStatus4aResult.setText("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "UPDATE_RTC":
				self.lblStatus1aResult.setText("Pending...")
				self.lblStatus2aResult.setText("Pending...")
				self.lblStatus3aResult.setText("Pending...")
				self.lblStatus4a.setText("Updating Real Time Clock...")
				self.lblStatus4aResult.setText("")
				self.btnCancel.setEnabled(False)
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "SECTOR_ERASE":
				if elapsed >= 1:
					self.lblStatus3aResult.setText(Util.formatProgressTime(elapsed))
				self.lblStatus4a.setText("Erasing sector at address 0x{:X}...".format(args["sector_pos"]))
				self.lblStatus4aResult.setText("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "ABORTING":
				self.lblStatus1aResult.setText("–")
				self.lblStatus2aResult.setText("–")
				self.lblStatus3aResult.setText("–")
				self.lblStatus4a.setText("Stopping... Please wait.")
				self.lblStatus4aResult.setText("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "ERROR":
				self.lblStatus2aResult.setText("Pending...")
				self.lblStatus3aResult.setText("Pending...")
				self.lblStatus4a.setText("<span style=\"color: red;\">{:s}</span>".format(args["text"]))
				self.lblStatus4aResult.setText("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "UPDATE_INFO":
				self.lblStatus4a.setText(args["text"])
				self.lblStatus4aResult.setText("")
				self.btnCancel.setEnabled(args["abortable"])
				self.SetProgressBars(min=0, max=size, value=pos)
			elif args["action"] == "FINISHED":
				if pos > 0:
					self.lblStatus1aResult.setText(Util.formatFileSize(size=pos))
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
				self.grpStatus.setTitle("Transfer Status")
				self.lblStatus1aResult.setText("–")
				self.lblStatus2aResult.setText("–")
				self.lblStatus3aResult.setText("–")
				self.lblStatus4a.setText("Stopped.")
				self.lblStatus4aResult.setText("")
				self.btnCancel.setEnabled(False)
				self.SetProgressBars(min=0, max=1, value=0)
				self.btnCancel.setEnabled(False)
				
				if "info_type" in args.keys() and "info_msg" in args.keys():
					if args["info_type"] == "msgbox_critical":
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=args["info_msg"], standardButtons=QtWidgets.QMessageBox.Ok)
						Util.dprint("Queueing Message Box {:s}:\n----\n{:s} {:s}\n----\n{:s}\n----".format(str(msgbox), APPNAME, VERSION, args["info_msg"]))
						if not '\n' in args["info_msg"]: msgbox.setTextFormat(QtCore.Qt.RichText)
						self.MSGBOX_QUEUE.put(msgbox)
						self.WriteDebugLog()
						if "fatal" in args:
							self.LimitBaudRateGBxCartRW()
							self.DisconnectDevice()
					elif args["info_type"] == "msgbox_information":
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="{:s} {:s}".format(APPNAME, VERSION), text=args["info_msg"], standardButtons=QtWidgets.QMessageBox.Ok)
						Util.dprint("Queueing Message Box {:s}:\n----\n{:s} {:s}\n----\n{:s}\n----".format(str(msgbox), APPNAME, VERSION, args["info_msg"]))
						if not '\n' in args["info_msg"]: msgbox.setTextFormat(QtCore.Qt.RichText)
						#msgbox.exec()
						self.MSGBOX_QUEUE.put(msgbox)
					elif args["info_type"] == "label":
						self.lblStatus4a.setText(args["info_msg"])
				
				QtCore.QTimer.singleShot(1, lambda: [ self.ReadCartridge(resetStatus=False) ])
				return

			elif args["action"] == "PROGRESS":
				self.SetProgressBars(min=0, max=size, value=pos)
				if "abortable" in args:
					self.btnCancel.setEnabled(args["abortable"])
				else:
					self.btnCancel.setEnabled(True)
				self.lblStatus1aResult.setText("{:s}".format(Util.formatFileSize(size=pos)))
				if speed > 0:
					self.lblStatus2aResult.setText("{:.2f} KiB/s".format(speed))
				else:
					self.lblStatus2aResult.setText("Pending...")
				if left > 0:
					self.lblStatus4aResult.setText(Util.formatProgressTime(left))
				else:
					self.lblStatus4aResult.setText("Pending...")
				if elapsed > 0:
					self.lblStatus3aResult.setText(Util.formatProgressTime(elapsed))

				if speed == 0 and "skipping" in args and args["skipping"] is True:
					self.lblStatus4aResult.setText("Pending...")
				self.lblStatus4a.setText("Time left:")
	
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
					"GBxCart RW v1.4 or v1.4a/b/c":hw_GBxCartRW.GbxDevice.GetFirmwareUpdaterClass(None),
					"GBFlash":hw_GBFlash.GbxDevice.GetFirmwareUpdaterClass(None),
					"Joey Jr":hw_JoeyJr.GbxDevice.GetFirmwareUpdaterClass(None),
				}
				dlg_args = {
					"title":"Select Device Type",
					"intro":"Please select the device that you are using below.",
					"params": [
						# ID, Type, Value(s), Default Index
						[ "dev_type", "cmb", "Device Type:", dev_types.keys(), 0 ]
					]
				}
				dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
				if dlg.exec_() == 1:
					result = dlg.GetResult()
					FirmwareUpdater = list(dev_types.values())[result["dev_type"].currentIndex()][1]
				else:
					return False
			except:
				return False
		else:
			if not self.CONN.SupportsFirmwareUpdates():
				QtWidgets.QMessageBox.information(self, "{:s} {:s}".format(APPNAME, VERSION), "{:s} currently does not support updaing the firmware of your device.".format(APPNAME), QtWidgets.QMessageBox.Ok)
				return False
			else:
				FirmwareUpdater = self.CONN.GetFirmwareUpdaterClass()[1]
		
		self.FWUPWIN = None
		self.FWUPWIN = FirmwareUpdater(self, app_path=Util.APP_PATH, icon=self.windowIcon(), device=self.CONN)
		self.FWUPWIN.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
		self.FWUPWIN.setModal(True)
		self.FWUPWIN.run()
	
	def ShowPocketCameraWindow(self):
		data = None
		if self.CONN is not None:
			if self.CONN.GetMode() is None and "DMG" in self.CONN.GetSupprtedModes():
				answer = QtWidgets.QMessageBox.question(self, "{:s} {:s}".format(APPNAME, VERSION), "Is a Game Boy Camera cartridge currently inserted?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
				if answer == QtWidgets.QMessageBox.Yes:
					self.optDMG.setChecked(True)
					self.SetMode()
			if self.CONN.GetMode() == "DMG":
				header = self.CONN.ReadInfo(setPinsAsInputs=True)
				if header["mapper_raw"] == 252: # GBD
					args = { "path":None, "mbc":252, "save_type":header["ram_size_raw"], "rtc":False }
					self.lblStatus4a.setText("Loading data, please wait...")
					qt_app.processEvents()
					self.CONN.BackupRAM(fncSetProgress=False, args=args)
					data = self.CONN.INFO["data"]
					self.lblStatus4a.setText("Ready.")
		
		self.CAMWIN = None
		self.CAMWIN = PocketCameraWindow(self, icon=self.windowIcon(), file=data, config_path=Util.CONFIG_PATH, app_path=Util.APP_PATH)
		self.CAMWIN.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
		self.CAMWIN.setModal(True)
		self.CAMWIN.run()

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
				if platform.system() == 'Darwin':
					# pylint: disable=undefined-variable
					fn = str(NSURL.URLWithString_(str(url.toString())).filePathURL().path()) # type: ignore
				else:
					fn = str(url.toLocalFile())
				
				fn_split = os.path.splitext(os.path.abspath(fn))
				if fn_split[1].lower() in (".sav", ".srm", ".fla", ".eep"):
					return True
				elif self.CONN.GetMode() == "DMG" and fn_split[1].lower() in (".gb", ".sgb", ".gbc", ".bin", ".isx"):
					return True
				elif self.CONN.GetMode() == "AGB" and fn_split[1].lower() in (".gba", ".srl"):
					return True
				else:
					return False
		return False
	
	def dropEvent(self, e):
		if self.btnHeaderRefresh.isEnabled() and self.grpActions.isEnabled() and e.mimeData().hasUrls:
			e.setDropAction(QtCore.Qt.CopyAction)
			e.accept()
			for url in e.mimeData().urls():
				if platform.system() == 'Darwin':
					# pylint: disable=undefined-variable
					fn = str(NSURL.URLWithString_(str(url.toString())).filePathURL().path()) # type: ignore
				else:
					fn = str(url.toLocalFile())
				
				fn_split = os.path.splitext(os.path.abspath(fn))
				if fn_split[1].lower() in (".gb", ".sgb", ".gbc", ".bin", ".isx", ".gba", ".srl"):
					self.FlashROM(fn)
				elif fn_split[1].lower() in (".sav", ".srm", ".fla", ".eep"):
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
		screen = QtGui.QGuiApplication.screens()[0]
		screenGeometry = screen.geometry()
		x = (screenGeometry.width() - self.width()) / 2
		y = (screenGeometry.height() - self.height()) / 2
		self.move(x, y)
		self.setAcceptDrops(True)
		self.show()
		
		if callable(getattr(qt_app, "exec", None)): # PySide6
			try:
				if platform.system() == "Windows":
					qt_app.setStyle("windowsvista")
			except:
				pass
			qt_app.exec()

		else: # PySide2
			qt_app.exec_()
			# Taskbar Progress on Windows only
			try:
				from PySide2.QtWinExtras import QWinTaskbarButton, QtWin # type: ignore
				myappid = 'lesserkuma.flashgbx'
				QtWin.setCurrentProcessExplicitAppUserModelID(myappid)
				taskbar_button = QWinTaskbarButton()
				self.TBPROG = taskbar_button.progress()
				self.TBPROG.setRange(0, 100)
				taskbar_button.setWindow(self.windowHandle())
				self.TBPROG.setVisible(False)
			except ImportError:
				pass

qt_app = QApplication(sys.argv)
qt_app.setApplicationName(APPNAME)
