# -*- coding: utf-8 -*-
# FlashGBX
# Author: Lesserkuma (github.com/Lesserkuma)

import time, threading, statistics, random

class Progress():
	MUTEX = threading.Lock()
	PROGRESS = {}
	UPDATER = None
	WAITER = None

	def __init__(self, updater, waiter):
		self.UPDATER = updater
		self.WAITER = waiter

	def _is_outlier(self, speeds, new_number, threshold):
		if not speeds: return False
		mean = sum(speeds) / len(speeds)
		std_deviation = (sum((x - mean) ** 2 for x in speeds) / len(speeds)) ** 0.5
		lower_bound = mean - threshold * std_deviation
		upper_bound = mean + threshold * std_deviation
		if new_number < lower_bound or new_number > upper_bound:
			return True
		else:
			return False

	def SetProgress(self, args):
		self.MUTEX.acquire(1)
		try:
			if not "method" in self.PROGRESS: self.PROGRESS = {}
			now = time.perf_counter()
			emit_now = time.monotonic()
			if args["action"] == "USER_ACTION":
				self.WAITER(args)

			elif args["action"] == "INITIALIZE":
				self.PROGRESS["action"] = args["action"]
				self.PROGRESS["method"] = args["method"]
				if "voltage" in args:
					self.PROGRESS["voltage"] = args["voltage"]
				elif "voltage" in self.PROGRESS:
					del self.PROGRESS["voltage"]
				if "flash_offset" in args:
					self.PROGRESS["flash_offset"] = args["flash_offset"]
				else:
					self.PROGRESS["flash_offset"] = 0
				if "size" in args:
					self.PROGRESS["size"] = args["size"] - self.PROGRESS["flash_offset"]
				else:
					self.PROGRESS["size"] = 0
				if "pos" in args:
					self.PROGRESS["pos"] = args["pos"] - self.PROGRESS["flash_offset"]
				else:
					self.PROGRESS["pos"] = 0
				if "sector_count" in args:
					self.PROGRESS["sector_count"] = args["sector_count"]
				else:
					self.PROGRESS["sector_count"] = 1
				if "time_start" in args:
					self.PROGRESS["time_start"] = args["time_start"]
				else:
					self.PROGRESS["time_start"] = now
				if "abortable" in args:
					self.PROGRESS["abortable"] = args["abortable"]
				else:
					self.PROGRESS["abortable"] = True
				self.PROGRESS["time_last_emit"] = emit_now
				self.PROGRESS["time_last_update_speed"] = now
				self.PROGRESS["time_left"] = 0
				self.PROGRESS["speed"] = 0
				self.PROGRESS["speeds"] = []
				self.PROGRESS["transfer_elapsed"] = 0
				self.PROGRESS["transfer_bytes"] = 0
				self.PROGRESS["bytes_last_update_speed"] = 0
				self.PROGRESS["sector_erase_time"] = 0
				self.UPDATER(self.PROGRESS)

			if args["action"] == "ABORT":
				self.UPDATER(args)
				self.PROGRESS = {}

			elif args["action"] in ("ERASE", "SECTOR_ERASE", "UNLOCK", "UPDATE_RTC", "CALC_CHECKSUMS", "ERROR"):
				if "time_start" in self.PROGRESS:
					args["time_elapsed"] = now - self.PROGRESS["time_start"]
				elif "time_start" in args:
					args["time_elapsed"] = now - args["time_start"]
				args["pos"] = 1
				args["size"] = 0
				self.UPDATER(args)

			elif self.PROGRESS == {}:
				return

			elif args["action"] in ("READ", "WRITE", "UPDATE_POS"):
				if "method" not in self.PROGRESS: return
				elif args["action"] == "READ" and self.PROGRESS["method"] in ("SAVE_WRITE", "ROM_WRITE"): return
				elif args["action"] == "WRITE" and self.PROGRESS["method"] in ("SAVE_READ", "ROM_READ", "ROM_WRITE_VERIFY"): return
				if self.PROGRESS["pos"] > self.PROGRESS["size"]: return
				if self.PROGRESS["method"] == "ROM_READ" and "transfer_elapsed" in args:
					self.PROGRESS["transfer_elapsed"] += args["transfer_elapsed"]
					self.PROGRESS["transfer_bytes"] += args["transfer_bytes"]
				skip_speed = False
				self.PROGRESS["action"] = "PROGRESS"
				if args["action"] in ("READ", "WRITE"):
					self.PROGRESS["pos"] += args["bytes_added"]
				elif args["action"] == "UPDATE_POS":
					if self.PROGRESS["pos"] == args["pos"] - self.PROGRESS["flash_offset"]:
						skip_speed = True
					if "skipping" in args and args["skipping"] is True:
						skip_speed = True
					self.PROGRESS["pos"] = args["pos"] - self.PROGRESS["flash_offset"]
					if "sector_erase_time" in args:
						if "sector_erase_time" in self.PROGRESS:
							self.PROGRESS["sector_erase_time"] = (self.PROGRESS["sector_erase_time"] + args["sector_erase_time"]) / 2
						else:
							self.PROGRESS["sector_erase_time"] = args["sector_erase_time"]
					if "sector_pos" in args:
						if "sector_erase_time" not in args: self.PROGRESS["sector_erase_time"] = 0
						self.PROGRESS["sector_pos"] = args["sector_pos"]
					if "abortable" in args:
						self.PROGRESS["abortable"] = args["abortable"]

				if ((emit_now - self.PROGRESS["time_last_emit"]) > 0.06) or "force_update" in args and args["force_update"] is True:
					self.PROGRESS["time_elapsed"] = now - self.PROGRESS["time_start"]
					time_delta = now - self.PROGRESS["time_last_update_speed"]
					pos_delta = self.PROGRESS["pos"] - self.PROGRESS["bytes_last_update_speed"]
					if time_delta > 0 and (now - self.PROGRESS["time_start"] > 2) and "sector_erase_time" not in args:
						speed = (pos_delta / time_delta) / 1024
						if speed > 0 and not skip_speed:
							if len(self.PROGRESS["speeds"]) < 40 or not self._is_outlier(speeds=self.PROGRESS["speeds"], new_number=speed, threshold=25):
								self.PROGRESS["speeds"].append(speed)
							if len(self.PROGRESS["speeds"]) > 50: self.PROGRESS["speeds"].pop(0)
							if len(self.PROGRESS["speeds"]) > 1 and random.randint(0, 10) == 0: self.PROGRESS["speeds"].pop(0)
						if len(self.PROGRESS["speeds"]) > 0:
							self.PROGRESS["speed"] = statistics.mean(self.PROGRESS["speeds"])
						else:
							self.PROGRESS["speed"] = 0
					self.PROGRESS["time_last_update_speed"] = now
					self.PROGRESS["bytes_last_update_speed"] = self.PROGRESS["pos"]

					if "skipping" in args and args["skipping"] is True:
						self.PROGRESS["speed"] = 0
						self.PROGRESS["skipping"] = True
					else:
						self.PROGRESS["skipping"] = False

					if self.PROGRESS["speed"] > 0 and len(self.PROGRESS["speeds"]) > 0:
						total_speed = self.PROGRESS["speed"]
						self.PROGRESS["time_left"] = (self.PROGRESS["size"] - self.PROGRESS["pos"]) / 1024 / total_speed
						if self.PROGRESS["sector_erase_time"] > 0:
							self.PROGRESS["time_left"] += self.PROGRESS["sector_erase_time"] * (self.PROGRESS["sector_count"] - self.PROGRESS["sector_pos"])

					self.UPDATER(self.PROGRESS)
					self.PROGRESS["time_last_emit"] = emit_now

			elif args["action"] == "UPDATE_INFO":
				self.PROGRESS["text"] = args["text"]
				self.PROGRESS["action"] = args["action"]
				self.UPDATER(self.PROGRESS)

			elif args["action"] == "FINISHED":
				self.PROGRESS["pos"] = self.PROGRESS["size"]
				self.UPDATER(self.PROGRESS)
				self.PROGRESS["action"] = args["action"]
				self.PROGRESS["bytes_last_update_speed"] = self.PROGRESS["size"]
				self.PROGRESS["time_elapsed"] = now - self.PROGRESS["time_start"]
				self.PROGRESS["time_last_emit"] = emit_now
				self.PROGRESS["time_last_update_speed"] = now
				self.PROGRESS["time_left"] = 0
				if self.PROGRESS["time_elapsed"] == 0: self.PROGRESS["time_elapsed"] = 0.001
				self.PROGRESS["speed"] = (self.PROGRESS["size"] / self.PROGRESS["time_elapsed"]) / 1024
				self.PROGRESS["bytes_last_emit"] = self.PROGRESS["size"]
				if "verified" in args:
					self.PROGRESS["verified"] = (args["verified"] == True)

				if self.PROGRESS["speed"] > self.PROGRESS["size"] / 1024:
					self.PROGRESS["speed"] = self.PROGRESS["size"] / 1024

				if self.PROGRESS["method"] == "ROM_READ" and self.PROGRESS["transfer_elapsed"] > 0:
					self.PROGRESS["speed"] = self.PROGRESS["transfer_bytes"] / self.PROGRESS["transfer_elapsed"] / 1024

				self.UPDATER(self.PROGRESS)
				del(self.PROGRESS["method"])

		finally:
			self.MUTEX.release()
