"""Independent transform/input guards for offline receiver analysis."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monitor_receiver_decode import DECODE_TABLE, ENCODE_TABLE, decode_array
from monitor_receiver_map import build_mapping, validate_config


class ReceiverAnalysisGuards(unittest.TestCase):
    def test_published_transform_bit_examples_and_full_bijection(self):
        # Expected bytes are read from the upstream transform, not produced by the decoder.
        for decoded, encoded in ((1, 0x80), (2, 4), (4, 0x20), (8, 2),
                                 (0x10, 8), (0x20, 0x10), (0x40, 1), (0x80, 0x40)):
            self.assertEqual(ENCODE_TABLE[decoded], encoded)
            self.assertEqual(DECODE_TABLE[encoded], decoded)
        values = bytes(range(256))
        self.assertEqual(len(set(ENCODE_TABLE)), 256)
        self.assertEqual(values.translate(ENCODE_TABLE).translate(DECODE_TABLE), values)
        self.assertEqual(values.translate(DECODE_TABLE).translate(ENCODE_TABLE), values)

    def test_wrong_raw_and_decoded_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "pinned"):
            decode_array(bytes(1024 * 1024))
        with self.assertRaisesRegex(ValueError, "pinned"):
            build_mapping(bytes(62003), {"channels": []})

    def test_requested_favorites_have_expected_stock_identities(self):
        channels = [{"band": label[0], "channel": int(label[1])}
                    for label in ("L6", "L7", "R1", "R2", "F2", "F4", "R7", "R8")]
        self.assertEqual(validate_config({"channels": channels}),
                         [0x2D, 0x2E, 0x20, 0x21, 0x19, 0x1B, 0x26, 0x27])

    def test_invalid_virtual_and_channel_identities_are_rejected(self):
        for band, channel in (("Favorites", 1), ("L", 0), ("R", 9), ("F", True), ("F", "2")):
            with self.subTest(band=band, channel=channel), self.assertRaises(ValueError):
                validate_config({"channels": [{"band": band, "channel": channel}] * 8})
        with self.assertRaises(ValueError):
            validate_config({"channels": []})
        with self.assertRaises(ValueError):
            validate_config([])


if __name__ == "__main__":
    unittest.main()
