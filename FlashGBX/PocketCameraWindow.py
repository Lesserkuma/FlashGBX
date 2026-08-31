# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import functools, os, json, shutil, urllib.parse
from .i18n import __, c__
from PIL.ImageQt import ImageQt
from PIL import Image, ImageDraw
from .pyside import QtCore, QtWidgets, QtGui, QDesktopWidget
from .PocketCamera import PocketCamera
from .UserInputDialog import UserInputDialog
from .app import AppInfo

class PocketCameraWindow(QtWidgets.QDialog):
	CUR_PIC = None
	CUR_THUMBS = None
	CUR_INDEX = 0
	CUR_BICUBIC = False
	CUR_FILE = ""
	CUR_FILE_PATH = None
	CUR_FULL_FILE = None
	CUR_PHOTO_CUSTOM_ROLL = None
	CUR_EXPORT_PATH = "."
	CUR_PC = None
	CUR_PALETTE = 3
	APP_PATH = "."
	CONFIG_PATH = "."
	APP = None
	FORCE_EXIT = False
	PALETTES = [
		[ 255, 255, 255,   176, 176, 176,   104, 104, 104,   0, 0, 0 ], # Grayscale
		[ 208, 217, 60,   120, 164, 106,   84, 88, 84,   36, 70, 36 ], # Game Boy
		[ 255, 255, 255,   181, 179, 189,   84, 83, 103,   9, 7, 19 ], # Super Game Boy
		[ 240, 240, 240,   218, 196, 106,   112, 88, 52,   30, 30, 30 ], # Game Boy Color (JPN)
		[ 240, 240, 240,   220, 160, 160,   136, 78, 78,   30, 30, 30 ], # Game Boy Color (USA Gold)
		[ 240, 240, 240,   134, 200, 100,   58, 96, 132,   30, 30, 30 ], # Game Boy Color (USA/EUR)
	]

	def __init__(self, app, file=None, icon=None, config_path=".", app_path="."):
		QtWidgets.QDialog.__init__(self, app)
		self.setAcceptDrops(True)
		if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))

		self.FORCE_EXIT = False
		self.CUR_FILE = file
		self.CONFIG_PATH = config_path
		self.APP_PATH = app_path
		self.setWindowTitle(AppInfo.NAME + " – " + __("GB Camera Album Viewer"))
		self.setWindowFlags((self.windowFlags() | QtCore.Qt.MSWindowsFixedSizeDialogHint) & ~QtCore.Qt.WindowContextHelpButtonHint)

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
		self.cmbColor.addItems([
			__("Grayscale"),
			__("Original Game Boy"),
			__("Super Game Boy"),
			__("Game Boy Color (Pocket Camera)"),
			__("Game Boy Color (Game Boy Camera Gold)"),
			__("Game Boy Color (Game Boy Camera)")
		])
		self.cmbColor.currentIndexChanged.connect(self.SetColors)
		self.cmbColor.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
		self.cmbColor.setCurrentIndex(-1)
		self.rowOptions1.addWidget(self.lblColor)
		self.rowOptions1.addWidget(self.cmbColor)
		self.rowOptions1.addStretch(1)

		self.lblZoom = QtWidgets.QLabel(__("Saved Picture Zoom:"))
		self.spnZoom = QtWidgets.QSpinBox()
		self.spnZoom.setRange(1, 10)
		self.spnZoom.setSuffix("×")
		self.rowOptions1.addWidget(self.lblZoom)
		self.rowOptions1.addWidget(self.spnZoom)
		self.rowOptions1.addStretch(1)

		self.chkFrame = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "Save With &Frame"))
		self.rowOptions1.addWidget(self.chkFrame)

		grpOptionsLayout.addLayout(self.rowOptions1)
		# Export prefix option (default filled from settings later)
		self.rowOptions2 = QtWidgets.QHBoxLayout()
		self.rowOptions2.setSpacing(6)
		self.lblExportPrefix = QtWidgets.QLabel(__("Export Filename Prefix:"))
		self.txtExportPrefix = QtWidgets.QLineEdit()
		self.txtExportPrefix.setMaximumWidth(160)
		self.rowOptions2.addWidget(self.lblExportPrefix)
		self.rowOptions2.addWidget(self.txtExportPrefix)
		self.rowOptions2.addStretch(1)
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
		self.lblPhotoViewer.setStyleSheet("border-top: 1px solid #adadad; border-left: 1px solid #adadad; border-bottom: 1px solid #ffffff; border-right: 1px solid #ffffff;")
		self.lblPhotoViewer.mousePressEvent = self.lblPhotoViewer_Clicked
		self.grpPhotoViewLayout.addWidget(self.lblPhotoViewer)
		self.lblPhotoInfo = QtWidgets.QLabel("")
		self.lblPhotoInfo.setWordWrap(True)
		self.lblPhotoInfo.setStyleSheet("color: #606060; font-size: 11px;")
		self.grpPhotoViewLayout.addWidget(self.lblPhotoInfo)

		# Actions below Viewer
		rowActionsGeneral2 = QtWidgets.QHBoxLayout()
		self.btnSavePhoto = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Save This Picture"))
		self.btnSavePhoto.setStyleSheet("padding: 5px 10px;")
		self.btnSavePhoto.clicked.connect(self.btnSavePhoto_Clicked)
		rowActionsGeneral2.addWidget(self.btnSavePhoto)
		self.btnSaveAll = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "Save / Extract &All Pictures"))
		self.btnSaveAll.setStyleSheet("padding: 5px 10px;")
		self.btnSaveAll.clicked.connect(self.btnSaveAll_Clicked)
		self.btnSaveAll.setToolTip(__("Save the current slot or, for a full 1 MiB Photo ROM, extract all rolls into one folder."))
		rowActionsGeneral2.addWidget(self.btnSaveAll)
		self.grpPhotoViewLayout.addLayout(rowActionsGeneral2)

		self.grpPhotoView.setLayout(self.grpPhotoViewLayout)

		# Photo List
		self.grpPhotoThumbs = QtWidgets.QGroupBox(__("Photo Album"))
		self.grpPhotoThumbsLayout = QtWidgets.QVBoxLayout()
		self.grpPhotoThumbsLayout.setSpacing(2)
		self.grpPhotoThumbsLayout.setContentsMargins(-1, 3, -1, -1)
		# Static 30 thumbnails (kept for single-roll mode)
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

		# Scrollable area for multi-roll (240) thumbnails
		self.scrollThumbs = QtWidgets.QScrollArea()
		self.scrollThumbs.setWidgetResizable(True)
		self.scrollThumbsInner = QtWidgets.QWidget()
		self.scrollThumbsLayout = QtWidgets.QGridLayout(self.scrollThumbsInner)
		self.scrollThumbsLayout.setSpacing(2)
		self.scrollThumbsInner.setLayout(self.scrollThumbsLayout)
		self.scrollThumbs.setWidget(self.scrollThumbsInner)
		self.scrollThumbs.hide()

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
		self.layout_photos.addWidget(self.scrollThumbs)
		self.layout_photos.addWidget(self.grpPhotoView)

		self.layout.addLayout(self.layout_options1, 0, 0)
		self.layout.addLayout(self.layout_photos, 1, 0)
		self.layout.addLayout(self.layout_options3, 2, 0)
		self.setLayout(self.layout)

		self.APP = app

		try:
			self.spnZoom.setValue(int(self.APP.SETTINGS.value("PocketCameraZoom")))
		except:
			self.spnZoom.setValue(2)
		self.chkFrame.setChecked(self.APP.SETTINGS.value("PocketCameraFrame", default="disabled") == "enabled")

		palette = self.APP.SETTINGS.value("PocketCameraPalette")
		try:
			palette = json.loads(palette)
		except:
			palette = None
			self.cmbColor.setCurrentIndex(3)
		palette_found = False
		if palette is not None:
			for i in range(0, len(self.PALETTES)):
				if palette == self.PALETTES[i]:
					self.cmbColor.setCurrentIndex(i)
					self.CUR_PALETTE = i
					palette_found = True
		if not palette_found:
			self.PALETTES.append(palette)
			self.CUR_PALETTE = len(self.PALETTES) - 1

		# Always default the export prefix to IMG_PC on startup
		self.txtExportPrefix.setText("IMG_PC")

		if self.CUR_FILE is not None:
			if self.OpenFile(self.CUR_FILE) is False:
				self.FORCE_EXIT = True
				return

		self.CUR_EXPORT_PATH = self.APP.SETTINGS.value("LastDirPocketCamera")
		if self.CUR_EXPORT_PATH is None:
			self.CUR_EXPORT_PATH = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DocumentsLocation)

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

	def OpenFile(self, file):
		original_file_path = file if isinstance(file, str) else self.CUR_FILE_PATH
		if isinstance(file, bytearray) and len(file) == 0x100000 or isinstance(file, str) and os.path.getsize(file) == 0x100000:
			self.CUR_FILE_PATH = file if isinstance(file, str) else self.CUR_FILE_PATH
			self.CUR_FULL_FILE = file if isinstance(file, bytearray) else None
			self.CUR_PHOTO_CUSTOM_ROLL = None
			dlg_args = {
				"title":"Photo!",
				"intro":__("A “Photo!” save file was detected. Please select the roll of pictures that you would like to load."),
				"params": [
					[ "index", "cmb", __("Film roll:"), [ __("Current Save Data") , __("Current Save Data and All Slots") ] + [ __("“{flash_directory}” Slot {number}", flash_directory="Flash Directory", number="{:d}".format(l)) for l in range(1, 8) ], 1 ],
				]
			}
			dlg = UserInputDialog(self, icon=self.windowIcon(), args=dlg_args)
			if dlg.exec_() == 1:
				result = dlg.GetResult()
				index = result["index"].currentIndex()
				if isinstance(file, str):
					with open(file, "rb") as f:
						full_file = bytearray(f.read())
				else:
					full_file = file
				self.CUR_FULL_FILE = full_file
				if index == 1:
					self.CUR_PHOTO_CUSTOM_ROLL = -1
					file = full_file[0x20000 * 0:0x20000 * 1]
				else:
					self.CUR_PHOTO_CUSTOM_ROLL = index - 1 if index > 1 else index
					file = full_file[0x20000 * self.CUR_PHOTO_CUSTOM_ROLL:0x20000 * (self.CUR_PHOTO_CUSTOM_ROLL + 1)]
			else:
				self.CUR_PC = None
				return False

		self.CUR_FILE_PATH = original_file_path if isinstance(original_file_path, str) else self.CUR_FILE_PATH
		self.CUR_PC = None
		try:
			self.CUR_PC = PocketCamera()
			if self.CUR_PC.LoadFile(file) == False:
				self.CUR_PC = None
				QtWidgets.QMessageBox.critical(self, AppInfo.NAME, __("The save data file couldn’t be loaded."), QtWidgets.QMessageBox.Ok)
				return False
			self.CUR_FILE = original_file_path if isinstance(original_file_path, str) else ""
			if self.CUR_EXPORT_PATH == "" and self.CUR_FILE != "":
				self.CUR_EXPORT_PATH = os.path.dirname(self.CUR_FILE)
			self.UpdateViewer(0)
			self.SetColors()
			if self._IsPhotoCustomRom():
				if self.CUR_PHOTO_CUSTOM_ROLL == -1:
					self.lblPhotoInfo.setText(__("1 MiB Photo save file detected. The current roll is shown while all slots are available for export."))
				else:
					self.lblPhotoInfo.setText(__("1 MiB Photo save file detected. Use Save / Extract All Pictures to export all rolls."))
			else:
				self.lblPhotoInfo.setText("")
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

	def _IsPhotoCustomRom(self):
		if self.CUR_FULL_FILE is not None and len(self.CUR_FULL_FILE) == 0x100000:
			return True
		if self.CUR_FILE_PATH is not None and os.path.isfile(self.CUR_FILE_PATH) and os.path.getsize(self.CUR_FILE_PATH) == 0x100000:
			return True
		return False

	def _GetExportPrefix(self, path, digits=2):
		prefix = os.path.splitext(path)[0]
		dirname = os.path.dirname(prefix)
		basename = os.path.basename(prefix)
		if len(basename) > digits and basename[-digits:].isdigit():
			basename = basename[:-digits]
		return os.path.join(dirname, basename)

	def _GetNextExportIndex(self, directory, prefix, ext, digits=2):
		prefix_base = os.path.basename(prefix)
		existing_index = -1
		try:
			for fn in os.listdir(directory):
				if not fn.lower().endswith(ext.lower()):
					continue
				name = fn[:-len(ext)]
				if not name.startswith(prefix_base):
					continue
				suffix = name[len(prefix_base):]
				if len(suffix) != digits or not suffix.isdigit():
					continue
				idx = int(suffix)
				if idx > existing_index:
					existing_index = idx
			return existing_index + 1
		except OSError:
			return 0

	def _GetPhotoRomSource(self):
		if self.CUR_FULL_FILE is not None and len(self.CUR_FULL_FILE) == 0x100000:
			return self.CUR_FULL_FILE
		if self.CUR_FILE_PATH is not None and os.path.isfile(self.CUR_FILE_PATH) and os.path.getsize(self.CUR_FILE_PATH) == 0x100000:
			try:
				with open(self.CUR_FILE_PATH, "rb") as f:
					return bytearray(f.read())
			except OSError:
				return None
		return None

	def _BuildAllRollImages(self):
		# Build a flat list of (PIL Image RGBA, deleted_flag) for all 8 rolls (240 images)
		full = self._GetPhotoRomSource()
		if full is None: return None
		all_images = []
		for roll in range(0, 8):
			roll_data = full[0x20000 * roll:0x20000 * (roll + 1)]
			pc = PocketCamera()
			if pc.LoadFile(roll_data) == False:
				continue
			for i in range(0, 30):
				img = pc.GetPicture(i).convert("RGBA")
				is_deleted = pc.IsDeleted(i)
				all_images.append((img, is_deleted))
		return all_images

	def _ExportPicture(self, cam, index, path):
		frame = False
		if self.chkFrame.isChecked():
			frame = True
			own_frame = self.CONFIG_PATH + os.sep + "pc_frame.png"
			if not os.path.exists(own_frame):
				shutil.copy(self.APP_PATH + os.sep + os.path.join("res", "pc_frame.png"), own_frame)
			with open(own_frame, "rb") as f:
				frame = f.read()
		if index == 31:
			frame = False
		cam.ExportPicture(index=index, path=path, scale=self.spnZoom.value(), frame=frame)

	def _ExportAllPhotoRomRolls(self):
		full_file = self._GetPhotoRomSource()
		if full_file is None:
			QtWidgets.QMessageBox.critical(self, AppInfo.NAME, __("Unable to retrieve the full Photo ROM source file."), QtWidgets.QMessageBox.Ok)
			return
		for roll in range(1, 9):
			roll_data = full_file[0x20000 * (roll - 1):0x20000 * roll]
			pc = PocketCamera()
			if pc.LoadFile(roll_data) == False:
				continue
			# Use user-defined export prefix if available
			base_prefix = "IMG_PC"
			try:
				if hasattr(self, 'txtExportPrefix'):
					val = str(self.txtExportPrefix.text()).strip()
					if val != "":
						base_prefix = val
			except:
				base_prefix = "IMG_PC"
			prefix = os.path.join(self.CUR_EXPORT_PATH, "{}_{:d}".format(base_prefix, roll))
			ext = ".png"
			start = self._GetNextExportIndex(self.CUR_EXPORT_PATH, prefix, ext)
			for i in range(0, 32):
				file = prefix + "{:02d}".format(start + i) + ext
				self._ExportPicture(pc, i, file)
		QtWidgets.QMessageBox.information(self, AppInfo.NAME, __("The pictures were extracted."), QtWidgets.QMessageBox.Ok)

	def btnSaveAll_Clicked(self, event):
		if self.CUR_PC is None: return
		if self._IsPhotoCustomRom():
			directory = QtWidgets.QFileDialog.getExistingDirectory(self, __("Export all pictures"), self.CUR_EXPORT_PATH)
			if directory == "":
				return
			self.CUR_EXPORT_PATH = directory
			self._ExportAllPhotoRomRolls()
			return

		# default filename uses export prefix field when present
		default_name = "IMG_PC"
		if hasattr(self, 'txtExportPrefix'):
			val = str(self.txtExportPrefix.text()).strip()
			if val != "":
				default_name = val
		path = self.CUR_EXPORT_PATH + os.sep + default_name + ".png"
		path = QtWidgets.QFileDialog.getSaveFileName(self, __("Export all pictures"), path, __("PNG files") + " (*.png);;" + __("BMP files") + " (*.bmp);;" + __("GIF files") + " (*.gif);;" + __("JPEG files") + " (*.jpg);;" + __("All files") + " (*.*)")[0]
		if path == "": return
		self.CUR_EXPORT_PATH = os.path.dirname(path)
		prefix = self._GetExportPrefix(path)
		ext = os.path.splitext(path)[1]
		start = self._GetNextExportIndex(self.CUR_EXPORT_PATH, prefix, ext)
		if start < 1:
			start = 1

		for i in range(0, 32):
			file = prefix + "{:02d}".format(start + i) + ext
			self.SavePicture(i, path=file)

	def btnSavePhoto_Clicked(self, event):
		if self.CUR_PC is None: return
		self.SavePicture(self.CUR_INDEX)

	def btnClose_Clicked(self, event):
		self.FORCE_EXIT = True
		self.reject()

	def hideEvent(self, event):
		self.APP.SETTINGS.setValue("PocketCameraPalette", json.dumps(self.PALETTES[self.cmbColor.currentIndex()]))
		self.APP.SETTINGS.setValue("PocketCameraZoom", str(self.spnZoom.value()))
		self.APP.SETTINGS.setValue("PocketCameraFrame", str(self.chkFrame.isChecked()).lower().replace("true", "enabled").replace("false", "disabled"))
		self.APP.SETTINGS.setValue("LastDirPocketCamera", self.CUR_EXPORT_PATH)
		self.APP.activateWindow()

	def BuildPhotoList(self):
		# Single-roll mode
		if not (self.CUR_PHOTO_CUSTOM_ROLL == -1):
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
			# ensure static thumbs visible, hide scroll area
			self.grpPhotoThumbs.show()
			self.scrollThumbs.hide()
			return

		# Multi-roll mode: build and show 240 thumbnails in scroll area
		all_images = self._BuildAllRollImages()
		if all_images is None:
			self.grpPhotoThumbs.show()
			self.scrollThumbs.hide()
			return
		self.CUR_ALL_IMAGES = all_images
		# clear existing widgets in scrollThumbsLayout
		for i in reversed(range(self.scrollThumbsLayout.count())):
			w = self.scrollThumbsLayout.itemAt(i).widget()
			if w is not None:
				w.setParent(None)

		cols = 10
		for idx, (img, deleted) in enumerate(self.CUR_ALL_IMAGES):
			thumb = img.resize((47, 41), Image.Resampling.HAMMING)
			qthumb = QtGui.QPixmap.fromImage(ImageQt(thumb))
			lbl = QtWidgets.QLabel(self.scrollThumbsInner)
			lbl.setPixmap(qthumb)
			lbl.setMinimumSize(49, 43)
			lbl.setMaximumSize(49, 43)
			lbl.setAlignment(QtCore.Qt.AlignCenter)
			lbl.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
			lbl.mousePressEvent = functools.partial(self.lblPhoto_Clicked, index=idx)
			if deleted:
				lbl.setToolTip(__("This picture was marked as “deleted” and may be overwritten when you take new pictures."))
			self.scrollThumbsLayout.addWidget(lbl, idx // cols, idx % cols)

		self.grpPhotoThumbs.hide()
		self.scrollThumbs.show()

	def UpdateViewer(self, index, scale_factor=4):
		resampler = Image.Resampling.NEAREST
		if self.CUR_BICUBIC or index == 31: resampler = Image.Resampling.BICUBIC
		if resampler == Image.Resampling.BICUBIC: scale_factor = 0.5
		# If multi-roll mode, use prebuilt images
		if self.CUR_PHOTO_CUSTOM_ROLL == -1 and hasattr(self, 'CUR_ALL_IMAGES'):
			if index < 0 or index >= len(self.CUR_ALL_IMAGES):
				return
			img = self.CUR_ALL_IMAGES[index][0]
			resized = img.resize((int(256 * scale_factor), int(224 * scale_factor)), resampler)
			self.CUR_PIC = ImageQt(resized)
			qpixmap = QtGui.QPixmap.fromImage(self.CUR_PIC)
			qpixmap.setDevicePixelRatio(scale_factor)
			self.lblPhotoViewer.setPixmap(qpixmap)
			# update selection highlight for static thumbs if visible
			for i in range(0, len(self.lblPhoto)):
				self.lblPhoto[i].setStyleSheet("border-top: 1px solid #adadad; border-left: 1px solid #adadad; border-bottom: 1px solid #ffffff; border-right: 1px solid #ffffff;")
			return

		# single-roll mode
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

	def SavePicture(self, index, path=""):
		if path == "":
			# Use export prefix from UI when present
			default_name = "IMG_PC"
			if hasattr(self, 'txtExportPrefix'):
				val = str(self.txtExportPrefix.text()).strip()
				if val != "":
					default_name = val
			path = self.CUR_EXPORT_PATH + os.sep + default_name + "{:02d}.png".format(index+1)
			path = QtWidgets.QFileDialog.getSaveFileName(self, __("Save Photo"), path, __("PNG files") + " (*.png);;" + __("BMP files") + " (*.bmp);;" + __("GIF files") + " (*.gif);;" + __("JPEG files") + " (*.jpg);;" + __("All files") + " (*.*)")[0]
			if path != "": self.CUR_EXPORT_PATH = os.path.dirname(path)
		if path == "": return

		self._ExportPicture(self.CUR_PC, index, path)

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
