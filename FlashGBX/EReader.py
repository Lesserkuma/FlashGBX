# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import datetime, hashlib, json, os, re, struct, tempfile, threading, time, traceback, zlib
from serial import SerialException
from reedsolo import RSCodec, ReedSolomonError
from collections import Counter, defaultdict, deque
from ctypes import c_int32
from codecs import charmap_decode
from functools import reduce
from heapq import nlargest
from operator import xor
from statistics import median_high
from itertools import combinations, product
from .i18n import __
from .Logging import dprint

class ScanControl:
	RANGES = {
		"sensor_brightness":(0, 63, "Sensor Brightness"),
		"vertical_offset":(7, 61, "Vertical Offset"),
		"pwm":(0, 4531, "PWM"),
		"threshold_factor":(34, 80, "Threshold Factor"),
	}

	def __init__(self, auto_calibration=True, sensor_brightness=None, vertical_offset=None, pwm=None, threshold_factor=56, auto_calibration_reused=False, error_correction=True):
		self.LOCK, self.VALUES = threading.Lock(), {}
		self.Update(auto_calibration=auto_calibration, auto_calibration_reused=auto_calibration_reused, sensor_brightness=sensor_brightness,
			vertical_offset=vertical_offset, pwm=pwm, threshold_factor=threshold_factor, error_correction=error_correction)

	def Validate(self, values):
		for key, value in values.items():
			if key in ("auto_calibration", "auto_calibration_reused", "error_correction"): continue
			minimum, maximum, label = self.RANGES[key]
			if value is None and key != "threshold_factor": continue
			if not isinstance(value, int) or not minimum <= value <= maximum:
				raise ValueError(__("{setting} must be between {minimum} and {maximum}", setting=__(label), minimum=minimum, maximum=maximum))

	def Update(self, **values):
		self.Validate(values)
		if "auto_calibration" in values: values.setdefault("auto_calibration_reused", False)
		for key in ("auto_calibration", "auto_calibration_reused", "error_correction"):
			if key in values: values[key] = bool(values[key])
		with self.LOCK: self.VALUES.update(values)

	def Get(self):
		with self.LOCK: return self.VALUES.copy()

	def FactorySettings(self, factory, pwm=None, sensor_brightness=None, threshold_factor=56, vertical_offset=None):
		factory = bytes(factory)
		if sensor_brightness is None: sensor_brightness = factory[49]
		if vertical_offset is None: vertical_offset = (factory[48] if factory[48] <= 54 else 27) + 7
		if pwm is None: pwm = min(struct.unpack_from("<H", factory, 50)[0], 4531)
		self.Validate({"sensor_brightness":sensor_brightness, "vertical_offset":vertical_offset,
			"pwm":pwm, "threshold_factor":threshold_factor})
		adjustment = struct.unpack_from("<h", factory, 0x36)[0]
		dark = ((adjustment + 64) >> 7) & 255 if adjustment > 0 else 0
		thresholds = bytes(min(127, max(0, dark + ((threshold_factor * (value - dark) + 64) >> 7))) for value in factory[:48])
		return bytearray(struct.pack(">BBH", sensor_brightness, vertical_offset, pwm) + thresholds)


class EReaderCalibration:
	UPDATE_NONE = 0
	UPDATE_GLOBAL = 1
	UPDATE_THRESHOLDS = 2

	def __init__(self, factory, settings, auto=True):
		self.FACTORY = bytes(factory)
		self.DARK_Q7 = struct.unpack_from("<h", factory, 0x36)[0]  # Q7 = 2^7 = 128
		self.DARK = ((self.DARK_Q7 + 64) >> 7) & 255 if self.DARK_Q7 > 0 else 0
		self.USED_DARK, self.REFERENCE = self.DARK, list(factory[:48])
		self.PWM = struct.unpack_from(">H", settings, 2)[0]
		self.FACTORY_SCALE, self.DOT_LIMIT = 8192, 16
		self.ADJUSTED, self.AUTO = False, auto
		self.ADDRESSES = set()
		self.FACTORS, self.WARMUP = [56, 56], [1, 1]
		self.SETTLING = 4 if auto else 0
		self.BOOTSTRAP_CONFIRMATIONS = 0
		self.BOOTSTRAP_READY = False
		self.BOOTSTRAP_WHITES, self.BOOTSTRAP_BLOCKS = deque(maxlen=3), {}
		self.BOOTSTRAP_GEOMETRY, self.BOOTSTRAP_GEOMETRY_CONFIRMATIONS = set(), 0
		self.LAST_FACTOR = None

	def Update(self, statistics, geometry, buffer, settings, blocks=None):
		self.LAST_FACTOR = None
		# Statistics contain one dark value and 48 regional intensities.
		measured_dark, maxima = statistics[0], statistics[1:]
		if not self.AUTO:
			return self.UPDATE_NONE
		if self.SETTLING:
			self.SETTLING -= 1
			return self.UPDATE_NONE

		# Software PHI changes the LED exposure. Establish a usable image before geometry adjustment.
		if not self.BOOTSTRAP_READY:
			white = median_high(maxima[row * 8 + column] for row in range(1, 5) for column in range(1, 7))
			self.BOOTSTRAP_WHITES.append(white)
			readable = dict(blocks or {}) if white < 120 else {}
			matching = {address:data for address, data in readable.items() if self.BOOTSTRAP_BLOCKS.get(address) == data}
			if matching:
				self.BOOTSTRAP_BLOCKS = matching
				self.BOOTSTRAP_CONFIRMATIONS += 1
			else:
				self.BOOTSTRAP_BLOCKS = readable
				self.BOOTSTRAP_CONFIRMATIONS = 1 if readable else 0
			# Validated block borders can guide calibration before the payload is readable.
			visible = set(geometry) if white < 120 else set()
			matching_geometry = visible & self.BOOTSTRAP_GEOMETRY
			if matching_geometry:
				self.BOOTSTRAP_GEOMETRY = matching_geometry
				self.BOOTSTRAP_GEOMETRY_CONFIRMATIONS += 1
			else:
				self.BOOTSTRAP_GEOMETRY = visible
				self.BOOTSTRAP_GEOMETRY_CONFIRMATIONS = 1 if visible else 0
			if len(self.BOOTSTRAP_WHITES) < 3: return self.UPDATE_NONE
			white = median_high(self.BOOTSTRAP_WHITES)
			if (self.BOOTSTRAP_CONFIRMATIONS >= 3
					or (self.BOOTSTRAP_GEOMETRY_CONFIRMATIONS >= 3 and len(visible) >= 2)):
				self.BOOTSTRAP_READY = True
			else:
				if abs(white - (self.DARK + 45)) <= 5:
					dprint('PWM pre-calibration: checking readability at PWM {}, white level {} ({}/3).'.format(self.PWM, white, self.BOOTSTRAP_CONFIRMATIONS))
					return self.UPDATE_NONE
				if white >= 120:
					pwm = self.PWM // 2
				elif white <= self.DARK:
					pwm = max(1, self.PWM * 2)
				else:
					# Signed division
					pwm = int(c_int32((128 * ((self.DARK + 45) & 255) - self.DARK_Q7) * self.PWM).value / c_int32(128 * white - self.DARK_Q7).value)
				pwm = min(4531, max(1, pwm))
				self.PWM = pwm
				struct.pack_into(">H", settings, 2, pwm)
				self.BOOTSTRAP_WHITES.clear()
				self.BOOTSTRAP_BLOCKS.clear()
				self.BOOTSTRAP_CONFIRMATIONS = 0
				self.BOOTSTRAP_GEOMETRY.clear()
				self.BOOTSTRAP_GEOMETRY_CONFIRMATIONS = 0
				self.SETTLING = 2
				dprint('PWM pre-calibration: {}, white level {}.'.format(pwm, white))
				return self.UPDATE_GLOBAL

		self.ADDRESSES.update(geometry)
		changed, current_scale = False, 8192
		if not self.ADJUSTED and len(self.ADDRESSES) >= 2 and geometry:
			rows = next(iter(geometry.values()))[0]
			# Map geometry rows to the 8x6 statistics grid and select the lowest value in columns 1..6.
			indices = [((y * 25) >> 10) * 8 + column for column in range(1, 7) for y in reversed(rows)]
			if any(not 0 <= index < 48 for index in indices): return self.UPDATE_NONE
			selected = min(indices, key=lambda index: maxima[index])
			white, dark = maxima[selected], self.DARK
			if white <= dark or self.FACTORY[selected] <= dark: return self.UPDATE_NONE
			# Adjust exposure toward dark+45 with Q13 scaling (Q13 = 2^13 = 8192) and PWM saturation handling.
			denominator = 128 * white - self.DARK_Q7
			# Signed division
			pwm = int(c_int32((128 * ((dark + 45) & 255) - self.DARK_Q7) * self.PWM).value / c_int32(denominator).value)
			current_scale = int(45 * 8192 / c_int32(white - dark).value)
			self.FACTORY_SCALE = int(45 * 8192 / c_int32(self.FACTORY[selected] - dark).value)
			if pwm > 4531:
				if self.DARK_Q7 > 0:
					current_scale = int(4531 * 8192 / c_int32(self.PWM).value)
				else:
					current_scale = 8192 + int(c_int32((4531 - self.PWM) * denominator * 32).value / c_int32((white * self.PWM) >> 1).value)
				self.FACTORY_SCALE = int(c_int32((white - dark) * current_scale + dark * 8192).value / self.FACTORY[selected])
				pwm = 4531
			if pwm < 0: return False
			self.PWM = pwm
			self.ADJUSTED = changed = True
			dprint('ROM exposure adjustment: PWM {}, white level {}.'.format(pwm, white))

		# Use dot-area/span feedback and per-buffer warmup.
		if self.ADJUSTED and geometry and not changed:
			measurements = geometry.values()
			area = sum(item[1] for item in measurements)
			count = sum(item[2] for item in measurements)
			span = sum(item[3] for item in measurements)
			tracks = sum(item[4] for item in measurements)
			if count > 22 and tracks:
				average_area = int(c_int32(area << 4).value / c_int32(count).value)
				average_span = ((int(c_int32(span * 602).value / c_int32(tracks).value) + 16384) >> 15) - 135
				if not self.WARMUP[buffer ^ 1]: self.DOT_LIMIT = (average_span * 3 + 144) >> 5
				factor_input = ((average_span - average_area) << self.WARMUP[buffer]) + 4 * self.FACTORS[buffer]
				self.FACTORS[buffer] = (13 * min(336, max(112, factor_input)) + 768) >> 6
				self.WARMUP[buffer] = max(0, self.WARMUP[buffer] - 1)
		factor = self.FACTORS[buffer]
		self.LAST_FACTOR = factor
		# Select a dark reference while limiting measured-dark changes.
		if not self.ADJUSTED:
			self.USED_DARK = self.DARK
		elif 3 * (measured_dark - self.DARK) <= 45:
			self.USED_DARK = measured_dark
		# Update regional references with factory fallback, Q7/Q13 scaling, and threshold clamping.
		for index, new in enumerate(maxima):
			fallback = False
			if self.ADJUSTED:
				old = self.REFERENCE[index]
				stable = old <= 2 * new and 5 * (new - old) <= old
				if not geometry or (changed and not stable):
					self.REFERENCE[index] = (self.DARK + (c_int32(self.FACTORY_SCALE * (self.FACTORY[index] - self.DARK) + 4096).value >> 13)) & 255
					fallback = True
				elif stable:
					self.REFERENCE[index] = new
			old = self.REFERENCE[index]
			if changed and geometry and not fallback:
				self.REFERENCE[index] = (self.DARK + (c_int32((old - self.DARK) * current_scale + 4096).value >> 13)) & 255
				threshold = c_int32((2 * self.USED_DARK + ((factor * (old - self.USED_DARK)) >> 6)) * current_scale + 8192).value >> 14
			else:
				threshold = self.USED_DARK + ((factor * (old - self.USED_DARK) + 64) >> 7)
			settings[4 + index] = min(127, max(0, threshold))
		struct.pack_into(">H", settings, 2, self.PWM)
		if changed:
			self.SETTLING = 2
			return self.UPDATE_GLOBAL
		if self.ADJUSTED: return self.UPDATE_THRESHOLDS
		return self.UPDATE_NONE


class EReaderDotcode:
	WIDTH, HEIGHT = 320, 246
	ROW_BYTES = WIDTH // 8
	FRAME_SIZE = ROW_BYTES * HEIGHT
	BLOCK_SIZE = 104
	RAW_HEADER_SIZE = 2
	PAYLOAD_SIZE = BLOCK_SIZE - RAW_HEADER_SIZE
	CODEWORD_SIZE = 64
	HEADER_SIZE = 48
	PARITY_SIZE = CODEWORD_SIZE - HEADER_SIZE
	REED_SOLOMON_ROOT = 0x78
	ALIGNMENT = frozenset((6, 8, 10, 12, 14, 16, 19, 21, 23, 25, 27, 29))
	# mGBA, BLOCK_HEADER: fixed 24-byte headers; GBACartEReaderScan: short/long strip addresses and block counts.
	# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L134-L137
	# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L389-L402
	LAYOUTS = {
		1:(18, 28, bytes.fromhex("00 02 00 01 40 10 00 1C 10 6F 40 DA 39 25 8E E0 7B B5 98 B6 5B CF 7F 72"), "Short"),
		25:(28, 44, bytes.fromhex("00 03 00 19 40 10 00 2C 0E 88 ED 82 50 67 FB D1 43 EE 03 C6 C6 2B 2C 93"), "Long"),
	}

	TABLES = None

	def __init__(self):
		self.GEOMETRY = {}
		self.DOT_LIMIT = 16
		self.ADDRESSES, self.BYTE_CODES, self.DATA_BITS = self.GetTables()

	def GetTables(self):
		if EReaderDotcode.TABLES is not None: return EReaderDotcode.TABLES
		addresses = {}
		for address in range(54):
			parity = address << 10
			for bit in range(15, 9, -1):
				if parity & (1 << bit): parity ^= 0x769 << (bit - 10)
			addresses[0x1000000 | (address << 10) | (parity ^ 0x3FF)] = address
		# Valid mappings match that table; invalid-symbol markers follow mGBA's EREADER_NYBBLE_LOOKUP.
		# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L51-L56
		demodulation = (0, 1, 2, -1, 4, 5, 6, -1, 8, 9, 10, -1, 12, 13, -1, -1, 15, 14, 3, -1, 11, -1, 7, -1) + (-1,) * 8
		byte_codes = tuple((high << 4) | low for high in demodulation for low in demodulation)
		# mGBA, EReaderScanSaveRaw: row-major payload positions and ten bits per decoded byte.
		# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L1600-L1628
		positions = [(x, y) for top, bottom, left, right in ((2, 5, 5, 31), (5, 31, 1, 35), (31, 34, 5, 31))
			for y in range(top, bottom) for x in range(left, right)]
		data_bits = tuple(tuple(positions[offset:offset + 10]) for offset in range(0, len(positions), 10))
		EReaderDotcode.TABLES = addresses, byte_codes, data_bits
		return EReaderDotcode.TABLES

	def GetLayoutByBlockCount(self, block_count):
		for start, layout in self.LAYOUTS.items():
			if layout[0] == block_count: return start, layout
		return None, None

	def GetLayoutByAddress(self, address):
		for start, layout in self.LAYOUTS.items():
			if start <= address < start + layout[0]: return start, layout
		return None, None

	def Decode(self, frame):
		# Polarity trials, run-based flood fill, geometric tolerances and voting are heuristics.
		if len(frame) != self.FRAME_SIZE: return False
		self.GEOMETRY = {}
		rows = [int.from_bytes(frame[offset:offset + self.ROW_BYTES], "big") for offset in range(0, len(frame), self.ROW_BYTES)]
		found = {}
		for inverted in (True, False):
			pixels = [row ^ ((1 << self.WIDTH) - 1) for row in rows] if inverted else rows
			remaining, markers = pixels.copy(), []
			for y in range(self.HEIGHT):
				while True:
					line = remaining[y]
					# Binary morphological erosion with a horizontal 5-pixel structuring element.
					seeds = line & (line >> 1) & (line >> 2) & (line >> 3) & (line >> 4)
					if not seeds: break
					stack = [(y, (seeds & -seeds).bit_length() - 1)]
					left, top, right, bottom, area = self.WIDTH, self.HEIGHT, 0, 0, 0
					# Scanline flood fill with 8-connectivity: collect connected horizontal pixel runs.
					while stack:
						row, x = stack.pop()
						line = remaining[row]
						if not (line >> x) & 1: continue
						start = (~line & ((1 << x) - 1)).bit_length()
						run = line >> x
						end = x + (run ^ (run + 1)).bit_length() - 1
						span = (1 << end) - (1 << start)
						remaining[row] &= ~span
						left, right = min(left, start), max(right, end)
						top, bottom = min(top, row), max(bottom, row + 1)
						area += end - start
						span |= (span << 1) | (span >> 1)
						for neighbor in (row - 1, row + 1):
							if not 0 <= neighbor < self.HEIGHT: continue
							overlaps = remaining[neighbor] & span
							while overlaps:
								first = overlaps & -overlaps
								x = first.bit_length() - 1
								stack.append((neighbor, x))
								run = overlaps >> x
								length = (run ^ (run + 1)).bit_length() - 1
								overlaps &= ~(first * ((1 << length) - 1))
					# Blob analysis (connected component analysis): filter by size, aspect ratio, and fill ratio.
					# mGBA comparison: EReaderScanFilterAnchors filters bounding boxes by size and aspect ratio.
					# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L1093-L1115
					width, height = right - left, bottom - top
					if left == 0 or top == 0 or right == self.WIDTH or bottom == self.HEIGHT: continue
					if not (5 <= min(width, height) and max(width, height) <= min(48, 1.6 * min(width, height))): continue
					if area * 4 >= width * height:
						markers.append((complex((left + right - 1) / 2, (top + bottom - 1) / 2), (width * height) ** 0.5))

			markers = nlargest(64, markers, key=lambda marker: marker[1])
			# Heuristic geometric pattern matching: group four anchors into an approximate square.
			# mGBA structural reference: EReaderScanCreateBlocks forms blocks from four neighboring anchors.
			# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L1195-L1253
			squares, seen = [], set()
			for origin, (a, size) in enumerate(markers):
				neighbors = []
				for index, (point, other_size) in enumerate(markers):
					if index == origin or not 0.55 <= other_size / size <= 1.8: continue
					distance = abs(point - a)
					if 4.5 <= 2 * distance / (size + other_size) <= 10.5:
						neighbors.append((index, point, distance))
				for (first, b, ab), (second, c, ac) in combinations(neighbors, 2):
					ratio = (c - a) / (b - a)
					if abs(ratio.real) > 0.25 or not 0.7 <= abs(ratio.imag) <= 1.43: continue
					opposites = []
					for corner, (point, other_size) in enumerate(markers):
						if corner in (origin, first, second) or not 0.55 <= other_size / size <= 1.8: continue
						opposites.append((abs(point - (b + c - a)), corner))
					if not opposites: continue
					distance, fourth = min(opposites)
					key = tuple(sorted((origin, first, second, fourth)))
					if distance <= 0.2 * min(ab, ac) and key not in seen:
						seen.add(key)
						squares.append((a, b, markers[fourth][0], c))

			for corners in squares:
				corners = sorted(corners, key=lambda point: point.imag)
				a, b = sorted(corners[:2], key=lambda point: point.real)
				d, c = sorted(corners[2:], key=lambda point: point.real)
				orientations = ((a, b, c, d), (c, d, a, b))
				votes = Counter()
				# The offset trials and five-point majority sample below are sampling heuristics.
				# Discrete grid search over sampling offsets, testing both block orientations.
				for offset_y, offset_x in product((0, -0.07, 0.07), repeat=2):
					block = None
					for a, b, c, d in orientations:
						# Bilinear mapping: transform logical grid coordinates into image coordinates.
						# mGBA, EReaderScanCreateBlocks: bilinear mapping of a 36x36 grid between four anchor centers.
						# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L1258-L1269
						x_step, y_step, warp = (b - a) / 35, (d - a) / 35, (a - b + c - d) / 35 ** 2

						def sample(x, y):
							x, y = x + offset_x, y + offset_y
							point = a + x * x_step + y * y_step + x * y * warp
							horizontal, vertical = (x_step + y * warp) * 0.2, (y_step + x * warp) * 0.2
							votes = 0
							# Nearest-neighbor sampling with a five-position majority vote.
							for position in (point, point + horizontal, point - horizontal, point + vertical, point - vertical):
								px, py = round(position.real), round(position.imag)
								if not (0 <= px < self.WIDTH and 0 <= py < self.HEIGHT): return -1
								votes += (pixels[py] >> px) & 1
							return int(votes >= 3)

						# Exact pattern matching: check the alignment pattern at positions 3..32 on both borders.
						# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L1380-L1397
						if any(sample(x, y) != (x in self.ALIGNMENT) for y in (0, 35) for x in range(3, 33)): continue
						# Lookup-table address decoding: sample each address edge starting at grid position five.
						addresses = []
						for x in (0, 35):
							value = 0
							for y in range(5, 30): value = (value << 1) | sample(x, y)
							addresses.append(self.ADDRESSES.get(value, -1))
						address = addresses[0]
						# The right edge address must equal the left address plus one.
						if addresses[1] != address + 1: continue
						start, layout = self.GetLayoutByAddress(address)
						if layout is None: continue
						if address not in self.GEOMETRY:
							self.GEOMETRY[address] = self.MeasureGeometry(pixels, (a, b, c, d))
						# mGBA, GBACartEReaderScan: two header bytes per block, cycling through the 24-byte header.
						# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L504-L508
						header_count = len(layout[2]) // self.RAW_HEADER_SIZE
						header_offset = ((address - start) % header_count) * self.RAW_HEADER_SIZE
						header = layout[2][header_offset:header_offset + self.RAW_HEADER_SIZE]
						# Lookup-table demodulation: decode ten-bit symbols into bytes in row order.
						# Reject invalid symbols and unexpected header bytes here.
						data = bytearray()
						for positions in self.DATA_BITS:
							value = 0
							for x, y in positions: value = (value << 1) | sample(x, y)
							value = self.BYTE_CODES[value] if value >= 0 else -1
							if value < 0 or (len(data) < self.RAW_HEADER_SIZE and value != header[len(data)]): break
							data.append(value)
						else:
							block = address, bytes(data)
						break
					if block is not None:
						votes[block] += 1
						if votes[block] >= 5: break
				if not votes: continue
				# Majority voting: require a strict majority among successfully decoded blocks.
				(address, data), count = votes.most_common(1)[0]
				if count * 2 <= sum(votes.values()): continue
				# Conflicting readings remain invalid for this frame.
				if address not in found:
					found[address] = data
				elif found[address] != data:
					found[address] = None
		return {address:data for address, data in found.items() if data is not None}

	def MeasureGeometry(self, pixels, corners):
		# Use a 7x5 dot window with bounds, area, and a Q7 centroid.
		tracks, areas = [], []
		a, b, c, d = corners
		for left, right in ((a, b), (d, c)):
			if left.real > right.real: left, right = right, left
			centers = []
			for x in sorted(self.ALIGNMENT):
				point = left + (right - left) * x / 35
				px, py = round(point.real), round(point.imag)
				if not (3 <= px < self.WIDTH - 3 and 2 <= py < self.HEIGHT - 3): continue
				window = [[(pixels[py + dy] >> (px + dx)) & 1 for dx in range(-3, 4)] for dy in range(-2, 3)]
				# Horizontal and vertical projection profiles: delimit the dot using empty rows and columns.
				columns = [sum(row[i] for row in window) for i in range(7)]
				rows = [sum(row) for row in window]
				x0 = next((i + 1 for i in range(2, -1, -1) if columns[i] == 0), 0)
				x1 = next((i for i in range(4, 7) if columns[i] == 0), 7)
				y0 = next((i + 1 for i in range(1, -1, -1) if rows[i] == 0), 0)
				y1 = next((i for i in range(3, 5) if rows[i] == 0), 5)
				dots = [dx - 3 for dy in range(y0, y1) for dx in range(x0, x1) if window[dy][dx]]
				if not dots: continue
				# Binary image moments: measure dot area and the horizontal centroid in Q7 fixed point.
				area = len(dots)
				if area < self.DOT_LIMIT: areas.append(area)
				center = ((area * px + sum(dots)) * 128 + area // 2) // area + 64
				centers.append((x, center))
			# Ordinary least-squares line fit: estimate the horizontal anchor span from all 12 dot centers.
			if len(centers) == 12:
				midpoint = round((left.real + right.real) * 64)
				# Use weights 2*i-25 and scale by 886/32768.
				span = (sum((center - midpoint) * (2 * (x - 5) - 25) for x, center in centers) * 886 + 16384) >> 15
				tracks.append(span)
		# Compare geometry positions with the horizontal image center.
		edge = min(((a, d), (b, c)), key=lambda edge: abs((edge[0].real + edge[1].real) / 2 - self.WIDTH // 2))
		return (tuple(sorted(int(point.imag) for point in edge)), sum(areas), len(areas), sum(tracks), len(tracks))


class EReaderStrip:
	BLOCK_NOT_SCANNED, BLOCK_UNCONFIRMED, BLOCK_CONFIRMED, BLOCK_UNREADABLE = range(4)
	BLOCK_SYMBOLS = " .!E"
	UNPROTECTED_CONFIRMATIONS = 5
	DATABASE_CONFIRMATIONS = 2

	def __init__(self, dotcode=None):
		self.DOTCODE = dotcode or EReaderDotcode()
		self.RS_CODEC = RSCodec(EReaderDotcode.PARITY_SIZE, nsize=EReaderDotcode.CODEWORD_SIZE,
			fcr=EReaderDotcode.REED_SOLOMON_ROOT, prim=0x187, generator=2)
		self.Reset()

	def Reset(self):
		self.START, self.COUNT, self.COLUMNS = None, 0, 0
		self.ERROR_CORRECTED_BLOCKS = 0
		self.HEADER, self.VOTES = b"", defaultdict(lambda: [Counter() for _ in range(EReaderDotcode.PAYLOAD_SIZE)])
		self.PAYLOAD_VOTES, self.CONFIRMED = defaultdict(Counter), set()
		self.UNPROTECTED_VOTES = defaultdict(Counter)

	# Reed-Solomon error correction over GF(256).
	def CorrectStrip(self, data, erasures, columns):
		"""Correct interleaved Reed-Solomon words in place. Return False if more readings are needed."""
		for column in range(columns):
			word = data[column:columns * EReaderDotcode.CODEWORD_SIZE:columns]
			missing_bytes = [index // columns for index in erasures if index % columns == column]
			if len(missing_bytes) > EReaderDotcode.PARITY_SIZE:
				return False
			# Load an interleaved word and complement its parity bytes.
			decoded = bytearray(value ^ (255 if index >= EReaderDotcode.HEADER_SIZE else 0) for index, value in enumerate(word))
			try:
				_, decoded, _ = self.RS_CODEC.decode(decoded, erase_pos=missing_bytes)
			except ReedSolomonError:
				return False
			data[column:columns * EReaderDotcode.CODEWORD_SIZE:columns] = bytes(value ^ (255 if index >= EReaderDotcode.HEADER_SIZE else 0) for index, value in enumerate(decoded))
		return True

	def CheckStrip(self, data, columns):
		protected_size = columns * EReaderDotcode.CODEWORD_SIZE
		if columns <= 0 or len(data) < protected_size: return False
		for column in range(columns):
			word = data[column:protected_size:columns]
			encoded = self.RS_CODEC.encode(word[:EReaderDotcode.HEADER_SIZE])
			parity = bytes(value ^ 255 for value in encoded[EReaderDotcode.HEADER_SIZE:])
			if word[EReaderDotcode.HEADER_SIZE:] != parity: return False
		return True

	def AddBlocks(self, blocks):
		for address, block in blocks.items():
			if self.START is None:
				start, layout = self.DOTCODE.GetLayoutByAddress(address)
				if layout is None: continue
				self.START = start
				self.COUNT, self.COLUMNS, self.HEADER = layout[:3]
			if not self.START <= address < self.START + self.COUNT: continue
			payload = block[EReaderDotcode.RAW_HEADER_SIZE:]
			self.PAYLOAD_VOTES[address][payload] += 1
			unprotected_start = max(0, self.COLUMNS * EReaderDotcode.CODEWORD_SIZE - (address - self.START) * EReaderDotcode.PAYLOAD_SIZE)
			if unprotected_start < len(payload):
				counts = self.UNPROTECTED_VOTES[address]
				counts[payload[unprotected_start:]] += 1
			elif self.PAYLOAD_VOTES[address][payload] >= 2:
				self.CONFIRMED.add(address)
			for counts, value in zip(self.VOTES[address], payload): counts[value] += 1
		self.UpdateUnprotectedStates()

	def UpdateUnprotectedStates(self, confirmations=UNPROTECTED_CONFIRMATIONS):
		for address, counts in self.UNPROTECTED_VOTES.items():
			total = max(counts.values())
			if total >= confirmations and total * 2 > sum(counts.values()):
				self.CONFIRMED.add(address)
			else:
				self.CONFIRMED.discard(address)
		return all(address in self.CONFIRMED for address in self.UNPROTECTED_VOTES)

	def GetBlockStates(self, error_correction=True):
		if self.START is None: return ()
		states = []
		for address in range(self.START, self.START + self.COUNT):
			if address not in self.VOTES:
				state = self.BLOCK_NOT_SCANNED
			elif not error_correction:
				counts = self.PAYLOAD_VOTES[address]
				total = max(counts.values())
				if total * 2 <= sum(counts.values()): state = self.BLOCK_UNREADABLE
				elif address in self.CONFIRMED: state = self.BLOCK_CONFIRMED
				else: state = self.BLOCK_UNCONFIRMED
			elif address in self.CONFIRMED:
				state = self.BLOCK_CONFIRMED
			elif any(max(counts.values()) * 2 <= sum(counts.values()) for counts in self.VOTES[address]):
				state = self.BLOCK_UNREADABLE
			else:
				state = self.BLOCK_UNCONFIRMED
			states.append(state)
		return tuple(states)

	def BuildRaw(self, database_lookup=None, error_correction=True):
		self.ERROR_CORRECTED_BLOCKS = 0
		confirmed = self.UpdateUnprotectedStates()
		if self.START is None or len(self.VOTES) < self.COUNT: return None
		data, erasures = bytearray(), []
		protected_size = self.COLUMNS * EReaderDotcode.CODEWORD_SIZE
		minimum = self.DATABASE_CONFIRMATIONS if database_lookup is not None else self.UNPROTECTED_CONFIRMATIONS
		for address in range(self.START, self.START + self.COUNT):
			if address not in self.VOTES:
				return None
			if address in self.UNPROTECTED_VOTES:
				counts = self.UNPROTECTED_VOTES[address]
				total = max(counts.values())
				if total < minimum or total * 2 <= sum(counts.values()): return None
			for counts in self.VOTES[address]:
				if not counts: return None
				value, total = counts.most_common(1)[0]
				majority = total * 2 > sum(counts.values())
				if len(data) >= protected_size:
					if not majority: return None
				elif not majority:
					erasures.append(len(data))
				data.append(value)
		if error_correction:
			uncorrected = bytes(data)
			if not self.CorrectStrip(data, erasures, self.COLUMNS): return None
			self.ERROR_CORRECTED_BLOCKS = sum(data[offset:offset + EReaderDotcode.PAYLOAD_SIZE] != uncorrected[offset:offset + EReaderDotcode.PAYLOAD_SIZE]
				for offset in range(0, len(data), EReaderDotcode.PAYLOAD_SIZE))
		elif erasures or not self.CheckStrip(data, self.COLUMNS):
			return None
		# mGBA: RAW blocks contain two cyclic header bytes followed by interleaved payload bytes.
		# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L504-L528
		# https://github.com/mgba-emu/mgba/blob/7bd39e238e8c30bfce32210ef5334e38b360826c/src/gba/cart/ereader.c#L1595-L1599
		header_bytes = EReaderDotcode.RAW_HEADER_SIZE
		header_count = len(self.HEADER) // header_bytes
		raw = b"".join(self.HEADER[(index % header_count) * header_bytes:(index % header_count) * header_bytes + header_bytes] + data[index * EReaderDotcode.PAYLOAD_SIZE:(index + 1) * EReaderDotcode.PAYLOAD_SIZE]
			for index in range(self.COUNT))
		if not confirmed:
			if database_lookup is None or database_lookup(raw) is None: return None
			self.UpdateUnprotectedStates(self.DATABASE_CONFIRMATIONS)
		if not error_correction and any(state != self.BLOCK_CONFIRMED for state in self.GetBlockStates(error_correction=False)):
			return None
		return raw


class EReader:
	ENGLISH_TITLE_CHARACTERS = {**{value:value for value in range(0x20, 0x7F)}, 0x7F:"é", 0x9B:"♂", 0x9C:"♀"}
	JAPANESE_TITLE_CHARACTERS = (
		"\u3000\u3000０１２３４５６７８９ぁあぃいぅうぇえぉおかがきぎくぐけげこご"
		"さざしじすずせぜそぞただちぢっつづてでとどなにぬねのはばぱひびぴ"
		"ふぶぷヘべぺほぼぽまみむめもゃやゅゆょよらりるれろゎわをんァアィ"
		"イゥウェエォオカガキギクグケゲコゴサザシジスズセゼソゾタダチヂッ"
		"ツヅテデトドナニヌネノハバパヒビピフブプヘベペホボポマミムメモャ"
		"ヤュユョヨラリルレロヮワンヴヵヶー♂♀、。！”％＆～？／＋－：．"
		"´ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ\u3000\u3000\u3000\u3000\u3000"
		"\u3000\u3000\u3000\u3000\u3000\u3000ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
	)

	TRANSFER_SIZE = 0x1000
	SETTINGS_SIZE = 52
	PACKET_HEADER_SIZE = 2
	FRAME_METADATA_SIZE = 58
	ROW_BYTES = EReaderDotcode.ROW_BYTES

	STATUS_OK = 1
	STATUS_ERROR = 2
	REPLY_STOP = 2
	REPLY_CONTINUE = 3
	REPLY_UPDATE_ALL = 4
	REPLY_UPDATE_BUFFER = 5
	DEFAULT_FACTORY_CALIBRATION = bytes.fromhex("282C3034343431302A2E32343434322E2A3034343434312E2B2F32343432302C2B2E30323232302E2B2E3031323332302C19C804000020007700000001000000")

	SESSION_VARIABLES = ("ADDRESS", "TRANSFER_SIZE", "AGB_READ_METHOD", "AGB_IRQ_ENABLED",
		"AUTO_POWEROFF_TIME", "AUTO_POWEROFF_ENABLED")

	FRAME_SIZE = EReaderDotcode.FRAME_SIZE

	BLOCK_NOT_SCANNED = EReaderStrip.BLOCK_NOT_SCANNED
	BLOCK_UNCONFIRMED = EReaderStrip.BLOCK_UNCONFIRMED
	BLOCK_CONFIRMED = EReaderStrip.BLOCK_CONFIRMED
	BLOCK_UNREADABLE = EReaderStrip.BLOCK_UNREADABLE
	BLOCK_SYMBOLS = EReaderStrip.BLOCK_SYMBOLS

	def __init__(self, conn=None):
		self.CONN = conn
		self.TRANSFER_SIZE = min(self.TRANSFER_SIZE, getattr(conn, "MAX_BUFFER_READ", self.TRANSFER_SIZE))
		self.ERROR = False
		self.SCANNING = False
		self.CANCEL_REQUESTED = False
		self.SYNCHRONIZED = True
		self.DOTCODE = EReaderDotcode()
		self.STRIP = EReaderStrip(self.DOTCODE)
		self.DUMP_INFO = None
		self.DATABASE = None

	def IsFactorySector(self, sector):
		if len(sector) != 0x1000 or sector[:20] != b"Card-E Reader 2001\0\0": return False
		checksum = sum(struct.unpack("<2048H", sector))
		return ((checksum & 0xFFFF) + (checksum >> 16)) & 0xFFFF == 0xFFFF

	def ExtractFactoryCalibration(self, data):
		if not isinstance(data, (bytes, bytearray, memoryview)): return False
		data = bytes(data)
		if len(data) == 64: return data if data[0x3C] & 3 == 1 else False
		for offset in range(0, len(data) - 0xFFF, 0x1000):
			sector = data[offset:offset + 0x1000]
			if not self.IsFactorySector(sector): continue
			# Calibration bytes start at sector offset 0x16.
			calibration = self.ExtractFactoryCalibration(sector[0x16:0x56])
			if calibration is not False: return calibration
		return False

	def Read(self, count, timeout=None):
		if self.CONN is None or self.CONN.DEVICE is None or not self.SYNCHRONIZED:
			self.SYNCHRONIZED = False
			self.ERROR = self.ERROR or __("Could not read from the device.")
			return False
		device = self.CONN.DEVICE
		previous_timeout = device.timeout
		data = False
		try:
			if timeout is not None: device.timeout = timeout
			data = self.CONN._read(count)
		except (SerialException, OSError):
			dprint(traceback.format_exc())
		finally:
			if timeout is not None:
				try:
					device.timeout = previous_timeout
				except (SerialException, OSError):
					dprint(traceback.format_exc())
					data = False
		if data is not False and data is not None:
			data = bytes([data]) if isinstance(data, int) else bytes(data)
			if len(data) == count: return data
		dprint("Incomplete device response:", data, "expected bytes:", count)
		self.SYNCHRONIZED = False
		self.ERROR = self.ERROR or __("Could not read from the device.")
		return False

	def Write(self, data, wait=False):
		if self.CONN is None or self.CONN.DEVICE is None or not self.SYNCHRONIZED:
			self.SYNCHRONIZED = False
			self.ERROR = self.ERROR or __("Could not write to the device.")
			return False
		data = bytearray([data]) if isinstance(data, int) else bytearray(data)
		try:
			result = self.CONN._write(data)
		except (SerialException, OSError):
			dprint(traceback.format_exc())
			result = False
		if result is False:
			self.SYNCHRONIZED = False
			self.ERROR = self.ERROR or __("Could not write to the device.")
			return False
		return self.Expect(bytes([self.STATUS_OK])) if wait else True

	def Expect(self, value, timeout=None):
		value = bytes(value)
		data = self.Read(len(value), timeout)
		if data is False: return False
		if data == value: return True
		dprint("Unexpected firmware response:", data, "expected:", value)
		self.SYNCHRONIZED = False
		self.ERROR = self.ERROR or __("Unexpected firmware response.")
		return False

	def InvalidateConnection(self):
		self.SYNCHRONIZED = False
		try:
			if self.CONN.DEVICE is not None: self.CONN.DEVICE.close()
		except (SerialException, OSError):
			dprint(traceback.format_exc())
		finally:
			self.CONN.DEVICE = None
			self.CONN.MODE = None
			self.CONN.ERROR = True

	def SetFirmwareVariables(self, values):
		for key, value in values.items():
			if self.CONN.ERROR: break
			if self.CONN._set_fw_variable(key, value) is False: break
		else:
			if not self.CONN.ERROR: return True
		self.SYNCHRONIZED = False
		self.ERROR = self.ERROR or __("Could not write to the device.")
		return False

	def RunScan(self, factory_calibration=None, control=None, on_preview=None, on_status=None, on_warning=None):
		self.DUMP_INFO = None
		self.ERROR = False
		if self.CANCEL_REQUESTED: return False
		if self.CONN is None or self.CONN.DEVICE is None or not self.SYNCHRONIZED:
			self.SYNCHRONIZED = False
			self.ERROR = __("A connected device is required.")
			return False
		if (self.CONN.FW or {}).get("fw_ver", 0) < 16 or not self.CONN.IsClkConnected():
			self.ERROR = __("The e-Reader Dot Code Dumper requires firmware L16 or newer and a connected CLK pin.")
			return False
		started = time.monotonic()
		timestamp = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
		device = self.CONN.DEVICE
		previous_timeout = device.timeout
		previous_device_timeout = self.CONN.DEVICE_TIMEOUT
		previous_skip_powercycle = self.CONN.SKIP_POWERCYCLE
		has_write_timeout = hasattr(device, "write_timeout")
		previous_write_timeout = device.write_timeout if has_write_timeout else None
		variables = {}
		raw = False
		try:
			self.CONN.SetTimeout(6)
			if has_write_timeout: device.write_timeout = 5
			for key in self.SESSION_VARIABLES:
				value = self.CONN._get_fw_variable(key)
				if value is False:
					self.SYNCHRONIZED = False
					self.ERROR = self.ERROR or __("Could not read from the device.")
					return False
				variables[key] = value
			if not self.SetFirmwareVariables({"AUTO_POWEROFF_ENABLED":0, "AUTO_POWEROFF_TIME":0}): return False
			self.CONN.SKIP_POWERCYCLE = True
			self.CONN.SetMode("AGB")
			if not self.SetFirmwareVariables({"AGB_IRQ_ENABLED":0, "AGB_READ_METHOD":0}): return False
			prepared = self.Prepare(factory_calibration, control, on_warning)
			if prepared is False or self.CANCEL_REQUESTED: return False
			self.CONN.CartPowerCycle()
			if not self.SetFirmwareVariables({"TRANSFER_SIZE":self.TRANSFER_SIZE}): return False
			raw = self.Scan(prepared, control, on_preview, on_status)
			if raw is not False:
				self.DUMP_INFO.update(timestamp=timestamp, time_elapsed=time.monotonic() - started)
		except (SerialException, OSError):
			dprint(traceback.format_exc())
			self.SYNCHRONIZED = False
			self.ERROR = self.ERROR or __("The connection to the device was lost. Please reconnect the device.")
		finally:
			self.CONN.SKIP_POWERCYCLE = previous_skip_powercycle
			try:
				if variables and self.SYNCHRONIZED and not self.CONN.ERROR:
					self.CONN.CartPowerOff()
					self.SetFirmwareVariables(variables)
				if self.SYNCHRONIZED and not self.CONN.ERROR:
					self.CONN.SetTimeout(previous_device_timeout)
					device.timeout = previous_timeout
					if has_write_timeout: device.write_timeout = previous_write_timeout
			except (SerialException, OSError):
				dprint(traceback.format_exc())
				self.SYNCHRONIZED = False
				self.ERROR = self.ERROR or __("Could not restore the device settings.")
			if not self.SYNCHRONIZED or self.CONN.ERROR:
				self.InvalidateConnection()
		return raw if self.SYNCHRONIZED and not self.ERROR else False

	def GetDatabaseEntry(self, raw_data):
		from .app import AppContext
		if self.DATABASE is None:
			self.DATABASE = {}
			try:
				with open(os.path.join(AppContext.CONFIG_PATH, "db_DOT.json"), encoding="utf-8") as file:
					database = json.load(file)
				if isinstance(database, dict): self.DATABASE = database
			except (OSError, ValueError) as e:
				dprint("Could not load e-Reader database: {}".format(e))
		db = self.DATABASE.get(hashlib.sha1(raw_data).hexdigest())
		if isinstance(db, dict) and db.get("rc") == zlib.crc32(raw_data) and db.get("rs") == len(raw_data):
			return db
		return None

	def GetFileName(self, raw_data):
		db = self.GetDatabaseEntry(raw_data)
		if db is not None and db.get("gn"):
			title = "{} {}".format(db["gn"], db.get("ne", "")).strip()
		else:
			info = self.ParseRaw(raw_data) or {}
			title = info.get("program_title") or "Untitled"
			if info.get("strip_count", 0) > 1:
				title += " (Strip {} of {})".format(info["strip_number"], info["strip_count"])
		title = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", title).strip().rstrip(". ") or "Untitled"
		return title + ".raw"

	def SaveRaw(self, raw_data, path, overwrite=False):
		if not path: return False
		data = bytes(raw_data)
		if self.ParseRaw(data) is False: return False
		path = os.path.abspath(os.fspath(path))
		if not overwrite:
			with open(path, "xb") as file: file.write(data)
			return True
		# Do not truncate an existing dump if a replacement cannot be written in full.
		fd, temporary = tempfile.mkstemp(prefix=".ereader-", suffix=".tmp", dir=os.path.dirname(path))
		try:
			with os.fdopen(fd, "wb") as file: file.write(data)
			os.replace(temporary, path)
		finally:
			if os.path.exists(temporary): os.remove(temporary)
		return True

	def GetDumpReport(self, raw_data, path):
		from .DumpReport import DumpReport
		if self.DUMP_INFO is None: return False
		info = self.ParseRaw(raw_data)
		if info is False: return False
		return DumpReport.generate_ereader(self.DUMP_INFO, self.CONN, bytes(raw_data), path, info)

	def SaveDumpReport(self, raw_data, path):
		report = self.GetDumpReport(raw_data, path)
		if report is False: return False
		target = os.path.splitext(os.fspath(path))[0] + ".txt"
		if os.path.splitext(os.fspath(path))[1].lower() == ".txt": target = os.fspath(path) + ".txt"
		with open(target, "w", encoding="utf-8-sig", newline="") as file: file.write(report)
		return target

	def DecodeTitle(self, data, region, extended=False):
		data = bytes(data).split(b"\0", 1)[0]
		if region == 1:
			return charmap_decode(data, "replace", self.ENGLISH_TITLE_CHARACTERS)[0]
		if extended:
			return data.decode("cp932", errors="replace")
		return charmap_decode(data, "replace", self.JAPANESE_TITLE_CHARACTERS)[0]

	def DecodeStats(self, data):
		value = int.from_bytes(data, "little")
		if value & 0x800000: return None, None
		number = value >> 7 & 0x7F
		number = "{:02d}".format(number + 1) if number < 99 else "{}{}".format(chr(ord("A") + (number - 99) // 10), (number - 99) % 10)
		prefix = (tuple("ABCDEFGHIJKLMNOPQRSTUVWXYZ-_") + ("HP", ".", "ID", ":"))[value >> 14 & 0x1F]
		suffix = "abcdefg#"[value >> 4 & 7]
		return (value & 0xF) * 10 or None, "{}-{}-{}".format(prefix, number, suffix)

	def DecodeNativeTitle(self, data, region):
		field = bytes(data[:33])
		title, separator, padding = field.partition(b"\0")
		if not title or (separator and any(padding)): return None
		if region == 1:
			if any(value not in self.ENGLISH_TITLE_CHARACTERS for value in title): return None
			return self.DecodeTitle(title, region)
		for encoding in ("cp932", "utf-8"):
			try:
				decoded = title.decode(encoding)
			except UnicodeDecodeError:
				continue
			if all(ord(character) >= 0x20 and ord(character) != 0x7F for character in decoded): return decoded
		return None

	def ParseRaw(self, raw_data):
		data = bytes(raw_data)
		blocks = len(data) // EReaderDotcode.BLOCK_SIZE
		_, layout = self.DOTCODE.GetLayoutByBlockCount(blocks)
		if len(data) != blocks * EReaderDotcode.BLOCK_SIZE or layout is None:
			return False
		interleave, strip_type = layout[1], layout[3]
		payload = b"".join(data[offset + EReaderDotcode.RAW_HEADER_SIZE:offset + EReaderDotcode.BLOCK_SIZE] for offset in range(0, len(data), EReaderDotcode.BLOCK_SIZE))
		fragments = [payload[offset:interleave * EReaderDotcode.HEADER_SIZE:interleave] for offset in range(interleave)]
		header = fragments[0]
		if header[:3] != b"\0\x30\x01": return False
		contents = b"".join(fragments[1:])
		# GBATEK, GBA Cart e-Reader Data Format: checksums cover the deinterleaved data without RS parity.
		# https://problemkaputt.de/gbatek-gba-cart-e-reader-data-format.htm
		data_checksum = ~sum(value for value, in struct.iter_unpack(">H", contents)) & 0xFFFF
		if int.from_bytes(header[0x13:0x15], "big") != data_checksum:
			return False
		header_checksum = reduce(xor, header[0x0C:0x0E] + header[0x10:0x12] + header[0x26:0x2E], 0)
		if header[0x2E] != header_checksum:
			return False
		global_checksum = sum(header[:0x2F]) + sum(reduce(xor, fragment, 0) for fragment in fragments[1:])
		if header[0x2F] != (~global_checksum & 0xFF):
			return False
		if not self.STRIP.CheckStrip(payload, interleave): return False
		region_type = int.from_bytes(header[0x0C:0x0E], "little")
		region_code = region_type >> 8 & 0xF
		region = {0:"Japanese", 1:"English", 2:"Japanese (Plus)"}.get(region_code, "Unknown ({:X})".format(region_code))
		strip_format = ((header[3] & 1) << 4) | (region_type >> 4 & 0xF)
		size_info = int.from_bytes(header[0x26:0x2A], "little")
		flags = int.from_bytes(header[0x2A:0x2E], "little")
		application = strip_format in (2, 3, 4, 5, 0xE, 0x1E)
		strip_number = strip_count = 1
		strips = []
		program_title = program_size = None
		program_type = "NES/6502" if application and flags & 4 else None
		if application:
			strip_number, strip_count = size_info >> 1 & 0xF, size_info >> 5 & 0xF
			extended = strip_format in (0xE, 0x1E)
			title_size = 33 if extended else 17
			program_title = self.DecodeTitle(contents[:title_size], region_code, extended)
			offset = title_size
			if not flags & 2:
				strip_title_size = 33 if extended else 21
				for number in range(1, strip_count + 1):
					entry = contents[offset:offset + strip_title_size]
					offset += strip_title_size
					if len(entry) != strip_title_size: break
					title = self.DecodeTitle(entry if extended else entry[3:], region_code, extended)
					hp = strip_id = None
					if not extended: hp, strip_id = self.DecodeStats(entry[:3])
					strips.append({"strip_number":number, "title":title, "hp":hp, "id":strip_id})
			if strip_number == 1 and offset + 2 <= len(contents):
				program_size = int.from_bytes(contents[offset:offset + 2], "little")
				if not flags & 4:
					program_type = "ARM/THUMB" if contents[offset + 2:offset + 6] == bytes(4) else "Z80"
		elif 0x10 <= strip_format <= 0x1D:
			program_type = "e-Viewer"
			program_title = self.DecodeTitle(contents[1:20], region_code)
			if region_code in (0, 2) and header[0x27:0x29] == b"\x20\x01" and flags == 0:
				title = contents[:20].split(b"\0", 1)[0]
				if title and len(title) % 2 == 0 and all((0x81 <= title[i] <= 0x9F or 0xE0 <= title[i] <= 0xFC) and 0x40 <= title[i + 1] <= 0xFC and title[i + 1] != 0x7F for i in range(0, len(title), 2)):
					try:
						program_title = title.decode("cp932")
					except UnicodeDecodeError:
						pass
			stats = (int.from_bytes(header[0x10:0x12], "big") << 4) | (header[0x27] >> 1 & 0xF)
			hp, strip_id = self.DecodeStats(stats.to_bytes(3, "little"))
			strips.append({"strip_number":1, "title":program_title, "hp":hp, "id":strip_id})
		else:
			if strip_format in (0x0F, 0x1F): program_title = self.DecodeNativeTitle(contents, region_code)
			program_type = {
				6:"Recognize", 7:"Recognize",
				8:"Construction Escape", 9:"Construction Escape",
				10:"Construction Action", 11:"Construction Action",
				12:"Construction Melody Box", 13:"Construction Melody Box",
				15:"Game-specific data", 31:"Game-specific data",
			}.get(strip_format)
		return {
			"region":region,
			"strip_format":strip_format,
			"strip_number":strip_number,
			"strip_count":strip_count,
			"strips":strips,
			"strip_type":"{} Strip ({} blocks)".format(strip_type, blocks),
			"data_size":size_info >> 9 & 0x7FFF,
			"flags":flags,
			"program_title":program_title,
			"program_type":program_type,
			"program_size":program_size,
			"data_checksum":data_checksum,
			"id_string":header[0x1A:0x22].split(b"\0", 1)[0].decode("ascii", errors="replace"),
			"header_checksum":header[0x2E],
			"global_checksum":header[0x2F],
			"save_permission":bool(flags & 1),
		}

	def CalibrateBrightness(self, brightness, vertical):
		if not self.Write(bytes([self.CONN.DEVICE_CMD["AGB_EREADER_CALIBRATE"], brightness, vertical])): return False
		status = self.Read(1, 30)
		if status is False: return False
		if status[0] != self.STATUS_OK:
			self.SYNCHRONIZED = status[0] == self.STATUS_ERROR
			self.ERROR = __("Could not calibrate camera brightness.")
			return False
		brightness = self.Read(1)
		if brightness is False: return False
		if brightness[0] <= 63: return brightness[0]
		self.SYNCHRONIZED = False
		self.ERROR = __("Invalid calibrated brightness value.")
		return False

	def StartScan(self, settings, threshold_tag):
		if len(settings) != self.SETTINGS_SIZE: return False
		return self.Write(bytes([self.CONN.DEVICE_CMD["AGB_EREADER_SCAN"]]) + bytes(settings) + struct.pack(">I", threshold_tag), wait=True)

	def SendReply(self, reply, data=b"", threshold_tag=None):
		if threshold_tag is not None: data = bytes(data) + struct.pack(">I", threshold_tag)
		return self.Write(bytes([reply]) + bytes(data))

	def Cancel(self):
		self.CANCEL_REQUESTED = True

	def ReadFactoryCalibration(self, on_warning=None):
		factory = self.ExtractFactoryCalibration(self.CONN.INFO.get("ereader_calibration"))
		if factory is not False: return factory
		message = __("No valid e-Reader factory calibration found.") + " " + __("Default calibration values will be used.")
		dprint(message)
		if on_warning is not None: on_warning(message)
		return self.DEFAULT_FACTORY_CALIBRATION

	def Prepare(self, factory_calibration=None, control=None, on_warning=None):
		control = control or ScanControl()
		if self.CANCEL_REQUESTED: return False
		factory = self.ExtractFactoryCalibration(factory_calibration) if factory_calibration is not None else self.ReadFactoryCalibration(on_warning)
		if factory is False:
			self.ERROR = __("No valid e-Reader factory calibration found.")
			return False
		options = control.Get()
		manual = {key:options[key] for key in ScanControl.RANGES} if not options["auto_calibration"] else {}
		settings = control.FactorySettings(factory, **manual)
		calibration = EReaderCalibration(factory, settings, auto=options["auto_calibration"])
		if not calibration.AUTO: calibration.FACTORS = [options["threshold_factor"]] * 2
		if self.CANCEL_REQUESTED: return False
		if calibration.AUTO:
			brightness = self.CalibrateBrightness(settings[0], settings[1])
			if brightness is False: return False
			settings[0] = brightness
		if self.CANCEL_REQUESTED: return False
		return factory, settings, calibration, options

	def ValidateScanPacket(self, packet, frame_size, threshold_tags):
		packet_size = int.from_bytes(packet[:self.PACKET_HEADER_SIZE], "big")
		if not self.PACKET_HEADER_SIZE < packet_size <= self.TRANSFER_SIZE or len(packet) != packet_size:
			return False
		size = packet_size - self.PACKET_HEADER_SIZE
		frame_end = size == self.FRAME_SIZE - frame_size + self.FRAME_METADATA_SIZE
		if frame_end: size -= self.FRAME_METADATA_SIZE
		end = frame_size + size
		if (size <= 0 or size % self.ROW_BYTES or end > self.FRAME_SIZE
				or (end == self.FRAME_SIZE and not frame_end)):
			return False
		if not frame_end: return size, None
		statistics, buffer, brightness, vertical, pwm, threshold_tag = struct.unpack_from(
			">49sBBBHI", packet, self.PACKET_HEADER_SIZE + size)
		if (any(value > 127 for value in statistics) or buffer not in (0, 1)
				or brightness > 63 or not 7 <= vertical <= 61 or pwm > 4531 or threshold_tag not in threshold_tags):
			return False
		return size, {"statistics":statistics, "buffer":buffer, "brightness":brightness,
			"vertical_offset":vertical, "pwm":pwm, "threshold_tag":threshold_tag}

	def StopStream(self):
		if not self.SCANNING: return self.SYNCHRONIZED
		self.SCANNING = False
		if not self.SYNCHRONIZED: return False
		dprint("Stopping e-Reader scan stream")
		return self.SendReply(self.REPLY_STOP) and self.Expect(bytes([self.STATUS_OK]))

	def Scan(self, prepared, control=None, on_preview=None, on_status=None):
		control = control or ScanControl()
		factory, settings, calibration, options = prepared
		settings = bytearray(settings)
		self.STRIP.Reset()
		self.DOTCODE.GEOMETRY = {}

		initial_settings = bytearray(settings)
		initial_settings[2:4] = b"\0\0"
		threshold_tags = {1:(bytes(initial_settings[4:]), options["threshold_factor"])}
		next_tag = 2
		active_settings = None
		active_factor = None
		current_blocks = ()
		frame = bytearray()
		completed, frames = 0, 0
		frame_started = None
		used_settings = defaultdict(set)

		def Emit(status):
			if on_status is None: return
			diagnostics = active_settings if active_settings is not None else settings
			states = self.STRIP.GetBlockStates(error_correction=options["error_correction"])
			on_status({"status":status, "frames":frames,
				"framerate":(frames - 1) / max(time.monotonic() - frame_started, 1e-9) if frames > 1 else 0.0,
				"block_count":self.STRIP.COUNT, "block_states":states,
				"current_blocks":current_blocks,
				"blocks_read":sum(state != self.BLOCK_NOT_SCANNED for state in states),
				"blocks_confirmed":states.count(self.BLOCK_CONFIRMED), "blocks_unconfirmed":states.count(self.BLOCK_UNCONFIRMED),
				"blocks_unreadable":states.count(self.BLOCK_UNREADABLE), "auto_calibration":options["auto_calibration"],
				"sensor_brightness":diagnostics[0], "vertical_offset":diagnostics[1],
				"pwm":int.from_bytes(diagnostics[2:4], "big"), "active_factor":active_factor})

		def ManualSettings(base, changed, force=False):
			desired = bytearray(base)
			for key, offset in (("sensor_brightness", 0), ("vertical_offset", 1)):
				if force or key in changed:
					value = options[key]
					if value is not None: desired[offset] = value
			if force or "pwm" in changed:
				value = options["pwm"]
				if value is not None: struct.pack_into(">H", desired, 2, value)
			if force or "threshold_factor" in changed:
				desired[4:] = control.FactorySettings(factory, threshold_factor=options["threshold_factor"])[4:]
			calibration.FACTORS = [options["threshold_factor"]] * 2
			calibration.PWM = int.from_bytes(desired[2:4], "big")
			return desired

		def ReplyScan(kind, payload=None, factor=None):
			nonlocal next_tag
			if self.CANCEL_REQUESTED: return False
			if kind == self.REPLY_CONTINUE:
				return self.SendReply(kind)
			thresholds = payload[4:] if kind == self.REPLY_UPDATE_ALL else payload
			threshold_tags[next_tag] = (bytes(thresholds), factor)
			dprint("Updating e-Reader scan settings: reply=0x{:02X}, payload=0x{:X} bytes, threshold_tag={:d}, threshold_factor={}".format(
				kind, len(payload), next_tag, factor))
			if not self.SendReply(kind, payload, next_tag): return False
			next_tag += 1
			return True

		try:
			dprint("Starting e-Reader scan: frame size=0x{:X} bytes, maximum packet size=0x{:X} bytes, auto_calibration={}".format(
				self.FRAME_SIZE, self.TRANSFER_SIZE, calibration.AUTO))
			if not self.StartScan(initial_settings, 1): return False
			self.SCANNING = True
			Emit(__("Calibrating...") if calibration.AUTO else __("Starting..."))

			while True:
				packet = self.Read(self.PACKET_HEADER_SIZE)
				if packet is False: return False
				packet_size = int.from_bytes(packet, "big")
				if self.PACKET_HEADER_SIZE < packet_size <= self.TRANSFER_SIZE:
					dprint("Reading 0x{:X} bytes from e-Reader scan stream for frame {:d} at 0x{:X} (packet size=0x{:X} bytes, header=0x{:X} bytes)".format(
						packet_size - self.PACKET_HEADER_SIZE, completed + 1, len(frame), packet_size, self.PACKET_HEADER_SIZE))
					payload = self.Read(packet_size - self.PACKET_HEADER_SIZE)
					if payload is False: return False
					packet += payload
				validated = self.ValidateScanPacket(packet, len(frame), threshold_tags)
				if validated is False:
					dprint("Invalid scan packet:", packet)
					self.SYNCHRONIZED = False
					self.ERROR = __("Received invalid scan data.")
					return False
				size, metadata = validated
				frame.extend(packet[self.PACKET_HEADER_SIZE:self.PACKET_HEADER_SIZE + size])

				if self.CANCEL_REQUESTED: return False

				if metadata is None:
					if not self.SendReply(self.REPLY_CONTINUE): return False
					continue

				image = bytes(frame)
				frame.clear()
				active_thresholds, active_factor = threshold_tags[metadata["threshold_tag"]]
				active_settings = bytearray(struct.pack(">BBH", metadata["brightness"], metadata["vertical_offset"], metadata["pwm"]) + active_thresholds)
				statistics = metadata["statistics"]
				buffer = metadata["buffer"]
				dprint("Received e-Reader frame {:d}: 0x{:X} image bytes, buffer={:d}, brightness={:d}, vertical_offset={:d}, pwm={:d}, threshold_tag={:d}".format(
					completed + 1, len(image), buffer, metadata["brightness"], metadata["vertical_offset"], metadata["pwm"], metadata["threshold_tag"]))
				if on_preview is not None: on_preview(image)
				completed += 1

				previous_options = options
				options = control.Get()
				changed = {key for key in options if options[key] != previous_options[key]}
				force_manual_sync = False
				if "auto_calibration" in changed:
					calibration.AUTO = options["auto_calibration"]
					if not calibration.AUTO:
						settings[:] = active_settings
						force_manual_sync = True
					elif not calibration.BOOTSTRAP_READY:
						settings[:] = active_settings
						calibration.PWM = metadata["pwm"]
						calibration.SETTLING = 0

				reply = self.REPLY_CONTINUE
				reply_payload = None
				reply_factor = active_factor if active_factor is not None else options["threshold_factor"]

				if not calibration.AUTO and (force_manual_sync or changed.intersection(ScanControl.RANGES)):
					settings[:] = ManualSettings(active_settings, changed, force=force_manual_sync)
					reply = self.REPLY_UPDATE_ALL
					reply_payload = bytes(settings)
					reply_factor = options["threshold_factor"]

				before = bytes(settings) if completed <= 4 else active_settings
				blocks, geometry = {}, {}
				if completed > 4:
					if frame_started is None: frame_started = time.monotonic()
					frames += 1
					self.DOTCODE.DOT_LIMIT = calibration.DOT_LIMIT
					current_blocks = ()
					blocks = self.DOTCODE.Decode(image)
					if blocks is False: return False
					geometry = self.DOTCODE.GEOMETRY
				settling = calibration.SETTLING > 0
				scope = calibration.Update(statistics, geometry, buffer, settings, blocks)
				if scope is False:
					self.ERROR = __("Could not calibrate the camera.")
					return False
				generated = bytes(settings)

				if reply == self.REPLY_CONTINUE:
					if completed == 1:
						reply = self.REPLY_UPDATE_ALL
						reply_payload = generated
						reply_factor = options["threshold_factor"]
					elif scope == EReaderCalibration.UPDATE_GLOBAL and generated != before:
						reply = self.REPLY_UPDATE_ALL
						reply_payload = generated
						reply_factor = calibration.LAST_FACTOR if calibration.LAST_FACTOR is not None else reply_factor
					elif completed > 4 and scope == EReaderCalibration.UPDATE_THRESHOLDS:
						factor = calibration.LAST_FACTOR if calibration.LAST_FACTOR is not None else reply_factor
						if generated[4:] != active_thresholds or factor != active_factor:
							reply = self.REPLY_UPDATE_BUFFER
							reply_payload = generated[4:]
							reply_factor = factor

				if completed <= 4 or (calibration.AUTO and (settling or not calibration.BOOTSTRAP_READY)):
					Emit(__("Calibrating...") if calibration.AUTO else __("Starting..."))
					if not ReplyScan(reply, reply_payload, reply_factor): return False
					continue

				self.STRIP.AddBlocks(blocks)
				if blocks:
					for key, value in (("auto_calibration", options["auto_calibration"] or options["auto_calibration_reused"]),
						("sensor_brightness", active_settings[0]), ("vertical_offset", active_settings[1]),
						("pwm", int.from_bytes(active_settings[2:4], "big")), ("threshold_factor", active_factor)):
						if value is not None: used_settings[key].add(value)
				if self.STRIP.START is not None:
					current_blocks = tuple(address - self.STRIP.START for address in blocks
						if self.STRIP.START <= address < self.STRIP.START + self.STRIP.COUNT)
				Emit(__("Scanning..."))
				if (self.STRIP.START is None or len(self.STRIP.VOTES) < self.STRIP.COUNT
						or (calibration.AUTO and not calibration.ADJUSTED)):
					if not ReplyScan(reply, reply_payload, reply_factor): return False
					continue

				raw = self.STRIP.BuildRaw(self.GetDatabaseEntry, error_correction=options["error_correction"])
				if raw is None or self.ParseRaw(raw) is False:
					if not ReplyScan(reply, reply_payload, reply_factor): return False
					continue
				if self.CANCEL_REQUESTED: return False
				if not self.StopStream(): return False
				used_settings["error_correction"].add(options["error_correction"])
				self.DUMP_INFO = {"factory":bytes(factory), "transfer_size":self.TRANSFER_SIZE,
					"block_states":self.STRIP.GetBlockStates(error_correction=options["error_correction"]),
					"blocks_error_corrected":self.STRIP.ERROR_CORRECTED_BLOCKS,
					"settings":{key:tuple(sorted(values)) for key, values in used_settings.items()}}
				Emit(__("Complete."))
				dprint("Completed e-Reader scan: 0x{:X} raw bytes, {:d} block(s), {:d} received frame(s), {:d} decoded frame(s)".format(
					len(raw), self.STRIP.COUNT, completed, frames))
				return raw

		finally:
			self.StopStream()

class EReaderScanWorker(threading.Thread):
	"""Run a scan without importing Qt. Callbacks execute on this worker thread."""
	def __init__(self, conn, factory=None, control=None, on_preview=None, on_status=None,
		on_completed=None, on_stopped=None, on_failed=None, on_finished=None, on_warning=None):
		threading.Thread.__init__(self, name="EReaderScan")
		self.READER = EReader(conn)
		self.FACTORY = factory
		self.CONTROL = control or ScanControl()
		self.CALLBACKS = {"on_preview":on_preview, "on_status":on_status, "on_warning":on_warning}
		self.ON_COMPLETED, self.ON_STOPPED = on_completed, on_stopped
		self.ON_FAILED, self.ON_FINISHED = on_failed, on_finished

	def run(self):
		try:
			try:
				raw = self.READER.RunScan(self.FACTORY, self.CONTROL, **self.CALLBACKS)
			except Exception as e:
				dprint(traceback.format_exc())
				self.READER.ERROR = str(e)
				raw = False
			if raw is not False:
				if self.ON_COMPLETED is not None: self.ON_COMPLETED(raw)
			elif self.READER.CANCEL_REQUESTED and not self.READER.ERROR and self.READER.SYNCHRONIZED:
				if self.ON_STOPPED is not None: self.ON_STOPPED()
			elif self.ON_FAILED is not None:
				message = self.READER.ERROR or __("The scan could not be completed.")
				self.ON_FAILED(message, not self.READER.SYNCHRONIZED)
		finally:
			if self.ON_FINISHED is not None: self.ON_FINISHED()
