import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import monitor_usb_backup as backup
from monitor_usb_probe import Bridge


class FakeBridge:
    def __init__(self, path=None):
        self.data = bytes(range(256)) * 16
        self.events = []
        self.identity = "EF4014"
        self.fail_at = None
        self.corrupt_large = False

    def open(self):
        self.events.append("open")

    def select(self, name):
        self.events.append("select:" + name)

    def jedec_id(self):
        return self.identity

    def read(self, address, length):
        if address == self.fail_at:
            raise RuntimeError("Injected USB read failure")
        result = self.data[address:address + length]
        if self.corrupt_large and length > 256:
            result = bytes([result[0] ^ 1]) + result[1:]
        return result

    def close(self):
        self.events.append("close")


class BackupFailureTests(unittest.TestCase):
    def test_unknown_identity_stops_before_memory_reads(self):
        bridge = FakeBridge()
        bridge.identity = "123456"
        with self.assertRaisesRegex(RuntimeError, "Unexpected"):
            backup.validate_target(bridge, "5680")

    def test_chunk_boundary_corruption_is_rejected(self):
        bridge = FakeBridge()
        bridge.corrupt_large = True
        with self.assertRaisesRegex(RuntimeError, "boundary"):
            backup.check_chunk_size(bridge, len(bridge.data), 1024)

    def test_failed_acquisition_closes_and_keeps_partial_unverified(self):
        bridge = FakeBridge()
        bridge.fail_at = 1024  # Outside the three preflight positions.
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch.object(backup, "Bridge", return_value=bridge), patch.dict(
                backup.TARGET_INFO, {"5680": ("EF4014", len(bridge.data))}
            ):
                with self.assertRaisesRegex(RuntimeError, "Injected"):
                    backup.acquire(Path("unused"), "5680", 1, output, 1024, bridge.data[:512])
            self.assertEqual(bridge.events[-1], "close")
            self.assertEqual((output / "5680-pass1.partial").stat().st_size, 1024)
            self.assertFalse((output / "5680-pass1.bin").exists())

    def test_difference_outside_matching_prefix_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "a", Path(directory) / "b"
            original = bytes(4096)
            changed = bytearray(original)
            changed[4000] = 1
            first.write_bytes(original)
            second.write_bytes(changed)
            self.assertEqual(backup.compare_files(first, second, 4096),
                             {"byte_equal": False, "first_difference": 4000})

    def test_flash_mutation_opcode_is_rejected_before_native_io(self):
        bridge = Bridge.__new__(Bridge)
        bridge.opened = bridge.routed = True
        for command in (b"\x06", b"\x02\x00\x00\x00", b"\xC7", b"\x01\x00"):
            with self.assertRaises(ValueError):
                bridge._read_transaction(command)

    def test_address_wrap_and_oversized_reads_are_rejected(self):
        bridge = Bridge.__new__(Bridge)
        for address, length in ((-1, 1), (0, 0), (0, 1025), (0xFFFFFF, 2)):
            with self.assertRaises(ValueError):
                bridge.read(address, length)

    def test_bus_release_precedes_close_even_when_release_fails(self):
        bridge = Bridge.__new__(Bridge)
        bridge.opened = bridge.routed = True
        events = []
        bridge.set_output = lambda *args: events.append("release") or False
        bridge.close_device = lambda *args: events.append("close")
        with self.assertRaisesRegex(RuntimeError, "release failed"):
            bridge.close()
        self.assertEqual(events, ["release", "close"])
        self.assertFalse(bridge.opened)


if __name__ == "__main__":
    unittest.main()
