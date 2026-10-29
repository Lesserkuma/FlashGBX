# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

# pylint: disable=wildcard-import, unused-wildcard-import
import datetime, os, struct, time, zipfile
from enum import IntEnum
from serial import SerialException
from .app import AppInfo
from .LK_Device import *
from .i18n import __, c__
from .IniSettings import IniSettings

class USBMode(IntEnum):
	CH340 = 0
	CDC = 1

USB_IDS = {
	USBMode.CH340:(0x1A86, 0x7523),
	USBMode.CDC:(0x16C0, 0x27DD),
}

class GbxDevice(LK_Device):
	USBMode = USBMode
	DEVICE_NAME = "GBFlash"
	USB_IDS = tuple(USB_IDS.values())
	DEVICE_MIN_FW = 1
	DEVICE_MAX_FW = 12
	DEVICE_LATEST_FW_TS = { 5:1793184971, 10:1793184971, 11:1793184971, 12:1793184971, 13:1793184971 }
	PCB_VERSIONS = { 5:'', 12:'v1.2', 13:'v1.3' }
	DEVICE_LABEL_LONG = "GBFlash"
	DEVICE_LABEL_SHORT = "GBFlash"
	FWUPDATE_ACTION = "fwupdate-gbflash"
	CLI_UPDATER_METHOD = "UpdateFirmwareGBFlash"
	DEVICE_SUPPORT_MESSAGE = "For help with your GBFlash, please visit the GitHub page:\nhttps://github.com/simonkwng/GBFlash/issues"

	MAX_BUFFER_READ = 0x1000
	MAX_BUFFER_WRITE = 0x800
	DEVICE_CMD = LK_Device.DEVICE_CMD.copy()
	DEVICE_CMD.update({
		"SET_USB_MODE_CH340":0x3C,
		"SET_USB_MODE_CDC":0x3E,
	})

	def __init__(self):
		self.DEVICE = None
		self.FW = None
		self.USB_PORT = {}
		self.USB_MODE = None

	def Initialize(self, flashcarts, port=None, max_baud=2000000):
		reconnect = port is not None and self.USB_PORT.get("device") == port
		if self.DEVICE is not None: self.DEVICE.close()
		self.DEVICE = None
		self.FW = None
		conn_msg = []
		ports = []
		usb_ports = self.GetUSBPorts()
		if port is not None:
			ports = [ port ]
		else:
			for i in range(0, len(usb_ports)):
				if (usb_ports[i]["vid"], usb_ports[i]["pid"]) in self.USB_IDS:
					ports.append(usb_ports[i]["device"])
			if len(ports) == 0: return False

		for i in range(0, len(ports)):
			if self.TryConnect(ports[i], max_baud, keep_open=True):
				self.BAUDRATE = max_baud
				dev = self.DEVICE
			else:
				continue

			if self.FW is None or self.FW == {}: continue

			dprint(f"Found a {self.DEVICE_NAME}")
			dprint("Firmware information:", self.FW)

			if self.DEVICE is None or not self.IsConnected():
				dev.close()
				self.DEVICE = None
				if self.FW is not None:
					conn_msg.append([0, __("Couldn’t communicate with the {device_name} on port {port}. Please disconnect and reconnect the device, then try again.", device_name=self.DEVICE_NAME, port=ports[i])])
				continue
			elif not self.IsIdentified():
				dprint("Incompatible firmware:", self.FW)
				dev.close()
				self.DEVICE = None
				continue
			elif self.FW["fw_ts"] > self.DEVICE_LATEST_FW_TS[self.FW["pcb_ver"]]:
				conn_msg.append([1, __("Note: The {device_name} on port {port} is running a firmware version that is newer than what this version of FlashGBX was developed to work with, so errors may occur.", device_name=self.DEVICE_NAME, port=ports[i])])

			self.SetUSBPort(self.GetUSBPort(ports[i], usb_ports))

			self.DEVICE.timeout = self.DEVICE_TIMEOUT

			# Load Flash Cartridge Handlers
			self.UpdateFlashCarts(flashcarts)

			# Stop after first found device
			break

		if reconnect and not self.IsIdentified(): return False
		return conn_msg

	def LoadFirmwareVersion(self):
		dprint("Querying firmware version")
		try:
			self.DEVICE.timeout = 0.075
			self.DEVICE.reset_input_buffer()
			self.DEVICE.reset_output_buffer()
			self._write(self.DEVICE_CMD["QUERY_FW_INFO"])
			size = self.DEVICE.read(1)
			self.DEVICE.timeout = self.DEVICE_TIMEOUT
			if len(size) == 0:
				dprint("No response")
				self.FW = None
				return False
			size = struct.unpack("B", size)[0]
			if size != 8: return False
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

				# Cartridge Power Control support, Switch Power support, and Switch Mode support
				temp = self._read(1)
				self.FW["cart_power_ctrl"] = True if temp & 1 == 1 else False
				self.FW["cart_presence_switch"] = True if (temp >> 1) & 1 == 1 else False
				self.FW["cart_mode_switch"] = True if (temp >> 2) & 1 == 1 else False

				# Reset to bootloader support
				temp = self._read(1)
				self.FW["bootloader_reset"] = bool(temp & 1)
				self.FW["device_serial"] = self.ReadDeviceSerial() if temp & 2 else None
				self.FW["unregistered"] = True if temp >> 7 == 1 else False

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

	def FormatDeviceSerial(self, data):
		return data.hex("-").upper()

	def ChangeBaudRate(self, _):
		dprint("Baudrate change is not supported.")

	@staticmethod
	def GetUSBPorts():
		ports = []
		comports = serial.tools.list_ports.comports()
		for i in range(0, len(comports)):
			ports.append({
				"device":comports[i].device,
				"vid":comports[i].vid,
				"pid":comports[i].pid,
				"location":comports[i].location,
			})
		return ports

	@staticmethod
	def GetUSBPort(name, ports):
		for port in ports:
			if port["device"] == name: return port.copy()
		return { "device":name }

	@staticmethod
	def FindUSBPort(source, before, ports, usb_id, restore=False):
		candidates = []
		for port in ports:
			if (port.get("vid"), port.get("pid")) == usb_id:
				candidates.append(port)

		matches = []
		location = source.get("location")
		if location: location = location.split(":", 1)[0]
		if location:
			for port in candidates:
				port_location = port.get("location")
				if port_location and port_location.split(":", 1)[0] == location: matches.append(port)
		elif restore:
			for port in ports:
				if port["device"] == source["device"] and (port in candidates or (port.get("vid"), port.get("pid")) == (None, None)):
					matches.append(port)
		else:
			known = []
			old_ports = []
			for port in before:
				if (port.get("vid"), port.get("pid")) in USB_IDS.values(): known.append(port)
				if (port.get("vid"), port.get("pid")) == usb_id: old_ports.append(port["device"])
			if len(known) != 1 or known[0]["device"] != source["device"]: return None
			if len(candidates) != 1: return None
			for port in candidates:
				if port["device"] not in old_ports: matches.append(port)

		if len(matches) == 1: return matches[0]
		return None

	def ChangeUSBMode(self, mode):
		if isinstance(mode, bool) or not isinstance(mode, int):
			raise ValueError("USB mode must be USBMode.CH340 (0) or USBMode.CDC (1)")
		mode = USBMode(mode)
		if not self.IsIdentified():
			raise RuntimeError("USB mode changes require an identified GBFlash connection")
		if self.FW["fw_ver"] < 16:
			dprint("USB mode switching requires firmware L16 or newer")
			return False

		usb_ports = self.GetUSBPorts()
		source = self.GetUSBPort(self.PORT, usb_ports)
		self.SetUSBPort(source)
		if self.USB_MODE == mode: return True

		dprint("Changing USB mode to", mode.name)
		firmware = self.FW.copy()
		try:
			if mode == USBMode.CH340:
				self._write(self.DEVICE_CMD["SET_USB_MODE_CH340"])
			elif mode == USBMode.CDC:
				self._write(self.DEVICE_CMD["SET_USB_MODE_CDC"])
		except (OSError, SerialException):
			# The device may disconnect before the OS reports write completion.
			pass
		finally:
			self.DEVICE.close()
			self.DEVICE = None

		deadline = time.monotonic() + 10
		while time.monotonic() < deadline:
			candidate = self.FindUSBPort(source, usb_ports, self.GetUSBPorts(), USB_IDS[mode])
			if candidate is not None and self.ReopenUSBPort(candidate, firmware):
				return True
			time.sleep(0.1)

		# Restore the selected device if the mode change did not complete.
		candidate = self.FindUSBPort(source, usb_ports, self.GetUSBPorts(), (source.get("vid"), source.get("pid")), restore=True)
		if candidate is not None:
			self.ReopenUSBPort(candidate, firmware)
		return False

	def IsIdentified(self):
		if self.DEVICE is None or not self.DEVICE.isOpen(): return False
		if not isinstance(self.FW, dict): return False
		if self.FW.get("cfw_id") != "L" or self.FW.get("pcb_ver") not in self.PCB_VERSIONS: return False
		if self.FW.get("fw_ver", 0) < self.DEVICE_MIN_FW: return False
		if self.FW.get("pcb_name") not in (None, "GBFlash"): return False
		return True

	def SetUSBPort(self, port):
		self.USB_PORT = port.copy()
		self.PORT = port["device"]
		self.USB_MODE = None
		for mode in USB_IDS:
			if (port.get("vid"), port.get("pid")) == USB_IDS[mode]:
				self.USB_MODE = mode
				break
		self.MAX_BUFFER_READ = 0x2000 if self.USB_MODE == USBMode.CDC else 0x1000

	def ReopenUSBPort(self, port, firmware):
		try:
			self.DEVICE = serial.Serial(port["device"], self.BAUDRATE, timeout=0.1)
			self.FW = None
			if self.LoadFirmwareVersion() and self.IsIdentified():
				match = True
				for key in ("cfw_id", "fw_ver", "pcb_ver", "fw_ts", "pcb_name", "device_serial"):
					if self.FW.get(key) != firmware.get(key):
						match = False
						break
				if match:
					self.SetUSBPort(port)
					self.DEVICE.timeout = self.DEVICE_TIMEOUT
					return True
		except (OSError, SerialException):
			pass
		if self.DEVICE is not None:
			self.DEVICE.close()
		self.DEVICE = None
		self.FW = firmware
		return False

	def GetFirmwareVersion(self, more=False):
		s = "{:s}{:d}".format(self.FW["cfw_id"], self.FW["fw_ver"])
		if self.FW["pcb_name"] is None:
			s = s + " <" + __("unverified") + ">"
		if more:
			return "{base} ({timestamp})".format(base=s, timestamp=self.FW["fw_dt"])
		return s

	def GetFullNameExtended(self, more=False):
		if more:
			s = __("{device_name} – Firmware {fw_version} ({timestamp}) on {port}", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), timestamp=self.FW["fw_dt"], port=self.GetPort())
			if self.USB_MODE == USBMode.CH340: s += " (CH340)"
			return s
		else:
			return __("{device_name} – Firmware {fw_version} ({port})", device_name=self.GetFullName(), fw_version=self.GetFirmwareVersion(), port=self.GetPort())

	def CanSetVoltageBySwitch(self):
		return False

	def CanSetVoltageByCode(self):
		return True

	def CanSetVoltageByAutoswitch(self):
		return False

	def CanPowerCycleCart(self):
		return self.FW["cart_power_ctrl"]

	def GetSupportedModes(self):
		return ["DMG", "AGB"]

	def IsSupported3dMemory(self):
		return True

	def IsClkConnected(self):
		return True

	def SupportsFirmwareUpdates(self):
		return True

	def FirmwareUpdateAvailable(self):
		if self.FW["pcb_ver"] == 5 or self.FW["fw_ts"] < 1730592000: # unofficial firmware
			self.FW_UPDATE_REQ = True
			return True
		if self.FW["fw_ts"] != self.DEVICE_LATEST_FW_TS[self.FW["pcb_ver"]]:
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
			if self._write(self.DEVICE_CMD["BOOTLOADER_RESET"], wait=True) != 1: return False
			try:
				self._write(1)
			except (OSError, SerialException):
				pass
			finally:
				self.DEVICE.close()
			return True
		except Exception as e:
			print(__("Disconnecting..."), e)
			return False

	def SupportsAudioAsWe(self):
		return not (self.FW["pcb_ver"] < 13 and self.CanPowerCycleCart())

	def GetMode(self):
		if self.FW["fw_ts"] == 1681900614: return self.MODE
		return super().GetMode()

	def SetAutoPowerOff(self, value):
		value &= 0xFFFFFFFF
		return super().SetAutoPowerOff(value)

	def GetFullName(self):
		if self.FW["pcb_ver"] < 13 and self.CanPowerCycleCart():
			s = "{device_name} {pcb_version} + PLUGIN 01".format(device_name=self.GetName(), pcb_version=self.GetPCBVersion())
		else:
			s = "{:s} {:s}".format(self.GetName(), self.GetPCBVersion())
		if self.IsUnregistered():
			s += " (" + __("unregistered") + ")"
		return s

	def GetRegisterInformation(self):
		text = __("Your GBFlash device reported a registration error, which means it may be an illegitimate clone.") + "<br><br>" + __("The device’s integrated piracy detection may limit the device in performance and functionality until proper registration. The FlashGBX software has no control over this.")
		return text


class FirmwareUpdater():
	PORT = None
	DEVICE = None

	def __init__(self, app_path=".", port=None):
		self.APP_PATH = app_path
		self.PORT = port
		self.USB_PORTS = GbxDevice.GetUSBPorts()
		self.USB_SOURCE = GbxDevice.GetUSBPort(port, self.USB_PORTS)
		self.BOOTLOADER_REQUESTED = False
		self.UPDATED = False

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
		try:
			temp = self.DEVICE.read(11)
			if temp is False: temp = b''
			values = struct.unpack(">IBHHH", temp)
		except (struct.error, TypeError):
			return {"clone":True, "error": "Bootloader error! " + ''.join(format(x, '02X') for x in temp)}
		try:
			data = dict(zip(keys, values))
			data["payload"] = self.DEVICE.read(data["payload_len"])
			data["outro"] = self.DEVICE.read(4)
			if data["outro"] is False: data["outro"] = b''
			data["outro"] = struct.unpack(">I", data["outro"])[0]
		except struct.error:
			return {"clone":True, "error": "Erroneous outro response! " + ''.join(format(x, '02X') for x in data["outro"])}
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

	def ClosePort(self):
		if self.DEVICE is not None:
			self.DEVICE.close()
		self.DEVICE = None

	def FindApplicationPort(self):
		deadline = time.monotonic() + 10
		while time.monotonic() < deadline:
			ports = GbxDevice.GetUSBPorts()
			candidates = []
			for usb_id in USB_IDS.values():
				port = GbxDevice.FindUSBPort(self.USB_SOURCE, self.USB_PORTS, ports, usb_id, restore=True)
				if port is None:
					port = GbxDevice.FindUSBPort(self.USB_SOURCE, self.USB_PORTS, ports, usb_id)
				if port is not None and port not in candidates: candidates.append(port)
			if len(candidates) == 1: return candidates[0]["device"]
			time.sleep(0.1)
		return None

	def TryConnect(self, port):
		packet = {
			"intro":0x48484A4A,
			"sender":0,
			"seq_no":1,
			"command":0x21,
			"payload_len":0,
			"payload":bytearray(),
			"outro":0x4A4A4848,
		}
		query = self.PackPacket(packet)
		self.DEVICE = None
		if self.USB_SOURCE.get("device") != port:
			self.USB_PORTS = GbxDevice.GetUSBPorts()
			self.USB_SOURCE = GbxDevice.GetUSBPort(port, self.USB_PORTS)
		source = self.USB_SOURCE
		try:
			if not self.BOOTLOADER_REQUESTED:
				current = None
				for usb_port in GbxDevice.GetUSBPorts():
					if usb_port["device"] == port:
						current = usb_port
						break
				if current is not None:
					self.DEVICE = serial.Serial(port, 2000000, timeout=0.5)
					self.DEVICE.reset_input_buffer()
					self.DEVICE.write(b'\xF1')
					self.DEVICE.flush()
					if self.DEVICE.read(1) == b'\x01':
						self.BOOTLOADER_REQUESTED = True
						try:
							self.DEVICE.write(b'\x01')
							self.DEVICE.flush()
						except (OSError, SerialException):
							pass
					self.ClosePort()
					if self.BOOTLOADER_REQUESTED: time.sleep(0.25)
			deadline = time.monotonic() + 10
			while time.monotonic() < deadline:
				candidate = GbxDevice.FindUSBPort(source, self.USB_PORTS, GbxDevice.GetUSBPorts(), USB_IDS[USBMode.CH340], restore=True)
				if candidate is None:
					# A CDC COM port may be replaced by a new CH340 COM port.
					candidate = GbxDevice.FindUSBPort(source, self.USB_PORTS, GbxDevice.GetUSBPorts(), USB_IDS[USBMode.CH340])
				if candidate is not None:
					try:
						self.DEVICE = serial.Serial(candidate["device"], 2000000, timeout=0.5)
						self.DEVICE.reset_input_buffer()
						self.DEVICE.write(query)
						self.DEVICE.flush()
						time.sleep(0.1)
						self.DEVICE.reset_input_buffer()
						self.DEVICE.write(query)
						self.DEVICE.flush()
						data = self.GetPacket()
						if (isinstance(data, dict) and "error" not in data
							and data.get("seq_no") == 1 and data.get("command") == 0x21
							and len(data.get("payload", b"")) >= 9 and data["payload"][1:3] == b'\x00\x03'):
							self.PORT = candidate["device"]
							return data
						if isinstance(data, dict) and data.get("clone"):
							self.ClosePort()
							return data
					except (OSError, SerialException):
						pass
					self.ClosePort()
				time.sleep(0.1)
		except (OSError, SerialException):
			self.ClosePort()
		return False

	def WriteFirmware(self, zipfn, fncSetStatus):
		self.UPDATED = False
		try:
			return self._WriteFirmware_Worker(zipfn, fncSetStatus)
		finally:
			self.ClosePort()

	def _WriteFirmware_Worker(self, zipfn, fncSetStatus):
		try:
			with zipfile.ZipFile(zipfn) as archive:
				with archive.open("fw.bin") as f: fw_data = bytearray(f.read())
		except (zipfile.BadZipFile, KeyError):
			fncSetStatus(__("The firmware update file is corrupted."))
			return 2

		fncSetStatus(__("Connecting..."))
		data = False
		if self.PORT is None:
			ports = []
			usb_ports = GbxDevice.GetUSBPorts()
			for i in range(0, len(usb_ports)):
				if (usb_ports[i]["vid"], usb_ports[i]["pid"]) in USB_IDS.values():
					ports.append(usb_ports[i]["device"])
			if len(ports) > 1:
				fncSetStatus(__("More than one device found. Please select a port."))
				return 2
			if len(ports) == 0:
				fncSetStatus(__("No device found."))
				return 2

			for port in ports:
				data = self.TryConnect(port)
				if data is not False:
					break
		else:
			data = self.TryConnect(self.PORT)

		if isinstance(data, dict) and "error" in data:
			fncSetStatus(text=data["error"], cloneError="clone" in data and data["clone"] is True)
			return 2
		if not isinstance(data, dict) or self.DEVICE is None:
			fncSetStatus(__("No device found."))
			return 2

		if len(data.get("payload", b"")) < 9:
			fncSetStatus(text=__("Update failed!"), enableUI=True)
			return 2
		data["program_size"] = struct.unpack(">H", data["payload"][3:5])[0]
		data["page_size"] = struct.unpack(">H", data["payload"][7:9])[0]
		page_size = data["page_size"]
		if page_size == 0:
			fncSetStatus(text=__("Update failed!"), enableUI=True)
			return 2
		num_packets = len(fw_data) / page_size
		num_packets = int(-(-num_packets // 1)) # round up

		fncSetStatus(__("Updating firmware..."), setProgress=0)
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
			if data is None:
				fncSetStatus(__("No response from device."))
				return 2
			if len(data.get("payload", b"")) < 3:
				fncSetStatus(text=__("Update failed!"), enableUI=True)
				return 2
			if data.get("seq_no") != seq_no:
				fncSetStatus(__("Incorrect sequence number."))
				time.sleep(1)
				continue
			if data.get("command") != 0x24:
				fncSetStatus(__("Incorrect command."))
				time.sleep(1)
				continue
			if struct.unpack(">H", data["payload"][0:2])[0] != packet_index:
				fncSetStatus(__("Incorrect data packet number."))
				time.sleep(1)
				continue
			if data["payload"][2] != 0x01:
				fncSetStatus(__("Write failed."))
				time.sleep(1)
				continue

			percent = packet_index / num_packets * 100
			fncSetStatus(text=__("Updating firmware... Do not unplug the device!"), setProgress=percent)
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
			if data is None:
				fncSetStatus(__("No response from device."))
				return 2
			if (data.get("seq_no") != seq_no or data.get("command") != 0x23
				or len(data.get("payload", b"")) < 1 or data["payload"][0] != 1):
				fncSetStatus(text=__("Update failed!"), enableUI=True)
				return 2

			self.UPDATED = True
			self.ClosePort()
			time.sleep(0.8)
			fncSetStatus(__("Done!"))
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
			QtWidgets.QDialog.__init__(self, app)
			if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
			self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
			self.setWindowTitle(AppInfo.NAME + " – " + __("Firmware Updater for {device_name}", device_name="GBFlash"))
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
			self.lblDeviceNameResult = QtWidgets.QLabel("GBFlash")
			rowDeviceInfo1.addWidget(self.lblDeviceName)
			rowDeviceInfo1.addWidget(self.lblDeviceNameResult)
			rowDeviceInfo1.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo1)
			rowDeviceInfo3 = QtWidgets.QHBoxLayout()
			self.lblDeviceFWVer = QtWidgets.QLabel(__("Firmware version:"))
			self.lblDeviceFWVer.setMinimumWidth(120)
			self.lblDeviceFWVerResult = QtWidgets.QLabel("")
			rowDeviceInfo3.addWidget(self.lblDeviceFWVer)
			rowDeviceInfo3.addWidget(self.lblDeviceFWVerResult)
			rowDeviceInfo3.addStretch(1)
			self.grpDeviceInfoLayout.addLayout(rowDeviceInfo3)
			self.grpDeviceInfo.setLayout(self.grpDeviceInfoLayout)
			self.layout_device.addWidget(self.grpDeviceInfo)
			# ↑↑↑ Current Device Information

			# ↓↓↓ Available Firmware Updates
			self.grpAvailableFwUpdates = QtWidgets.QGroupBox(__("Available Firmware"))
			self.grpAvailableFwUpdates.setMinimumWidth(400)
			self.grpAvailableFwUpdatesLayout = QtWidgets.QVBoxLayout()
			self.grpAvailableFwUpdatesLayout.setContentsMargins(-1, 3, -1, -1)

			rowDeviceInfo4 = QtWidgets.QHBoxLayout()
			self.lblDeviceFWVer2 = QtWidgets.QLabel(__("Firmware version:"))
			self.lblDeviceFWVer2.setMinimumWidth(120)
			self.lblDeviceFWVer2Result = QtWidgets.QLabel("(" + __("Please choose the PCB version") + ")")
			rowDeviceInfo4.addWidget(self.lblDeviceFWVer2)
			rowDeviceInfo4.addWidget(self.lblDeviceFWVer2Result)
			rowDeviceInfo4.addStretch(1)
			self.grpAvailableFwUpdatesLayout.addLayout(rowDeviceInfo4)

			self.rowUpdate = QtWidgets.QHBoxLayout()
			self.btnUpdate = QtWidgets.QPushButton(__("Install Firmware Update"))
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
			self.SetPCBVersion()

		def SetPCBVersion(self):
			file_name = self.FWUPD.APP_PATH + os.sep + os.path.join("res", "fw_GBFlash.zip")

			with zipfile.ZipFile(file_name) as zip:
				with zip.open("fw.ini") as f: ini_file = f.read()
				ini_file = ini_file.decode(encoding="utf-8")
				self.INI = IniSettings(ini=ini_file, main_section="Firmware")
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
			if self.DEVICE is None and self.FWUPD.UPDATED:
				port = self.FWUPD.FindApplicationPort()
				if port is not None:
					self.APP.FindDevices(port=port)
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
			file_name = self.FWUPD.APP_PATH + os.sep + os.path.join("res", "fw_GBFlash.zip")

			if self.APP.CONN is None or self.APP.CONN.BootloaderReset() is False:
				self.APP.DisconnectDevice()
				text = __("Please follow these steps to proceed with the firmware update:")
				text += "\n\n" + __(
					"- Unplug your GBFlash device.\n"
					"- On your GBFlash circuit board, push and hold the small button (U22) while plugging the USB cable back in.\n"
					"- If done right, the blue LED labeled “ACT” should now keep blinking twice continuously."
				)
				text += "\n" + __("- Click OK to continue.")
				text += "\n\n" + __("Note: Illegitimate clones of the GBFlash may have been modified to disallow firmware updates.")
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
				msgbox.setDefaultButton(QtWidgets.QMessageBox.Ok)
				answer = msgbox.exec()
				if answer == QtWidgets.QMessageBox.Cancel: return
			else:
				self.FWUPD.BOOTLOADER_REQUESTED = True
				self.APP.DisconnectDevice()
				time.sleep(1)

			self.btnUpdate.setEnabled(False)
			self.btnClose.setEnabled(False)

			while True:
				ret = self.FWUPD.WriteFirmware(file_name, self.SetStatus)
				if ret == 1:
					text = __("The firmware update is complete!")
					if self.PCB_VER != "v1.3":
						text += "\n\n" + __("Please re-connect the USB cable now.")
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Information, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					self.DEVICE = None
					self.reject()
					return True
				elif ret == 2:
					text = __("The firmware update has failed. Please try again.")
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return False
				elif ret == 3:
					text = __("The firmware update file is corrupted. Please re-install the application.")
					self.btnUpdate.setEnabled(True)
					self.btnClose.setEnabled(True)
					msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
					answer = msgbox.exec()
					return False

		def SetStatus(self, text, enableUI=False, setProgress=None, cloneError=False):
			self.lblStatus.setText(__("Status: {text}", text=text))

			if cloneError:
				text = __("Your GBFlash device failed to enter the firmware update mode. This means your GBFlash may be an <b>illegitimate clone</b> that blocks certain features intentionally. If this error persists, return the device for a refund.") + "<br><br>" + text
				msgbox = QtWidgets.QMessageBox(parent=self, icon=QtWidgets.QMessageBox.Critical, windowTitle=AppInfo.NAME, text=text, standardButtons=QtWidgets.QMessageBox.Ok)
				msgbox.exec()
				return False

			if setProgress is not None:
				self.prgStatus.setValue(setProgress * 10)
			if enableUI:
				self.btnUpdate.setEnabled(True)
				self.btnClose.setEnabled(True)
			self.APP.QT_APP.processEvents()
except ImportError:
	pass
