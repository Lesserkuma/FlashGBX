# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

from .pyside import QtCore, QtWidgets, QtGui
from .i18n import __
from .app import AppInfo

class UserInputDialog(QtWidgets.QDialog):
	APP = None

	def __init__(self, app, icon=None, args=None):
		super(UserInputDialog, self).__init__(app)
		if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
		self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
		self.setWindowTitle(AppInfo.NAME + " – " + args["title"])
		self.setWindowFlags((self.windowFlags() | QtCore.Qt.MSWindowsFixedSizeDialogHint) & ~QtCore.Qt.WindowContextHelpButtonHint)

		self.APP = app

		self.lblIntro = QtWidgets.QLabel(args["intro"])
		self.lblIntro.setWordWrap(True)
		self.btnOK = QtWidgets.QPushButton(__("&OK"))
		self.btnCancel = QtWidgets.QPushButton(__("&Cancel"))

		grid_layout = QtWidgets.QGridLayout()
		grid_layout.addWidget(self.lblIntro, 0, 0, 1, 2)
		grid_rows = 1

		self.paramWidgets = {}
		for param in args["params"]:
			if param[1] in ("cmb", "cmb_e"):
				lbl = QtWidgets.QLabel(param[2])
				cmb = QtWidgets.QComboBox()
				cmb.clear()
				cmb.addItems(param[3])
				cmb.setCurrentIndex(param[4])
				if param[1] == "cmb_e":
					cmb.setEditable(True)
				elif len(param[3]) == 1:
					cmb.setEnabled(False)
				cmb.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
				self.paramWidgets[param[0]] = cmb
				grid_layout.addWidget(lbl, grid_rows, 0, 1, 1)
				grid_layout.addWidget(cmb, grid_rows, 1, 1, 1)

			elif param[1] in ("spb"):
				lbl = QtWidgets.QLabel(param[2])
				spb = QtWidgets.QSpinBox()
				spb.setRange(param[3][0], param[3][1])
				spb.setValue(param[4])
				self.paramWidgets[param[0]] = spb
				grid_layout.addWidget(lbl, grid_rows, 0, 1, 1)
				grid_layout.addWidget(spb, grid_rows, 1, 1, 1)

			elif param[1] in ("chk"):
				chk = QtWidgets.QCheckBox()
				chk.setChecked(param[4])
				chk.setText(param[2])
				self.paramWidgets[param[0]] = chk
				grid_layout.addWidget(chk, grid_rows, 0, 1, 2)

			else:
				continue

			grid_rows += 1
		grid_layout.setColumnStretch(1, 1)

		grpButtonsLayout = QtWidgets.QHBoxLayout()
		grpButtonsLayout.addStretch(30)
		grpButtonsLayout.addWidget(self.btnOK, grid_rows, QtCore.Qt.AlignRight)
		grpButtonsLayout.addWidget(self.btnCancel, grid_rows, QtCore.Qt.AlignRight)

		grid_layout.addLayout(grpButtonsLayout, grid_rows, 0, 1, 2)
		self.setLayout(grid_layout)
		width = max(self.minimumSizeHint().width(), self.sizeHint().width() * 2 // 3)
		self.resize(width, grid_layout.totalHeightForWidth(width))

		self.btnOK.clicked.connect(self.accept)
		self.btnCancel.clicked.connect(self.reject)

	def GetResult(self):
		return self.paramWidgets

	def hideEvent(self, event):
		self.APP.activateWindow()
