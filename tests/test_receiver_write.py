"""Receiver write/restore session on the local NOR model through the real bridge code, without USB."""
import ctypes
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from monitor_receiver_flash_plan import CAPACITY, ERASE_BYTES, NorModel, projected_favorites, verified_backups
import monitor_usb_receiver_write as write


class NorBackedBridge(write.ReceiverWriteBridge):
    """Real ReceiverWriteBridge logic; only the DLL entry points are replaced by the NOR model."""

    def __init__(self, model):
        self.model = model
        self.events = []
        self.opened = self.routed = False
        self.native_calls = 0
        self.set_stream = lambda index, mode: 1
        self.set_output = lambda index, enable, mask, value: self.events.append(f"gpio:{value:04X}") or 1
        self.close_device = lambda index: self.events.append("close")

    def transfer(self, index, cs, length, buffer):
        self.native_calls += 1
        response = self.model.transfer(ctypes.string_at(buffer, length))
        ctypes.memmove(buffer, response, length)
        return 1

    def open(self):
        self.opened = True
        self.events.append("open")
        return {"simulation": True}


class ReceiverWriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = ROOT / "artifacts/device-backups/20261009-usb-01"
        receiver = ROOT / "artifacts/firmware-analysis/20261010-pscan-v7/favorites-build-v7/receiver-rebuilt.bin"
        if not (directory / "manifest.json").exists() or not receiver.exists():
            raise unittest.SkipTest("Private verified backup/source fixtures unavailable")
        cls.stock = verified_backups(directory)["5680"]
        config = json.loads((ROOT / "config/favorite-channels.json").read_text(encoding="utf-8"))
        cls.favorites = projected_favorites(cls.stock, receiver.read_bytes(), config)

    def session(self, model, mode, directory, **options):
        bridge = NorBackedBridge(model)
        options.setdefault("busy_deadlines", {"status": 1.0, "program": 1.0, "erase": 1.0})
        options.setdefault("poll_interval", 0)
        report = write.run(bridge, self.stock, self.favorites, mode, Path(directory) / "session", **options)
        return bridge, report

    def test_dry_run_reads_and_plans_without_mutation(self):
        model = NorModel(self.stock)
        with tempfile.TemporaryDirectory() as directory:
            bridge, report = self.session(model, "favorites", directory)
            self.assertTrue(report["success"] and report["dry_run"])
            self.assertEqual(report["plan_program_pages"], 245)
            self.assertTrue((Path(directory) / "session/plan.json").exists())
        self.assertEqual(model.mutations, 0)
        self.assertNotIn("06", [t["opcode"] for t in model.transactions])
        self.assertEqual(bridge.events, ["open", "gpio:4300", "gpio:C200", "close"])

    def test_favorites_then_restore_roundtrip(self):
        model = NorModel(self.stock)
        with tempfile.TemporaryDirectory() as directory:
            bridge, report = self.session(model, "favorites", directory, execute_write=True)
            self.assertTrue(report["success"], report.get("error"))
            self.assertEqual(report["after_sha256"], write.FAVORITES_ARRAY_SHA256)
            self.assertEqual((Path(directory) / "session/5680-after.bin").read_bytes(), self.favorites)
        self.assertEqual(bytes(model.data), self.favorites)
        self.assertFalse(bridge.mutation_armed)
        self.assertEqual(bridge.events[-2:], ["gpio:C200", "close"])
        restored = NorModel(bytes(model.data))
        with tempfile.TemporaryDirectory() as directory:
            _, report = self.session(restored, "restore", directory, execute_write=True)
            self.assertTrue(report["success"], report.get("error"))
        self.assertEqual(bytes(restored.data), self.stock)
        self.assertEqual(restored.programs, 243)

    def test_verified_earlier_arrays_upgrade_directly_to_current_favorites(self):
        from monitor_receiver_decode import ENCODE_TABLE
        from monitor_receiver_flash_plan import PREVIOUS_FAVORITES_ARRAY_SHA256, digest
        builds = ("20261009-scan-guard/favorites-build-v4", "20261010-label-v5/favorites-build-v5",
                  "20261010-scan-v6b/favorites-build-v6")
        for build in builds:
            path = ROOT / "artifacts/firmware-analysis" / build / "receiver-rebuilt.bin"
            if not path.exists():
                self.skipTest("Earlier build fixture unavailable")
            array = bytearray(self.stock)
            array[:ERASE_BYTES] = b"\xff" * ERASE_BYTES
            receiver = path.read_bytes()
            array[:len(receiver)] = receiver.translate(ENCODE_TABLE)
            self.assertIn(digest(bytes(array)), PREVIOUS_FAVORITES_ARRAY_SHA256)
            model = NorModel(bytes(array))
            with self.subTest(build=build), tempfile.TemporaryDirectory() as directory:
                _, report = self.session(model, "favorites", directory, execute_write=True)
                self.assertTrue(report["success"], report.get("error"))
                self.assertEqual(bytes(model.data), self.favorites)

    def test_interrupted_write_reports_hint_and_restore_recovers(self):
        model = NorModel(self.stock, fail_program=20)
        with tempfile.TemporaryDirectory() as directory:
            bridge, report = self.session(model, "favorites", directory, execute_write=True)
            saved = json.loads((Path(directory) / "session/write-session.json").read_text(encoding="utf-8"))
        self.assertFalse(report["success"])
        self.assertTrue(report["mutation_started"])
        self.assertIn("restore", report["recovery_hint"])
        self.assertEqual(saved["protocol_progress"]["program_pages_issued"], 20)
        self.assertEqual(bridge.events[-2:], ["gpio:C200", "close"])
        partial = bytes(model.data)
        self.assertEqual(partial[ERASE_BYTES:], self.stock[ERASE_BYTES:])
        resumed = NorModel(partial)
        with tempfile.TemporaryDirectory() as directory:
            _, report = self.session(resumed, "restore", directory, execute_write=True)
        self.assertTrue(report["success"], report.get("error"))
        self.assertEqual(bytes(resumed.data), self.stock)

    def test_stuck_busy_hits_wall_clock_deadline(self):
        model = NorModel(self.stock, stuck_busy=True)
        with tempfile.TemporaryDirectory() as directory:
            # A small poll interval makes the wall clock, not the poll budget, expire first.
            _, report = self.session(model, "favorites", directory, execute_write=True, poll_interval=0.001,
                                     busy_deadlines={"status": 0.05, "program": 0.05, "erase": 0.05})
        self.assertFalse(report["success"])
        self.assertIn("deadline", report["error"])
        self.assertEqual((model.mutations, model.programs), (1, 0))

    def test_unexpected_status_or_preimage_stops_before_mutation(self):
        changed = bytearray(self.stock)
        changed[ERASE_BYTES + 5] ^= 1
        for model in (NorModel(self.stock, sr2=0x40), NorModel(self.stock, write_protected=True),
                      NorModel(bytes(changed))):  # An already-installed image is a verified no-op instead.
            with self.subTest(), tempfile.TemporaryDirectory() as directory:
                bridge, report = self.session(model, "favorites", directory, execute_write=True)
                self.assertFalse(report["success"])
                self.assertFalse(report["mutation_started"])
                self.assertEqual(model.mutations, 0)
                self.assertEqual(bridge.events[-1], "close")

    def test_mutations_require_arming_and_reviewed_shapes(self):
        bridge = NorBackedBridge(NorModel(self.stock))
        bridge.opened = bridge.routed = True
        for command in (b"\x06", b"\xd8\x00\x00\x00", b"\x02\x00\x00\x00" + bytes(256)):
            with self.subTest(command=command[:4].hex()), self.assertRaises(ValueError):
                bridge.spi(command)
        bridge.mutation_armed = True
        rejected = (b"\xc7", b"\x60", b"\x01\x00", b"\x31\x00", b"\x20\x00\x00\x00", b"\x52\x00\x00\x00",
                    b"\xd8\x01\x00\x00", b"\xd8\x00\x00\x00\x00", b"\x02\x00\x00\x01" + bytes(256),
                    b"\x02\x01\x00\x00" + bytes(256), b"\x02\x00\x00\x00" + bytes(255),
                    b"\x03\x0f\xff\xff\x00\x00", b"\x03\x00\x00\x00\x01", b"\x03\x00\x00\x00" + bytes(1025),
                    b"\x5a\x00\x00\x00\x00\x00", bytearray(b"\x06"))
        for command in rejected:
            with self.subTest(command=bytes(command[:4]).hex()), self.assertRaises(ValueError):
                bridge.spi(command)
        self.assertEqual(bridge.native_calls, 0)
        bridge.close()
        self.assertFalse(bridge.mutation_armed)

    def test_cli_requires_matching_confirmation_before_any_file_access(self):
        argv = ["write", "--dll", "missing.dll", "--backups", "missing", "--receiver", "missing.bin",
                "--mode", "favorites", "--output-dir", "missing-out", "--execute-write",
                "--confirm-after-sha256", write.EXPECTED_AFTER["restore"]]
        with patch.object(sys, "argv", argv), patch("sys.stderr"), self.assertRaises(SystemExit) as raised:
            write.main()
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
