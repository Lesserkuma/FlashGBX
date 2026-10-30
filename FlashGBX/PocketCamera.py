# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

from PIL import Image
from PIL.PngImagePlugin import PngInfo
import os, hashlib, io, math, time, threading
import email.utils
from .app import AppInfo
from .i18n import __

class PocketCamera:
	DATA = None
	PALETTES = [
		[ 255, 255, 255,   176, 176, 176,   104, 104, 104,   0, 0, 0 ], # Grayscale
		[ 208, 217, 60,   120, 164, 106,   84, 88, 84,   36, 70, 36 ], # Game Boy
		[ 255, 255, 255,   181, 179, 189,   84, 83, 103,   9, 7, 19 ], # Super Game Boy
		[ 240, 240, 240,   218, 196, 106,   112, 88, 52,   30, 30, 30 ], # Game Boy Color (JPN)
		[ 240, 240, 240,   220, 160, 160,   136, 78, 78,   30, 30, 30 ], # Game Boy Color (USA Gold)
		[ 240, 240, 240,   134, 200, 100,   58, 96, 132,   30, 30, 30 ], # Game Boy Color (USA/EUR)
	]
	# CLI / argparse identifiers for PALETTES (parallel list, same order).
	PALETTE_NAMES = ["grayscale", "dmg", "sgb", "cgb1", "cgb2", "cgb3"]
	# Output file formats accepted by ExportPicture().
	OUTPUT_FORMATS = ["png", "bmp", "gif", "jpg"]
	PALETTE = [ 240, 240, 240,   218, 196, 106,   112, 88, 52,   30, 30, 30 ] # default
	IMAGES = [None] * 32
	IMAGES_DELETED = []
	ORDER = None

	def __init__(self):
		pass

	def LoadFile(self, savefile):
		if isinstance(savefile, bytearray):
			self.DATA = savefile
		else:
			if os.path.getsize(savefile) != 128*1024: return False
			with open(savefile, "rb") as file: self.DATA = file.read()

		# if self.DATA[0x1FFB1:0x1FFB6] != b'Magic':
		# 	self.DATA = None
		# 	return False

		order_raw = self.DATA[0x11D7:0x11F5]
		order = [None] * 30
		deleted = []
		seen_indicies = []
		for i in range(0, 30):
			if order_raw[i] == 0xFF or order_raw[i] in seen_indicies:
				deleted.append(i)
			else:
				order[order_raw[i]] = i
			seen_indicies.append(order_raw[i])

		while None in order: order.remove(None)
		order.extend(deleted)
		self.ORDER = order
		self.IMAGES_DELETED = deleted

		for i in range(0, 30):
			self.IMAGES[i] = self.ExtractPicture(i)
		self.IMAGES[30] = self.ExtractGameFace()
		self.IMAGES[31] = self.ExtractLastSeen()
		return True

	def SetPalette(self, palette):
		if isinstance(palette, int):
			palette = self.PALETTES[palette]
		for p in range (0, len(self.IMAGES)):
			self.IMAGES[p].putpalette(palette)
		self.PALETTE = palette

	def GetPicture(self, index):
		return self.IMAGES[index]

	def IsEmpty(self, index):
		return (hashlib.sha1(self.IMAGES[index].tobytes()).digest() == b'\xefX\xa8\x12\xa8\x1a\xb1EI\xd8\xf4\xfb\x86\xe9\xec\xb5J_\xb7#')

	def IsDeleted(self, index):
		index = self.ORDER[index]
		return index in self.IMAGES_DELETED

	def ConvertPicture(self, buffer, lastseen=False):
		tile_width = 16
		tile_height = 14 if not lastseen else 16

		img = Image.new(mode='P', size=(128, 112 if not lastseen else 128))
		img.putpalette(self.PALETTE)
		pixels = img.load()
		for h in range(tile_height):
			for w in range(tile_width):
				tile_pos = 16 * ((h * tile_width) + w)
				tile = buffer[tile_pos:tile_pos+16]
				for i in range(8):
					for j in range(8):
						hi = (tile[i * 2] >> (7 - j)) & 1
						lo = (tile[i * 2 + 1] >> (7 - j)) & 1
						pixels[(w * 8) + j, (h * 8) + i] = (lo << 1 | hi)

		return img.crop((0, 0, 128, 112 if not lastseen else 123))

	def ExtractGameFace(self):
		offset = 0x11FC
		imgbuffer = self.DATA[offset:offset+0x1000]
		return self.ConvertPicture(imgbuffer)

	def ExtractLastSeen(self):
		offset = 0
		imgbuffer = self.DATA[offset:offset+0x1000]
		return self.ConvertPicture(imgbuffer, lastseen=True)

	def ExtractPicture(self, index):
		if index < 30:
			index = self.ORDER[index]
			offset = 0x2000 + (index * 0x1000)
		elif index == 30:
			offset = 0x11FC
		else:
			offset = 0
		imgbuffer = self.DATA[offset:offset+0x1000]
		return self.ConvertPicture(imgbuffer)

	def ExportPicture(self, index, path, scale=1.0, frame=False):
		title = "Game Face" if index == 30 else "Last Seen Image" if index == 31 else "Photo {:02d}".format(index + 1)
		self.ExportImage(self.GetPicture(index), path, scale, frame, title)

	@staticmethod
	def AddFrame(pic, frame=False):
		if frame is not False:
			if not isinstance(frame, Image.Image):
				frame = Image.open(io.BytesIO(frame)).convert("RGB")
			if frame.width >= 160 and frame.height >= 144:
				# Match the album crop: sensor rows 8 through 119.
				if pic.size in ((128, 121), (128, 123)): pic = pic.crop((0, 8, 128, 120))
				frame = frame.copy()
				left = math.floor(frame.width / 2) - 64
				top = math.floor(frame.height / 2) - 56
				frame.paste(pic, (left, top))
				return frame
		return pic

	@staticmethod
	def ExportImage(pic, path, scale=1.0, frame=False, title="Photo", rotation=0):
		pnginfo = PngInfo()
		pnginfo.add_text("Software", AppInfo.NAME)
		pnginfo.add_text("Creation Time", email.utils.formatdate())
		pnginfo.add_text("Title", title)
		pic = PocketCamera.AddFrame(pic, frame)
		if rotation: pic = pic.rotate(-rotation, expand=True)
		pic = pic.resize((int(pic.width * scale), int(pic.height * scale)), Image.Resampling.NEAREST)

		ext = os.path.splitext(path)[1]
		if ext == "" or ext.lower() == ".png":
			outpic = pic
			outpic.save(path, format="PNG", pnginfo=pnginfo)
		elif ext.lower() == ".gif":
			outpic = pic
			outpic.save(path)
		elif ext.lower() in (".jpg", ".jpeg"):
			outpic = pic.convert("RGB")
			outpic.save(path, quality=100, subsampling=0)
		else:
			outpic = pic.convert("RGB")
			outpic.save(path)


class PocketCameraCapture:
	# Game Boy Camera (USA, Europe) ROM, 0A:7C60..7C9F: mid_gain contrast table.
	# Four anchors interpolate three grayscale thresholds; default row: 0A:7C7C.
	CONTRAST_ANCHORS = (
		(128, 148, 220, 255), (130, 149, 210, 255),
		(132, 150, 202, 255), (134, 150, 196, 255),
		(136, 151, 190, 255), (138, 151, 184, 255),
		(139, 152, 178, 245), (140, 152, 172, 235),
		(141, 152, 170, 221), (142, 152, 168, 208),
		(143, 152, 166, 196), (144, 152, 164, 186),
		(146, 152, 161, 177), (148, 152, 157, 168),
		(150, 152, 153, 160), (152, 152, 152, 152),
	)
	# ROM 0A:7B00: exposure correction shifts, indexed by metered level.
	EXPOSURE_SHIFTS = (
		2, 3, 3, 3, 4, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
		4, 4, 4, 5, 4, 5, 5, 5, 5, 5, 6, 5, 6, 6, 6, 7,
		7, 8, 9, 16, 16, 16, 9, 8, 7, 7, 6, 6, 5, 6, 5, 5,
		5, 5, 4, 5,
	) + (4,) * 28 + (3,) * 80
	# ROM 0A:4427: row-major ranks of the repeating 4×4 dithering pattern.
	RANKS = (0, 12, 3, 15, 8, 4, 11, 7, 2, 14, 1, 13, 10, 6, 9, 5)
	BIT_COUNTS = tuple(bin(value).count("1") for value in range(256))
	DEFAULT_BRIGHTNESS, DEFAULT_CONTRAST = 10, 8

	def __init__(self, device, exposure=0x1000):
		self.DEVICE = device
		self.EXPOSURE, self.USED_EXPOSURE, self.LEVEL = exposure, exposure, None
		self.STATE = None
		self.ABORTED, self.CLOSING = threading.Event(), False
		self.HEADER, self.LAST_CHECK = None, 0
		self.CONTRAST = None
		self.CAMERA = PocketCamera()
		self.CAMERA.PALETTE = [255] * 3 + [170] * 3 + [85] * 3 + [0] * 3

	def CheckAbort(self):
		if self.ABORTED.is_set(): raise InterruptedError(__("Game Boy Camera capture aborted"))

	def Abort(self):
		if self.ABORTED.is_set(): return
		self.ABORTED.set()
		self.DEVICE.AbortOperation()
		port = self.DEVICE.DEVICE
		self.DEVICE.DEVICE, self.DEVICE.MODE = None, None
		if port is not None:
			def disconnect():
				for method in ("cancel_read", "cancel_write", "close"):
					try: getattr(port, method)()
					except Exception: pass
			threading.Thread(target=disconnect, daemon=True).start()

	def ReadRAM(self, offset, size):
		self.CheckAbort()
		data = self.DEVICE.ReadRAM(offset, size, max_length=0x2000)
		if len(data) != size: raise IOError(__("Incomplete response from the Game Boy Camera."))
		return data

	def WriteRAM(self, offset, data):
		self.CheckAbort()
		if not self.DEVICE.WriteRAM(offset, bytearray(data), max_length=0x800):
			raise IOError(__("Writing to the Game Boy Camera failed."))

	def CheckCamera(self):
		self.CheckAbort()
		header = self.DEVICE.ReadROM(0, 0x150, max_length=0x150)
		if len(header) != 0x150 or header[0x147] != 0xFC or (self.HEADER is not None and header != self.HEADER):
			raise RuntimeError(__("No Game Boy Camera detected. Check the cartridge connection."))
		self.HEADER, self.LAST_CHECK = bytes(header), time.monotonic()

	def __enter__(self):
		self.CheckAbort()
		device = self.DEVICE
		if not device.IsConnected():
			raise RuntimeError(__("Game Boy Camera Live View requires a connected device."))
		if device.GetMode() != "DMG" or (device.FW or {}).get("fw_ver", 0) < 16 or not device.IsClkConnected():
			raise RuntimeError(__("Game Boy Camera Live View requires Game Boy mode, firmware L16 or newer, and a connected CLK pin."))
		if not 0 <= self.EXPOSURE <= 0xFFFF: raise ValueError(__("Invalid exposure"))
		self.STATE = {"progress":device.NO_PROG_UPDATE, "timeout":device.DEVICE_TIMEOUT,
			"cancel":device.CANCEL, "skip_powercycle":device.SKIP_POWERCYCLE, "variables":{}}
		try:
			for key in ("AUTO_POWEROFF_TIME", "AUTO_POWEROFF_ENABLED", "DMG_WRITE_CS_PULSE", "DMG_READ_CS_PULSE"):
				value = device._get_fw_variable(key)
				if value is False: raise IOError(__("Incomplete response from the Game Boy Camera."))
				self.STATE["variables"][key] = value
			device.NO_PROG_UPDATE, device.CANCEL = True, False
			device.SetTimeout(5)
			device.SetAutoPowerOff(0)
			device.CartPowerOn()
			device._set_fw_variable("DMG_WRITE_CS_PULSE", 0)
			device._set_fw_variable("DMG_READ_CS_PULSE", 0)
			time.sleep(0.2)
			self.CheckCamera()
			device._cart_write(0x4000, 0x10)
			if self.ReadRAM(0, 1)[0] & 1:
				time.sleep(0.1)
				if self.ReadRAM(0, 1)[0] & 1: raise RuntimeError(__("The Game Boy Camera is not responding."))
			# Fixed mid gain, reference voltage and offset; exposure follows each image.
			self.WriteRAM(1, [0xE4, 0, 0, 0x03, 0xA0])
			self.CONTRAST = None
		except BaseException:
			self.Close()
			raise
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self.Close()

	def Close(self):
		if self.STATE is None: return
		device, state = self.DEVICE, self.STATE
		self.STATE = None
		self.CLOSING = True
		try:
			self.CheckAbort()
			for key, value in state["variables"].items():
				self.CheckAbort()
				device._set_fw_variable(key, value)
		finally:
			self.CLOSING = False
			device.NO_PROG_UPDATE = state["progress"]
			device.CANCEL = True if self.ABORTED.is_set() else state["cancel"]
			device.SKIP_POWERCYCLE = state["skip_powercycle"]
			device.DEVICE_TIMEOUT = state["timeout"]
			if device.DEVICE is not None and not self.ABORTED.is_set(): device.SetTimeout(state["timeout"])

	@staticmethod
	def Settings(brightness, contrast):
		if type(brightness) is not int or type(contrast) is not int or brightness not in range(1, 17) or contrast not in range(1, 17):
			raise ValueError(__("Brightness and contrast must be integers between 1 and 16"))
		# ROM 06:6136/6161: brightness divisor 12..192, contrast 1..16.
		# Reverse the divisor so higher values brighten the image; default 10 gives 0x54.
		return 12 * (17 - brightness), contrast - 1

	def AdjustExposure(self, pixels, brightness):
		total = 0
		# ROM 0A:4FBD/5091: weighted bitplane samples relative to image buffer A100.
		for start, rows, stride, columns, weight in (
			(0x220, 10, 0x103, (0, 22, 44, 50, 72, 94, 100, 122, 128, 150, 172, 178), 2),
			(0x440, 6, 0x100, (0, 22, 44, 50, 72, 94, 100, 122), 1),
		):
			for row in range(rows):
				for column in columns:
					offset = start + row * stride + column
					total += weight * (self.BIT_COUNTS[pixels[offset]] + 2 * self.BIT_COUNTS[pixels[offset + 1]])
		# ROM 0A:4000: table-driven exposure correction with a fixed gain.
		self.LEVEL = min(159, total // brightness) if brightness else 159
		step = self.EXPOSURE >> self.EXPOSURE_SHIFTS[self.LEVEL]
		exposure = self.EXPOSURE - step if self.LEVEL < 36 else self.EXPOSURE + step
		self.EXPOSURE = max(0x10, min(0xFFFF, exposure))

	def Capture(self, brightness=DEFAULT_BRIGHTNESS, contrast=DEFAULT_CONTRAST, frequency=1, vertical_sharpening=True):
		self.CheckAbort()
		if self.STATE is None: raise RuntimeError(__("Game Boy Camera capture is not active"))
		brightness, contrast = self.Settings(brightness, contrast)
		if time.monotonic() - self.LAST_CHECK >= 1: self.CheckCamera()
		self.DEVICE._cart_write(0x4000, 0x10)
		if contrast != self.CONTRAST:
			anchors = self.CONTRAST_ANCHORS[contrast]
			# Three interpolated thresholds per 4×4 cell, written to A006..A035.
			matrix = [anchors[k] + (anchors[k + 1] - anchors[k]) * rank // 16
				for rank in self.RANKS for k in range(3)]
			self.WriteRAM(6, matrix)
			self.CONTRAST = contrast
		self.USED_EXPOSURE = self.EXPOSURE
		# A001: 2D enhancement (E4) or horizontal enhancement only (24), both at gain 4.
		self.WriteRAM(1, bytes([0xE4 if vertical_sharpening else 0x24]) + self.EXPOSURE.to_bytes(2, "big"))
		self.WriteRAM(0, [0x03])
		clocks = 32446 + (0 if vertical_sharpening else 512) + 16 * self.EXPOSURE + 1024
		if self.DEVICE._clk_toggle(clocks, frequency=frequency) is False:
			raise IOError(__("Game Boy Camera clock generation failed."))
		if self.ReadRAM(0, 1)[0] & 1:
			time.sleep(0.1)
			if self.ReadRAM(0, 1)[0] & 1: raise TimeoutError(__("The Game Boy Camera is not responding."))
		self.DEVICE._cart_write(0x4000, 0)
		pixels = self.ReadRAM(0, 0x1000)
		self.AdjustExposure(pixels[0x100:0xF00], brightness)
		return self.CAMERA.ConvertPicture(pixels, lastseen=True).crop((0, 0, 128, 121))
