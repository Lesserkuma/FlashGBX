# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import html, math, re
from .pyside import QtCore, QtWidgets, QtGui
from .i18n import __, ___, c__
from .app import AppInfo
from .Formatter import Formatter
from .Mapper import DMG_Mapper

class AnalyzeCartridgeDialog(QtWidgets.QDialog):
	TRY_GENERIC = 2
	RETRY = 3

	def __init__(self, app, args):
		super(AnalyzeCartridgeDialog, self).__init__(app)
		self.ARGS = args
		self.PROFILES = {index:config for index, name, config in args["profiles"]}
		self.setWindowTitle(AppInfo.NAME + " – " + __("Analyze Flash Cartridge"))
		self.setWindowFlags((self.windowFlags() | QtCore.Qt.MSWindowsFixedSizeDialogHint) & ~QtCore.Qt.WindowContextHelpButtonHint)
		layout = QtWidgets.QGridLayout(self)
		layout.setContentsMargins(-1, 8, -1, 8)
		layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
		layout.setColumnStretch(1, 1)
		summary = QtWidgets.QLabel(args["summary"][:-4] if args["summary"].endswith("<br>") else args["summary"], wordWrap=True)
		layout.addWidget(summary, 0, 0, 1, 2)
		layout.addWidget(QtWidgets.QLabel("<b>" + ___("{n} matching profile:", "{n} matching profiles:", n=len(args["profiles"])) + "</b>"), 2, 0, 1, 2)
		self.cmbProfiles = QtWidgets.QComboBox(enabled=bool(args["profiles"]))
		self.cmbProfiles.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
		for index, name, config in args["profiles"]:
			self.cmbProfiles.addItem(name, index)
		self.cmbProfiles.setCurrentIndex(self.cmbProfiles.findData(args["selected"]))
		self.lblSelectProfile = QtWidgets.QLabel(__("- Please select -"), self.cmbProfiles)
		self.lblSelectProfile.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
		placeholder = QtWidgets.QHBoxLayout(self.cmbProfiles)
		placeholder.setContentsMargins(4, 0, 20, 0)
		placeholder.addWidget(self.lblSelectProfile)
		layout.addWidget(self.cmbProfiles, 3, 0, 1, 2)
		self.lblProfile = QtWidgets.QLabel(wordWrap=True)
		layout.addWidget(self.lblProfile, 1, 0, 1, 2)
		self.btnDetails = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Details"), checkable=True, autoDefault=False)
		self.txtDetails = QtWidgets.QTextBrowser(self, html=args["details"], visible=False)
		details_document = self.txtDetails.document().clone()
		details_document.adjustSize()
		self.cmbProfiles.setMinimumWidth(max(350, math.ceil(details_document.idealWidth()) + 2 * self.txtDetails.frameWidth() + self.txtDetails.verticalScrollBar().sizeHint().width()))
		self.txtDetails.setFixedHeight(max(180, self.txtDetails.fontMetrics().lineSpacing() * 12))
		layout.addWidget(self.txtDetails, 7, 0, 1, 2)
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
		tools.setAlignment(QtCore.Qt.AlignTop)
		tools.addStretch()
		self.btnCopy, self.btnSave = QtWidgets.QToolButton(autoRaise=True), QtWidgets.QToolButton(autoRaise=True)
		for button, icon, title in (
			(self.btnCopy, QtGui.QIcon.fromTheme("edit-copy", QtGui.QIcon(copy_icon)), c__("Button (& = Keyboard Shortcut)", "&Copy to Clipboard")),
			(self.btnSave, self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton), c__("Button (& = Keyboard Shortcut)", "&Save Diagnostic Data…")),
		):
			button.setIcon(icon)
			button.setToolTip(title.replace("&", ""))
			button.setAccessibleName(button.toolTip())
			tools.addWidget(button)
		self.btnCopy.clicked.connect(self.CopyReport)
		diagnostics = app.CONN.INFO.get("flash_diagnostics")
		self.btnSave.setEnabled(bool(diagnostics))
		self.btnSave.clicked.connect(lambda: app.SaveFlashDiagnostics(diagnostics))
		if args["generic"] is not None:
			self.btnGeneric = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Try “{generic_type}”", generic_type=args["generic"][1]), autoDefault=False)
			self.btnGeneric.clicked.connect(lambda: self.done(self.TRY_GENERIC))
			layout.addWidget(self.btnGeneric, 4, 0, 1, 2)
		if args["retry"]:
			self.btnRetry = QtWidgets.QPushButton(__("Analyze again without voltage limit"), autoDefault=False)
			self.btnRetry.clicked.connect(lambda: self.done(self.RETRY))
			layout.addWidget(self.btnRetry, 5, 0, 1, 2)
		self.chkSkip = QtWidgets.QCheckBox(c__("Check Box (& = Keyboard Shortcut)", "&Always skip this message"), visible=args["can_skip"] and args["selected"] > 0)
		layout.addWidget(self.chkSkip, 6, 0, 1, 2)
		buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)
		buttons.button(QtWidgets.QDialogButtonBox.Cancel).setAutoDefault(False)
		self.btnOK = buttons.addButton(__("&Continue") if args["waiting"] else __("&Apply"), QtWidgets.QDialogButtonBox.AcceptRole)
		if not args["profiles"]:
			self.btnOK.setText(c__("Button (& = Keyboard Shortcut)", "&Close"))
		self.btnOK.setDefault(True)
		buttons.accepted.connect(self.accept)
		buttons.rejected.connect(self.reject)
		layout.addWidget(self.btnDetails, 8, 0, QtCore.Qt.AlignLeft)
		layout.addWidget(buttons, 8, 1)
		self.cmbProfiles.currentIndexChanged.connect(self.UpdateProfile)
		self.UpdateProfile()
		self.btnOK.setFocus()

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
		profiles = [___("{n} matching profile:", "{n} matching profiles:", n=len(self.PROFILES))]
		for index, name, config in self.ARGS["profiles"]:
			if index == self.cmbProfiles.currentData():
				name += " ← " + c__("Flashcart Profile List “- PROFILE NAME ← selected”", "selected")
			profiles.append("- " + html.escape(name))
		doc = QtGui.QTextDocument()
		details = self.ARGS["details"].replace("<b>", "<br><br><b>").replace("<i>", "<br><i>")
		doc.setHtml(self.ARGS["summary"] + self.lblProfile.text() + "<br><br>" + "<br>".join(profiles) + details)
		QtWidgets.QApplication.clipboard().setText(re.sub(r"\n{3,}", "\n\n", doc.toPlainText()).strip())
