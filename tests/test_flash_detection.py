import copy
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from FlashGBX.FlashGBX import LoadConfig
from FlashGBX.Flashcart import Flashcart
from FlashGBX.LK_Device import LK_Device
from FlashGBX.app import AppInfo


ROOT = Path(__file__).resolve().parents[1]
OFFSETS = [0, 1, 2, 3, 0x1C, 0x1D, 0x1E, 0x1F]
TOP_ID = [1, 1, 0x7E, 0x7E, 0x0A, 0x0A, 1, 1]
GL_ID = [1, 1, 0x7E, 0x7E, 0x22, 0x22, 1, 1]


def load_profile(filename):
    source = (ROOT / "FlashGBX" / "config" / filename).read_text(encoding="utf-8")
    return json.loads(re.sub(r"0x[0-9A-F]+", lambda m: str(int(m[0], 16)), source))


def profile(name, ids, offsets=None):
    config = {
        "type": "DMG", "names": [name], "flash_ids": ids,
        "voltage": 5, "flash_size": 0x400000, "command_set": "AMD",
        "commands": {"reset": [[0, 0xF0]], "read_identifier": [[0xAAA, 0xAA], [0x555, 0x55], [0xAAA, 0x90]]},
    }
    if offsets is not None:
        config["flash_id_offsets"] = offsets
    return config


def detect(profiles, identity=TOP_ID, mode="DMG", rom_is_id=False):
    device = Mock(spec=LK_Device)
    device.MODE = mode
    device.DEVICE_NAME = "simulated"
    device.INFO = {}
    device.DEVICE_CMD = LK_Device.DEVICE_CMD
    device.FW = {"fw_ver": 16}
    device.SUPPORTED_CARTS = {mode: {"Auto": {}, **{p["names"][0]: copy.deepcopy(p) for p in profiles}}}
    device.GetFirmwareVersion.return_value = "simulated"
    device.SupportsAudioAsWe.return_value = False
    device.GetSupportedCartridgesDMG.side_effect = lambda: LK_Device.GetSupportedCartridgesDMG(device)
    device.GetSupportedCartridgesAGB.side_effect = lambda: LK_Device.GetSupportedCartridgesAGB(device)

    def read(kind, address, length, config, *args):
        data = bytearray(length)
        if kind == "id" or (kind == "rom" and rom_is_id):
            for offset, value in zip(OFFSETS, identity):
                if offset < length:
                    data[offset] = value
        return data

    device._ReadFlashDiagnostic.side_effect = read
    with patch("FlashGBX.LK_Device.CFI") as cfi:
        cfi.return_value.Parse.return_value = False
        return LK_Device._DetectFlash(device), device


class FlashDetectionTests(unittest.TestCase):
    def test_extended_id_beats_generic_id(self):
        generic = profile("generic", [TOP_ID[:4]])
        specific = load_profile("fc_DMG_S29JL032J_TOP.txt")
        result, device = detect([generic, specific])
        self.assertEqual(result[:2], ([2, 1], 2))
        self.assertEqual(device.INFO["flash_diagnostics"]["matches"][0], specific["names"][0])

    def test_longest_matching_id_within_profile_counts(self):
        medium = profile("medium", [TOP_ID[:6]], OFFSETS)
        specific = profile("specific", [TOP_ID[:4], TOP_ID], OFFSETS)
        self.assertEqual(detect([medium, specific])[0][:2], ([2, 1], 2))

    def test_equal_length_matches_keep_profile_order(self):
        profiles = [profile(name, [TOP_ID], OFFSETS) for name in ("first", "second")]
        self.assertEqual(detect(profiles)[0][:2], ([1, 2], 1))

    def test_extended_id_mismatch_rejects_top_boot_profile(self):
        top = load_profile("fc_DMG_S29JL032J_TOP.txt")
        self.assertEqual(detect([top], GL_ID)[0][:2], ([], 0))

    def test_unchanged_rom_data_is_not_a_flash_id(self):
        top = profile("top", [TOP_ID], OFFSETS)
        self.assertEqual(detect([top], rom_is_id=True)[0][:2], ([], 0))

    def test_agb_keeps_only_the_longest_match(self):
        profiles = [profile("generic", [TOP_ID[:4]]), profile("specific", [TOP_ID], OFFSETS)]
        for config in profiles:
            config["type"] = "AGB"
        self.assertEqual(detect(profiles, mode="AGB")[0][:2], ([2], 2))

    def test_matching_alias_is_reported(self):
        names = ["other cartridge", "ModRetro cartridge"]
        configs = [profile(name, [GL_ID, TOP_ID], OFFSETS) for name in names]
        for config in configs:
            config["_profile_names"] = names
        self.assertEqual(detect(configs)[0][1], 2)

    def test_duplicate_ids_keep_first_alias(self):
        names = ["first", "second"]
        configs = [profile(name, [TOP_ID, TOP_ID], OFFSETS) for name in names]
        for config in configs:
            config["_profile_names"] = names
        self.assertEqual(detect(configs)[0][1], 1)

    def test_config_loader_preserves_alias_order(self):
        with tempfile.TemporaryDirectory() as directory:
            config = profile("first", [GL_ID, TOP_ID], OFFSETS)
            config["names"].append("second")
            path = Path(directory) / "fc_DMG_test.txt"
            path.write_text(json.dumps(config), encoding="utf-8")
            with patch("FlashGBX.FlashGBX.ReadConfigFiles", return_value=(AppInfo.VERSION, [str(path)])):
                loaded = LoadConfig({"app_path": directory, "config_path": directory})
            for name in config["names"]:
                self.assertEqual(loaded["flashcarts"]["DMG"][name]["_profile_names"], config["names"])

    def test_top_boot_id_verification_uses_offsets(self):
        config = load_profile("fc_DMG_S29JL032J_TOP.txt")
        state = {"id": False}

        def write(commands, **kwargs):
            state["id"] = commands == config["commands"]["read_identifier"]

        def read(address, length):
            data = bytearray(length)
            if state["id"]:
                for offset, value in zip(OFFSETS, TOP_ID):
                    if offset < length:
                        data[offset] = value
            return data

        callbacks = {name: Mock() for name in (
            "cart_write_fncptr", "cart_powercycle_fncptr", "progress_fncptr", "set_we_pin_wr", "set_we_pin_audio",
        )}
        callbacks.update(cart_write_fast_fncptr=write, cart_read_fncptr=read)
        flashcart = Flashcart(config, callbacks)
        verified, _ = flashcart.VerifyFlashID()
        self.assertTrue(verified)
        self.assertFalse(state["id"])

    def test_chisflash_spansion_profile_uses_full_id(self):
        config = load_profile("fc_DMG_ChisFlash-MBC5-MAX_S29GL256N.txt")
        self.assertEqual(config.get("flash_id_offsets"), OFFSETS)
        self.assertEqual(config["flash_ids"], [GL_ID])

    def test_distributed_profiles_match_source(self):
        filenames = ["fc_DMG_S29JL032J_TOP.txt", "fc_DMG_ChisFlash-MBC5-MAX_S29GL256N.txt", "fc_DMG_ChisFlash-MBC5-MAX_28EW256A.txt"]
        with zipfile.ZipFile(ROOT / "FlashGBX" / "res" / "config.zip") as archive:
            for filename in filenames:
                with self.subTest(filename=filename):
                    packaged = archive.read(filename).decode("utf-8").splitlines()
                    self.assertEqual(packaged, (ROOT / "FlashGBX" / "config" / filename).read_text(encoding="utf-8").splitlines())


if __name__ == "__main__":
    unittest.main()
