"""Guard tests for offline analysis; no USB or firmware files required."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from offline_firmware import load_application
from monitor_function_emulator import contains


class OfflineInputGuards(unittest.TestCase):
    def test_unrecognized_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "not-firmware.bin"
            contents = b"MCR5" + bytes(1024)
            path.write_bytes(contents)
            with self.assertRaisesRegex(ValueError, "hash-pinned"):
                load_application(path)
            self.assertEqual(path.read_bytes(), contents)

    def test_memory_access_must_fit_entirely_inside_model(self):
        region = (0x1000, 4)
        self.assertTrue(contains(region, 0x1000, 4))
        self.assertTrue(contains(region, 0x1003, 1))
        for address, size in ((0xFFF, 2), (0x1003, 2), (0x1004, 1), (0x1000, 0), (0x1000, -1)):
            with self.subTest(address=address, size=size):
                self.assertFalse(contains(region, address, size))


if __name__ == "__main__":
    unittest.main()
