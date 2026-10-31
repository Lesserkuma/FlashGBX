# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

# pylint: disable=wildcard-import, unused-wildcard-import
import ctypes, datetime, mmap, os, platform, plistlib, re, socket, stat, struct, subprocess, sys, time, zipfile
from contextlib import closing
from .app import AppInfo
from .LK_Device import *
from .i18n import __, c__
from .IniSettings import IniSettings

class GbxDevice(LK_Device):
	DEVICE_NAME = "Joey Jr"
	USB_IDS = ((0x0483, 0x5740),)
	DEVICE_MIN_FW = 1
	DEVICE_MAX_FW = 12
	DEVICE_LATEST_FW_TS = 1793184971
	PCB_VERSIONS = { -1:"", 0x01:"V2", 0x81:"V2", 0x02:"V2C", 0x82:"V2C", 0x03:"V2CC", 0x83:"V2CC/V2++" }
	DEVICE_LABEL_LONG = "Joey Jr"
	DEVICE_LABEL_SHORT = "Joey Jr"
	FWUPDATE_ACTION = "fwupdate-joeyjr"
	CLI_UPDATER_METHOD = "UpdateFirmwareJoeyJr"
	DEVICE_SUPPORT_MESSAGE = "For help with your Joey Jr, please visit the BennVenn Discord:\nhttps://discord.gg/F5ckxM2"
	MAX_BUFFER_READ = 0x2000
	MAX_BUFFER_WRITE = 0x800

	def __init__(self):
		pass

	def Initialize(self, flashcarts, port=None, max_baud=2000000):
		if self.DEVICE is not None: self.DEVICE.close()
		self.DEVICE = None
		self.FW = None
		conn_msg = []
		ports = []
		if port is not None:
			ports = [ port ]
		else:
			ports = self.GetCandidatePorts()
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
			# dprint("Baud rate:", self.BAUDRATE)

			if self.DEVICE is None or not self.IsConnected():
				dev.close()
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
				temp = self._read(1)
				self.FW["bootloader_reset"] = bool(temp & 1)
				self.FW["device_serial"] = self.ReadDeviceSerial() if temp & 2 else None
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
		if len(data) != 12: return super().FormatDeviceSerial(data)
		return "{:08X}{:08X}{:08X}".format(*struct.unpack("<3I", data))

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

	def GetSupportedModes(self):
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
	MSC_FIRMWARE_OFFSET = 0x2074A00
	MSC_DEBUG_OFFSET = 0x2084A00
	MSC_MODE_OFFSET = 0x2094A00
	MSC_PREFIX_SIZE = 0xFE00

	def __init__(self, app_path=".", port=None):
		self.APP_PATH = app_path
		self.PORT = port

	def IsValidFirmware(self, buffer):
		return len(buffer) == 0x10000 and struct.unpack(">I", buffer[0xFFFC:])[0] == sum(buffer[:0xFFFC])

	def WriteFirmwareMSC(self, path, buffer, fncSetStatus):
		if not self.IsValidFirmware(buffer): return 3
		if platform.system() == "Darwin":
			return self.WriteFirmwareMSCMacOS(path, buffer, fncSetStatus)

		directory = os.path.dirname(path)
		firmware_path = os.path.join(directory, "FIRMWARE.JR")
		fncSetStatus(text=__("Connecting... This may take a moment."))
		with open(path, "rb") as f: mode = f.read(6)
		if mode != b"UPDATE":
			try:
				with open(path, "r+b", buffering=0) as f:
					f.write(b"UPDATE" + bytes(250))
					os.fsync(f.fileno())
			except OSError:
				pass
			time.sleep(1)
		for attempt in range(30):
			mode = b""
			for filename in ("MODE.TXT", "MODE!.TXT"):
				try:
					with open(os.path.join(directory, filename), "rb") as f: mode = f.read(6)
				except OSError:
					continue
				if mode == b"UPDATE": break
			if mode == b"UPDATE" and os.path.exists(firmware_path): break
			time.sleep(1)
		else:
			fncSetStatus(text=__("Couldn’t enter {update} mode. Please try again.", update="UPDATE"))
			return 2

		try:
			with self.OpenMSCFirmware(firmware_path) as f:
				if self.WriteFirmwareMSCData(f, buffer, fncSetStatus) != 1: return 2
		except OSError:
			fncSetStatus(text=__("Couldn’t write new firmware. Please try again."))
			return 2

		if b"Joey Jr. Firmware" not in buffer:
			for attempt in range(5):
				if not os.path.exists(firmware_path): break
				time.sleep(1)
			else:
				fncSetStatus(text=__("Couldn’t verify. Please try again."))
				return 2

		fncSetStatus(__("Done!"), setProgress=100)
		time.sleep(2)
		return 1

	def OpenMSCFirmware(self, path):
		if platform.system() == "Windows":
			import msvcrt
			kernel = ctypes.WinDLL("kernel32", use_last_error=True)
			kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
			kernel.CreateFileW.restype = ctypes.c_void_p
			handle = kernel.CreateFileW(path, 0xC0000000, 3, None, 3, 0xA0000000, None) # OPEN_EXISTING, NO_BUFFERING | WRITE_THROUGH
			if handle == ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
			fd = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
		else:
			fd = os.open(path, os.O_RDWR | os.O_DIRECT | os.O_SYNC)
		return os.fdopen(fd, "r+b", buffering=0)

	def WriteFirmwareMSCData(self, f, buffer, fncSetStatus, offset=0, target=None):
		total = 0x10000 + self.MSC_PREFIX_SIZE
		with mmap.mmap(-1, 512) as data:
			try:
				for verify in (False, True):
					text = __("Verifying...") if verify else __("Updating firmware... Do not unplug the device!")
					error = __("Couldn’t verify. Please try again.") if verify else __("Couldn’t write new firmware. Please try again.")
					progress = self.MSC_PREFIX_SIZE if verify else 0
					fncSetStatus(text=text, setProgress=float(progress) / total * 100)
					for i in range(0, self.MSC_PREFIX_SIZE, 512):
						f.seek(offset + i)
						if not verify:
							data[:] = buffer[i:i+512]
							if f.write(data) != 512:
								fncSetStatus(text=error)
								return 2
							f.seek(offset + i)
						if f.readinto(data) != 512 or data[:] != buffer[i:i+512]:
							fncSetStatus(text=error)
							return 2
						fncSetStatus(text=text, setProgress=float(progress + i + 512) / total * 100)
				if target is not None:
					f.seek(self.MSC_MODE_OFFSET)
					if not f.read(512).startswith(b"UPDATE") or not self.CheckMacOSDevice(f.fileno(), target):
						fncSetStatus(text=error)
						return 2
				f.seek(offset + self.MSC_PREFIX_SIZE)
			except OSError:
				fncSetStatus(text=error)
				return 2
			data[:] = buffer[self.MSC_PREFIX_SIZE:]
			try:
				if f.write(data) != 512:
					fncSetStatus(text=__("Couldn’t write new firmware. Please try again."))
					return 2
			except OSError:
				pass
		return 1

	def ReadMacOSPlist(self, command):
		return plistlib.loads(subprocess.check_output(command, timeout=30))

	def WalkMacOSRegistry(self, nodes=None, usb=None):
		if nodes is None: nodes = self.ReadMacOSPlist(["/usr/sbin/ioreg", "-a", "-l", "-p", "IOService"])
		if isinstance(nodes, dict): nodes = [nodes]
		for node in nodes:
			device = usb
			if node.get("IOObjectClass") in ("IOUSBHostDevice", "IOUSBDevice"):
				device = tuple(node.get(key) for key in ("idVendor", "idProduct", "locationID", "IORegistryEntryID"))
			yield node, device
			yield from self.WalkMacOSRegistry(node.get("IORegistryEntryChildren", []), device)

	def GetMacOSMedia(self, disk):
		matches = [(node, usb) for node, usb in self.WalkMacOSRegistry() if node.get("BSD Name") == disk]
		if len(matches) != 1: return None
		node, usb = matches[0]
		if not usb or usb[:2] != (0xC251, 0x2020): return None
		if node.get("Whole") is not True or node.get("Size") != 0x4000000 or node.get("Preferred Block Size") != 512: return None
		path = "/dev/r" + disk
		info = os.lstat(path)
		if not stat.S_ISCHR(info.st_mode): return None
		return { "disk":disk, "raw":path, "rdev":info.st_rdev, "usb":usb, "entry":node["IORegistryEntryID"] }

	def CheckMacOSDevice(self, fd, target):
		if self.GetMacOSMedia(target["disk"]) != target or os.fstat(fd).st_rdev != target["rdev"]: return False
		mounts = subprocess.check_output(["/sbin/mount"], text=True, timeout=10)
		return not any(line.startswith("/dev/" + target["disk"] + " on ") for line in mounts.splitlines())

	def WaitForMacOSDevice(self, original, msc=True):
		key, identity = ("BSD Name", (0xC251, 0x2020)) if msc else ("IOCalloutDevice", (0x0483, 0x5740))
		deadline = time.monotonic() + 45
		while time.monotonic() < deadline:
			matches = [(node, usb) for node, usb in self.WalkMacOSRegistry() if usb and usb[:2] == identity and usb[2] == original[2] and usb[3] != original[3] and node.get(key) and (not msc or node.get("Whole") is True)]
			if len(matches) > 1: return None
			if matches:
				node, usb = matches[0]
				if not msc: return node[key]
				if self.ReadMacOSPlist(["/usr/sbin/diskutil", "info", "-plist", "/dev/" + node[key]]).get("MountPoint"):
					target = self.GetMacOSMedia(node[key])
					if target is not None and target["usb"] == usb: return target
			time.sleep(1)
		return None

	def OpenMacOSDevice(self, target, external):
		if self.GetMacOSMedia(target["disk"]) != target: return None
		subprocess.run(["/usr/sbin/diskutil", "unmountDisk", "/dev/" + target["disk"]], check=True, stdout=subprocess.DEVNULL, timeout=30)
		parent, child = socket.socketpair()
		process, descriptors = None, []
		try:
			command = ["/usr/libexec/authopen", "-stdoutpipe", "-extauth", "-o", str(os.O_RDWR | os.O_EXLOCK | os.O_NONBLOCK), target["raw"]]
			process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=child, stderr=subprocess.PIPE)
			child.close()
			unused, error = process.communicate(external, timeout=15)
			parent.settimeout(10)
			unused, descriptors, unused, unused = socket.recv_fds(parent, 4096, 1)
			if process.returncode != 0 or len(descriptors) != 1:
				dprint(error.decode("UTF-8", "replace"))
				return None
			os.set_inheritable(descriptors[0], False)
			device = os.fdopen(descriptors[0], "r+b", buffering=0)
			descriptors.clear()
			return device
		finally:
			parent.close()
			child.close()
			for fd in descriptors: os.close(fd)
			if process is not None and process.poll() is None:
				process.kill()
				process.communicate()

	def WriteFirmwareMSCMacOS(self, path, buffer, fncSetStatus):
		if sys.version_info < (3, 9):
			fncSetStatus(text=__("Firmware updates in Drag’n’Drop mode on macOS require Python 3.9 or newer."))
			return 2
		info = self.ReadMacOSPlist(["/usr/sbin/diskutil", "info", "-plist", os.path.dirname(path)])
		target = self.GetMacOSMedia(info["DeviceIdentifier"])
		if target is None:
			fncSetStatus(text=__("Couldn’t communicate with the Joey Jr device."))
			return 2
		security = ctypes.CDLL("/System/Library/Frameworks/Security.framework/Security")
		for name, arguments in (
			("AuthorizationCreate", [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]),
			("AuthorizationCopyRights", [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]),
			("AuthorizationMakeExternalForm", [ctypes.c_void_p, ctypes.c_void_p]),
			("AuthorizationFree", [ctypes.c_void_p, ctypes.c_uint32]),
		):
			function = getattr(security, name)
			function.argtypes, function.restype = arguments, ctypes.c_int32
		authorization = ctypes.c_void_p()
		if security.AuthorizationCreate(None, None, 0, ctypes.byref(authorization)) != 0: authorization = None
		try:
			for attempt in range(2):
				fncSetStatus(text=__("Requesting macOS authorization...") if attempt == 0 else __("Connecting..."))
				right_name = ctypes.create_string_buffer(("sys.openfile.readwrite." + target["raw"]).encode("UTF-8"))
				# Native AuthorizationItem and AuthorizationRights layouts, including pointer alignment.
				item = ctypes.create_string_buffer(struct.pack("@PNPI0P", ctypes.addressof(right_name), 0, 0, 0))
				rights = ctypes.create_string_buffer(struct.pack("@IP", 1, ctypes.addressof(item)))
				external = ctypes.create_string_buffer(32)
				if (not authorization or
					security.AuthorizationCopyRights(authorization, ctypes.byref(rights), None, 0x13 if attempt == 0 else 0x12, None) != 0 or
					security.AuthorizationCopyRights(authorization, ctypes.byref(rights), None, 0x02, None) != 0 or
					security.AuthorizationMakeExternalForm(authorization, external) != 0):
					fncSetStatus(text=__("Device not accessible."))
					return 2
				fncSetStatus(text=__("Unmounting the device..."))
				f = self.OpenMacOSDevice(target, external.raw)
				if f is None:
					fncSetStatus(text=__("Couldn’t write new firmware. Please try again."))
					return 2
				with f:
					fd = f.fileno()
					if not self.CheckMacOSDevice(fd, target) or not os.pread(fd, 512, self.MSC_DEBUG_OFFSET).startswith(b"Joey Jr. Firmware V2_02_29 "):
						fncSetStatus(text=__("Couldn’t communicate with the Joey Jr device."))
						return 2
					if os.pread(fd, 512, self.MSC_MODE_OFFSET).startswith(b"UPDATE"):
						if self.WriteFirmwareMSCData(f, buffer, fncSetStatus, offset=self.MSC_FIRMWARE_OFFSET, target=target) != 1: return 2
						break
					if attempt > 0:
						fncSetStatus(text=__("Couldn’t enter {update} mode. Please try again.", update="UPDATE"))
						return 2
					fncSetStatus(text=__("Rebooting device..."))
					try:
						os.pwrite(fd, b"UPDATE" + bytes(506), self.MSC_MODE_OFFSET)
					except OSError:
						pass
				target = self.WaitForMacOSDevice(target["usb"])
				if target is None:
					fncSetStatus(text=__("Couldn’t enter {update} mode. Please try again.", update="UPDATE"))
					return 2
			fncSetStatus(text=__("Verifying..."))
			msc = b"Joey Jr. Firmware" in buffer
			result = self.WaitForMacOSDevice(target["usb"], msc=msc)
			if result is None:
				fncSetStatus(text=__("Couldn’t verify. Please try again."))
				return 2
			if not msc:
				device = GbxDevice()
				if not device.TryConnect(result, 2000000) or (b"FW LK" in buffer and device.FW["cfw_id"] != "L") or (b"FW GUI" in buffer and device.FW["cfw_id"] != "G"):
					fncSetStatus(text=__("Couldn’t verify. Please try again."))
					return 2
				self.PORT = result
			fncSetStatus(__("Done!"), setProgress=100)
			return 1
		finally:
			if authorization: security.AuthorizationFree(authorization, 0x08)

	def GetMSCLocations(self):
		locations = set()
		if platform.system() == "Darwin":
			for node, usb in self.WalkMacOSRegistry():
				if not usb or usb[:2] != (0xC251, 0x2020) or usb[2] is None: continue
				location = usb[2]
				bus, ports = location >> 24, []
				while location & 0xF00000:
					ports.append(str((location >> 20) & 0xF))
					location <<= 4
				if ports: locations.add(str(bus) + "-" + ".".join(ports))
		elif platform.system() == "Linux":
			for device in os.listdir("/sys/bus/usb/devices"):
				if ":" in device: continue
				try:
					path = os.path.join("/sys/bus/usb/devices", device)
					with open(os.path.join(path, "idVendor")) as f: vid = f.read().strip().lower()
					with open(os.path.join(path, "idProduct")) as f: pid = f.read().strip().lower()
				except OSError:
					continue
				if (vid, pid) == ("c251", "2020"): locations.add(device)
		elif platform.system() == "Windows":
			from serial.tools import list_ports_windows as win
			handle = win.SetupDiGetClassDevs(None, "USB", None, win.DIGCF_PRESENT | 4) # DIGCF_ALLCLASSES
			if handle == ctypes.c_void_p(-1).value: raise ctypes.WinError()
			try:
				info = win.SP_DEVINFO_DATA()
				info.cbSize = ctypes.sizeof(info)
				index = 0
				while win.SetupDiEnumDeviceInfo(handle, index, ctypes.byref(info)):
					index += 1
					identity = ctypes.create_unicode_buffer(512)
					if not win.SetupDiGetDeviceInstanceId(handle, ctypes.byref(info), identity, len(identity), None): continue
					if not identity.value.upper().startswith("USB\\VID_C251&PID_2020\\"): continue
					path = ctypes.create_unicode_buffer(1024)
					if not win.SetupDiGetDeviceRegistryProperty(handle, ctypes.byref(info), win.SPDRP_LOCATION_PATHS, None, ctypes.byref(path), ctypes.sizeof(path), None): continue
					bus = re.search(r"USBROOT\((\d+)\)", path.value)
					ports = re.findall(r"#USB\((\w+)\)", path.value)
					if bus and ports: locations.add(str(int(bus.group(1)) + 1) + "-" + ".".join(ports))
			finally:
				win.SetupDiDestroyDeviceInfoList(handle)
		else:
			raise OSError("USB device detection is not supported on this platform")
		return locations

	def WriteFirmware(self, buffer, fncSetStatus):
		if not self.IsValidFirmware(buffer): return 3

		# Check for serial mode
		comports = serial.tools.list_ports.comports()
		port = self.PORT
		if port is None:
			port = next((item.device for item in comports if (item.vid, item.pid) in GbxDevice.USB_IDS), None)
			if port is None: return 4
		if platform.system() == "Windows":
			port = port.upper()
			if port.startswith("\\\\.\\"): port = port[4:]
		else:
			port = os.path.realpath(port)
		original = next((item for item in comports if item.device == port), None)
		location = original.location.split(":", 1)[0] if original is not None and original.location else None
		msc = b"Joey Jr. Firmware" in buffer

		try:
			if msc:
				error = __("Couldn’t identify the USB location of the Joey Jr device.")
				if not location or location in self.GetMSCLocations(): raise OSError(error)
			error = __("Device not accessible.")
			fncSetStatus(text=__("Connecting..."))
			dev = serial.Serial(port, 2000000, timeout=1, write_timeout=2)
			try:
				dev.reset_input_buffer()
				for attempt in range(2):
					error = __("Joey Jr device not found.")
					fncSetStatus(__("Identifying device..."))
					if dev.write(b'\x55\xAA') != 2: raise OSError(error)
					device_id = dev.read(64)
					if len(device_id) < 19 or not device_id.startswith(b'\x00Joey Jr'): raise OSError(error)
					if b"FW L" not in device_id or device_id[-1] == 0: break
					error = __("Couldn’t enter {update} mode. Please try again.", update="UPDATE")
					if attempt == 1 or dev.write(b'KL') != 2 or dev.read(1) != b'\xFF': raise OSError(error)

				error = __("Couldn’t enter {update} mode. Please try again.", update="UPDATE")
				if dev.write(b'\xFE\x01') != 2 or dev.read(1) != b'\xFF': raise OSError(error)
				for counter in range(0, len(buffer), 64):
					fncSetStatus(text=__("Updating firmware... Do not unplug the device!"), setProgress=float(counter) / len(buffer) * 100)
					error = __("Error! Bad response at {address}!", address="0x{address:X}".format(address=counter))
					try:
						written = dev.write(buffer[counter:counter+64])
					except OSError as e:
						if counter + 64 < len(buffer): raise
						dprint("USB error during final firmware block; waiting for restart:", e)
					else:
						if written != 64: raise OSError(error)
					# The final block starts the flash copy and reset before an acknowledgement can be sent.
					if counter + 64 < len(buffer) and dev.read(1) != b'\xFF': raise OSError(error)

				error = __("Couldn’t verify. Please try again.")
				deadline = time.monotonic() + 15
				while time.monotonic() < deadline:
					fncSetStatus(__("Rebooting device..."))
					try:
						dev.read(max(1, dev.in_waiting))
					except OSError:
						break
					time.sleep(0.5)
				else:
					raise OSError(error)

			finally:
				try:
					dev.close()
				except OSError as e:
					dprint("USB error closing the firmware update connection:", e)
			marker = b"FW L" if b"FW LK" in buffer else b"FW GUI" if b"FW GUI" in buffer else b"Joey Jr"
			deadline = time.monotonic() + 15
			while time.monotonic() < deadline:
				fncSetStatus(__("Verifying..."))
				if msc:
					verified = location in self.GetMSCLocations()
				else:
					verified = False
					for candidate in serial.tools.list_ports.comports():
						if (candidate.vid, candidate.pid) not in GbxDevice.USB_IDS: continue
						if location:
							if not candidate.location or candidate.location.split(":", 1)[0] != location: continue
						elif candidate.device != port:
							continue
						try:
							with closing(serial.Serial(candidate.device, 2000000, timeout=0.2, write_timeout=2)) as dev:
								dev.reset_input_buffer()
								if dev.write(b'\x55\xAA') != 2: continue
								device_id = dev.read(64)
								verified = len(device_id) >= 19 and device_id.startswith(b'\x00Joey Jr') and marker in device_id
						except OSError:
							verified = False
						if verified:
							self.PORT = candidate.device
							break
				if verified: break
				time.sleep(0.01)
			else:
				raise OSError(error)
		except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException) as e:
			dprint("Firmware update failed:", e)
			if "Errno 13" in str(e) and platform.system() == "Linux":
				error = __("No permission to use device! See the {readme} file.", readme="README.md")
			fncSetStatus(text=error)
			return 2

		fncSetStatus(__("Done!"), setProgress=100)
		return 1


try:
	from .pyside import QtCore, QtWidgets, QtGui, QDesktopWidget

	class FirmwareUpdaterWindow(QtWidgets.QDialog):
		def __init__(self, app, app_path, file=None, icon=None, device=None):
			QtWidgets.QDialog.__init__(self, app)
			if icon is not None: self.setWindowIcon(QtGui.QIcon(icon))
			self.setStyleSheet("QMessageBox { messagebox-text-interaction-flags: 5; }")
			self.setWindowTitle("FlashGBX – " + __("Firmware Updater for {device_name}", device_name="Joey Jr"))
			self.setWindowFlags((self.windowFlags() | QtCore.Qt.MSWindowsFixedSizeDialogHint) & ~QtCore.Qt.WindowContextHelpButtonHint)

			self.APP = app
			self.DEVICE = device
			if device is None: self.APP.QT_APP.processEvents()
			self.FWUPD = FirmwareUpdater(app_path, device.GetPort() if device is not None else None)
			name = device.GetName() + " " + device.GetPCBVersion() if device is not None else "Joey Jr "
			version = device.GetFirmwareVersion(more=True) if device is not None else ""

			self.layout = QtWidgets.QVBoxLayout(self)
			self.layout.setContentsMargins(-1, 8, -1, 8)
			self.layout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)

			# ↓↓↓ Current Device Information
			device_info = QtWidgets.QGroupBox(__("Current Firmware"))
			device_info.setMinimumWidth(420)
			device_layout = QtWidgets.QVBoxLayout(device_info)
			device_layout.setContentsMargins(-1, 3, -1, -1)
			for title, value in ((__("Device:"), name), (__("Firmware version:"), version)):
				row = QtWidgets.QHBoxLayout()
				label = QtWidgets.QLabel(title)
				label.setMinimumWidth(120)
				row.addWidget(label)
				row.addWidget(QtWidgets.QLabel(value))
				row.addStretch(1)
				device_layout.addLayout(row)
			self.layout.addWidget(device_info)
			# ↑↑↑ Current Device Information

			# ↓↓↓ Available Firmware Updates
			file_name = os.path.join(self.FWUPD.APP_PATH, "res", "fw_JoeyJr.zip")

			try:
				with zipfile.ZipFile(file_name) as archive:
					ini = IniSettings(ini=archive.read("fw.ini").decode("UTF-8"), main_section="Firmware")
				self.FW_LK_VER = __("LK firmware version {version} by {author} (updated on {date})", version=ini.GetValue("fw_ver"), author="Lesserkuma", date=datetime.datetime.fromtimestamp(int(ini.GetValue("fw_buildts"))).strftime("%x"))
				self.FW_MSC_VER = __("BennVenn Drag’n’Drop firmware version {version} (updated on {date})", version=ini.GetValue("fw_msc_ver"), date=datetime.datetime.fromtimestamp(int(ini.GetValue("fw_msc_buildts"))).strftime("%x"))
				self.FW_JOEYGUI_VER = __("BennVenn JoeyGUI firmware version {version} (updated on {date})", version=ini.GetValue("fw_joeygui_ver"), date=datetime.datetime.fromtimestamp(int(ini.GetValue("fw_joeygui_buildts"))).strftime("%x"))
			except (FileNotFoundError, zipfile.BadZipFile, KeyError, ValueError):
				QtWidgets.QMessageBox.critical(self, __("Error"), __("The firmware update file is corrupted."))
				self.reject()
				return

			self.grpAvailableFwUpdates = QtWidgets.QGroupBox(__("Firmware Update Options"))
			self.grpAvailableFwUpdates.setMinimumWidth(400)
			firmware_layout = QtWidgets.QVBoxLayout(self.grpAvailableFwUpdates)
			firmware_layout.setContentsMargins(-1, 3, -1, -1)

			self.optFW_LK = QtWidgets.QRadioButton(self.FW_LK_VER)
			self.optFW_MSC = QtWidgets.QRadioButton(self.FW_MSC_VER)
			self.optFW_JoeyGUI = QtWidgets.QRadioButton(self.FW_JOEYGUI_VER)
			for option, text in (
				(self.optFW_LK, __("For use with the FlashGBX software\nNo support by BennVenn").replace("\n", "</li><li>")),
				(self.optFW_MSC, __("For use with the Windows file explorer")),
				(self.optFW_JoeyGUI, __("For use with the JoeyGUI software")),
			):
				label = QtWidgets.QLabel("<ul><li>" + text + "</li></ul>")
				label.setWordWrap(True)
				label.mousePressEvent = lambda event, button=option: button.setChecked(True)
				firmware_layout.addWidget(option)
				firmware_layout.addWidget(label)
			self.optFW_LK.setChecked(True)
			self.optExternal = QtWidgets.QRadioButton(__("External FIRMWARE.JR file"))

			self.btnUpdate = QtWidgets.QPushButton(__("Install Firmware Update"))
			self.btnUpdate.setMinimumWidth(200)
			self.btnUpdate.setContentsMargins(20, 20, 20, 20)
			self.connect(self.btnUpdate, QtCore.SIGNAL("clicked()"), self.UpdateFirmware)
			disclaimer = QtWidgets.QLabel(__("Please note that FlashGBX is not officially supported by BennVenn."))
			disclaimer.setWordWrap(True)
			disclaimer.setAlignment(QtGui.Qt.AlignmentFlag.AlignCenter)

			firmware_layout.addWidget(self.optExternal)
			firmware_layout.addSpacing(3)
			firmware_layout.addWidget(self.btnUpdate, alignment=QtCore.Qt.AlignHCenter)
			firmware_layout.addWidget(disclaimer)
			self.layout.addWidget(self.grpAvailableFwUpdates)
			# ↑↑↑ Available Firmware Updates

			self.grpStatus = QtWidgets.QGroupBox("")
			status_layout = QtWidgets.QVBoxLayout(self.grpStatus)
			self.prgStatus = QtWidgets.QProgressBar()
			self.prgStatus.setRange(0, 1000)
			self.prgStatus.setValue(0)
			self.lblStatus = QtWidgets.QLabel(__("Status: Ready."))

			status_layout.addWidget(self.prgStatus)
			status_layout.addWidget(self.lblStatus)
			self.layout.addWidget(self.grpStatus)

			self.btnClose = QtWidgets.QPushButton(c__("Button (& = Keyboard Shortcut)", "&Close"))
			self.connect(self.btnClose, QtCore.SIGNAL("clicked()"), self.reject)
			self.layout.addWidget(self.btnClose, alignment=QtCore.Qt.AlignRight)

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
			if not self.btnClose.isEnabled():
				text = __("<b>Warning:</b> If you close this window while a firmware update is still running, it might leave the device in an unbootable state.") + "<br><br>" + __("Are you sure you want to close this window?")
				if QtWidgets.QMessageBox.warning(self, AppInfo.NAME, text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No) == QtWidgets.QMessageBox.No: return
			super().reject()

		def UpdateFirmware(self):
			with zipfile.ZipFile(os.path.join(self.FWUPD.APP_PATH, "res", "fw_JoeyJr.zip")) as archive:
				fn = None
				path = ""
				verified = False
				if self.optFW_LK.isChecked():
					fw, fn, marker = self.FW_LK_VER, "FIRMWARE_LK.JR", b"FW LK"
				elif self.optFW_MSC.isChecked():
					fw, fn, marker = self.FW_MSC_VER, "FIRMWARE_MSC.JR", b"Joey Jr. Firmware"
				elif self.optFW_JoeyGUI.isChecked():
					fw, fn, marker = self.FW_JOEYGUI_VER, "FIRMWARE_JOEYGUI.JR", b"FW GUI"
				else:
					path = self.APP.SETTINGS.value("LastDirFirmwareUpdate")
					path = QtWidgets.QFileDialog.getOpenFileName(self, __("Choose Joey Jr Firmware File"), path, __("Firmware Update ({firmware_jr})", firmware_jr="FIRMWARE.JR"))[0]
					if path == "": return
					if not os.path.basename(path).endswith(".JR"):
						QtWidgets.QMessageBox.critical(self, AppInfo.NAME, __("The expected filename for a valid firmware file is <b>{filename_pattern}</b>. Please visit {url} for the latest official firmware updates.", firmware_jr="FIRMWARE.JR", url='<a href="https://bennvenn.myshopify.com/products/usb-gb-c-cart-dumper-the-joey-jr">https://bennvenn.myshopify.com/products/usb-gb-c-cart-dumper-the-joey-jr</a>'))
						return
					elif os.path.exists(os.path.dirname(path) + "DEBUG.TXT"):
						QtWidgets.QMessageBox.critical(self, AppInfo.NAME, __("The selected file can not be used. Please visit {url} for the latest official firmware updates.", url='<a href="https://bennvenn.myshopify.com/products/usb-gb-c-cart-dumper-the-joey-jr">https://bennvenn.myshopify.com/products/usb-gb-c-cart-dumper-the-joey-jr</a>'))
						return
					self.APP.SETTINGS.setValue("LastDirFirmwareUpdate", os.path.dirname(path))
					fw = path
					try:
						with open(path, "rb") as f: fw_data = bytearray(f.read())
						index_from = fw_data.index(b"Joey Jr")
						index_to = fw_data.index(b"\x00", index_from)
						fw_string = fw_data[index_from:index_to].decode("ASCII", "ignore")
						verified = (len(fw_data) <= 0x10000 and "Firmware" in fw_string and
							"N64 Firmware" not in fw_string and "Jr4Gen3 Firmware" not in fw_string)
						if verified:
							fw += "<br><br><b>" + __("Detected firmware string:") + "</b><br>" + fw_string
					except (OSError, ValueError):
						verified = False
				if fn is not None:
					fw_data = bytearray(archive.read(fn))
					verified = b"Joey Jr" in fw_data and marker in fw_data

			if verified is False:
				text = __("The firmware update file is corrupted or invalid.")
				self.btnUpdate.setEnabled(True)
				self.btnClose.setEnabled(True)
				QtWidgets.QMessageBox.critical(self, AppInfo.NAME, text)
				return False

			text = __("The following firmware will now be written to your Joey Jr device:") + "\n- " + fw
			text += "\n\n" + __("Do you want to continue?")
			if QtWidgets.QMessageBox.question(self, AppInfo.NAME, text, QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes) == QtWidgets.QMessageBox.No: return
			ret = 0
			while True:
				for widget in (self.grpAvailableFwUpdates, self.btnUpdate, self.btnClose):
					widget.setEnabled(False)
				try:
					if ret == 0: self.APP.DisconnectDevice()
					if ret == 4:
						ret = self.FWUPD.WriteFirmwareMSC(path, fw_data, self.SetStatus)
					else:
						ret = self.FWUPD.WriteFirmware(fw_data, self.SetStatus)
				finally:
					for widget in (self.grpAvailableFwUpdates, self.btnUpdate, self.btnClose):
						widget.setEnabled(True)

				if ret == 1:
					text = __("The firmware update is complete!")
					if self.optFW_MSC.isChecked():
						text += "\n\n" + __("Please note that you need to manually copy over the {romlist} file. You can find the latest version of it on the Joey Jr website.", romlist="ROMLIST.RAW")
					QtWidgets.QMessageBox.information(self, AppInfo.NAME, text)
					self.DEVICE = None
					self.reject()
					return True
				elif ret in (2, 3):
					text = __("The firmware update has failed. Please try again.") if ret == 2 else __("The firmware update file is corrupted. Please re-install the application.")
					QtWidgets.QMessageBox.critical(self, AppInfo.NAME, text)
					return False
				elif ret == 4:
					text = __("If your Joey Jr device is currently running the Drag’n’Drop firmware, please select the <b>{mode_txt}</b> (or <b>{mode_txt_2}</b>) file that is stored on the device.", mode_txt="MODE.TXT", mode_txt_2="MODE!.TXT")
					if b"Joey Jr. Firmware" not in fw_data:
						text = text + "<br><br>" + __("After installing this firmware, the Joey Jr removable drive will no longer be available. You can restore it at any time by reinstalling the Drag’n’Drop firmware using this updater.")
					answer = QtWidgets.QMessageBox.information(self, AppInfo.NAME, text, QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel, QtWidgets.QMessageBox.Ok)
					if answer == QtWidgets.QMessageBox.Cancel:
						self.SetStatus(__("No device found."))
						return False
					path = self.APP.SETTINGS.value("LastDirFirmwareUpdate")
					path = QtWidgets.QFileDialog.getOpenFileName(self, __("Choose the {mode_txt} file of your Joey Jr removable drive", mode_txt="MODE.TXT"), path, "MODE.TXT (MODE*.TXT)")[0]
					self.APP.QT_APP.processEvents()
					if os.path.basename(path) not in ("MODE.TXT", "MODE!.TXT"):
						self.SetStatus(__("No device found."))
						return False
					self.APP.SETTINGS.setValue("LastDirFirmwareUpdate", os.path.dirname(path))

		def SetStatus(self, text, setProgress=None):
			self.lblStatus.setText(__("Status: {text}", text=text))
			if setProgress is not None:
				self.prgStatus.setValue(int(setProgress * 10))
			self.grpStatus.repaint()
			self.APP.QT_APP.processEvents()
except ImportError:
	pass
