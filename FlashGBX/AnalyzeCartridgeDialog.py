# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import html, math, re
from .pyside import QtCore, QtWidgets, QtGui
from .i18n import __, ___, c__
from .app import AppInfo
from .Formatter import Formatter
from .Mapper import DMG_Mapper

class AnalyzeCartridgeDialog(QtWidgets.QMessageBox):
	TRY_GENERIC = 2
	RETRY = 3

	def __init__(self, app, args):
		super(AnalyzeCartridgeDialog, self).__init__(app)
		self.ARGS = args
		self.PROFILES = {index:config for index, name, config in args["profiles"]}
		self.setWindowTitle(AppInfo.NAME + " – " + __("Analyze Flash Cartridge"))
		self.setIcon(QtWidgets.QMessageBox.Information)
		summary = (args["summary"][:-4] if args["summary"].endswith("<br>") else args["summary"]).split("<br>", 1)
		self.setText(summary[0])
		layout = QtWidgets.QVBoxLayout()
		layout.setContentsMargins(0, 0, 0, 6)
		if len(summary) > 1:
			layout.addWidget(QtWidgets.QLabel(summary[1], wordWrap=True))
		self.lblProfile = QtWidgets.QLabel(wordWrap=True)
		layout.addWidget(self.lblProfile)
		layout.addWidget(QtWidgets.QLabel("<b>" + ___("{n} matching flash cart profile:", "{n} matching flash cart profiles:", n=len(args["profiles"])) + "</b>", self, visible=bool(args["profiles"])))
		self.cmbProfiles = QtWidgets.QComboBox(self, visible=bool(args["profiles"]))
		self.cmbProfiles.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
		for index, name, config in args["profiles"]:
			self.cmbProfiles.addItem(name, index)
		self.cmbProfiles.setCurrentIndex(self.cmbProfiles.findData(args["selected"]))
		self.lblSelectProfile = QtWidgets.QLabel(__("- Please select -"), self.cmbProfiles)
		self.lblSelectProfile.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
		placeholder = QtWidgets.QHBoxLayout(self.cmbProfiles)
		placeholder.setContentsMargins(4, 0, 20, 0)
		placeholder.addWidget(self.lblSelectProfile)
		layout.addWidget(self.cmbProfiles)
		layout.addWidget(QtWidgets.QLabel(args["hint"], self, wordWrap=True, visible=not args["profiles"]))
		self.btnDetails = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Details"), self, checkable=True, autoDefault=False, visible=not args["is_generic"])
		self.txtDetails = QtWidgets.QTextBrowser(self, html=args["details"], visible=False)
		details_document = self.txtDetails.document().clone()
		details_document.adjustSize()
		layout.addStrut(max(350, math.ceil(details_document.idealWidth()) + 2 * self.txtDetails.frameWidth() + self.txtDetails.verticalScrollBar().sizeHint().width()))
		self.txtDetails.setFixedHeight(max(180, self.txtDetails.fontMetrics().lineSpacing() * 12))
		self.btnDetails.toggled.connect(self.txtDetails.setVisible)
		copy_icon = QtGui.QPixmap(32, 32)
		copy_icon.setDevicePixelRatio(2)
		copy_icon.fill(QtCore.Qt.transparent)
		painter = QtGui.QPainter(copy_icon)
		painter.setPen(self.palette().color(QtGui.QPalette.Text))
		painter.setBrush(self.palette().brush(QtGui.QPalette.Base))
		painter.drawRect(2, 1, 8, 10)
		painter.drawRect(5, 4, 8, 10)
		painter.end()
		tools = QtWidgets.QHBoxLayout(self.txtDetails)
		scrollbar = self.txtDetails.verticalScrollBar()
		update_margins = lambda minimum, maximum: tools.setContentsMargins(4, 2, (scrollbar.sizeHint().width() if maximum > minimum else 0) + 4, 0)
		scrollbar.rangeChanged.connect(update_margins)
		update_margins(scrollbar.minimum(), scrollbar.maximum())
		tools.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignRight)
		diagnostics = app.CONN.INFO.get("flash_diagnostics")
		for icon, title, callback, enabled in (
			(QtGui.QIcon.fromTheme("edit-copy", QtGui.QIcon(copy_icon)), c__("Button (& = Keyboard Shortcut)", "&Copy to Clipboard"), self.CopyReport, True),
			(self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), c__("Button (& = Keyboard Shortcut)", "&Save Diagnostic Data…"), lambda: app.SaveFlashDiagnostics(diagnostics), bool(diagnostics)),
		):
			title = title.replace("&", "")
			button = QtWidgets.QToolButton(autoRaise=True, icon=icon, toolTip=title, accessibleName=title, enabled=enabled)
			button.clicked.connect(callback)
			tools.addWidget(button)
		if args["generic"] is not None:
			self.btnGeneric = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Try “{generic_type}”", generic_type=args["generic"][1]), autoDefault=False)
			self.btnGeneric.clicked.connect(lambda: self.done(self.TRY_GENERIC))
			layout.addWidget(self.btnGeneric)
		if args["retry"]:
			self.btnRetry = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "Analyze again without voltage limit"), autoDefault=False)
			self.btnRetry.clicked.connect(lambda: self.done(self.RETRY))
			layout.addWidget(self.btnRetry)
		self.chkSkip = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Always skip this message"), self, visible=args["can_skip"] and args["selected"] > 0)
		layout.addWidget(self.chkSkip)
		layout.addWidget(self.txtDetails)
		self.setStandardButtons(QtWidgets.QMessageBox.Cancel)
		self.button(QtWidgets.QMessageBox.Cancel).setAutoDefault(False)
		self.button(QtWidgets.QMessageBox.Cancel).setVisible(bool(args["profiles"]))
		self.setEscapeButton(QtWidgets.QMessageBox.Cancel)
		self.btnOK = self.addButton(QtWidgets.QMessageBox.Ok)
		self.btnOK.setText(c__("Button (& = Keyboard Shortcut)", "&Continue") if args["waiting"] else c__("Button (& = Keyboard Shortcut)", "&Apply"))
		if not args["profiles"]:
			self.btnOK.setText(c__("Button (& = Keyboard Shortcut)", "&Close"))
		self.setDefaultButton(self.btnOK)
		button_layout = QtWidgets.QHBoxLayout()
		button_layout.addWidget(self.btnDetails, 0, QtCore.Qt.AlignBottom)
		button_layout.addWidget(self.findChild(QtWidgets.QDialogButtonBox), 1)
		self.layout().addLayout(layout, 1, 2)
		self.layout().addLayout(button_layout, 2, 0, 1, 3)
		self.cmbProfiles.currentIndexChanged.connect(self.UpdateProfile)
		self.UpdateProfile()
		self.btnOK.setFocus()
		for widget in [self] + self.findChildren(QtWidgets.QWidget):
			if isinstance(widget, QtWidgets.QLabel) and widget.text():
				widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
			widget.installEventFilter(self)

	def eventFilter(self, obj, event):
		if event.type() == QtCore.QEvent.KeyPress and event.matches(QtGui.QKeySequence.Copy):
			if isinstance(obj, QtWidgets.QLabel) and obj.hasSelectedText():
				QtWidgets.QApplication.clipboard().setText(obj.selectedText())
			elif obj in (self.txtDetails, self.txtDetails.viewport()) and self.txtDetails.textCursor().hasSelection():
				self.txtDetails.copy()
			else:
				self.CopyReport()
			return True
		return super(AnalyzeCartridgeDialog, self).eventFilter(obj, event)

	def UpdateProfile(self):
		config = self.PROFILES.get(self.cmbProfiles.currentData(), {})
		requires_selection = bool(self.PROFILES) and self.cmbProfiles.currentIndex() == -1
		self.btnOK.setEnabled(not requires_selection)
		self.lblSelectProfile.setVisible(requires_selection)
		self.cmbProfiles.setToolTip(self.cmbProfiles.currentText())
		size = self.ARGS["detected_size"] or config.get("flash_size", 0)
		text = "<b>" + __("ROM Size:") + "</b> " + (Formatter.file_size(size, as_int=True) if size > 0 else "–")
		if self.ARGS["mode"] == "DMG":
			mapper = config.get("mbc", 0x19)
			name = __("Manual selection") if mapper == "manual" else DMG_Mapper().GetMapperType(mapper)
			text += "<br><b>" + __("Mapper Type:") + "</b> " + (html.escape(name) if config else "–")
		self.lblProfile.setText(text)

	def CopyReport(self):
		profiles = [___("{n} matching flash cart profile:", "{n} matching flash cart profiles:", n=len(self.PROFILES))] if self.PROFILES else [html.escape(self.ARGS["hint"])]
		for index, name, config in self.ARGS["profiles"]:
			if index == self.cmbProfiles.currentData():
				name += " ← " + c__("Flashcart Profile List “- PROFILE NAME ← selected”", "selected")
			profiles.append("- " + html.escape(name))
		doc = QtGui.QTextDocument()
		details = self.ARGS["details"].replace("<b>", "<br><br><b>").replace("<i>", "<br><i>")
		doc.setHtml(self.ARGS["summary"] + self.lblProfile.text() + "<br><br>" + "<br>".join(profiles) + details)
		QtWidgets.QApplication.clipboard().setText(re.sub(r"\n{3,}", "\n\n", doc.toPlainText()).strip())
