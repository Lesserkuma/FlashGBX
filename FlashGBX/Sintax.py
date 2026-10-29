# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)
# Thanks to taizou (https://hhug.me/) for the initial research
# Thanks to RibShark (github.com/RibShark) for additional research and code contributions

import ctypes, hashlib, os, platform, struct, sysconfig, time, zlib
from .i18n import __
from .app import AppContext
from .Logging import dprint

class MissingLibraryError(RuntimeError):
	def __init__(self, message, path):
		super().__init__(message)
		self.PATH = path

def LoadLibrary():
	from .PluginLoader import _GetPluginDirectory

	system = platform.system()
	machine = platform.machine().lower()
	if system == "Windows":
		machine = {"win-amd64":"x86_64", "win-arm64":"arm64", "win32":"x86"}.get(sysconfig.get_platform().lower(), machine)
	machine = {"amd64":"x86_64", "aarch64":"arm64"}.get(machine, machine)
	name, extension = {"Windows":("windows", "dll"), "Darwin":("macos", "dylib"), "Linux":("linux", "so")}[system]
	filename = "libmgba-{}-{}.{}".format(name, machine, extension)
	path = os.path.join(AppContext.APP_PATH, "res", filename)
	if not os.path.isfile(path):
		plugin_dir = _GetPluginDirectory(AppContext.CONFIG_PATH)
		path = os.path.join(plugin_dir, filename)
		if not os.path.isfile(path):
			raise MissingLibraryError(__("The libmgba library required for Sintax ROM backups was not found. Place {filename} in the {plugins} directory:", plugins="plugins", filename=filename) + "\n" + plugin_dir, plugin_dir)
	return ctypes.CDLL(path)

def CanReadSintax(device):
	return device.MODE == "AGB" and device.FW.get("cfw_id") == "L" and device.FW["fw_ver"] >= 16

class Sintax:
	def __init__(self, device):
		self.DEVICE = device
		self.TRACE = None
		self.SAVED = {}
		self.READS = 0
		self.WRITES = 0

	def SetStatus(self, text, abortable=True):
		self.DEVICE.SetProgress({"action":"UNLOCK", "text":text, "abortable":abortable})

	def CheckCancel(self):
		if self.DEVICE.CANCEL: raise InterruptedError("The Sintax ROM backup was cancelled.")

	def Call(self, method, *args, **kwargs):
		result = method(*args, **kwargs)
		if result is False: raise RuntimeError("Sintax cartridge access failed.")
		return result

	def ReadData(self, offset, length, repeat=1):
		try:
			self.Prepare()
			self.Call(self.DEVICE.CartPowerOn)
			data = []
			for index in range(repeat):
				if index: time.sleep(0.1)
				data.append(self.Read(offset, length))
			return data
		finally:
			self.Restore()

	def PrepareUnlock(self):
		device = self.DEVICE
		self.CheckCancel()
		device.INFO.update(action=device.ACTIONS["ROM_READ"], last_action=0, transferred=0)
		self.SetStatus(__("Power cycling cartridge..."))
		device.CartPowerCycleOrAskReconnect()
		self.CheckCancel()
		self.Prepare()
		if self.Call(device._get_fw_variable, "CART_MODE") != 2:
			raise RuntimeError("Sintax cartridge access failed.")
		device.SetProgress({"action":"INITIALIZE", "method":"ROM_READ", "size":0, "abortable":True})
		if not device.CanPowerCycleCart(): self.Call(device.CartPowerOn)

	def UnlockSequence(self, commands):
		self.CheckCancel()
		sequence = []
		for address, value, write in commands:
			command = {"address":address, "write":write}
			if write: command["value"] = value
			else: command.update(count=value, read_method=2)
			sequence.append(command)
		self.Call(self.DEVICE._cart_unlock_sequence, sequence)

	def QuickUnlock(self):
		self.PrepareUnlock()
		self.SetStatus(__("Unlocking cartridge..."))
		# Unlock Sequence (enters config mode)
		self.UnlockSequence([
			(0x000000, 0x0C, False),
			(0xFFFFF0, 0x10, False),
			(0xFFFC00, 0xAC, False),
			(0x1FE0000, 0x594A, True), # "YJ"
			(0x1FE0004, 0x4F4B, True), # "OK"
			(0x1FE0008, 0x0001, True),
			(0xFFFC78, (1 << 15) | 2000, False), # Repeat reads to unlock mirror parameters
		])
		
		# Configure ROM mirroring
		mirrors = self.Read(0x001180, 0x10)
		sequence = [(0x1FE0008, 0x0002, True)]
		for i in range(16):
			sequence.extend([
				(0x1FE0050, i + (i << 8), True),
				(0x1FE0054, mirrors[i] + (mirrors[i] << 8), True),
			])
		self.UnlockSequence(sequence)

		# Get final unlock sequence address (needs to happen before traps are configured)
		final_unlock_addr = (int.from_bytes(self.Read(0x0011D0, 4), "little") & 0x1FFFFFF) + 0xD4
		self.UnlockSequence([
			# Repeat reads to unlock full cart
			(0xFFFC78, (1 << 15) | 2000, False),
			# Configure traps (required to unlock cart, set to disabled)
			(0x1FE005C, 0x0080, True),
			(0x1FE0060, 0x0000, True),
		])
		data = bytes(byte ^ 0xA5 for byte in self.Read(final_unlock_addr, 272))
		sequence = [(address & 0x1FFFFFF, value & 0xFFFF, True) for value, address in struct.iter_unpack("<LL", data)]
		sequence.extend([
			# Disable trap blocks (were set by unlock sequence read from ROM above)
			(0x1FE005C, 0x0082, True),
			(0x1FE0060, 0x0000, True),
			# Exit config mode
			(0x1FE0004, 0x0000, True),
			(0x1FE0000, 0x0000, True),
		])
		self.UnlockSequence(sequence)
		self.CheckCancel()

	def Unlock(self, path):
		self.CheckCancel()
		try:
			library = LoadLibrary()
		except MissingLibraryError:
			dprint("libmgba library not found. Falling back to quick unlock without an unlock sequence log.")
			return self.QuickUnlock()
		self.PrepareUnlock()
		device = self.DEVICE
		self.TRACE = bytearray()
		path = os.path.splitext(path)[0] + ".unl"
		try:
			cpu = CPU(self, library)
			last_update = 0
			for _ in range(100000):
				now = time.monotonic()
				if now - last_update >= 0.1:
					self.SetStatus(__("Emulating unlock... ({reads} reads, {writes} writes)", reads=self.READS, writes=self.WRITES))
					last_update = now
				if not cpu.Step(): self.CheckCancel()
				if cpu.UNLOCKED_TARGET is not None: break
			else:
				raise RuntimeError("Sintax cartridge unlock failed.")
		finally:
			trace, self.TRACE = self.TRACE, None
			with open(path, "wb") as file: file.write(trace)
		log = {"file_name":path, "file_size":len(trace), "hash_crc32":zlib.crc32(trace) & 0xFFFFFFFF}
		for name in ("md5", "sha1", "sha256"): log["hash_" + name] = getattr(hashlib, name)(trace).hexdigest()
		device.INFO["dump_info"].update(sintax_traps=GetTraps(trace), sintax_binary_log=log)
		self.UnlockSequence([
			(0x09FE0000, 0x594A, True),
			(0x09FE0004, 0x4F4B, True),
			(0x09FE005C, 0x0080, True),
			(0x09FE0060, 0x0000, True),
			(0x09FE005C, 0x0082, True),
			(0x09FE0060, 0x0000, True),
			(0x09FE0004, 0x0000, True),
			(0x09FE0000, 0x0000, True),
		])
		self.WRITES += 8

	def Prepare(self):
		if not CanReadSintax(self.DEVICE):
			raise RuntimeError("Sintax backup requires AGB mode and LK firmware L16 or newer.")
		self.SAVED = {"AGB_READ_METHOD":self.DEVICE.AGB_READ_METHOD,
			"AUTO_POWEROFF_ENABLED":self.Call(self.DEVICE._get_fw_variable, "AUTO_POWEROFF_ENABLED")}
		self.Call(self.DEVICE._set_fw_variable, "AUTO_POWEROFF_ENABLED", 0, log=False)
		self.DEVICE.SetAGBReadMethod(2)
		self.Call(self.DEVICE._write, self.DEVICE.DEVICE_CMD["SET_VOLTAGE_3_3V"], wait=True)
		self.Call(self.DEVICE._write, self.DEVICE.DEVICE_CMD["DISABLE_PULLUPS"], wait=True)

	def Read(self, offset, length):
		address = offset if offset >= 0x08000000 else 0x08000000 + offset
		offset &= 0x01FFFFFF
		max_length = min(0x2000, self.DEVICE.MAX_BUFFER_READ, length)
		no_progress = self.DEVICE.NO_PROG_UPDATE
		self.DEVICE.NO_PROG_UPDATE = True
		data = bytearray()
		position = 0
		try:
			while position < length:
				current = (offset + position) & 0x01FFFFFF
				count = min(length - position, 0x20000 - (current & 0x1FFFF))
				chunk = self.Call(self.DEVICE.ReadROM, address=current, length=count, max_length=min(max_length, count))
				if len(chunk) != count:
					raise RuntimeError("Sintax cartridge access failed.")
				self.READS += 1
				data.extend(chunk)
				position += count
		finally:
			self.DEVICE.NO_PROG_UPDATE = no_progress
		if self.TRACE is not None:
			for halfword, (value,) in enumerate(struct.iter_unpack("<H", data)):
				self.TRACE.extend(struct.pack("<HIH", 0, address + halfword * 2, value))
		return bytes(data)

	def Write(self, address, value):
		command = {"address":address, "write":True, "value":value}
		self.Call(self.DEVICE._cart_unlock_sequence, [command])
		self.WRITES += 1
		if self.TRACE is not None:
			self.TRACE.extend(struct.pack("<HIH", 1, address, value))

	def Restore(self):
		if not self.SAVED: return
		state = self.DEVICE.ERROR, self.DEVICE.CANCEL, self.DEVICE.CANCEL_ARGS
		self.DEVICE.CANCEL_ARGS = {}
		try:
			self.DEVICE.SetAGBReadMethod(self.SAVED["AGB_READ_METHOD"])
			self.Call(self.DEVICE._set_fw_variable, "AUTO_POWEROFF_ENABLED", self.SAVED["AUTO_POWEROFF_ENABLED"], log=False)
		finally:
			self.DEVICE.ERROR, self.DEVICE.CANCEL, self.DEVICE.CANCEL_ARGS = state
			self.SAVED = {}

class _ARMCore(ctypes.Structure):
	pass

_CorePointer = ctypes.POINTER(_ARMCore)
_Cycles = ctypes.POINTER(ctypes.c_int32)
_Load = ctypes.CFUNCTYPE(ctypes.c_uint32, _CorePointer, ctypes.c_uint32, _Cycles)
_Store32 = ctypes.CFUNCTYPE(None, _CorePointer, ctypes.c_uint32, ctypes.c_int32, _Cycles)
_Store16 = ctypes.CFUNCTYPE(None, _CorePointer, ctypes.c_uint32, ctypes.c_int16, _Cycles)
_Store8 = ctypes.CFUNCTYPE(None, _CorePointer, ctypes.c_uint32, ctypes.c_int8, _Cycles)
_Multiple = ctypes.CFUNCTYPE(ctypes.c_uint32, _CorePointer, ctypes.c_uint32, ctypes.c_int, ctypes.c_int, _Cycles)
_Stall = ctypes.CFUNCTYPE(ctypes.c_int32, _CorePointer, ctypes.c_int32)
_Active = ctypes.CFUNCTYPE(None, _CorePointer, ctypes.c_uint32)
_IRQ = ctypes.CFUNCTYPE(None, _CorePointer)
_Immediate = ctypes.CFUNCTYPE(None, _CorePointer, ctypes.c_int)
_Opcode = ctypes.CFUNCTYPE(None, _CorePointer, ctypes.c_uint32)

class _ARMMemory(ctypes.Structure):
	_fields_ = [
		("load32", _Load), ("load16", _Load), ("load8", _Load),
		("store32", _Store32), ("store16", _Store16), ("store8", _Store8),
		("loadMultiple", _Multiple), ("storeMultiple", _Multiple),
		("activeRegion", ctypes.POINTER(ctypes.c_uint32)), ("activeMask", ctypes.c_uint32),
		("activeSeqCycles32", ctypes.c_uint32), ("activeSeqCycles16", ctypes.c_uint32),
		("activeNonseqCycles32", ctypes.c_uint32), ("activeNonseqCycles16", ctypes.c_uint32),
		("stall", _Stall), ("setActiveRegion", _Active),
	]

class _ARMIRQ(ctypes.Structure):
	_fields_ = [
		("reset", _IRQ), ("processEvents", _IRQ),
		("swi16", _Immediate), ("swi32", _Immediate),
		("hitIllegal", _Opcode), ("bkpt16", _Immediate),
		("bkpt32", _Immediate), ("readCPSR", _IRQ), ("hitStub", _Opcode),
	]

_ARMCore._fields_ = [
	("gprs", ctypes.c_int32 * 16), ("cpsr", ctypes.c_uint32), ("spsr", ctypes.c_uint32),
	("cycles", ctypes.c_int32), ("nextEvent", ctypes.c_int32), ("halted", ctypes.c_int),
	("bankedRegisters", (ctypes.c_int32 * 7) * 6), ("bankedSPSRs", ctypes.c_int32 * 6),
	("shifterOperand", ctypes.c_int32), ("shifterCarryOut", ctypes.c_int32),
	("prefetch", ctypes.c_uint32 * 2), ("executionMode", ctypes.c_int), ("privilegeMode", ctypes.c_int),
	("memory", _ARMMemory), ("irqh", _ARMIRQ), ("master", ctypes.c_void_p),
	("numComponents", ctypes.c_size_t), ("components", ctypes.c_void_p),
]

class CPU:
	def __init__(self, bus, library):
		self.BUS = bus
		self.ERROR = None
		self.INITIAL_TARGET = None
		self.UNLOCKED_TARGET = None
		self.PENDING_FETCH = None
		self.CALLBACKS = []
		self.CORE = _ARMCore()
		self.FETCH_BUFFER = (ctypes.c_uint32 * 4)()
		self.RAM = {2: bytearray(0x40000), 3: bytearray(0x8000)}
		self.LIB = library
		self.LIB.ARMRun.argtypes = [_CorePointer]
		self.LIB.ARMRun.restype = None

		for name, kind, method in [
			("load32", _Load, lambda cpu, address, cycles: self.Read(address, 4)),
			("load16", _Load, lambda cpu, address, cycles: self.Read(address, 2)),
			("load8", _Load, lambda cpu, address, cycles: self.Read(address, 1)),
			("store32", _Store32, lambda cpu, address, value, cycles: self.Write(address, 4, value)),
			("store16", _Store16, lambda cpu, address, value, cycles: self.Write(address, 2, value)),
			("store8", _Store8, lambda cpu, address, value, cycles: self.Write(address, 1, value)),
			("loadMultiple", _Multiple, lambda cpu, address, mask, direction, cycles: self.Multiple(address, mask, direction, False)),
			("storeMultiple", _Multiple, lambda cpu, address, mask, direction, cycles: self.Multiple(address, mask, direction, True)),
			("stall", _Stall, lambda cpu, wait: wait),
			("setActiveRegion", _Active, self.SetActiveRegion),
		]:
			setattr(self.CORE.memory, name, self.Callback(kind, method))

		for name, kind in _ARMIRQ._fields_:
			method = lambda *args: self.Fail()
			if name == "processEvents": method = lambda cpu: setattr(self.CORE, "nextEvent", 0x7FFFFFFF)
			elif name == "readCPSR": method = lambda cpu: None
			setattr(self.CORE.irqh, name, self.Callback(kind, method))

		self.CORE.memory.activeRegion = ctypes.cast(self.FETCH_BUFFER, ctypes.POINTER(ctypes.c_uint32))
		self.CORE.cpsr = 0x1F
		self.CORE.privilegeMode = 0x1F
		self.CORE.gprs[13] = 0x03007F00
		self.CORE.bankedRegisters[2][0] = 0x03007FA0
		self.CORE.bankedRegisters[3][0] = 0x03007FE0
		self.SetActiveRegion(None, 0x08000000)
		self.CORE.prefetch[0] = self.FETCH_BUFFER[0]
		self.CORE.prefetch[1] = self.FETCH_BUFFER[1]
		self.CORE.gprs[15] = 0x08000004

	def Callback(self, kind, method):
		def Call(*args):
			if self.ERROR is not None: return 0
			try:
				return method(*args)
			except BaseException as e:
				self.ERROR = e
				return 0
		self.CALLBACKS.append(kind(Call))
		return self.CALLBACKS[-1]

	def Fail(self):
		raise RuntimeError("Failed to unlock the Sintax cartridge.")

	def Read(self, address, width):
		address &= 0xFFFFFFFF
		aligned = address & ~(width - 1)
		region = aligned >> 24
		if 8 <= region <= 13:
			if width == 1:
				data = self.BUS.Read(aligned & ~1, 2)[aligned & 1:(aligned & 1) + 1]
			else:
				data = self.BUS.Read(aligned, width)
		elif region in self.RAM:
			memory = self.RAM[region]
			offset = aligned & (len(memory) - 1)
			data = memory[offset:offset + width]
		else: self.Fail()
		value = int.from_bytes(data, "little")
		rotate = (address - aligned) * 8
		if rotate:
			value = ((value >> rotate) | (value << (32 - rotate))) & 0xFFFFFFFF
		return value

	def Write(self, address, width, value):
		address = (address & 0xFFFFFFFF) & ~(width - 1)
		value &= (1 << (width * 8)) - 1
		region = address >> 24
		if 8 <= region <= 13:
			if width == 1: value *= 0x101
			address &= ~1
			self.BUS.Write(address, value & 0xFFFF)
			if width == 4:
				self.BUS.Write(address + 2, value >> 16)
		elif region in self.RAM:
			memory = self.RAM[region]
			offset = address & (len(memory) - 1)
			memory[offset:offset + width] = value.to_bytes(width, "little")
		else: self.Fail()

	def Multiple(self, address, mask, direction, store):
		registers = [i for i in range(16) if mask & (1 << i)]
		count = len(registers)
		start = address
		if direction & 2:
			start -= 4 * (count - 1)
		if direction & 1:
			start += -4 if direction & 2 else 4
		start &= 0xFFFFFFFC
		for index, register in enumerate(registers):
			position = (start + index * 4) & 0xFFFFFFFF
			if store:
				value = self.CORE.gprs[register]
				if register == 15:
					value += 4
				self.Write(position, 4, value)
			else:
				self.CORE.gprs[register] = self.Read(position, 4)
		return (address + (-4 if direction & 2 else 4) * count) & 0xFFFFFFFF

	def Fetch(self, address, width):
		address = (address & 0xFFFFFFFF) & ~(width - 1)
		value = self.Read(address, width)
		ctypes.memmove(ctypes.addressof(self.FETCH_BUFFER) + (address & 15), value.to_bytes(width, "little"), width)
		return value

	def SetActiveRegion(self, cpu, address):
		width = 2 if self.CORE.executionMode else 4
		self.CORE.memory.activeMask = 15 & ~(width - 1)
		aligned = address & ~(width - 1)
		if 8 <= aligned >> 24 <= 13 and (aligned & 0x1FFFF) + width * 3 <= 0x20000:
			data = self.BUS.Read(aligned, width * 3)
			for index in range(3):
				position = (aligned + index * width) & 15
				ctypes.memmove(ctypes.addressof(self.FETCH_BUFFER) + position, data[index * width:(index + 1) * width], width)
			opcode = int.from_bytes(data[:width], "little")
		else:
			opcode = self.Fetch(address, width)
			self.Fetch((address + width) & 0xFFFFFFFF, width)
			self.Fetch((address + width * 2) & 0xFFFFFFFF, width)
		self.PENDING_FETCH = ((aligned + width * 2) & 0xFFFFFFFF, width)
		if address != 0x08000000 or width != 4: return
		if (opcode & 0xFF000000) != 0xEA000000:
			self.Fail()
		displacement = int.from_bytes(opcode.to_bytes(4, "little")[:3], "little", signed=True)
		target = (address + 8 + displacement * 4) & 0xFFFFFFFF
		if self.INITIAL_TARGET is None:
			self.INITIAL_TARGET = target
		elif target != self.INITIAL_TARGET:
			self.UNLOCKED_TARGET = target

	def Step(self):
		if self.BUS.DEVICE.CANCEL: return False
		width = 2 if self.CORE.executionMode else 4
		fetch_address = ((self.CORE.gprs[15] + width) & 0xFFFFFFFF) & ~(width - 1)
		if self.PENDING_FETCH != (fetch_address, width):
			self.Fetch(fetch_address, width)
		self.PENDING_FETCH = None
		self.CORE.cycles = 0
		self.CORE.nextEvent = 0x7FFFFFFF
		self.LIB.ARMRun(ctypes.byref(self.CORE))
		if self.ERROR is not None: raise self.ERROR
		return True

def GetTraps(trace):
	registers, selected = {}, None
	for operation, address, value in struct.iter_unpack("<HIH", trace):
		if operation != 1: continue
		if address == 0x09FE005C:
			selected = value
		elif address == 0x09FE0060 and selected is not None:
			registers[selected] = value

	def Decode(index):
		value = registers[index] | (registers[index + 1] << 16)
		return (value ^ 0x00FF1234) << 1

	mask = registers.get(0x80, 0x0FFF)
	offsets = sorted({Decode(slot * 2) for slot in range(12) if mask & (1 << slot)})
	regions = []
	mask = registers.get(0x82, 0)
	for slot in range(2):
		if not mask & (1 << slot): continue
		base = 0xC0 + slot * 4
		start, end = Decode(base) + 2, Decode(base + 2)
		regions.append((start, end - start))
	return offsets, sorted(set(regions))
