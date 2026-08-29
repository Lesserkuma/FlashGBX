# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

# pylint: disable=wildcard-import, unused-wildcard-import
import datetime, os, platform, struct, time, zipfile
from serial import SerialException
from .app import AppInfo
from .LK_Device import *
from .i18n import __, c__
from .IniSettings import IniSettings

class GbxDevice(LK_Device):
	DEVICE_NAME = "Joey Jr"
	DEVICE_MIN_FW = 1
	DEVICE_MAX_FW = 12
	DEVICE_LATEST_FW_TS = 1787946056
	PCB_VERSIONS = { -1:"", 0x01:"V2", 0x81:"V2", 0x02:"V2C", 0x82:"V2C", 0x03:"V2CC", 0x83:"V2CC/V2++" }
	DEVICE_LABEL_LONG = "Joey Jr"
	DEVICE_LABEL_SHORT = "Joey Jr"
	FWUPDATE_ACTION = "fwupdate-joeyjr"
	CLI_UPDATER_METHOD = "UpdateFirmwareJoeyJr"
	DEVICE_SUPPORT_MESSAGE = "For help with your Joey Jr, please visit the BennVenn Discord:\nhttps://discord.gg/F5ckxM2"
	MAX_BUFFER_READ = 0x1000
	MAX_BUFFER_WRITE = 0x800

	def __init__(self):
		pass

	def Initialize(self, flashcarts, port=None, max_baud=2000000):
		if self.IsConnected(): self.DEVICE.close()
		conn_msg = []
		ports = []
		if port is not None:
			ports = [ port ]
		else:
			comports = serial.tools.list_ports.comports()
			for i in range(0, len(comports)):
				if comports[i].vid == 0x483 and comports[i].pid == 0x5740:
					ports.append(comports[i].device)
			if len(ports) == 0: return False

		for i in range(0, len(ports)):
			if self.TryConnect(ports[i], max_baud):
				self.BAUDRATE = max_baud
				dev = serial.Serial(ports[i], self.BAUDRATE, timeout=0.1)
				self.DEVICE = dev
			else:
				continue

			if self.FW is None or self.FW == {}: continue

			dprint(f"Found a {self.DEVICE_NAME}")
			dprint("Firmware information:", self.FW)
			# dprint("Baud rate:", self.BAUDRATE)

			if self.DEVICE is None or not self.IsConnected():
				self.DEVICE = None
				if self.FW is not None:
					conn_msg.append([0, __("Couldn’t communicate with the {device_name} on port {port}. Please disconnect and reconnect the device, then try again.", device_name=self.DEVICE_NAME, port=ports[i])])
				continue
			elif self.FW is None:
				dev.close()
				self.DEVICE = None
				continue
			elif self.FW["cfw_id"] == "G": # Not a CFW by Lesserkuma
				dprint("Device runs the JoeyGUI firmware")
			elif self.FW["pcb_ver"] not in self.PCB_VERSIONS.keys() or "cfw_id" not in self.FW or self.FW["cfw_id"] != 'L' or self.FW["fw_ver"] < self.DEVICE_MIN_FW: # Not a CFW by Lesserkuma
				dprint("Incompatible firmware:", self.FW)
				dev.close()
				self.DEVICE = None
				continue
			elif self.FW["fw_ts"] > self.DEVICE_LATEST_FW_TS:
				conn_msg.append([1, __("Note: The {device_name} on port {port} is running a firmware version that is newer than what this version of FlashGBX was developed to work with, so errors may occur.", device_name=self.DEVICE_NAME, port=ports[i])])

			if (self.FW["pcb_ver"] & 0x7F) == 1:
				conn_msg.append([2, __("Warning: Your {device_name} does not support the software-controlled voltage setting feature, so please be extra careful and always set the switch to the correct voltage before inserting a cartridge.", device_name=self.DEVICE_NAME)])

			self.PORT = ports[i]
			self.DEVICE.timeout = self.DEVICE_TIMEOUT

			# Load Flash Cartridge Handlers
			self.UpdateFlashCarts(flashcarts)

			# Stop after first found device
			break

		return conn_msg

	def LoadFirmwareVersion(self):
		dprint("Querying firmware version")
		try:
			self.DEVICE.timeout = 0.075
			self.DEVICE.reset_input_buffer()
			self.DEVICE.reset_output_buffer()

			self._write(bytearray(b'\x55\xAA'))
			time.sleep(0.01)
			device_id = self.DEVICE.read(self.DEVICE.in_waiting)

			if b"Joey" not in device_id:
				dprint("Not a Joey Jr")
				self.FW = None
				return False

			if b"FW L" not in device_id:
				dprint("Not running LK firmware")
				if b"GUI" in device_id or b"FW vG" in device_id:
					pcb_name = device_id[1:].decode("UTF-8", "ignore")
					self.FW = {
						"pcb_ver":-1,
						"pcb_name":f"{pcb_name}",
						"cfw_id":"G",
						"fw_ver":0,
						"fw_ts":0,
						"fw_dt":"JoeyGUI",
						"cart_power_ctrl":False,
						"bootloader_reset":True
					}
					return True
				return False

			if device_id[0] == 0:
				self._write(bytearray(b'LK')) # Enable LK firmware
				if self.DEVICE.read(1) != b'\xFF':
					dprint("LK firmware was not enabled successfully")
					self.FW = None
					return False

			self._write(self.DEVICE_CMD["QUERY_FW_INFO"])
			size = self.DEVICE.read(1)
			self.DEVICE.timeout = self.DEVICE_TIMEOUT
			if len(size) == 0:
				dprint("No response")
				self.FW = None
				return False
			size = struct.unpack("B", size)[0]
			if size != 8:
				print(size)
				return False
			data = self._read(size)
			info = data[:8]
			keys = ["cfw_id", "fw_ver", "pcb_ver", "fw_ts"]
			values = struct.unpack(">cHBI", bytearray(info))
			self.FW = dict(zip(keys, values))
			self.FW["cfw_id"] = self.FW["cfw_id"].decode('ascii')
			self.FW["fw_dt"] = datetime.datetime.fromtimestamp(self.FW["fw_ts"]).astimezone().replace(microsecond=0).isoformat()
			self.FW["ofw_ver"] = None
			self.FW["pcb_name"] = None
			self.FW["cart_power_ctrl"] = False
			self.FW["bootloader_reset"] = False
			if self.FW["cfw_id"] == "L" and self.FW["fw_ver"] >= 12:
				size = self._read(1)
				name = self._read(size)
				if len(name) > 0:
					try:
						self.FW["pcb_name"] = name.decode("UTF-8").replace("\x00", "").strip()
					except:
						self.FW["pcb_name"] = "Unnamed Device"
					self.DEVICE_NAME = self.FW["pcb_name"]

				# Cartridge Power Control support
				temp = self._read(1)
				self.FW["cart_power_ctrl"] = True if temp & 1 == 1 else False
				self.FW["cart_presence_switch"] = True if (temp >> 1) & 1 == 1 else False
				self.FW["cart_mode_switch"] = True if (temp >> 2) & 1 == 1 else False

				# Reset to bootloader support
				self.FW["bootloader_reset"] = True if self._read(1) == 1 else False
			return True

		except Exception as e:
			dprint("Disconnecting due to an error", e, sep="\n")
			try:
				if self.DEVICE.isOpen():
					self.DEVICE.reset_input_buffer()
					self.DEVICE.reset_output_buffer()
					self.DEVICE.close()
				self.DEVICE = None
			except:
				pass
			return False

	def ChangeBaudRate(self, _):
		dprint("Baudrate change is not supported.")

	def GetFirmwareVersion(self, more=False):
		if self.FW["pcb_ver"] == -1:
			return "JoeyGUI"

		base = "{:s}{:d}".format(self.FW["cfw_id"], self.FW["fw_ver"])
		if self.FW["pcb_name"] is None:
			base = base + " <" + __("unverified") + ">"
		if more:
			return "{base} ({dt})".format(base=base, dt=self.FW["fw_dt"])
		return base

	def GetFullNameLabel(self):
		if self.FW["pcb_ver"] == -1:
			return self.FW["pcb_name"]
		return super().GetFullNameLabel()

	def GetFullName(self):
		return self.GetName()

	def GetFullNameExtended(self, more=False):
		if self.FW["pcb_ver"] == -1:
			return self.FW["pcb_name"]

		if more:
			return __("{device_name} – Firmware {fw_version} ({timestamp}) on {port}", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), timestamp=self.FW["fw_dt"], port=self.GetPort())
		else:
			return __("{device_name} – Firmware {fw_version} ({port})", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), port=self.GetPort())

	def CanSetVoltageBySwitch(self):
		return ((self.FW["pcb_ver"] & 0x7F) == 1)

	def CanSetVoltageByCode(self):
		if ((self.FW["pcb_ver"] & 0x7F) == 1): return False
		return True

	def CanSetVoltageByAutoswitch(self):
		return False

	def CanPowerCycleCart(self):
		return self.FW["cart_power_ctrl"]

	def GetSupprtedModes(self):
		return ["DMG", "AGB"]

	def IsSupported3dMemory(self):
		return True

	def IsClkConnected(self):
		return True

	def SupportsFirmwareUpdates(self):
		return True

	def FirmwareUpdateAvailable(self):
		if self.FW["cfw_id"] == "G":
			self.FW_UPDATE_REQ = True
			return True
		if self.FW["fw_ts"] != self.DEVICE_LATEST_FW_TS:
			return True
		self.FW_UPDATE_REQ = False
		return False

	def GetFirmwareUpdaterClass(self):
		try:
			return (None, FirmwareUpdaterWindow)
		except:
			return None

	def ResetLEDs(self):
		pass

	def SupportsBootloaderReset(self):
		return self.FW["bootloader_reset"]

	def BootloaderReset(self):
		if not self.SupportsBootloaderReset(): return False
		dprint("Resetting to bootloader...")
		try:
			self._write(self.DEVICE_CMD["BOOTLOADER_RESET"], wait=True)
			self._write(1)
			self.Close()
			return True
		except Exception as e:
			print(__("Disconnecting..."), e)
			return False

	def SupportsAudioAsWe(self):
		return True

	def Close(self, cartPowerOff=False):
		if self.FW["cfw_id"] == "G":
			self.DEVICE.close()

		if self.IsConnected():
			dprint("Disconnecting from the device")
			try:
				if cartPowerOff and self.CanPowerCycleCart():
					self._set_fw_variable("AUTO_POWEROFF_TIME", 0)
					self._write(self.DEVICE_CMD["CART_PWR_OFF"], wait=self.FW["fw_ver"] >= 12)
				else:
					self._write(self.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=self.FW["fw_ver"] >= 12)
				self.DEVICE.write(b'KL') # Disable LK firmware
				self.DEVICE.read(1)
				self.DEVICE.close()
			except:
				self.DEVICE = None
			self.MODE = None


class FirmwareUpdater():
	PORT = None
	DEVICE = None

	def __init__(self, app_path=".", port=None):
		self.APP_PATH = app_path
		self.PORT = port

	def CalcChecksum(self, buffer):
		checksum = 0
		for value in buffer[:0xFFFC]:
			checksum += value
		return checksum

	def TryConnect(self, port):
		return True

	def WriteFirmwareMSC(self, path, buffer, fncSetStatus):
		file = path
		path = os.path.dirname(path) + os.sep
		fncSetStatus(text=__("Connecting... This may take a moment."))

		filename = os.path.split(file)[1]
		filepath = os.path.split(file)[0]
		with open(filepath + os.sep + filename, "rb") as f: temp = f.read().decode("UTF-8", "ignore")
		if not temp.startswith("UPDATE"):
			with open(file, "wb") as f:
				temp = bytearray(b"UPDATE")
				temp += bytearray([0] * (256 - len(temp)))
				f.write(temp)
			hp = 30
			while hp > 0:
				if os.path.exists(path + "FIRMWARE.JR"): break
				time.sleep(1)
				hp -= 1
			if hp == 0:
				fncSetStatus(text=__("Couldn’t communicate with the Joey Jr device."))
				return 2

		try:
			with open(filepath + os.sep + filename, "rb") as f: temp = f.read().decode("UTF-8", "ignore")
		except FileNotFoundError as e:
			try:
				if filename == "MODE.TXT":
					with open(filepath + os.sep + "MODE!.TXT", "rb") as f: temp = f.read().decode("UTF-8", "ignore")
				else:
					raise FileNotFoundError from e
			except FileNotFoundError:
				fncSetStatus(text=__("Couldn’t access the {mode_txt} file. Remove cartridge and try again.", mode_txt="MODE.TXT"))
				return 2

		if not temp.startswith("UPDATE"):
			fncSetStatus(text=__("Couldn’t enter {update} mode. Please try again.", update="UPDATE"))
			return 2

		fncSetStatus(text=__("Updating firmware... Do not unplug the device!"), setProgress=0)
		os.unlink(path + "FIRMWARE.JR")
		if os.path.exists(path + "FIRMWARE.JR"):
			fncSetStatus(text=__("Couldn’t write new firmware. Please try again."))
			return 2

		try:
			f = open(path + "FIRMWARE.JR", "wb")
		except OSError:
			fncSetStatus(text=__("Couldn’t write new firmware. Please try again."))
			return 2

		for i in range(0, len(buffer), 64):
			f.write(buffer[i:i+64])
			percent = float(i + 64) / len(buffer) * 100
			fncSetStatus(text=__("Updating firmware... Do not unplug the device!"), setProgress=percent)

		try:
			f.close()
		except OSError:
			pass

		if b"Joey Jr. Firmware" not in buffer:
			hp = 5
			while hp > 0:
				if not os.path.exists(path + "FIRMWARE.JR"): break
				time.sleep(1)
				hp -= 1
			if hp == 0:
				fncSetStatus(text=__("Couldn’t verify. Please try again."))
				return 2

		fncSetStatus(__("Done!"))
		time.sleep(2)

		return True

	def WriteFirmware(self, buffer, fncSetStatus):
		if len(buffer) < 0x10000:
			return 3
		if struct.unpack(">I", buffer[0xFFFC:0x10000])[0] != self.CalcChecksum(buffer): return 3

		# Check for serial mode
		if self.PORT is None:
			ports = []
			comports = serial.tools.list_ports.comports()
			for i in range(0, len(comports)):
				if comports[i].vid == 0x483 and comports[i].pid == 0x5740:
					ports.append(comports[i].device)
			if len(ports) == 0:
				return 4
			port = ports[0]
		else:
			port = self.PORT

		while True:
			fncSetStatus(text=__("Connecting..."))
			try:
				dev = serial.Serial(port, 2000000, timeout=0.2)
			except SerialException as e:
				if "Errno 13" in str(e) and platform.system() == "Linux":
					fncSetStatus(text=__("No permission to use device! See the {readme} file.", readme="README.md"), enableUI=True)
				else:
					fncSetStatus(text=__("Device not accessible."), enableUI=True)
				return 2
			except:
				fncSetStatus(text=__("Unknown error while accessing the device."), enableUI=True)
				return 2
			dev.reset_input_buffer()

			fncSetStatus(__("Identifying device..."))
			dev.write(b'\x55\xAA')
			time.sleep(0.01)
			device_id = dev.read(dev.in_waiting)

			if b"Joey" not in device_id:
				# print("Not a Joey Jr")
				fncSetStatus(__("Joey Jr device not found."))
				return 2

			if b"FW L" in device_id and device_id[-1] != 0:
				fncSetStatus(__("Rebooting device..."))
				dev.write(b'\xF1')
				dev.read(1)
				dev.write(b'\x01')
				dev.close()
				time.sleep(0.5)
				continue
			break

		dev.write(b'\xFE\x01')
		time.sleep(0.01)
		dev.read(1)
		# print("")

		size = len(buffer)
		counter = 0
		while counter < size:
			percent = float(counter)/size*100
			fw_buffer = buffer[counter:counter+64]
			dev.write(fw_buffer)
			time.sleep(0.001)
			try:
				temp = dev.read(dev.in_waiting)
			except:
				temp = False
			if temp is not False:
				# print("Flashing...", hex(i), end="\r")
				pass
			elif counter + 64 < size:
				fncSetStatus(text=__("Error! Bad response at {address}!", address="0x{address:X}".format(address=counter)), setProgress=percent)
				return 2

			counter += 64
			fncSetStatus(text=__("Updating firmware... Do not unplug the device!"), setProgress=percent)

		dev.close()
		time.sleep(1)
		fncSetStatus(__("Done!"), setProgress=100)
		time.sleep(2)
		return 1


try:
	from .pyside import QtCore, QtWidgets, QtGui, QDesktopWidget

	class FirmwareUpdaterWindow(QtWidgets.QDialog):
		APP = None
		DEVICE = None
		FWUPD = None
		DEV_NAME = "Joey Jr"
		FW_VER = ""
		PCB_VER = ""

		def __init__(self, app, app_path, file=None, icon=None, device=None):
			QtWidgets.QDialog.__init__(self, app)
			if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
			self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
			self.setWindowTitle("FlashGBX – " + __("Firmware Updater for {device_name}", device_name="Joey Jr"))
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
			self.grpDeviceInfo = QtWidgets.QGroupBox(__("Current Firmware"))
			self.grpDeviceInfo.setMinimumWidth(420)
			self.grpDeviceInfoLayout = QtWidgets.QVBoxLayout()
			self.grpDeviceInfoLayout.setContentsMargins(-1, 3, -1, -1)
			rowDeviceInfo1 = QtWidgets.QHBoxLayout()
			self.lblDeviceName = QtWidgets.QLabel(__("Device:"))
			self.lblDeviceName.setMinimumWidth(120)
			self.lblDeviceNameResult = QtWidgets.QLabel("Joey Jr")
			rowDeviceInfo1.addWidget(self.lblDeviceName)
			rowDeviceInfo1.addWidget(self.lblDeviceNameResult)
			rowDeviceInfo1.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo1)
			rowDeviceInfo3 = QtWidgets.QHBoxLayout()
			self.lblDeviceFWVer = QtWidgets.QLabel(__("Firmware version:"))
			self.lblDeviceFWVer.setMinimumWidth(120)
			self.lblDeviceFWVerResult = QtWidgets.QLabel()
			rowDeviceInfo3.addWidget(self.lblDeviceFWVer)
			rowDeviceInfo3.addWidget(self.lblDeviceFWVerResult)
			rowDeviceInfo3.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo3)
			self.grpDeviceInfo.setLayout(self.grpDeviceInfoLayout)
			self.layout_device.addWidget(self.grpDeviceInfo)
			# ↑↑↑ Current Device Information

			# ↓↓↓ Available Firmware Updates
			file_name = self.FWUPD.APP_PATH + os.sep + os.path.join("res", "fw_JoeyJr.zip")

			try:
				with zipfile.ZipFile(file_name) as zip:
					with zip.open("fw.ini") as f: ini_file = f.read()
					ini_file = ini_file.decode(encoding="utf-8")
					self.INI = IniSettings(ini=ini_file, main_section="Firmware")
					self.FW_LK_VER = __("LK firmware version {version} by {author} (updated on {date})", version=self.INI.GetValue("fw_ver"), author="Lesserkuma", date=datetime.datetime.fromtimestamp(int(self.INI.GetValue("fw_buildts"))).strftime("%x"))
					self.FW_LK_BUILDTS = self.INI.GetValue("fw_buildts")
					self.FW_LK_TEXT = "<ul><li>" + __("For use with the FlashGBX software\nNo support by BennVenn").replace("\n", "</li><li>") + "</li></ul>"
					self.FW_MSC_VER = __("BennVenn Drag’n’Drop firmware version {version} (updated on {date})", version=self.INI.GetValue("fw_msc_ver"), date=datetime.datetime.fromtimestamp(int(self.INI.GetValue("fw_msc_buildts"))).strftime("%x"))
					self.FW_MSC_TEXT = "<ul><li>" + __("For use with the Windows file explorer") + "</li></ul>"
					self.FW_JOEYGUI_VER = __("BennVenn JoeyGUI firmware version {version} (updated on {date})", version=self.INI.GetValue("fw_joeygui_ver"), date=datetime.datetime.fromtimestamp(int(self.INI.GetValue("fw_joeygui_buildts"))).strftime("%x"))
					self.FW_JOEYGUI_TEXT = "<ul><li>" + __("For use with the JoeyGUI software") + "</li></ul>"
			except (FileNotFoundError, zipfile.BadZipFile, KeyError, ValueError):
				QtWidgets.QMessageBox.critical(self, __("Error"), __("The firmware update file is corrupted."))
				self.reject()
				return

			self.grpAvailableFwUpdates = QtWidgets.QGroupBox(__("Firmware Update Options"))
			self.grpAvailableFwUpdates.setMinimumWidth(400)
			self.grpAvailableFwUpdatesLayout = QtWidgets.QVBoxLayout()
			self.grpAvailableFwUpdatesLayout.setContentsMargins(-1, 3, -1, -1)

			self.optFW_LK = QtWidgets.QRadioButton("{:s}".format(self.FW_LK_VER))
			self.lblFW_LK_Info = QtWidgets.QLabel("{:s}".format(self.FW_LK_TEXT))
			self.lblFW_LK_Info.setWordWrap(True)
			self.lblFW_LK_Info.mousePressEvent = lambda x: [ self.optFW_LK.setChecked(True) ]
			self.optFW_MSC = QtWidgets.QRadioButton("{:s}".format(self.FW_MSC_VER))
			self.lblFW_MSC_Info = QtWidgets.QLabel("{:s}".format(self.FW_MSC_TEXT))
			self.lblFW_MSC_Info.setWordWrap(True)
			self.lblFW_MSC_Info.mousePressEvent = lambda x: [ self.optFW_MSC.setChecked(True) ]
			self.optFW_JoeyGUI = QtWidgets.QRadioButton("{:s}".format(self.FW_JOEYGUI_VER))
			self.lblFW_JoeyGUI_Info = QtWidgets.QLabel("{:s}".format(self.FW_JOEYGUI_TEXT))
			self.lblFW_JoeyGUI_Info.setWordWrap(True)
			self.lblFW_JoeyGUI_Info.mousePressEvent = lambda x: [ self.optFW_JoeyGUI.setChecked(True) ]
			self.optExternal = QtWidgets.QRadioButton(__("External FIRMWARE.JR file"))

			self.rowUpdate = QtWidgets.QHBoxLayout()
			self.btnUpdate = QtWidgets.QPushButton(__("Install Firmware Update"))
			self.btnUpdate.setMinimumWidth(200)
			self.btnUpdate.setContentsMargins(20, 20, 20, 20)
			self.connect(self.btnUpdate, QtCore.SIGNAL("clicked()"), lambda: [ self.UpdateFirmware() ])
			self.rowUpdate.addStretch()
			self.rowUpdate.addWidget(self.btnUpdate)
			self.rowUpdate.addStretch()

			self.rowUpdate2 = QtWidgets.QHBoxLayout()
			self.lblUpdateDisclaimer = QtWidgets.QLabel(__("Please note that FlashGBX is not officially supported by BennVenn."))
			self.lblUpdateDisclaimer.setWordWrap(True)
			self.lblUpdateDisclaimer.setAlignment(QtGui.Qt.AlignmentFlag.AlignCenter)
			self.rowUpdate2.addWidget(self.lblUpdateDisclaimer)

			self.grpAvailableFwUpdatesLayout.addWidget(self.optFW_LK)
			self.grpAvailableFwUpdatesLayout.addWidget(self.lblFW_LK_Info)
			self.optFW_LK.setChecked(True)
			self.grpAvailableFwUpdatesLayout.addWidget(self.optFW_MSC)
			self.grpAvailableFwUpdatesLayout.addWidget(self.lblFW_MSC_Info)
			self.grpAvailableFwUpdatesLayout.addWidget(self.optFW_JoeyGUI)
			self.grpAvailableFwUpdatesLayout.addWidget(self.lblFW_JoeyGUI_Info)
			self.grpAvailableFwUpdatesLayout.addWidget(self.optExternal)
			self.grpAvailableFwUpdatesLayout.addSpacing(3)
			self.grpAvailableFwUpdatesLayout.addItem(self.rowUpdate)
			self.grpAvailableFwUpdatesLayout.addItem(self.rowUpdate2)
			self.grpAvailableFwUpdates.setLayout(self.grpAvailableFwUpdatesLayout)
			self.layout_device.addWidget(self.grpAvailableFwUpdates)
			# ↑↑↑ Available Firmware Updates

			self.grpStatus = QtWidgets.QGroupBox("")
			self.grpStatusLayout = QtWidgets.QGridLayout()
			self.prgStatus = QtWidgets.QProgressBar()
			self.prgStatus.setMinimum(0)
			self.prgStatus.setMaximum(1000)
			self.prgStatus.setValue(0)
			self.lblStatus = QtWidgets.QLabel(__("Status: Ready."))

			self.grpStatusLayout.addWidget(self.prgStatus, 1, 0)
			self.grpStatusLayout.addWidget(self.lblStatus, 2, 0)

			self.grpStatus.setLayout(self.grpStatusLayout)
			self.layout_device.addWidget(self.grpStatus)

			self.grpFooterLayout = QtWidgets.QHBoxLayout()
			self.btnClose = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Close"))
			self.connect(self.btnClose, QtCore.SIGNAL("clicked()"), lambda: [ self.reject() ])
			self.grpFooterLayout.addStretch()
			self.grpFooterLayout.addWidget(self.btnClose)
			self.layout_device.addItem(self.grpFooterLayout)

			self.layout.addLayout(self.layout_device, 0, 0)
			self.setLayout(self.layout)

			self.lblDeviceNameResult.setText(self.DEV_NAME + " " + self.PCB_VER)
			self.lblDeviceFWVerResult.setText(self.FW_VER)

			# if platform.system() == 'Darwin':
			# 	self.optFW_MSC.setVisible(False)
			# 	self.lblFW_MSC_Info.setVisible(False)

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
				text = __("<b>Warning:</b> If you close this window while a firmware update is still running, it might leave the device in an unbootable state.") + " " + __("You can still recover it by running the Firmware Updater again later.") + "<br><br>" + __("Are you sure you want to close this window?")
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Warning, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.No)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.No: return False
			return True

		def UpdateFirmware(self):
			with zipfile.ZipFile(self.FWUPD.APP_PATH + os.sep + os.path.join("res", "fw_JoeyJr.zip")) as archive:
				fw = ""
				path = ""
				verified = False
				if self.optFW_LK.isChecked():
					fw = self.FW_LK_VER
					fn = "FIRMWARE_LK.JR"
					with archive.open(fn) as f: fw_data = bytearray(f.read())
					if (b"Joey Jr" in fw_data and b"FW LK" in fw_data): verified = True
				elif self.optFW_MSC.isChecked():
					fw = self.FW_MSC_VER
					fn = "FIRMWARE_MSC.JR"
					with archive.open(fn) as f: fw_data = bytearray(f.read())
					if (b"Joey Jr. Firmware" in fw_data): verified = True
				elif self.optFW_JoeyGUI.isChecked():
					fw = self.FW_JOEYGUI_VER
					fn = "FIRMWARE_JOEYGUI.JR"
					with archive.open(fn) as f: fw_data = bytearray(f.read())
					if (b"Joey Jr" in fw_data and b"FW GUI" in fw_data): verified = True
				else:
					path = self.APP.SETTINGS.value("LastDirFirmwareUpdate")
					path = QtWidgets.QFileDialog.getOpenFileName(self, __("Choose Joey Jr Firmware File"), path, __("Firmware Update ({firmware_jr})", firmware_jr="FIRMWARE.JR"))[0]
					if path == "": return
					if not os.path.basename(path).endswith(".JR"):
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=__("The expected filename for a valid firmware file is <b>{filename_pattern}</b>. Please visit {url} for the latest official firmware updates.", firmware_jr="FIRMWARE.JR", url='<a href="https://bennvenn.myshopify.com/products/usb-gb-c-cart-dumper-the-joey-jr">https://bennvenn.myshopify.com/products/usb-gb-c-cart-dumper-the-joey-jr</a>'), standardButtons=QtWidgets.QMessageBox.Ok)
						answer = msgbox.exec()
						return
					elif os.path.exists(os.path.dirname(path) + "DEBUG.TXT"):
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=__("The selected file can not be used. Please visit {url} for the latest official firmware updates.", url='<a href="https://bennvenn.myshopify.com/products/usb-gb-c-cart-dumper-the-joey-jr">https://bennvenn.myshopify.com/products/usb-gb-c-cart-dumper-the-joey-jr</a>'), standardButtons=QtWidgets.QMessageBox.Ok)
						answer = msgbox.exec()
						return
					self.APP.SETTINGS.setValue("LastDirFirmwareUpdate", os.path.dirname(path))
					fw = path
					fn = None
					try:
						with open(path, "rb") as f: fw_data = bytearray(f.read())
						index_from = fw_data.index(b"Joey Jr")
						index_to = fw_data[index_from:].index(b"\x00")
						fw_string = fw_data[index_from:index_from+index_to].decode("ASCII", "ignore")
						if "Firmware" in fw_string:
							fw += "<br><br><b>" + __("Detected firmware string:") + "</b><br>" + fw_string
							if "N64 Firmware" in fw_string: raise ValueError(__("JoeyN64 Firmware found"))
							if "Jr4Gen3 Firmware" in fw_string: raise ValueError(__("Jr4Gen3 Firmware found"))
						verified = True
						if len(fw_data) > 0x10000:
							verified = False
							raise ValueError(__("Firmware file is too large."))
					except ValueError as e:
						fw += "<br><br>" + __("Warning: The selected firmware file couldn’t be confirmed to be valid automatically ({error}). Please double check that this is a valid firmware file for your Joey Jr. If it is invalid or an update for a different device, it may render your device unusable.", error=str(e))
					except:
						verified = False

			if verified is False:
				text = __("The firmware update file is corrupted or invalid.")
				self.btnUpdate.setEnabled(True)
				self.btnClose.setEnabled(True)
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
				answer = msgbox.exec()
				return False

			text = __("The following firmware will now be written to your Joey Jr device:") + "\n- " + fw
			text += "\n\n" + __("Do you want to continue?")
			msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Question, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
			msgbox.setDefaultButton(QtWidgets.QMessageBox.Yes)
			answer = msgbox.exec()
			if answer == QtWidgets.QMessageBox.No: return
			self.grpAvailableFwUpdates.setEnabled(False)
			self.btnUpdate.setEnabled(False)
			self.btnClose.setEnabled(False)

			self.APP.DisconnectDevice()

			ret = 0
			while True:
				if ret == 4:
					ret = self.FWUPD.WriteFirmwareMSC(path, fw_data, self.SetStatus)
				else:
					ret = self.FWUPD.WriteFirmware(fw_data, self.SetStatus)

				if ret == 1:
					text = __("The firmware update is complete!")
					if self.optFW_MSC.isChecked():
						text += "\n\n" + __("Please note that you need to manually copy over the {romlist} file. You can find the latest version of it on the Joey Jr website.", romlist="ROMLIST.RAW")
					self.grpAvailableFwUpdates.setEnabled(True)
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					self.DEVICE = None
					self.reject()
					return True
				elif ret == 2:
					text = __("The firmware update has failed. Please try again.")
					self.grpAvailableFwUpdates.setEnabled(True)
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return False
				elif ret == 3:
					text = __("The firmware update file is corrupted. Please re-install the application.")
					self.grpAvailableFwUpdates.setEnabled(True)
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return False
				elif ret == 4:
					if platform.system() == 'Darwin':
						self.SetStatus(__("No device found."), enableUI=True)
						text = __("If your Joey Jr device is currently running the Drag’n’Drop firmware, please update the firmware on Windows or Linux, or use the standalone firmware updater.")
						msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
						answer = msgbox.exec()
						return False
					answer = QtWidgets.QMessageBox.information(self, AppInfo.NAME, __("If your Joey Jr device is currently running the Drag’n’Drop firmware, please select the <b>{mode_txt}</b> (or <b>{mode_txt_2}</b>) file that is stored on the device.", mode_txt="MODE.TXT", mode_txt_2="MODE!.TXT"), QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
					if answer == QtWidgets.QMessageBox.Cancel:
						self.SetStatus(__("No device found."), enableUI=True)
						return False
					path = self.APP.SETTINGS.value("LastDirFirmwareUpdate")
					path = QtWidgets.QFileDialog.getOpenFileName(self, __("Choose the {mode_txt} file of your Joey Jr removable drive", mode_txt="MODE.TXT"), path, "MODE.TXT (MODE*.TXT)")[0]
					self.APP.QT_APP.processEvents()
					if os.path.basename(path) not in ("MODE.TXT", "MODE!.TXT"):
						self.SetStatus(__("No device found."), enableUI=True)
						return False
					self.APP.SETTINGS.setValue("LastDirFirmwareUpdate", os.path.dirname(path))

		def SetStatus(self, text, enableUI=False, setProgress=None):
			self.lblStatus.setText(__("Status: {text}", text=text))
			if setProgress is not None:
				self.prgStatus.setValue(setProgress * 10)
			if enableUI:
				self.grpAvailableFwUpdates.setEnabled(True)
				self.btnUpdate.setEnabled(True)
				self.btnClose.setEnabled(True)
			self.APP.QT_APP.processEvents()
except ImportError:
	pass
