# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import functools, os, json, shutil, urllib.parse, threading, time
from collections import deque
from .i18n import __, c__, format_decimal
from PIL.ImageQt import ImageQt
from PIL import Image, ImageDraw
from .pyside import QtCore, QtWidgets, QtGui, QDesktopWidget, bitmap2pixmap
from .PocketCamera import PocketCamera, PocketCameraCapture
from .UserInputDialog import UserInputDialog
from .app import AppInfo


class PocketCameraDialog(QtWidgets.QDialog):
	PREVIEW_STYLE = "border-top: 1px solid #adadad; border-left: 1px solid #adadad; border-bottom: 1px solid #ffffff; border-right: 1px solid #ffffff;"

	def LoadSettings(self, default_zoom=2):
		self.FRAME = None
		self.PALETTES = list(PocketCamera.PALETTES)
		try:
			palette = json.loads(self.APP.SETTINGS.value("PocketCameraPalette"))
		except (TypeError, ValueError):
			palette = None
		if not isinstance(palette, list) or len(palette) != 12 or not all(isinstance(c, int) and 0 <= c <= 255 for c in palette):
			palette = self.PALETTES[3]
		try:
			custom_palette = json.loads(self.APP.SETTINGS.value("PocketCameraCustomPalette"))
		except (TypeError, ValueError):
			custom_palette = None
		if not isinstance(custom_palette, list) or len(custom_palette) != 12 or not all(isinstance(c, int) and 0 <= c <= 255 for c in custom_palette):
			custom_palette = palette if palette not in self.PALETTES else [240, 240, 240, 133, 178, 245, 81, 74, 179, 30, 30, 30]
		if palette not in self.PALETTES: custom_palette = palette
		self.PALETTES.append(list(custom_palette))
		self.CUSTOM_PALETTE_INDEX = len(self.PALETTES) - 1
		self.cmbColor.blockSignals(True)
		self.cmbColor.clear()
		self.cmbColor.addItems([
			__("Grayscale"), __("Original Game Boy"), __("Super Game Boy"),
			__("Game Boy Color (Pocket Camera)"), __("Game Boy Color (Game Boy Camera Gold)"),
			__("Game Boy Color (Game Boy Camera)"),
			__("Custom Palette"),
		])
		try:
			selection = int(self.APP.SETTINGS.value("PocketCameraPaletteIndex"))
		except (TypeError, ValueError):
			selection = None
		if selection is None or not 0 <= selection < len(self.PALETTES) or self.PALETTES[selection] != palette:
			selection = self.PALETTES.index(palette)
		self.CUR_PALETTE = selection
		self.cmbColor.setCurrentIndex(self.CUR_PALETTE)
		self.cmbColor.blockSignals(False)
		self.UpdatePaletteColorButtons()
		try:
			zoom = int(self.APP.SETTINGS.value("PocketCameraZoom"))
		except (TypeError, ValueError):
			zoom = default_zoom
		self.spnZoom.setValue(zoom)
		self.chkFrame.setChecked(self.APP.SETTINGS.value("PocketCameraFrame", default="disabled") == "enabled")
		self.CUR_EXPORT_PATH = self.APP.SETTINGS.value("LastDirPocketCamera") or QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)

	def AddPaletteColorButtons(self, layout):
		self.colorButtons = []
		for index in range(4):
			button = QtWidgets.QToolButton()
			button.setFixedSize(21, 21)
			button.setCursor(QtCore.Qt.PointingHandCursor)
			button.clicked.connect(functools.partial(self.ChoosePaletteColor, index))
			layout.addWidget(button)
			self.colorButtons.append(button)

	def UpdatePaletteColorButtons(self):
		palette = self.PALETTES[self.cmbColor.currentIndex()]
		for index, button in enumerate(self.colorButtons):
			color = QtGui.QColor(*palette[index * 3:index * 3 + 3])
			button.setStyleSheet("background-color: {}; border: 1px solid #777;".format(color.name()))
			# button.setToolTip(color.name().upper())

	def SelectPalette(self, index):
		self.UpdatePaletteColorButtons()
		self.ApplyPalette()

	def ChoosePaletteColor(self, index, checked=False):
		palette = self.PALETTES[self.cmbColor.currentIndex()]
		start = index * 3
		color = QtGui.QColor(*palette[start:start + 3])
		chosen = QtWidgets.QColorDialog.getColor(color, self)
		if not chosen.isValid() or chosen == color: return
		if self.cmbColor.currentIndex() != self.CUSTOM_PALETTE_INDEX:
			self.PALETTES[self.CUSTOM_PALETTE_INDEX] = list(palette)
		self.PALETTES[self.CUSTOM_PALETTE_INDEX][start:start + 3] = [chosen.red(), chosen.green(), chosen.blue()]
		self.cmbColor.setCurrentIndex(self.CUSTOM_PALETTE_INDEX)
		self.SelectPalette(self.CUSTOM_PALETTE_INDEX)

	def GetFrame(self):
		if not self.chkFrame.isChecked(): return False
		if self.FRAME is None:
			try:
				path = os.path.join(self.CONFIG_PATH, "pc_frame.png")
				if not os.path.exists(path):
					shutil.copy(os.path.join(self.APP_PATH, "res", "pc_frame.png"), path)
				with Image.open(path) as frame: self.FRAME = frame.convert("RGB")
			except OSError as error:
				self.chkFrame.blockSignals(True)
				self.chkFrame.setChecked(False)
				self.chkFrame.blockSignals(False)
				QtWidgets.QMessageBox.critical(self, self.windowTitle(),
					__("The photo frame could not be loaded: {error}", error=str(error)), QtWidgets.QMessageBox.Ok)
				return False
		return self.FRAME

	def SavePicture(self, index=None, path="", image=None, rotation=0):
		try:
			if image is None: image = self.CUR_PC.GetPicture(index)
			image, zoom = image.copy(), self.spnZoom.value()
			frame = False if index == 31 else self.GetFrame()
			select_path = path == ""
			if select_path:
				name = "IMG_PC.png" if index is None else "IMG_PC{:02d}.png".format(index + 1)
				path = QtWidgets.QFileDialog.getSaveFileName(self, __("Save Photo"), os.path.join(self.CUR_EXPORT_PATH, name),
					__("PNG files") + " (*.png);;" + __("BMP files") + " (*.bmp);;" + __("GIF files") + " (*.gif);;" + __("JPEG files") + " (*.jpg);;" + __("All files") + " (*.*)")[0]
			if not path: return
			if not os.path.splitext(path)[1]:
				path += ".png"
				if select_path and os.path.exists(path):
					answer = QtWidgets.QMessageBox.warning(self, AppInfo.NAME, __("The target file “{file_path}” already exists.\nDo you want to overwrite it?", file_path=path), QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Cancel)
					if answer != QtWidgets.QMessageBox.Ok: return
			title = "Photo" if index is None else "Game Face" if index == 30 else "Last Seen Image" if index == 31 else "Photo {:02d}".format(index + 1)
			PocketCamera.ExportImage(image, path, zoom, frame, title, rotation)
			self.CUR_EXPORT_PATH = os.path.dirname(path)
			self.APP.SETTINGS.setValue("LastDirPocketCamera", self.CUR_EXPORT_PATH)
		except (OSError, ValueError) as error:
			QtWidgets.QMessageBox.critical(self, self.windowTitle(),
				__("The photo could not be saved: {error}", error=str(error)), QtWidgets.QMessageBox.Ok)

	def hideEvent(self, event):
		self.APP.SETTINGS.setValue("PocketCameraPalette", json.dumps(self.PALETTES[self.cmbColor.currentIndex()]))
		self.APP.SETTINGS.setValue("PocketCameraCustomPalette", json.dumps(self.PALETTES[self.CUSTOM_PALETTE_INDEX]))
		self.APP.SETTINGS.setValue("PocketCameraPaletteIndex", str(self.cmbColor.currentIndex()))
		self.APP.SETTINGS.setValue("PocketCameraZoom", str(self.spnZoom.value()))
		self.APP.SETTINGS.setValue("PocketCameraFrame", "enabled" if self.chkFrame.isChecked() else "disabled")
		self.APP.SETTINGS.setValue("LastDirPocketCamera", self.CUR_EXPORT_PATH)
		self.APP.activateWindow()
		super().hideEvent(event)


class PocketCameraLiveThread(QtCore.QObject):
	frameReady = QtCore.Signal(object)
	finished = QtCore.Signal()

	def __init__(self, device):
		super().__init__()
		self.DEVICE = device
		self.CAMERA = PocketCameraCapture(device)
		self.SETTINGS = (PocketCameraCapture.DEFAULT_BRIGHTNESS, PocketCameraCapture.DEFAULT_CONTRAST, 1, True)
		self.LOCK, self.ERROR = threading.Lock(), None
		self.RESUME = threading.Event()
		self.RESUME.set()
		self.STOP = threading.Event()
		self.WORKER = threading.Thread(target=self.run, daemon=True)

	def start(self):
		self.WORKER.start()

	def requestInterruption(self):
		self.STOP.set()
		self.RESUME.set()

	def Abort(self):
		self.requestInterruption()
		self.CAMERA.Abort()

	def SetControls(self, brightness, contrast, frequency=1, vertical_sharpening=True):
		with self.LOCK: self.SETTINGS = (brightness, contrast, frequency, vertical_sharpening)

	def SetPaused(self, paused):
		if paused: self.RESUME.clear()
		else: self.RESUME.set()

	def run(self):
		try:
			with self.CAMERA as camera:
				while not self.STOP.is_set():
					if not self.RESUME.wait(0.1): continue
					if self.STOP.is_set(): break
					with self.LOCK: settings = self.SETTINGS
					self.frameReady.emit(camera.Capture(*settings))
		except Exception as error:
			if not self.CAMERA.ABORTED.is_set(): self.ERROR = str(error)
		finally:
			self.finished.emit()


class PocketCameraLiveImage(QtWidgets.QLabel):
	clicked = QtCore.Signal()
	doubleClicked = QtCore.Signal()

	def __init__(self, parent=None):
		super().__init__(parent)
		self.PIXMAP = None
		self.IMAGE_ONLY = False
		self.DRAG_POSITION, self.DRAGGED = None, False
		self.CLICK_TIMER = QtCore.QTimer(self)
		self.CLICK_TIMER.setSingleShot(True)
		self.CLICK_TIMER.timeout.connect(self.clicked.emit)
		self.setFixedSize(128 * 4 + 2, 121 * 4 + 2)
		self.setStyleSheet(PocketCameraDialog.PREVIEW_STYLE)
		self.setCursor(QtCore.Qt.PointingHandCursor)

	def SetFrame(self, image):
		self.PIXMAP = bitmap2pixmap(image)
		self.update()

	def mousePressEvent(self, event):
		if event.button() == QtCore.Qt.LeftButton:
			self.DRAG_POSITION = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
			self.DRAGGED = False
		else: super().mousePressEvent(event)

	def mouseMoveEvent(self, event):
		if self.IMAGE_ONLY and self.DRAG_POSITION is not None and event.buttons() & QtCore.Qt.LeftButton:
			position = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
			delta = position - self.DRAG_POSITION
			if self.DRAGGED or delta.manhattanLength() >= QtWidgets.QApplication.startDragDistance():
				self.CLICK_TIMER.stop()
				self.window().move(self.window().pos() + delta)
				self.DRAG_POSITION = position
				self.DRAGGED = True
		else: super().mouseMoveEvent(event)

	def mouseReleaseEvent(self, event):
		if event.button() == QtCore.Qt.LeftButton:
			if self.DRAG_POSITION is not None and not self.DRAGGED:
				self.CLICK_TIMER.start(QtWidgets.QApplication.doubleClickInterval())
			self.DRAG_POSITION = None
		else: super().mouseReleaseEvent(event)

	def mouseDoubleClickEvent(self, event):
		if event.button() == QtCore.Qt.LeftButton:
			self.CLICK_TIMER.stop()
			self.DRAG_POSITION = None
			self.doubleClicked.emit()
		else: super().mouseDoubleClickEvent(event)

	def paintEvent(self, event):
		super().paintEvent(event)
		painter = QtGui.QPainter(self)
		painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform, False)
		painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
		painter.fillRect(self.contentsRect(), QtCore.Qt.black)
		if self.PIXMAP: painter.drawPixmap(self.contentsRect(), self.PIXMAP)
		painter.end()


class PocketCameraLiveWindow(PocketCameraDialog):
	def __init__(self, app, icon=None, config_path=".", app_path="."):
		super().__init__(app)
		self.APP, self.THREAD, self.CLOSING = app, None, False
		self.IMAGE, self.PAUSED = None, False
		self.FATAL_ERROR = False
		self.CONFIG_PATH, self.APP_PATH = config_path, app_path
		self.PICTURE_SIZE, self.SCREEN = (128, 121), None
		self.FITTING = False
		self.SWITCHING_VIEW = False
		self.CLOSE_TIMER = QtCore.QTimer(self)
		self.CLOSE_TIMER.setSingleShot(True)
		self.CLOSE_TIMER.timeout.connect(self.ForceClose)
		self.FRAME_TIMES = deque(maxlen=60)
		self.IMAGES_TAKEN, self.FRAMERATE = 0, 0.0
		self.FPS_TIMER = QtCore.QTimer(self)
		self.FPS_TIMER.setInterval(1000)
		self.FPS_TIMER.timeout.connect(self.UpdateFrameRate)
		flags = self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
		flags |= QtCore.Qt.MSWindowsFixedSizeDialogHint | QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint
		self.setWindowFlags(flags)
		self.setModal(True)
		if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
		outer_layout = QtWidgets.QVBoxLayout(self)
		outer_layout.setContentsMargins(0, 0, 0, 0)
		outer_layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
		self.controls = QtWidgets.QWidget(self)
		outer_layout.addWidget(self.controls)
		layout = QtWidgets.QVBoxLayout(self.controls)
		layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
		self.preview = PocketCameraLiveImage(self)
		self.preview.clicked.connect(self.TogglePaused)
		self.preview.doubleClicked.connect(self.ToggleImageOnly)
		self.grpPhotoView = QtWidgets.QGroupBox(__("Live View"))
		preview_layout = QtWidgets.QVBoxLayout(self.grpPhotoView)
		preview_layout.setContentsMargins(-1, 3, -1, -1)
		preview_layout.addWidget(self.preview, 0, QtCore.Qt.AlignCenter)
		self.lblCaptureStatus = QtWidgets.QLabel()
		self.lblCaptureStatus.setAlignment(QtCore.Qt.AlignCenter)
		self.lblCaptureStatus.setWordWrap(True)
		preview_layout.addWidget(self.lblCaptureStatus)
		self.UpdateFrameRate()
		layout.addWidget(self.grpPhotoView)
		options = QtWidgets.QHBoxLayout()
		layout.addLayout(options)
		self.cmbColor = QtWidgets.QComboBox()
		self.cmbColor.setStyleSheet("combobox-popup: 0;")
		self.cmbColor.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
		self.cmbColor.setMinimumContentsLength(12)
		options.addWidget(QtWidgets.QLabel(__("Color Palette:")))
		options.addWidget(self.cmbColor, 1)
		self.AddPaletteColorButtons(options)
		view_options = QtWidgets.QHBoxLayout()
		layout.addLayout(view_options)
		view_options.addWidget(QtWidgets.QLabel(__("Scaling:")))
		self.spnZoom = QtWidgets.QSpinBox()
		self.spnZoom.setRange(1, 10)
		self.spnZoom.setSuffix("×")
		self.spnZoom.setValue(3)
		view_options.addWidget(self.spnZoom)
		view_options.addWidget(QtWidgets.QLabel(__("Rotation:")))
		self.cmbRotation = QtWidgets.QComboBox()
		self.cmbRotation.addItems(("0°", "90°", "180°", "270°"))
		view_options.addWidget(self.cmbRotation)
		self.chkFrame = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Frame"))
		view_options.addWidget(self.chkFrame)
		self.chkOverclock = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Overclock"))
		self.chkOverclock.setEnabled(self.APP.CONN.GetName() != "Game Bub")
		# self.chkOverclock.setToolTip(__("Use a 2 MHz camera clock instead of 1 MHz."))
		view_options.addWidget(self.chkOverclock)
		self.chkVerticalSharpening = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Image Sharpening"))
		self.chkVerticalSharpening.setChecked(True)
		self.chkVerticalSharpening.toggled.connect(self.UpdateControls)
		view_options.addWidget(self.chkVerticalSharpening)
		view_options.addStretch()
		controls = QtWidgets.QGridLayout()
		layout.addLayout(controls)
		self.sliders = []
		for row, (title, default) in enumerate(((__("Brightness"), PocketCameraCapture.DEFAULT_BRIGHTNESS),
				(__("Contrast"), PocketCameraCapture.DEFAULT_CONTRAST))):
			label = QtWidgets.QLabel(title)
			slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
			slider.setRange(1, 16)
			slider.setPageStep(1)
			slider.setValue(default)
			label.setBuddy(slider)
			value = QtWidgets.QLabel(str(default))
			value.setMinimumWidth(value.fontMetrics().horizontalAdvance("16"))
			slider.valueChanged.connect(lambda number, label=value: label.setText(str(number)))
			slider.valueChanged.connect(self.UpdateControls)
			controls.addWidget(label, row, 0)
			controls.addWidget(slider, row, 1)
			controls.addWidget(value, row, 2)
			self.sliders.append(slider)
		actions = QtWidgets.QHBoxLayout()
		self.btnSaveImage = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Save Current Image"))
		self.btnSaveImage.setStyleSheet("padding: 5px 15px;")
		self.btnSaveImage.setEnabled(False)
		self.btnSaveImage.clicked.connect(self.SaveCurrentPicture)
		actions.addWidget(self.btnSaveImage)
		actions.addStretch()
		self.btnClose = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Close"))
		self.btnClose.setStyleSheet("padding: 5px 15px;")
		self.btnClose.clicked.connect(self.reject)
		actions.addWidget(self.btnClose)
		layout.addLayout(actions)
		self.LoadSettings(default_zoom=3)
		try:
			rotation = int(self.APP.SETTINGS.value("PocketCameraLiveRotation"))
		except (TypeError, ValueError):
			rotation = 0
		self.cmbRotation.setCurrentIndex(rotation // 90 if rotation in (0, 90, 180, 270) else 0)
		self.cmbColor.activated.connect(self.SelectPalette)
		self.spnZoom.valueChanged.connect(self.UpdateZoomLimit)
		self.cmbRotation.currentIndexChanged.connect(self.UpdateZoomLimit)
		self.chkFrame.toggled.connect(self.UpdateZoomLimit)
		self.chkOverclock.toggled.connect(self.UpdateControls)
		self.UpdateZoomLimit()

	def ToggleImageOnly(self):
		if self.CLOSING: return
		self.SWITCHING_VIEW = True
		try:
			if not self.preview.IMAGE_ONLY:
				self.NORMAL_POSITION = self.pos()
				self.NORMAL_FLAGS = self.windowFlags()
				self.IMAGE_POSITION = self.preview.mapToGlobal(self.preview.contentsRect().topLeft())
				size = self.preview.contentsRect().size()
				self.preview.IMAGE_ONLY = True
				self.preview.setParent(self)
				self.controls.hide()
				self.layout().addWidget(self.preview)
				self.preview.setStyleSheet("border: none;")
				self.preview.setFixedSize(size)
				self.setWindowFlags((self.NORMAL_FLAGS & ~QtCore.Qt.MSWindowsFixedSizeDialogHint) | QtCore.Qt.FramelessWindowHint)
				position = self.IMAGE_POSITION
			else:
				position = self.NORMAL_POSITION + self.pos() - self.IMAGE_POSITION
				self.preview.IMAGE_ONLY = False
				self.layout().removeWidget(self.preview)
				self.grpPhotoView.layout().insertWidget(0, self.preview, 0, QtCore.Qt.AlignCenter)
				self.preview.setStyleSheet(self.PREVIEW_STYLE)
				self.controls.show()
				self.setWindowFlags(self.NORMAL_FLAGS)
			self.preview.show()
			self.show()
			self.move(position)
			self.KeepOnScreen()
		finally:
			self.SWITCHING_VIEW = False

	def run(self):
		if self.THREAD is not None or self.CLOSING or self.FATAL_ERROR: return
		self.THREAD = PocketCameraLiveThread(self.APP.CONN)
		self.THREAD.frameReady.connect(self.ShowFrame)
		self.THREAD.finished.connect(self.ThreadFinished)
		self.UpdateControls()
		self.show()
		self.SetPaused(False)
		self.FPS_TIMER.start()
		self.THREAD.start()

	def UpdateControls(self, value=None):
		if self.THREAD is not None:
			self.THREAD.SetControls(self.sliders[0].value(), self.sliders[1].value(),
				frequency=2 if self.chkOverclock.isChecked() else 1, vertical_sharpening=self.chkVerticalSharpening.isChecked())

	def ShowFrame(self, image):
		if self.CLOSING or self.PAUSED: return
		self.IMAGE = image.copy()
		self.btnSaveImage.setEnabled(True)
		self.RefreshPicture()
		now = time.monotonic()
		self.FRAME_TIMES.append(now)
		while len(self.FRAME_TIMES) > 2 and self.FRAME_TIMES[1] < now - 2:
			self.FRAME_TIMES.popleft()
		self.IMAGES_TAKEN += 1
		self.UpdateCaptureStatus()

	def UpdateCaptureStatus(self):
		self.lblCaptureStatus.setText(
			__("Images taken: {count}, Framerate: {framerate} fps",
	  		count=self.IMAGES_TAKEN,
			framerate=format_decimal(self.FRAMERATE, precision=1))
		)

	def UpdateFrameRate(self):
		self.FRAMERATE = 0.0
		if len(self.FRAME_TIMES) >= 2 and not self.PAUSED and not self.CLOSING:
			# N completed frames span N-1 intervals, independent of the display timer.
			elapsed = self.FRAME_TIMES[-1] - self.FRAME_TIMES[0]
			intervals = len(self.FRAME_TIMES) - 1
			if elapsed > 0 and time.monotonic() - self.FRAME_TIMES[-1] <= max(2, 2 * elapsed / intervals):
				self.FRAMERATE = intervals / elapsed
			else:
				self.FRAME_TIMES.clear()
		title = AppInfo.NAME + " – " + __("Game Boy Camera Live View")
		if self.PAUSED: title += " (" + __("Paused") + ")"
		self.setWindowTitle(title)
		self.UpdateCaptureStatus()

	def RefreshPicture(self, value=None):
		if self.IMAGE is not None:
			self.IMAGE.putpalette(self.PALETTES[self.cmbColor.currentIndex()])
			image = PocketCamera.AddFrame(self.IMAGE, self.GetFrame())
			rotation = self.cmbRotation.currentIndex() * 90
			if rotation: image = image.rotate(-rotation, expand=True)
			self.preview.SetFrame(image)

	def ApplyPalette(self):
		self.RefreshPicture()

	def UpdateZoomLimit(self, value=None):
		if self.FITTING or self.preview.IMAGE_ONLY: return
		self.FITTING = True
		try:
			frame = self.GetFrame()
			self.PICTURE_SIZE = frame.size if frame is not False and frame.width >= 160 and frame.height >= 144 else (128, 121)
			width, height = self.PICTURE_SIZE
			if self.cmbRotation.currentIndex() % 2: width, height = height, width
			screen = self.SCREEN or self.screen()
			available = screen.availableGeometry()
			decoration = self.frameGeometry().size() - self.size()
			if not self.isVisible():
				border = self.style().pixelMetric(QtWidgets.QStyle.PM_DefaultFrameWidth) * 2
				decoration = QtCore.QSize(border, border + self.style().pixelMetric(QtWidgets.QStyle.PM_TitleBarHeight))
			for maximum in range(10, 0, -1):
				self.preview.setFixedSize(width * maximum + 2, height * maximum + 2)
				self.grpPhotoView.layout().invalidate()
				self.grpPhotoView.layout().activate()
				self.controls.layout().invalidate()
				self.controls.layout().activate()
				self.layout().invalidate()
				required = self.controls.layout().totalMinimumSize() + decoration
				if required.width() <= available.width() and required.height() <= available.height(): break
			self.spnZoom.blockSignals(True)
			self.spnZoom.setMaximum(maximum)
			self.spnZoom.blockSignals(False)
			zoom = self.spnZoom.value()
			self.preview.setFixedSize(width * zoom + 2, height * zoom + 2)
			self.grpPhotoView.layout().invalidate()
			self.grpPhotoView.layout().activate()
			self.controls.layout().invalidate()
			self.controls.layout().activate()
			self.layout().invalidate()
			self.layout().activate()
			self.RefreshPicture()
			self.KeepOnScreen()
			QtCore.QTimer.singleShot(10, self.KeepOnScreen)
		finally:
			self.FITTING = False

	def KeepOnScreen(self):
		if not self.isVisible(): return
		available = (self.SCREEN or self.screen()).availableGeometry()
		bounds = self.frameGeometry()
		position = QtCore.QPoint(max(available.left(), min(bounds.left(), available.right() - bounds.width() + 1)),
			max(available.top(), min(bounds.top(), available.bottom() - bounds.height() + 1)))
		self.move(self.pos() + position - bounds.topLeft())

	def UpdateScreen(self, screen):
		if self.SCREEN is not None:
			self.SCREEN.availableGeometryChanged.disconnect(self.UpdateZoomLimit)
			self.SCREEN.logicalDotsPerInchChanged.disconnect(self.UpdateZoomLimit)
		self.SCREEN = screen
		screen.availableGeometryChanged.connect(self.UpdateZoomLimit)
		screen.logicalDotsPerInchChanged.connect(self.UpdateZoomLimit)
		self.UpdateZoomLimit()

	def showEvent(self, event):
		super().showEvent(event)
		if self.SCREEN is None: self.windowHandle().screenChanged.connect(self.UpdateScreen)
		self.UpdateScreen(self.windowHandle().screen())
		QtCore.QTimer.singleShot(0, self.UpdateZoomLimit)

	def TogglePaused(self):
		if self.CLOSING or self.FATAL_ERROR: return
		if self.THREAD is None: self.run()
		else: self.SetPaused(not self.PAUSED)

	def SetPaused(self, paused):
		if self.CLOSING: return
		self.PAUSED = paused or self.THREAD is None
		if self.THREAD is not None: self.THREAD.SetPaused(paused)
		self.FRAME_TIMES.clear()
		self.UpdateFrameRate()

	def SaveCurrentPicture(self):
		if self.IMAGE is None or self.CLOSING: return
		paused = self.PAUSED
		self.SetPaused(True)
		try:
			self.SavePicture(image=self.IMAGE, rotation=self.cmbRotation.currentIndex() * 90)
		finally:
			self.SetPaused(paused)

	def hideEvent(self, event):
		if self.SWITCHING_VIEW:
			QtWidgets.QDialog.hideEvent(self, event)
			return
		self.APP.SETTINGS.setValue("PocketCameraLiveRotation", str(self.cmbRotation.currentIndex() * 90))
		super().hideEvent(event)

	def ThreadFinished(self):
		if self.THREAD is None: return
		self.FPS_TIMER.stop()
		self.CLOSE_TIMER.stop()
		thread, error = self.THREAD, self.THREAD.ERROR
		self.THREAD = None
		self.FATAL_ERROR = thread.DEVICE.DEVICE is None or thread.DEVICE.ERROR
		if self.FATAL_ERROR:
			if self.APP.CONN is thread.DEVICE: self.APP.DisconnectDevice()
			for widget in self.sliders + [self.chkOverclock, self.chkVerticalSharpening]: widget.setEnabled(False)
		thread.deleteLater()
		if self.CLOSING:
			super().reject()
			return
		self.SetPaused(True)
		if error is not None: QtWidgets.QMessageBox.critical(self, self.windowTitle(), error, QtWidgets.QMessageBox.Ok)

	def ForceClose(self):
		self.CLOSING = True
		self.FPS_TIMER.stop()
		self.CLOSE_TIMER.stop()
		thread, self.THREAD = self.THREAD, None
		try:
			if thread is not None:
				thread.frameReady.disconnect(self.ShowFrame)
				thread.finished.disconnect(self.ThreadFinished)
				thread.finished.connect(thread.deleteLater)
				thread.Abort()
				if self.APP.CONN is thread.DEVICE: self.APP.DisconnectDevice()
		finally:
			super().reject()

	def reject(self):
		if self.THREAD is not None:
			if self.CLOSING or self.THREAD.CAMERA.CLOSING:
				self.ForceClose()
				return
			self.CLOSING = True
			self.FPS_TIMER.stop()
			self.UpdateFrameRate()
			self.btnSaveImage.setEnabled(False)
			self.btnClose.setText(c__("Button (& = Keyboard Shortcut)", "&Abort"))
			for slider in self.sliders: slider.setEnabled(False)
			self.cmbColor.setEnabled(False)
			self.spnZoom.setEnabled(False)
			self.cmbRotation.setEnabled(False)
			self.chkFrame.setEnabled(False)
			self.chkOverclock.setEnabled(False)
			self.chkVerticalSharpening.setEnabled(False)
			self.THREAD.requestInterruption()
			self.CLOSE_TIMER.start(5000)
			return
		super().reject()

	def closeEvent(self, event):
		event.ignore()
		self.reject()

class PocketCameraWindow(PocketCameraDialog):
	CUR_PIC = None
	CUR_THUMBS = None
	CUR_INDEX = 0
	CUR_BICUBIC = False
	CUR_FILE = ""
	CUR_EXPORT_PATH = "."
	CUR_PC = None
	CUR_PALETTE = 3
	APP_PATH = "."
	CONFIG_PATH = "."
	APP = None
	FORCE_EXIT = False

	def __init__(self, app, file=None, icon=None, config_path=".", app_path="."):
		QtWidgets.QDialog.__init__(self, app)
		self.setAcceptDrops(True)
		if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))

		self.FORCE_EXIT = False
		self.CUR_FILE = file
		self.CONFIG_PATH = config_path
		self.APP_PATH = app_path
		self.setWindowTitle(AppInfo.NAME + " – " + __("GB Camera Album Viewer"))
		flags = self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint
		flags |= QtCore.Qt.MSWindowsFixedSizeDialogHint | QtCore.Qt.CustomizeWindowHint | QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint | QtCore.Qt.WindowCloseButtonHint
		self.setWindowFlags(flags)

		self.layout = QtWidgets.QGridLayout()
		self.layout.setContentsMargins(-1, 8, -1, 8)
		self.layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
		self.layout_options1 = QtWidgets.QVBoxLayout()
		self.layout_options2 = QtWidgets.QVBoxLayout()
		self.layout_options3 = QtWidgets.QVBoxLayout()
		self.layout_photos = QtWidgets.QHBoxLayout()

		# Options
		self.grpOptions = QtWidgets.QGroupBox(__("Options"))
		grpOptionsLayout = QtWidgets.QVBoxLayout()
		grpOptionsLayout.setContentsMargins(-1, 3, -1, -1)
		self.rowOptions1 = QtWidgets.QHBoxLayout()
		self.lblColor = QtWidgets.QLabel(__("Color Palette:"))
		self.cmbColor = QtWidgets.QComboBox()
		self.cmbColor.setStyleSheet("combobox-popup: 0;")
		self.cmbColor.view().setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
		self.cmbColor.activated.connect(self.SelectPalette)
		self.cmbColor.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
		self.cmbColor.setCurrentIndex(-1)
		self.rowOptions1.addWidget(self.lblColor)
		self.rowOptions1.addWidget(self.cmbColor)
		self.AddPaletteColorButtons(self.rowOptions1)
		self.rowOptions1.addStretch(1)

		self.rowOptions2 = QtWidgets.QHBoxLayout()
		self.lblZoom = QtWidgets.QLabel(__("Saved Picture Scaling:"))
		self.spnZoom = QtWidgets.QSpinBox()
		self.spnZoom.setRange(1, 10)
		self.spnZoom.setSuffix("×")
		self.rowOptions2.addWidget(self.lblZoom)
		self.rowOptions2.addWidget(self.spnZoom)
		self.rowOptions2.addStretch(1)

		self.chkFrame = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "Save With &Frame"))
		self.rowOptions2.addWidget(self.chkFrame)

		grpOptionsLayout.addLayout(self.rowOptions1)
		grpOptionsLayout.addLayout(self.rowOptions2)
		self.grpOptions.setLayout(grpOptionsLayout)

		self.layout_options1.addWidget(self.grpOptions)

		rowActionsGeneral1 = QtWidgets.QHBoxLayout()
		self.btnOpenSRAM = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Open Save Data File"))
		self.btnOpenSRAM.setStyleSheet("padding: 5px 10px;")
		self.btnOpenSRAM.clicked.connect(self.btnOpenSRAM_Clicked)
		self.btnClose = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Close"))
		self.btnClose.setStyleSheet("padding: 5px 15px;")
		self.btnClose.clicked.connect(self.btnClose_Clicked)
		rowActionsGeneral1.addWidget(self.btnOpenSRAM)
		rowActionsGeneral1.addStretch()
		rowActionsGeneral1.addWidget(self.btnClose)
		self.layout_options3.addLayout(rowActionsGeneral1)

		# Photo Viewer
		self.grpPhotoView = QtWidgets.QGroupBox(__("Preview"))
		self.grpPhotoViewLayout = QtWidgets.QVBoxLayout()
		self.grpPhotoViewLayout.setContentsMargins(-1, 3, -1, -1)
		self.lblPhotoViewer = QtWidgets.QLabel(self)
		self.lblPhotoViewer.setMinimumSize(256, 223)
		self.lblPhotoViewer.setMaximumSize(256, 223)
		self.lblPhotoViewer.setStyleSheet(self.PREVIEW_STYLE)
		self.lblPhotoViewer.mousePressEvent = self.lblPhotoViewer_Clicked
		self.grpPhotoViewLayout.addWidget(self.lblPhotoViewer)

		# Actions below Viewer
		rowActionsGeneral2 = QtWidgets.QHBoxLayout()
		self.btnSavePhoto = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Save This Picture"))
		self.btnSavePhoto.setStyleSheet("padding: 5px 10px;")
		self.btnSavePhoto.clicked.connect(self.btnSavePhoto_Clicked)
		rowActionsGeneral2.addWidget(self.btnSavePhoto)
		self.btnSaveAll = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "Save &All Pictures"))
		self.btnSaveAll.setStyleSheet("padding: 5px 10px;")
		self.btnSaveAll.clicked.connect(self.btnSaveAll_Clicked)
		rowActionsGeneral2.addWidget(self.btnSaveAll)
		self.grpPhotoViewLayout.addLayout(rowActionsGeneral2)

		self.grpPhotoView.setLayout(self.grpPhotoViewLayout)

		# Photo List
		self.grpPhotoThumbs = QtWidgets.QGroupBox(__("Photo Album"))
		self.grpPhotoThumbsLayout = QtWidgets.QVBoxLayout()
		self.grpPhotoThumbsLayout.setSpacing(2)
		self.grpPhotoThumbsLayout.setContentsMargins(-1, 3, -1, -1)
		self.lblPhoto = []
		rowsPhotos = []
		for row in range(0, 5):
			rowsPhotos.append(QtWidgets.QHBoxLayout())
			rowsPhotos[row].setSpacing(2)
			for _ in range(0, 6):
				self.lblPhoto.append(QtWidgets.QLabel(self))
				self.lblPhoto[len(self.lblPhoto)-1].setMinimumSize(49, 43)
				self.lblPhoto[len(self.lblPhoto)-1].setMaximumSize(49, 43)
				self.lblPhoto[len(self.lblPhoto)-1].mousePressEvent = functools.partial(self.lblPhoto_Clicked, index=len(self.lblPhoto)-1)
				self.lblPhoto[len(self.lblPhoto)-1].setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
				self.lblPhoto[len(self.lblPhoto)-1].setAlignment(QtCore.Qt.AlignCenter)
				self.lblPhoto[len(self.lblPhoto)-1].setStyleSheet("border-top: 1px solid #adadad; border-left: 1px solid #adadad; border-bottom: 1px solid #fefefe; border-right: 1px solid #fefefe;")
				rowsPhotos[row].addWidget(self.lblPhoto[len(self.lblPhoto)-1])
			self.grpPhotoThumbsLayout.addLayout(rowsPhotos[row])

		rowActionsGeneral3 = QtWidgets.QHBoxLayout()
		self.btnShowGameFace = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Game Face"))
		self.btnShowGameFace.setStyleSheet("padding: 5px 10px;")
		self.btnShowGameFace.clicked.connect(self.btnShowGameFace_Clicked)
		rowActionsGeneral3.addWidget(self.btnShowGameFace)
		self.btnShowLastSeen = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Last Seen Image"))
		self.btnShowLastSeen.setStyleSheet("padding: 5px 10px;")
		self.btnShowLastSeen.clicked.connect(self.btnShowLastSeen_Clicked)
		rowActionsGeneral3.addWidget(self.btnShowLastSeen)
		self.grpPhotoThumbsLayout.addStretch()
		self.grpPhotoThumbsLayout.addLayout(rowActionsGeneral3)

		self.grpPhotoThumbsLayout.setAlignment(QtCore.Qt.AlignTop)
		self.grpPhotoThumbs.setLayout(self.grpPhotoThumbsLayout)

		self.layout_photos.addWidget(self.grpPhotoThumbs)
		self.layout_photos.addWidget(self.grpPhotoView)

		self.layout.addLayout(self.layout_options1, 0, 0)
		self.layout.addLayout(self.layout_options2, 1, 0)
		self.layout.addLayout(self.layout_photos, 2, 0)
		self.layout.addLayout(self.layout_options3, 3, 0)
		self.setLayout(self.layout)

		self.APP = app
		self.LoadSettings()

		if self.CUR_FILE is not None:
			if self.OpenFile(self.CUR_FILE) is False:
				self.FORCE_EXIT = True
				return

		self.SetColors()

		self.btnSaveAll.setDefault(True)
		self.btnSaveAll.setAutoDefault(True)
		self.btnSaveAll.setFocus()

	def run(self):
		if self.FORCE_EXIT:
			self.reject()
			return
		self.layout.update()
		self.layout.activate()
		screenGeometry = QDesktopWidget().screenGeometry(self)
		x = (screenGeometry.width() - self.width()) / 2
		y = (screenGeometry.height() - self.height()) / 2
		self.move(x, y)
		self.show()

	def SetColors(self):
		if self.CUR_PC is None: return
		self.CUR_PALETTE = self.cmbColor.currentIndex()
		self.CUR_PC.SetPalette(self.PALETTES[self.CUR_PALETTE])
		self.BuildPhotoList()
		self.UpdateViewer(self.CUR_INDEX)

	def ApplyPalette(self):
		self.SetColors()

	def OpenFile(self, file):
		if isinstance(file, bytearray) and len(file) == 0x100000 or isinstance(file, str) and os.path.getsize(file) == 0x100000:
			dlg_args = {
				"title":"Photo!",
				"intro":__("A “Photo!” save file was detected. Please select the roll of pictures that you would like to load."),
				"params": [
					[ "index", "cmb", __("Film roll:"), [ __("Current Save Data") ] + [ __("“{flash_directory}” Slot {number}", flash_directory="Flash Directory", number="{:d}".format(l)) for l in range(1, 8) ], 0 ],
				]
			}
			dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
			if dlg.exec_() == 1:
				result = dlg.GetResult()
				index = result["index"].currentIndex()
				if isinstance(file, str):
					with open(file, "rb") as f:
						file = bytearray(f.read())
				file = file[0x20000 * index:][:0x20000]
			else:
				self.CUR_PC = None
				return False

		try:
			self.CUR_PC = PocketCamera()
			if self.CUR_PC.LoadFile(file) == False:
				self.CUR_PC = None
				QtWidgets.QMessageBox.critical(self, AppInfo.NAME, __("The save data file couldn’t be loaded."), QtWidgets.QMessageBox.Ok)
				return False
			self.CUR_FILE = file
			if self.CUR_EXPORT_PATH == "":
				self.CUR_EXPORT_PATH = os.path.dirname(self.CUR_FILE)
			self.UpdateViewer(0)
			self.SetColors()
			return True
		except:
			self.CUR_PC = None
			QtWidgets.QMessageBox.critical(self, AppInfo.NAME, __("An error occured while trying to load the save data file."), QtWidgets.QMessageBox.Ok)
			return False

	def lblPhoto_Clicked(self, event, index):
		if event.button() == QtCore.Qt.LeftButton:
			self.CUR_INDEX = index
			self.UpdateViewer(self.CUR_INDEX)

	def lblPhotoViewer_Clicked(self, event):
		if event.button() == QtCore.Qt.LeftButton:
			self.CUR_BICUBIC = not self.CUR_BICUBIC
			self.UpdateViewer(self.CUR_INDEX)

	def btnOpenSRAM_Clicked(self):
		last_dir = self.APP.SETTINGS.value("LastDirSaveDataDMG")
		if last_dir is None: last_dir = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)
		path = QtWidgets.QFileDialog.getOpenFileName(self, __("Open GB Camera Save Data File"), last_dir, __("Save Data File") + " (*.sav);;" + __("All Files") + " (*.*)")[0]
		if (path == ""): return
		if self.OpenFile(path) is True:
			self.APP.SETTINGS.setValue("LastDirSaveDataDMG", os.path.dirname(path))

	def btnShowGameFace_Clicked(self, event):
		self.UpdateViewer(30)
		self.CUR_INDEX = 30

	def btnShowLastSeen_Clicked(self, event):
		self.UpdateViewer(31)
		self.CUR_INDEX = 31

	def btnSaveAll_Clicked(self, event):
		if self.CUR_PC is None: return
		path = self.CUR_EXPORT_PATH + os.sep + "IMG_PC.png"
		path = QtWidgets.QFileDialog.getSaveFileName(self, __("Export all pictures"), path, __("PNG files") + " (*.png);;" + __("BMP files") + " (*.bmp);;" + __("GIF files") + " (*.gif);;" + __("JPEG files") + " (*.jpg);;" + __("All files") + " (*.*)")[0]
		if path == "": return
		self.CUR_EXPORT_PATH = os.path.dirname(path)

		name, ext = os.path.splitext(path)
		files = [name + "{:02d}".format(i) + (ext or ".png") for i in range(1, 33)]
		for file in files:
			if os.path.exists(file):
				answer = QtWidgets.QMessageBox.warning(self, AppInfo.NAME, __("There are already pictures that use the same file names. If you continue, these files will be overwritten."), QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
				if answer == QtWidgets.QMessageBox.Ok:
					break
				elif answer == QtWidgets.QMessageBox.Cancel:
					return

		for i, file in enumerate(files):
			self.SavePicture(i, path=file)

	def btnSavePhoto_Clicked(self, event):
		if self.CUR_PC is None: return
		self.SavePicture(self.CUR_INDEX)

	def btnClose_Clicked(self, event):
		self.FORCE_EXIT = True
		self.reject()

	def closeEvent(self, event):
		event.ignore()
		self.btnClose_Clicked(None)

	def BuildPhotoList(self):
		cam = self.CUR_PC
		self.CUR_THUMBS = [None] * 30
		for i in range(0, 30):
			pic = cam.GetPicture(i).convert("RGBA")
			self.lblPhoto[i].setToolTip("")
			if cam.IsEmpty(i):
				pass
			elif cam.IsDeleted(i):
				draw_bg = Image.new("RGBA", pic.size)
				draw = ImageDraw.Draw(draw_bg)
				draw.line([0, 0, 128, 112], fill=(255, 0, 0, 192), width=8)
				draw.line([0, 112, 128, 0], fill=(255, 0, 0, 192), width=8)
				pic.paste(draw_bg, mask=draw_bg)
				self.lblPhoto[i].setToolTip(__("This picture was marked as “deleted” and may be overwritten when you take new pictures."))
			self.CUR_THUMBS[i] = ImageQt(pic.resize((47, 41), Image.Resampling.HAMMING))
			qpixmap = QtGui.QPixmap.fromImage(self.CUR_THUMBS[i])
			self.lblPhoto[i].setPixmap(qpixmap)

	def UpdateViewer(self, index, scale_factor=4):
		resampler = Image.Resampling.NEAREST
		if self.CUR_BICUBIC or index == 31: resampler = Image.Resampling.BICUBIC
		if resampler == Image.Resampling.BICUBIC: scale_factor = 0.5
		cam = self.CUR_PC
		if cam is None: return

		for i in range(0, 30):
			self.lblPhoto[i].setStyleSheet("border-top: 1px solid #adadad; border-left: 1px solid #adadad; border-bottom: 1px solid #ffffff; border-right: 1px solid #ffffff;")

		self.CUR_PIC = ImageQt(cam.GetPicture(index).resize((int(256 * scale_factor), int(224 * scale_factor)), resampler))
		if index < 30:
			self.lblPhoto[index].setStyleSheet("border: 3px solid green; padding: 1px;")

		qpixmap = QtGui.QPixmap.fromImage(self.CUR_PIC)
		qpixmap.setDevicePixelRatio(scale_factor)
		self.lblPhotoViewer.setPixmap(qpixmap)

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
		if e.mimeData().hasUrls:
			for url in e.mimeData().urls():
				fn = str(url.toLocalFile())
				if fn == "":
					fn = urllib.parse.unquote(str(QtCore.QUrl(str(url.toString())).toLocalFile() or url.path()))

				fn_split = os.path.splitext(os.path.abspath(fn))
				if fn_split[1] == ".sav":
					return True
		return False

	def dropEvent(self, e):
		if e.mimeData().hasUrls:
			e.setDropAction(QtCore.Qt.CopyAction)
			e.accept()
			for url in e.mimeData().urls():
				fn = str(url.toLocalFile())
				if fn == "":
					fn = urllib.parse.unquote(str(QtCore.QUrl(str(url.toString())).toLocalFile() or url.path()))

				fn_split = os.path.splitext(os.path.abspath(fn))
				if fn_split[1] == ".sav":
					self.OpenFile(fn)
		else:
			e.ignore()
