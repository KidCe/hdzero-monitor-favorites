"""Read-only receiver preflight failure boundaries and lifecycle, without USB."""
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from monitor_usb_receiver_preflight import ReceiverReadBridge, acquire
from monitor_receiver_flash_plan import CAPACITY, JEDEC


class FakeReadBridge:
    def __init__(self, data, *, unstable=False, busy=False, fail_at=None, close_failure=False):
        self.data = data
        self.events = []
        self.unstable, self.busy, self.fail_at, self.close_failure = unstable, busy, fail_at, close_failure
        self.reads = 0
        self.ids = 0

    def open(self):
        self.events.append("open")
        return {"vid": "0x1A86", "pid": "0x5512", "simulation": True}

    def select(self, target):
        self.events.append("select:" + target)

    def jedec_id(self):
        self.ids += 1
        return JEDEC

    def status(self):
        return {"sr1": 1 if self.busy else 0, "sr2": 0}

    def sfdp(self):
        return b"SFDP" + bytes(252)

    def read(self, address, length):
        self.reads += 1
        if address == self.fail_at:
            raise RuntimeError("Injected receiver read failure")
        data = self.data[address:address + length]
        if self.unstable and self.reads > CAPACITY // 1024 and address == 1024:
            data = bytes([data[0] ^ 1]) + data[1:]
        return data

    def close(self):
        self.events += ["release", "close"]
        if self.close_failure:
            raise RuntimeError("Injected release failure")


class ReceiverPreflightTests(unittest.TestCase):
    def run_acquire(self, bridge, directory):
        # Small deterministic current-state fixtures, full-size as required by the tool.
        stock = bytes(range(256)) * (CAPACITY // 256)
        favorites = b"\xff" * 65536 + stock[65536:]
        return acquire(bridge, stock, favorites, Path(directory) / "new-session")

    def test_full_read_classification_and_cleanup(self):
        stock = bytes(range(256)) * (CAPACITY // 256)
        bridge = FakeReadBridge(stock)
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_acquire(bridge, directory)
            self.assertTrue(report["success"])
            self.assertTrue(report["stock_preimage_confirmed"])
            self.assertEqual(report["image_classification"], "stock")
            self.assertEqual(bridge.reads, 2048)
            self.assertEqual(bridge.events, ["open", "select:5680", "release", "close"])
            self.assertFalse(report["ready_for_device_use"])
            self.assertFalse(report["flash_mutation_commands_implemented"])

    def test_busy_stops_before_array_reads(self):
        bridge = FakeReadBridge(bytes(CAPACITY), busy=True)
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_acquire(bridge, directory)
            self.assertFalse(report["success"])
            self.assertEqual(bridge.reads, 0)
            self.assertTrue(report["cleanup_success"])
        # Expired session budget also closes the handle without starting an array read.
        bridge = FakeReadBridge(bytes(CAPACITY))
        with tempfile.TemporaryDirectory() as directory, patch(
            "monitor_usb_receiver_preflight.time.monotonic", side_effect=[0, 0, 1000]
        ):
            report = self.run_acquire(bridge, directory)
            self.assertFalse(report["success"])
            self.assertIn("deadline", report["error"])
            self.assertEqual(bridge.reads, 0)
            self.assertTrue(report["cleanup_success"])

    def test_unstable_second_pass_is_not_verified(self):
        bridge = FakeReadBridge(bytes(CAPACITY), unstable=True)
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_acquire(bridge, directory)
            self.assertFalse(report["success"])
            self.assertIn("differ", report["error"])
            self.assertNotIn("full_passes_equal", report)

    def test_interrupted_file_stays_partial_and_report_failed(self):
        bridge = FakeReadBridge(bytes(CAPACITY), fail_at=4096)
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_acquire(bridge, directory)
            output = Path(directory) / "new-session"
            self.assertFalse(report["success"])
            self.assertEqual((output / "5680-current-pass1.partial").stat().st_size, 4096)
            self.assertFalse((output / "5680-current-pass1.bin").exists())
            self.assertFalse(json.loads((output / "preflight.json").read_text())["success"])

    def test_cleanup_error_revokes_success(self):
        bridge = FakeReadBridge(bytes(CAPACITY), close_failure=True)
        with tempfile.TemporaryDirectory() as directory:
            report = self.run_acquire(bridge, directory)
            self.assertFalse(report["success"])
            self.assertFalse(report["cleanup_success"])

    def test_mutation_unknown_commands_and_sfdp_overflow_never_reach_native_io(self):
        bridge = ReceiverReadBridge.__new__(ReceiverReadBridge)
        bridge.opened = bridge.routed = True
        for command in (b"\x06", b"\x04", b"\x02\x00\x00\x00", b"\xd8\x00\x00\x00",
                        b"\x01\x00", b"\x15\x00", b"\x5a\x00\x01\x00\x00\x00",
                        b"\x5a\x00\x00\xff\x00\x00\x00", b"\x5a\x00\x00\x00\x01\x00"):
            with self.subTest(command=command.hex()), self.assertRaises(ValueError):
                bridge._diagnostic_transaction(command)

    def test_other_target_or_read_outside_receiver_is_rejected(self):
        bridge = ReceiverReadBridge.__new__(ReceiverReadBridge)
        for target in ("fpga", "8339", "unknown"):
            with self.assertRaises(ValueError):
                bridge.select(target)
        for address, length in ((CAPACITY, 1), (CAPACITY - 1, 2), (-1, 1), (True, 1)):
            with self.assertRaises(ValueError):
                bridge.read(address, length)


if __name__ == "__main__":
    unittest.main()
