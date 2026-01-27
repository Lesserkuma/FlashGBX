# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import zipfile, serial, struct, time, datetime
try:
	from . import Util
except ImportError:
	import Util

class FirmwareUpdater():
	PORT = None
	DEVICE = None

	def __init__(self, app_path=".", port=None):
		self.APP_PATH = app_path
		self.PORT = port

	def PackPacket(self, packet):
		values = list(packet.values())[:-2]
		data = struct.pack(">IBHHH", *values)
		if packet["payload_len"] > 0:
			data += list(packet.values())[-2]
		data += struct.pack(">I", packet["outro"])
		if len(data) % 2 == 1: data += b'\00'
		return data

	def GetPacket(self):
		hp = 100
		while self.DEVICE.in_waiting == 0:
			time.sleep(0.001)
			hp -= 1
			if hp <= 0:
				return None
		keys = ["intro", "sender", "seq_no", "command", "payload_len"]
		values = struct.unpack(">IBHHH", self.DEVICE.read(11))
		data = dict(zip(keys, values))
		data["payload"] = self.DEVICE.read(data["payload_len"])
		try:
			data["outro"] = self.DEVICE.read(4)
			data["outro"] = struct.unpack(">I", data["outro"])[0]
		except struct.error:
			return {"clone":True, "error": "Erroneous outro response: " + ''.join(format(x, '02X') for x in data["outro"])}
		return data

	def CRC16(self, data):
		CRCTableAbs = [
			0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
			0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
		]
		wCRC = 0xFFFF

		for i in range(len(data)):
			chChar = data[i]
			wCRC = (CRCTableAbs[(chChar ^ wCRC) & 0x0F] ^ (wCRC >> 4))
			wCRC = (CRCTableAbs[((chChar >> 4) ^ wCRC) & 0x0F] ^ (wCRC >> 4))

		return wCRC

	def TryConnect(self, port):
		seq_no = 1
		packet = {
			"intro":0x48484A4A,
			"sender":0,
			"seq_no":seq_no,
			"command":0x21,
			"payload_len":0,
			"payload":bytearray(),
			"outro":0x4A4A4848,
		}
		data = self.PackPacket(packet)

		self.DEVICE = None
		try:
			self.DEVICE = serial.Serial(port, 2000000, timeout=0.1)
			self.DEVICE.write(b'\xF1')
			self.DEVICE.read(1)
			self.DEVICE.write(b'\x01')
			self.DEVICE.close()
			time.sleep(3)
			self.DEVICE = serial.Serial(port, 2000000, timeout=0.1)
		
		except serial.serialutil.SerialException:
			return False

		self.DEVICE.write(data)
		time.sleep(0.1)
		self.DEVICE.read(self.DEVICE.in_waiting)
		self.DEVICE.write(data)
		data = self.GetPacket()
		if data is None:
			self.DEVICE = None
			return False
		if "error" in data:
			self.DEVICE = None
			return data
		if data["seq_no"] != seq_no:
			self.DEVICE = None
			return False
		if data["command"] != 0x21:
			self.DEVICE = None
			return False
		if struct.unpack(">H", data["payload"][1:3])[0] != 0x03:
			self.DEVICE = None
			return False
		return data

	def WriteFirmware(self, zipfn, fncSetStatus):
		with zipfile.ZipFile(zipfn) as archive:
			with archive.open("fw.bin") as f: fw_data = bytearray(f.read())

		fncSetStatus("Connecting...")
		if self.PORT is None:
			ports = []
			comports = serial.tools.list_ports.comports()
			for i in range(0, len(comports)):
				if comports[i].vid == 0x1A86 and comports[i].pid == 0x7523:
					ports.append(comports[i].device)
			if len(ports) == 0:
				fncSetStatus("No device found.")
				return 2
		
			for port in ports:
				data = self.TryConnect(port)
				if data is not False:
					break
		else:
			data = self.TryConnect(self.PORT)

		if "error" in data:
			fncSetStatus(text=data["error"], cloneError="clone" in data and data["clone"] is True)
			return 2
		if self.DEVICE is None:
			fncSetStatus("No device found.")
			return 2

		data["program_size"] = struct.unpack(">H", data["payload"][3:5])[0]
		data["page_size"] = struct.unpack(">H", data["payload"][7:9])[0]
		page_size = data["page_size"]
		num_packets = len(fw_data) / page_size
		num_packets = int(-(-num_packets // 1)) # round up

		fncSetStatus("Updating firmware...", setProgress=0)
		seq_no = 2

		pos = 0
		packet_index = 1
		while pos < num_packets:
			buffer = fw_data[pos*page_size:pos*page_size+page_size]
			packet_len = len(buffer)
			buffer += struct.pack(">H", self.CRC16(buffer))
			buffer = struct.pack(">H", packet_len) + buffer
			buffer = struct.pack(">H", packet_index) + buffer
			
			packet = {
				"intro":0x48484A4A,
				"sender":0,
				"seq_no":seq_no,
				"command":0x24,
				"payload_len":len(buffer),
				"payload":buffer,
				"outro":0x4A4A4848,
			}
			data = self.PackPacket(packet)
			
			self.DEVICE.write(data)
			data = self.GetPacket()
			
			if data["seq_no"] != seq_no:
				fncSetStatus("Incorrect sequence number.")
				time.sleep(1)
				continue
			if data["command"] != 0x24:
				fncSetStatus("Incorrect command.")
				time.sleep(1)
				continue
			if struct.unpack(">H", data["payload"][0:2])[0] != packet_index:
				fncSetStatus("Incorrect data packet number.")
				time.sleep(1)
				continue
			if data["payload"][2] != 0x01:
				fncSetStatus("Write failed.")
				time.sleep(1)
				continue

			percent = packet_index / num_packets * 100
			fncSetStatus(text="Updating firmware... Do not unplug the device!", setProgress=percent)
			pos += 1
			seq_no += 1
			packet_index += 1

		if pos == num_packets:
			payload = bytearray()
			payload += struct.pack(">H", self.CRC16(fw_data))
			payload += struct.pack(">H", ~self.CRC16(fw_data) & 0xFFFF)
			packet = {
				"intro":0x48484A4A,
				"sender":0,
				"seq_no":seq_no,
				"command":0x23,
				"payload_len":4,
				"payload":payload,
				"outro":0x4A4A4848,
			}
			data = self.PackPacket(packet)
			self.DEVICE.write(data)
			data = self.GetPacket()
			if data["payload"][0] != 1:
				fncSetStatus(text="Update failed!", enableUI=True)
			
			self.DEVICE.close()
			time.sleep(0.8)
			fncSetStatus("Done.")
			time.sleep(0.2)
			return 1

try:
	from .pyside import QtCore, QtWidgets, QtGui, QDesktopWidget
	class FirmwareUpdaterWindow(QtWidgets.QDialog):
		APP = None
		DEVICE = None
		FWUPD = None
		DEV_NAME = "GBFlash"
		FW_VER = ""
		PCB_VER = ""

		def __init__(self, app, app_path, file=None, icon=None, device=None):
			QtWidgets.QDialog.__init__(self)
			if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
			self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
			self.setWindowTitle("FlashGBX – Firmware Updater for GBFlash")
			self.setWindowFlags((self.windowFlags() | QtCore.Qt.MSWindowsFixedSizeDialogHint) & ~QtCore.Qt.WindowContextHelpButtonHint)

			self.APP = app
			if device is not None:
				self.FWUPD = FirmwareUpdater(app_path, device.GetPort())
				self.DEV_NAME = device.GetName()
				self.FW_VER = device.GetFirmwareVersion(more=True)
				self.PCB_VER = device.GetPCBVersion()
				self.DEVICE = device
			else:
				self.APP.QT_APP.processEvents()
				self.FWUPD = FirmwareUpdater(app_path, None)

			self.layout = QtWidgets.QGridLayout()
			self.layout.setContentsMargins(-1, 8, -1, 8)
			self.layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
			self.layout_device = QtWidgets.QVBoxLayout()
			
			# ↓↓↓ Current Device Information
			self.grpDeviceInfo = QtWidgets.QGroupBox("Current Firmware")
			self.grpDeviceInfo.setMinimumWidth(420)
			self.grpDeviceInfoLayout = QtWidgets.QVBoxLayout()
			self.grpDeviceInfoLayout.setContentsMargins(-1, 3, -1, -1)
			rowDeviceInfo1 = QtWidgets.QHBoxLayout()
			self.lblDeviceName = QtWidgets.QLabel("Device:")
			self.lblDeviceName.setMinimumWidth(120)
			self.lblDeviceNameResult = QtWidgets.QLabel("GBFlash")
			rowDeviceInfo1.addWidget(self.lblDeviceName)
			rowDeviceInfo1.addWidget(self.lblDeviceNameResult)
			rowDeviceInfo1.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo1)
			rowDeviceInfo3 = QtWidgets.QHBoxLayout()
			self.lblDeviceFWVer = QtWidgets.QLabel("Firmware version:")
			self.lblDeviceFWVer.setMinimumWidth(120)
			self.lblDeviceFWVerResult = QtWidgets.QLabel("L12")
			rowDeviceInfo3.addWidget(self.lblDeviceFWVer)
			rowDeviceInfo3.addWidget(self.lblDeviceFWVerResult)
			rowDeviceInfo3.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo3)
			self.grpDeviceInfo.setLayout(self.grpDeviceInfoLayout)
			self.layout_device.addWidget(self.grpDeviceInfo)
			# ↑↑↑ Current Device Information
			
			# ↓↓↓ Available Firmware Updates
			self.grpAvailableFwUpdates = QtWidgets.QGroupBox("Available Firmware")
			self.grpAvailableFwUpdates.setMinimumWidth(400)
			self.grpAvailableFwUpdatesLayout = QtWidgets.QVBoxLayout()
			self.grpAvailableFwUpdatesLayout.setContentsMargins(-1, 3, -1, -1)

			rowDeviceInfo4 = QtWidgets.QHBoxLayout()
			self.lblDeviceFWVer2 = QtWidgets.QLabel("Firmware version:")
			self.lblDeviceFWVer2.setMinimumWidth(120)
			self.lblDeviceFWVer2Result = QtWidgets.QLabel("(Please choose the PCB version)")
			rowDeviceInfo4.addWidget(self.lblDeviceFWVer2)
			rowDeviceInfo4.addWidget(self.lblDeviceFWVer2Result)
			rowDeviceInfo4.addStretch(1)
			self.grpAvailableFwUpdatesLayout.addLayout(rowDeviceInfo4)

			self.rowUpdate = QtWidgets.QHBoxLayout()
			self.btnUpdate = QtWidgets.QPushButton("Install Firmware Update")
			self.btnUpdate.setMinimumWidth(200)
			self.btnUpdate.setContentsMargins(20, 20, 20, 20)
			self.connect(self.btnUpdate, QtCore.SIGNAL("clicked()"), lambda: [ self.UpdateFirmware() ])
			self.rowUpdate.addStretch()
			self.rowUpdate.addWidget(self.btnUpdate)
			self.rowUpdate.addStretch()

			self.grpAvailableFwUpdatesLayout.addSpacing(3)
			self.grpAvailableFwUpdatesLayout.addItem(self.rowUpdate)
			self.grpAvailableFwUpdates.setLayout(self.grpAvailableFwUpdatesLayout)
			self.layout_device.addWidget(self.grpAvailableFwUpdates)
			# ↑↑↑ Available Firmware Updates

			self.grpStatus = QtWidgets.QGroupBox("")
			self.grpStatusLayout = QtWidgets.QGridLayout()
			self.prgStatus = QtWidgets.QProgressBar()
			self.prgStatus.setMinimum(0)
			self.prgStatus.setMaximum(1000)
			self.prgStatus.setValue(0)
			self.lblStatus = QtWidgets.QLabel("Ready.")

			self.grpStatusLayout.addWidget(self.prgStatus, 1, 0)
			self.grpStatusLayout.addWidget(self.lblStatus, 2, 0)
			
			self.grpStatus.setLayout(self.grpStatusLayout)
			self.layout_device.addWidget(self.grpStatus)
			
			self.grpFooterLayout = QtWidgets.QHBoxLayout()
			self.btnClose = QtWidgets.QPushButton("&Close")
			self.connect(self.btnClose, QtCore.SIGNAL("clicked()"), lambda: [ self.reject() ])
			self.grpFooterLayout.addStretch()
			self.grpFooterLayout.addWidget(self.btnClose)
			self.layout_device.addItem(self.grpFooterLayout)

			self.layout.addLayout(self.layout_device, 0, 0)
			self.setLayout(self.layout)

			self.lblDeviceNameResult.setText(self.DEV_NAME + " " + self.PCB_VER)
			self.lblDeviceFWVerResult.setText(self.FW_VER)
			self.SetPCBVersion()
		
		def SetPCBVersion(self):
			file_name = self.FWUPD.APP_PATH + "/res/fw_GBFlash.zip"

			with zipfile.ZipFile(file_name) as zip:
				with zip.open("fw.ini") as f: ini_file = f.read()
				ini_file = ini_file.decode(encoding="utf-8")
				self.INI = Util.IniSettings(ini=ini_file, main_section="Firmware")
				self.OFW_VER = self.INI.GetValue("fw_ver")
				self.OFW_BUILDTS = self.INI.GetValue("fw_buildts")
				self.OFW_TEXT = self.INI.GetValue("fw_text")
			
			self.lblDeviceFWVer2Result.setText("{:s} ({:s})".format(self.OFW_VER, datetime.datetime.fromtimestamp(int(self.OFW_BUILDTS)).astimezone().replace(microsecond=0).isoformat()))

		def run(self):
			try:
				self.layout.update()
				self.layout.activate()
				screenGeometry = QDesktopWidget().screenGeometry(self)
				x = (screenGeometry.width() - self.width()) / 2
				y = (screenGeometry.height() - self.height()) / 2
				self.move(x, y)
				self.show()
			except:
				return
		
		def hideEvent(self, event):
			if self.DEVICE is None:
				self.APP.ConnectDevice()
			self.APP.activateWindow()
		
		def reject(self):
			if self.CloseDialog():
				super().reject()
		
		def CloseDialog(self):
			if self.btnClose.isEnabled() is False:
				text = "<b>WARNING:</b> If you close this window while a firmware update is still running, it may leave the device in an unbootable state. You can still recover it by running the Firmware Updater again later.<br><br>Are you sure you want to close this window?"
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle="FlashGBX", text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.No)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.No: return False
			return True
		
		def UpdateFirmware(self):
			file_name = self.FWUPD.APP_PATH + "/res/fw_GBFlash.zip"

			if self.APP.CONN is None or self.APP.CONN.BootloaderReset() is False:
				self.APP.DisconnectDevice()
				text = "Please follow these steps to proceed with the firmware update:<ol><li>Unplug your GBFlash device.</li><li>On your GBFlash circuit board, push and hold the small button (U22) while plugging the USB cable back in.</li><li>If done right, the blue LED labeled “ACT” should now keep blinking twice.</li><li>Click OK to continue.</li></ol>"
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="FlashGBX", text=text, standardButtons=QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.Ok)
				msgbox.setTextFormat(QtCore.Qt.TextFormat.RichText)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.Cancel: return
			else:
				self.APP.DisconnectDevice()
				time.sleep(1)
			
			self.btnUpdate.setEnabled(False)
			self.btnClose.setEnabled(False)
			
			while True:
				ret = self.FWUPD.WriteFirmware(file_name, self.SetStatus)
				if ret == 1: 
					text = "The firmware update is complete!"
					if self.PCB_VER != "v1.3":
						text += "\n\nPlease re-connect the USB cable now."
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle="FlashGBX", text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					self.DEVICE = None
					self.reject()
					return True
				elif ret == 2:
					text = "The firmware update has failed. Please try again."
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="FlashGBX", text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return False
				elif ret == 3:
					text = "The firmware update file is corrupted. Please re-install the application."
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="FlashGBX", text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return False
		
		def SetStatus(self, text, enableUI=False, setProgress=None, cloneError=False):
			self.lblStatus.setText("Status: {:s}".format(text))

			if cloneError:
				text = "Your GBFlash device reported a registration error, which means it may be an illegitimate clone. If the error persists, try to get a refund from the seller.\r\n\r\n" + text
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle="FlashGBX", text=text, standardButtons=QtWidgets.QMessageBox.Ok)
				answer = msgbox.exec()
				return False

			if setProgress is not None:
				self.prgStatus.setValue(setProgress * 10)
			if enableUI:
				self.btnUpdate.setEnabled(True)
				self.btnClose.setEnabled(True)
			self.APP.QT_APP.processEvents()
except ImportError:
	pass
