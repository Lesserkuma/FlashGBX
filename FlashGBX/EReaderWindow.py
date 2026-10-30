# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import os, functools, threading, time, traceback
from PIL.ImageQt import ImageQt
from PIL import Image, ImageOps

from .pyside import QtCore, QtWidgets, QtGui, QDesktopWidget
from .EReader import EReader, EReaderScanWorker, ScanControl, EReaderDotcode
from .Formatter import Formatter
from .Logging import dprint
from .i18n import __, c__, format_decimal
from .app import AppInfo

class EReaderPreview(QtWidgets.QLabel):
	def __init__(self, parent=None):
		QtWidgets.QLabel.__init__(self, parent)
		self.CUR_PIC = None
		self.setFixedSize(EReaderDotcode.WIDTH, EReaderDotcode.HEIGHT)
		self.setAlignment(QtCore.Qt.AlignCenter)
		self.setStyleSheet("border-top: 1px solid #adadad; border-left: 1px solid #adadad; border-bottom: 1px solid #ffffff; border-right: 1px solid #ffffff; background: #202020;")

	def SetFrame(self, frame):
		if len(frame) != EReader.FRAME_SIZE: return
		image = Image.frombytes("1", (EReaderDotcode.WIDTH, EReaderDotcode.HEIGHT), frame)
		self.CUR_PIC = ImageQt(ImageOps.mirror(ImageOps.invert(image.convert("L"))))
		pixmap = QtGui.QPixmap.fromImage(self.CUR_PIC).scaled(EReaderDotcode.WIDTH * 4, EReaderDotcode.HEIGHT * 4, QtCore.Qt.KeepAspectRatio, QtCore.Qt.FastTransformation)
		pixmap.setDevicePixelRatio(4)
		self.setPixmap(pixmap)

	def ClearFrame(self):
		self.CUR_PIC = None
		self.clear()


class EReaderBlockStatus(QtWidgets.QWidget):
	COLORS = ("#111111", "#ffd21f", "#20a83a", "#ef2929")

	def __init__(self, parent=None):
		QtWidgets.QWidget.__init__(self, parent)
		self.STATES = ()
		self.CURRENT_BLOCKS = frozenset()
		layout = QtWidgets.QHBoxLayout()
		layout.setContentsMargins(0, 0, 0, 0)
		layout.setSpacing(3)
		self.lblBlocks = []
		for i in range(28):
			column = QtWidgets.QVBoxLayout()
			column.setContentsMargins(0, 0, 0, 0)
			column.setSpacing(2)
			block = QtWidgets.QLabel(self)
			block.setFixedSize(22, 22)
			block.setStyleSheet("background: {}; border: 1px solid #707070;".format(self.COLORS[0]))
			number = QtWidgets.QLabel(str(i + 1), self)
			number.setAlignment(QtCore.Qt.AlignCenter)
			column.addWidget(block, 0, QtCore.Qt.AlignCenter)
			column.addWidget(number)
			layout.addLayout(column)
			self.lblBlocks.append((block, number))
		self.setLayout(layout)
		self.setFixedSize(self.sizeHint())
		for block, number in self.lblBlocks:
			block.hide()
			number.hide()

	def SetStates(self, states, current_blocks=()):
		states = tuple(states)
		current_blocks = frozenset(current_blocks)
		for i, (block, number) in enumerate(self.lblBlocks):
			visible = i < len(states)
			was_visible = i < len(self.STATES)
			if visible != was_visible:
				block.setVisible(visible)
				number.setVisible(visible)
			if visible and (not was_visible or self.STATES[i] != states[i]
					or (i in self.CURRENT_BLOCKS) != (i in current_blocks)):
				border, color = (2, "#000000") if i in current_blocks else (1, "#707070")
				block.setStyleSheet("background: {}; border: {}px solid {};".format(self.COLORS[states[i]], border, color))
		self.STATES = states
		self.CURRENT_BLOCKS = current_blocks

	def ClearCurrentBlocks(self):
		self.SetStates(self.STATES)


class EReaderScanEvent(QtCore.QEvent):
	TYPE = QtCore.QEvent.Type(QtCore.QEvent.registerEventType())

	def __init__(self, action, args, completed=None):
		QtCore.QEvent.__init__(self, self.TYPE)
		self.ACTION, self.ARGS, self.COMPLETED = action, args, completed


class EReaderWindow(QtWidgets.QDialog):
	CALIBRATION_SETTINGS = {
		"sensor_brightness":("EReaderSensorBrightness", 24),
		"vertical_offset":("EReaderVerticalOffset", 48),
		"pwm":("EReaderPWM", 176),
		"threshold_factor":("EReaderThresholdFactor", 56),
	}

	def __init__(self, app, icon=None):
		QtWidgets.QDialog.__init__(self, app)
		self.APP, self.CONN = app, app.CONN
		if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
		self.CUR_EXPORT_PATH = app.SETTINGS.value("LastDirEReader", default=".")
		self.CUR_STATUS, self.SCAN_THREAD = "Ready", None
		self.FIRST_STRIP_INFO = None
		self.SCANNED_STRIPS = {}
		self.NEXT_SCAN = False
		self.SCAN_STARTED_AT = None
		self.SCAN_ELAPSED_SECONDS = 0
		self.TOTAL_SCAN_SECONDS = 0.0
		self.elapsedTimer = QtCore.QTimer(self)
		self.elapsedTimer.setInterval(250)
		self.elapsedTimer.timeout.connect(self.UpdateElapsedTime)
		self.FORCE_EXIT = self.FATAL_ERROR = False
		values = {}
		for key, (setting, default) in self.CALIBRATION_SETTINGS.items():
			try: value = int(app.SETTINGS.value(setting, default=str(default)))
			except (TypeError, ValueError): value = default
			minimum, maximum = ScanControl.RANGES[key][:2]
			values[key] = min(maximum, max(minimum, value))
		self.setWindowTitle(AppInfo.NAME + " – " + __("e-Reader Dot Code Dumper"))
		flags = self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
		flags |= QtCore.Qt.MSWindowsFixedSizeDialogHint | QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint
		self.setWindowFlags(flags)
		self.layout = QtWidgets.QGridLayout()
		self.layout.setContentsMargins(-1, 8, -1, 8)
		self.layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)

		self.grpPreview = QtWidgets.QGroupBox(__('e-Reader Camera View'))
		grpPreviewLayout = QtWidgets.QVBoxLayout()
		grpPreviewLayout.setContentsMargins(-1, 3, -1, -1)
		self.lblPreview = EReaderPreview(self)
		grpPreviewLayout.addWidget(self.lblPreview, 0, QtCore.Qt.AlignCenter)
		self.grpPreview.setLayout(grpPreviewLayout)

		self.grpBlockStatus = QtWidgets.QGroupBox(__('Block Status'))
		grpBlockStatusLayout = QtWidgets.QVBoxLayout()
		grpBlockStatusLayout.setContentsMargins(-1, 3, -1, -1)

		self.blockStatusViewport = QtWidgets.QWidget(self.grpBlockStatus)
		self.blockStatus = EReaderBlockStatus(self.blockStatusViewport)
		blockStatusSize = self.blockStatus.size()
		self.blockStatusViewport.setFixedSize(blockStatusSize)
		self.blockStatus.setGeometry(0, 0, blockStatusSize.width(), blockStatusSize.height())
		self.lblBlockStatusCalibrating = QtWidgets.QLabel(__('Calibrating...'), self.blockStatusViewport)
		self.lblBlockStatusCalibrating.setAlignment(QtCore.Qt.AlignCenter)
		self.lblBlockStatusCalibrating.setGeometry(0, 0, blockStatusSize.width(), blockStatusSize.height())
		self.lblBlockStatusCalibrating.hide()
		grpBlockStatusLayout.addWidget(self.blockStatusViewport, 0, QtCore.Qt.AlignCenter)
		self.grpBlockStatus.setLayout(grpBlockStatusLayout)

		# Scan Status
		self.grpScanStatus = QtWidgets.QGroupBox(__('Scan Status'))
		grpScanStatusLayout = QtWidgets.QGridLayout()
		grpScanStatusLayout.setContentsMargins(-1, 3, -1, -1)
		self.lblScanStatus = {}
		status_rows = (("status", __("Status:")), ("frames", __("Frames:")), ("framerate", __("Framerate:")), ("blocks_read", __("Blocks read:")), ("time_elapsed", __("Time elapsed:")))
		for i, (key, title) in enumerate(status_rows):
			self.lblScanStatus[key] = QtWidgets.QLabel()
			grpScanStatusLayout.addWidget(QtWidgets.QLabel(title), i, 0)
			grpScanStatusLayout.addWidget(self.lblScanStatus[key], i, 1)
		self.lblScanStatus["blocks_read"].setMinimumWidth(self.lblScanStatus["blocks_read"].fontMetrics().horizontalAdvance("28/28 (28 reconfirmed, 28 unreadable)"))
		grpScanStatusLayout.setColumnStretch(1, 1)
		self.grpScanStatus.setLayout(grpScanStatusLayout)

		self.grpCalibration = QtWidgets.QGroupBox(__('Calibration'))
		grpCalibrationLayout = QtWidgets.QVBoxLayout()
		grpCalibrationLayout.setContentsMargins(-1, 3, -1, -1)
		self.chkAutoCalibration = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Auto calibration"))
		self.chkAutoCalibration.setChecked(app.SETTINGS.value("EReaderAutoCalibration", default="enabled") == "enabled")
		self.chkAutoCalibration.toggled.connect(self.chkAutoCalibration_Toggled)
		grpCalibrationLayout.addWidget(self.chkAutoCalibration)

		calibrationGrid = QtWidgets.QGridLayout()
		calibrationGrid.setContentsMargins(0, 0, 0, 0)
		calibrationGrid.setHorizontalSpacing(8)
		calibrationGrid.setVerticalSpacing(6)
		self.sldCalibration, self.lblCalibration = {}, {}
		for rowIndex, (key, title) in enumerate((("sensor_brightness", __("Sensor Brightness:")), ("vertical_offset", __("Vertical Offset:")), ("pwm", __("PWM Value:")), ("threshold_factor", __("Threshold Factor:")))):
			titleLabel = QtWidgets.QLabel(title)
			valueLabel = QtWidgets.QLabel(str(values[key]))
			valueLabel.setFixedWidth(42)
			valueLabel.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
			slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
			slider.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
			slider.setRange(*ScanControl.RANGES[key][:2])
			slider.setValue(values[key])
			slider.valueChanged.connect(functools.partial(self.sldCalibration_ValueChanged, key=key))
			calibrationGrid.addWidget(titleLabel, rowIndex, 0)
			calibrationGrid.addWidget(valueLabel, rowIndex, 1)
			calibrationGrid.addWidget(slider, rowIndex, 2)
			self.sldCalibration[key], self.lblCalibration[key] = slider, valueLabel
		calibrationGrid.setColumnStretch(2, 1)
		grpCalibrationLayout.addLayout(calibrationGrid)
		grpCalibrationLayout.addStretch(1)
		self.grpCalibration.setLayout(grpCalibrationLayout)
		rowStatus = QtWidgets.QHBoxLayout()
		rowStatus.addWidget(self.grpScanStatus, 1)
		rowStatus.addWidget(self.grpCalibration, 1)

		# Actions
		rowActions = QtWidgets.QHBoxLayout()
		self.btnStartScan = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Start Scan"))
		self.btnStartScan.clicked.connect(self.btnStartScan_Clicked)
		self.chkErrorCorrection = QtWidgets.QCheckBox(__("Use error-correction"))
		self.chkErrorCorrection.setChecked(app.SETTINGS.value("EReaderErrorCorrection", default="enabled") == "enabled")
		self.chkErrorCorrection.toggled.connect(self.chkErrorCorrection_Toggled)
		self.btnClose = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Close"))
		self.btnClose.clicked.connect(self.reject)
		for button in (self.btnStartScan, self.btnClose):
			button.setStyleSheet("padding: 5px 15px;")
			if button is self.btnClose: rowActions.addStretch(1)
			rowActions.addWidget(button)
			if button is self.btnStartScan: rowActions.addWidget(self.chkErrorCorrection)
		self.layout.addWidget(self.grpPreview, 0, 0)
		self.layout.addWidget(self.grpBlockStatus, 1, 0)
		self.layout.addLayout(rowStatus, 2, 0)
		self.layout.addLayout(rowActions, 3, 0)
		self.setLayout(self.layout)
		self.SCAN_EVENT_HANDLERS = {
			"preview":self.lblPreview.SetFrame,
			"status":self.UpdateStatus,
			"completed":self.ScanCompleted,
			"stopped":self.ScanStopped,
			"failed":self.ScanFailed,
			"finished":self.ScanThreadFinished,
			"warning":self.ScanWarning,
		}
		self.ResetStatus()
		self.UpdateCalibrationControls()
		self.btnStartScan.setDefault(True)
		self.btnStartScan.setAutoDefault(True)
		self.btnStartScan.setFocus()

		self.layout.activate()
		self.adjustSize()
		stableWidth = self.sizeHint().width()
		self.setMinimumWidth(stableWidth)
		self.setMaximumWidth(stableWidth)

	def run(self):
		self.layout.activate()
		self.adjustSize()
		screen = QDesktopWidget().screenGeometry(self)
		self.move(screen.x() + (screen.width() - self.width()) // 2, screen.y() + (screen.height() - self.height()) // 2)
		self.show()

	def hideEvent(self, event):
		self.APP.SETTINGS.setValue("LastDirEReader", self.CUR_EXPORT_PATH)
		self.APP.SETTINGS.setValue("EReaderErrorCorrection", "enabled" if self.chkErrorCorrection.isChecked() else "disabled")
		self.APP.SETTINGS.setValue("EReaderAutoCalibration", "enabled" if self.chkAutoCalibration.isChecked() else "disabled")
		for key, (setting, _) in self.CALIBRATION_SETTINGS.items():
			self.APP.SETTINGS.setValue(setting, str(self.sldCalibration[key].value()))
		self.APP.activateWindow()
		QtWidgets.QDialog.hideEvent(self, event)

	def PostScanEvent(self, action, *args, blocking=False):
		completed = threading.Event() if blocking else None
		QtCore.QCoreApplication.postEvent(self, EReaderScanEvent(action, args, completed))
		if completed is not None: completed.wait()

	def customEvent(self, event):
		if event.type() != EReaderScanEvent.TYPE:
			return QtWidgets.QDialog.customEvent(self, event)
		try:
			handler = self.SCAN_EVENT_HANDLERS[event.ACTION]
			handler(*event.ARGS)
		finally:
			if event.COMPLETED is not None: event.COMPLETED.set()

	def ResetStatus(self):
		for label in self.lblScanStatus.values(): label.setText("0")
		self.lblScanStatus["status"].setText(__("Ready"))
		self.lblScanStatus["framerate"].setText(__("{framerate} frames per second", framerate="0.0"))
		self.lblScanStatus["blocks_read"].setText(__("{read}/{count} ({reconfirmed} reconfirmed, {unreadable} unreadable)", read="0", count="0", reconfirmed="0", unreadable="0"))
		self.lblScanStatus["time_elapsed"].setText(Formatter.progress_time(0))
		self.grpBlockStatus.setTitle(__("Block Status"))
		self.blockStatus.SetStates(())
		self.SetBlockStatusCalibrating(False)

	def StartElapsedTimer(self):
		self.SCAN_STARTED_AT = time.monotonic()
		self.SCAN_ELAPSED_SECONDS = 0
		self.lblScanStatus["time_elapsed"].setText(Formatter.progress_time(0))
		self.elapsedTimer.start()

	def GetElapsedSeconds(self):
		if self.SCAN_STARTED_AT is not None:
			self.SCAN_ELAPSED_SECONDS = int(max(0.0, time.monotonic() - self.SCAN_STARTED_AT))
		return self.SCAN_ELAPSED_SECONDS

	def UpdateElapsedTime(self):
		seconds = self.GetElapsedSeconds()
		self.lblScanStatus["time_elapsed"].setText(Formatter.progress_time(seconds))

	def StopElapsedTimer(self):
		seconds = self.GetElapsedSeconds()
		if self.SCAN_STARTED_AT is not None:
			self.TOTAL_SCAN_SECONDS += max(0.0, time.monotonic() - self.SCAN_STARTED_AT)
		self.elapsedTimer.stop()
		self.SCAN_STARTED_AT = None
		self.lblScanStatus["time_elapsed"].setText(Formatter.progress_time(seconds))

	def SetBlockStatusCalibrating(self, calibrating):
		self.blockStatus.setVisible(not calibrating)
		self.lblBlockStatusCalibrating.setVisible(calibrating)

	def UpdateCalibrationControls(self):
		stopping = self.SCAN_THREAD is not None and not self.btnStartScan.isEnabled()
		self.chkAutoCalibration.setEnabled(not stopping)
		self.chkErrorCorrection.setEnabled(not stopping)
		for slider in self.sldCalibration.values(): slider.setEnabled(not stopping and not self.chkAutoCalibration.isChecked())

	def chkAutoCalibration_Toggled(self, checked):
		if self.SCAN_THREAD is not None:
			values = {key:slider.value() for key, slider in self.sldCalibration.items()}
			self.SCAN_THREAD.CONTROL.Update(auto_calibration=checked, **values)
		self.UpdateCalibrationControls()

	def chkErrorCorrection_Toggled(self, checked):
		if self.SCAN_THREAD is not None:
			self.SCAN_THREAD.CONTROL.Update(error_correction=checked)

	def sldCalibration_ValueChanged(self, value, key):
		self.lblCalibration[key].setText(str(value))
		if self.SCAN_THREAD is not None and not self.chkAutoCalibration.isChecked():
			self.SCAN_THREAD.CONTROL.Update(**{key:value})

	def btnStartScan_Clicked(self, event=None):
		if self.SCAN_THREAD is not None:
			self.StopScan()
			return
		self.TryStartScan()

	def TryStartScan(self, next_strip=False):
		if self.SCAN_THREAD is not None or self.FATAL_ERROR: return
		self.NEXT_SCAN = False
		try:
			self.StartScan(next_strip)
		except Exception as e:
			dprint(traceback.format_exc())
			self.SCAN_THREAD = None
			self.ScanFailed(str(e), fatal=self.CONN.DEVICE is None or self.CONN.ERROR)

	def StartScan(self, next_strip=False):
		if not next_strip:
			self.FIRST_STRIP_INFO = None
			self.SCANNED_STRIPS = {}
			self.TOTAL_SCAN_SECONDS = 0.0
		self.NEXT_SCAN = False
		automatic = self.chkAutoCalibration.isChecked() and not next_strip
		values = {key:slider.value() for key, slider in self.sldCalibration.items()}
		if automatic:
			text = __("Place the card so that the Dot Code is centered in the e-Reader.") + "\n\n" + __("Do not move the card during calibration.") + "\n" + __("After calibration, move the card to the left and right until the scan is complete.")
		else:
			text = __("Place the card so that the Dot Code is centered in the e-Reader.") + "\n\n" + __("During scanning, move the card to the left and right until the scan is complete.")
		answer = QtWidgets.QMessageBox.information(self, self.windowTitle(), text, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
		if answer != QtWidgets.QMessageBox.Ok:
			return
		control = ScanControl(auto_calibration=automatic, auto_calibration_reused=next_strip and self.chkAutoCalibration.isChecked(),
			error_correction=self.chkErrorCorrection.isChecked(), **values)
		thread = EReaderScanWorker(self.CONN, control=control,
			on_preview=lambda frame: self.PostScanEvent("preview", frame),
			on_status=lambda status: self.PostScanEvent("status", status),
			on_completed=lambda raw: self.PostScanEvent("completed", raw, blocking=True),
			on_stopped=lambda: self.PostScanEvent("stopped"),
			on_failed=lambda message, fatal: self.PostScanEvent("failed", message, fatal),
			on_finished=lambda: self.PostScanEvent("finished"),
			on_warning=lambda message: self.PostScanEvent("warning", message, blocking=True))
		self.SCAN_THREAD = thread
		self.CUR_STATUS = "Scanning"
		self.lblPreview.ClearFrame()
		self.ResetStatus()
		self.lblScanStatus["status"].setText(__("Calibrating...") if automatic else __("Starting..."))
		self.SetBlockStatusCalibrating(automatic)
		self.btnStartScan.setText(c__("Button (& = Keyboard Shortcut)", "S&top Scan"))
		self.UpdateCalibrationControls()
		self.StartElapsedTimer()
		thread.start()

	def StopScan(self):
		if self.SCAN_THREAD is None: return
		self.lblScanStatus["status"].setText(__("Stopping..."))
		self.SetBlockStatusCalibrating(False)
		self.btnStartScan.setEnabled(False)
		self.UpdateCalibrationControls()
		self.SCAN_THREAD.READER.Cancel()

	def UpdateStatus(self, status):
		values = dict(status)
		values["status"] = __(status["status"])
		values["framerate"] = __("{framerate} frames per second", framerate=format_decimal(status["framerate"], precision=1))
		values["blocks_read"] = __("{read}/{count} ({reconfirmed} reconfirmed, {unreadable} unreadable)", read=status["blocks_read"], count=status["block_count"], reconfirmed=status["blocks_confirmed"], unreadable=status["blocks_unreadable"])
		for key, label in self.lblScanStatus.items():
			if key != "time_elapsed": label.setText(str(values[key]))
		self.SetBlockStatusCalibrating(status["status"] == __("Calibrating..."))
		if self.chkAutoCalibration.isChecked():
			values["threshold_factor"] = status["active_factor"]
			for key, slider in self.sldCalibration.items():
				if values[key] is None: continue
				slider.setValue(values[key])
		if status["block_count"]:
			self.grpBlockStatus.setTitle(__("Block Status ({count} blocks)", count=status["block_count"]))
			self.blockStatus.SetStates(status["block_states"], status.get("current_blocks", ()))

	def ScanCompleted(self, raw_data):
		raw_data = bytes(raw_data)
		self.StopElapsedTimer()
		info = EReader().ParseRaw(raw_data)
		if info is False:
			self.ScanFailed(__("Invalid e-Reader RAW data."))
			return
		if self.FIRST_STRIP_INFO is None and 1 <= info["strip_number"] <= info["strip_count"] and info["strip_count"] > 1:
			self.FIRST_STRIP_INFO = info
		if self.FIRST_STRIP_INFO is not None:
			keys = ("region", "strip_format", "strip_count", "data_size", "flags", "program_title", "id_string")
			if not 1 <= info["strip_number"] <= self.FIRST_STRIP_INFO["strip_count"] or any(info[key] != self.FIRST_STRIP_INFO[key] for key in keys):
				text = __("This Dot Code belongs to a different set.")
			elif info["strip_number"] in self.SCANNED_STRIPS:
				text = __("This Dot Code has already been scanned.")
			else:
				text = None
			if text is not None:
				self.ScanStopped()
				text += "\n\n" + self.MissingStripsText()
				answer = QtWidgets.QMessageBox.warning(self, self.windowTitle(), text, QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Abort, QtWidgets.QMessageBox.Retry)
				self.NEXT_SCAN = answer == QtWidgets.QMessageBox.Retry
				return
		number = info["strip_number"] if self.FIRST_STRIP_INFO is not None else 1
		self.CUR_STATUS = "Complete"
		self.lblScanStatus["status"].setText(__("Complete"))
		self.SetBlockStatusCalibrating(False)
		self.blockStatus.ClearCurrentBlocks()
		self.lblPreview.ClearFrame()
		if not self.SaveScan(raw_data, self.SCAN_THREAD.READER): return
		self.SCANNED_STRIPS[number] = raw_data
		if self.FIRST_STRIP_INFO is not None:
			count = self.FIRST_STRIP_INFO["strip_count"]
			if len(self.SCANNED_STRIPS) < count:
				text = "\n\n".join((
					__("This set contains {count} Dot Codes.", count=count),
					__("Successfully scanned Dot Codes:") + "\n" + self.StripsText(scanned=True),
					self.MissingStripsText(),
					__("Do you want to scan the next Dot Code now?"),
				))
				answer = QtWidgets.QMessageBox.question(self, self.windowTitle(), text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
				self.NEXT_SCAN = answer == QtWidgets.QMessageBox.Yes

	def StripsText(self, scanned):
		strips = {strip["strip_number"]:strip for strip in self.FIRST_STRIP_INFO["strips"]}
		lines = []
		for number in range(1, self.FIRST_STRIP_INFO["strip_count"] + 1):
			if (number in self.SCANNED_STRIPS) != scanned: continue
			fields = [__("Strip {number}", number=number)]
			strip = strips.get(number)
			if strip is not None:
				if strip["title"]: fields[0] += ": " + strip["title"]
				if strip["hp"] is not None: fields.append(__("HP: {hp}", hp=strip["hp"]))
				if strip["id"] is not None: fields.append(__("ID: {id}", id=strip["id"]))
			lines.append("- " + " | ".join(fields))
		return "\n".join(lines)

	def MissingStripsText(self):
		return __("Missing Dot Codes:") + "\n" + self.StripsText(scanned=False)

	def SaveScan(self, raw, reader):
		filename = reader.GetFileName(raw)
		while True:
			dialog = QtWidgets.QFileDialog(self, __("Dot Code file"), os.path.join(self.CUR_EXPORT_PATH, filename), __("e-Reader Dot Code RAW Data") + " (*.raw);;" + __("All files") + " (*.*)")
			dialog.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
			dialog.setDefaultSuffix("raw")
			if dialog.exec() != QtWidgets.QDialog.Accepted:
				self.ScanStopped()
				return False
			path = dialog.selectedFiles()[0]
			self.CUR_EXPORT_PATH = os.path.dirname(os.path.abspath(path))
			error = None
			try:
				if not reader.SaveRaw(raw, path, overwrite=os.path.exists(path)):
					error = __("Invalid e-Reader RAW data.")
			except Exception as e:
				dprint(traceback.format_exc())
				error = str(e)
			if error is not None:
				self.CUR_STATUS = "Error"
				self.lblScanStatus["status"].setText(__("Error"))
				answer = QtWidgets.QMessageBox.critical(self, self.windowTitle(), error, QtWidgets.QMessageBox.Retry | QtWidgets.QMessageBox.Abort, QtWidgets.QMessageBox.Retry)
				if answer == QtWidgets.QMessageBox.Retry: continue
				return False
			self.CUR_STATUS = "Complete"
			self.lblScanStatus["status"].setText(__("Complete"))
			text = __("The Dot Code was saved successfully!")
			elapsed = Formatter.progress_time(self.TOTAL_SCAN_SECONDS, as_float=True)
			text += "\n\n" + __("Total time elapsed: {elapsed}", elapsed=elapsed)
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle=self.windowTitle(), text=text, standardButtons=QtWidgets.QMessageBox.Ok)
			report = None
			if str(self.APP.SETTINGS.value("GenerateDumpReports", default="disabled")).lower() == "enabled":
				report = self.SaveDumpReport(reader, raw, path)
			button_dump_report = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "Open Dump &Report") if report else c__("Button (& = Keyboard Shortcut)", "Generate Dump &Report"), QtWidgets.QMessageBox.ActionRole)
			button_open_dir = msgbox.addButton(c__("Button (& = Keyboard Shortcut)", "Open Fol&der"), QtWidgets.QMessageBox.ActionRole)
			msgbox.exec()
			if msgbox.clickedButton() == button_dump_report:
				if not report: report = self.SaveDumpReport(reader, raw, path)
				if report: self.APP.OpenPath(report)
			elif msgbox.clickedButton() == button_open_dir:
				self.APP.OpenPath(path, select_file=True)
			return True

	def SaveDumpReport(self, reader, raw, path):
		try:
			report = reader.SaveDumpReport(raw, path)
			if report is not False: return report
			dprint("No scan information is available for the dump report.")
			return False
		except Exception as e:
			dprint(traceback.format_exc())
			error = str(e)
		QtWidgets.QMessageBox.warning(self, self.windowTitle(), __("Dump Report Error:") + "\n" + error, QtWidgets.QMessageBox.Ok)
		return False

	def ScanStopped(self):
		self.StopElapsedTimer()
		self.CUR_STATUS = "Stopped"
		self.lblScanStatus["status"].setText(__("Stopped"))
		self.SetBlockStatusCalibrating(False)

	def ScanFailed(self, message, fatal=False):
		self.StopElapsedTimer()
		self.CUR_STATUS = "Error"
		self.FATAL_ERROR = self.FATAL_ERROR or fatal
		self.lblScanStatus["status"].setText(__("Error"))
		self.SetBlockStatusCalibrating(False)
		if self.SCAN_THREAD is None: self.ResetScanControls()
		QtWidgets.QMessageBox.critical(self, self.windowTitle(), message, QtWidgets.QMessageBox.Ok)

	def ScanWarning(self, message):
		QtWidgets.QMessageBox.warning(self, self.windowTitle(), message, QtWidgets.QMessageBox.Ok)

	def ResetScanControls(self):
		self.StopElapsedTimer()
		if self.FATAL_ERROR and self.APP.CONN is self.CONN:
			self.APP.DisconnectDevice()
		self.btnStartScan.setText(c__("Button (& = Keyboard Shortcut)", "&Start Scan"))
		self.btnStartScan.setEnabled(not self.FATAL_ERROR)
		self.lblScanStatus["status"].setText(__(self.CUR_STATUS))
		self.SetBlockStatusCalibrating(False)
		self.UpdateCalibrationControls()

	def ScanThreadFinished(self):
		if self.SCAN_THREAD is not None:
			self.SCAN_THREAD.join()
		self.SCAN_THREAD = None
		self.ResetScanControls()
		self.ContinueScans()

	def ContinueScans(self):
		if self.NEXT_SCAN and not self.FORCE_EXIT and not self.FATAL_ERROR:
			self.TryStartScan(next_strip=True)
		else:
			self.NEXT_SCAN = False
			if self.FORCE_EXIT: self.reject()

	def reject(self):
		self.NEXT_SCAN = False
		if self.SCAN_THREAD is not None:
			self.FORCE_EXIT = True
			self.btnClose.setEnabled(False)
			self.StopScan()
			return
		QtWidgets.QDialog.reject(self)

	def closeEvent(self, event):
		event.ignore()
		self.reject()
