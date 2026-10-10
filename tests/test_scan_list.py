"""v6/v7: Favorites in the built-in scan, P-band scan list, shorter long press, stock activation, version text."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from monitor_receiver_candidate import make_candidate

STOCK = ROOT / "artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin"
BANDS = "ABEFRL"


def scan_list(code, selection=0x20):
    """Run the initializer from 6D6C (including the v7 hook) until it reaches 6DAC.

    Returns the twelve entries written to 0816..0821. Fails on unknown opcodes or other writes.
    """
    pc, a, c, dptr, entries = 0x6D6C, 0, 0, 0, {}
    for _ in range(400):
        if pc == 0x6DAC:
            if set(entries) != set(range(0x816, 0x822)):
                raise AssertionError("List incompletely written")
            return [entries[address] for address in range(0x816, 0x822)]
        op = code[pc]
        if op == 0x90:
            dptr, pc = code[pc + 1] << 8 | code[pc + 2], pc + 3
        elif op == 0x74:
            a, pc = code[pc + 1], pc + 2
        elif op == 0x04:
            a, pc = (a + 1) & 0xFF, pc + 1
        elif op == 0xE0:
            if dptr != 0x0D85:
                raise AssertionError(f"Unexpected read {dptr:04X}")
            a, pc = selection, pc + 1
        elif op == 0xF0:
            if not 0x816 <= dptr <= 0x821:
                raise AssertionError(f"Unexpected write {dptr:04X}")
            entries[dptr], pc = a, pc + 1
        elif op == 0xC3:
            c, pc = 0, pc + 1
        elif op == 0x94:
            value = a - code[pc + 1] - c
            c, a, pc = int(value < 0), value & 0xFF, pc + 2
        elif op in (0x40, 0x50):
            rel = code[pc + 1] - 256 if code[pc + 1] > 127 else code[pc + 1]
            taken = c == 1 if op == 0x40 else c == 0
            pc = pc + 2 + (rel if taken else 0)
        elif op == 0x02:
            pc = code[pc + 1] << 8 | code[pc + 2]
        else:
            raise AssertionError(f"Unexpected opcode {op:02X} at {pc:04X}")
    raise AssertionError("Instruction limit exceeded")


def name(identity):
    if 0x30 <= identity < 0x38:
        return f"P{identity - 0x2F}"
    return BANDS[identity >> 3] + str((identity & 7) + 1)


class ScanListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STOCK.exists():
            raise unittest.SkipTest("Private stock receiver fixture unavailable")
        cls.stock = STOCK.read_bytes()
        config = json.loads((ROOT / "config/favorite-channels.json").read_text(encoding="utf-8"))
        cls.code, cls.manifest = make_candidate(cls.stock, config)
        cls.favorites = [slot["label"] for slot in cls.manifest["favorites"]]

    def test_stock_and_new_scan_lists(self):
        stock = [name(i) for i in scan_list(self.stock)]
        self.assertEqual(stock, ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "E1", "F1", "F2", "F4"])
        new = [name(i) for i in scan_list(self.code)]
        self.assertEqual(new, self.manifest["scan_list"])
        self.assertEqual(len(new), 12)
        self.assertTrue(set(self.favorites) <= set(new))

    def test_p_band_scan_list_keeps_frequencies_and_order(self):
        stock_list = scan_list(self.code)
        ids = self.manifest["favorites_stock_ids"]
        for selection in range(0x30, 0x38):
            with self.subTest(selection=hex(selection)):
                p_list = scan_list(self.code, selection)
                self.assertEqual([name(i) for i in p_list], self.manifest["favorites_scan_list"])
                # Same RF frequency per position: a P entry maps back to the stock entry it replaces.
                self.assertEqual([ids[i - 0x30] if i >= 0x30 else i for i in p_list], stock_list)
                self.assertEqual(sorted(i for i in p_list if i >= 0x30), list(range(0x30, 0x38)))
                self.assertIn(selection, p_list)  # Start position is the current slot.
        self.assertEqual(self.manifest["favorites_scan_list"],
                         ["P3", "P4", "R3", "R4", "R5", "R6", "P7", "P8", "P5", "P1", "P2", "P6"])

    def test_other_selections_get_the_stock_list(self):
        expected = scan_list(self.code)
        for selection in list(range(0x30)) + [0x38, 0x3F, 0x80, 0xFF]:
            with self.subTest(selection=hex(selection)):
                self.assertEqual(scan_list(self.code, selection), expected)

    def test_replaced_entries_share_the_rf_profile_group(self):
        def profile(identity):  # 0C74 branch: RF index 8, 9 or >= 12
            index = self.stock[0xC6F0 + identity]
            return index in (8, 9) or index >= 12
        removed = set(scan_list(self.stock)) - set(scan_list(self.code))
        added = set(scan_list(self.code)) - set(scan_list(self.stock))
        self.assertEqual({name(i) for i in removed}, {"E1", "F1"})
        self.assertEqual({name(i) for i in added}, {"L6", "L7"})
        self.assertTrue(all(profile(i) for i in removed | added))

    def test_long_press_threshold_halved_in_both_directions(self):
        for low, high in ((0x0951, 0x0954), (0x099D, 0x09A0)):
            stock = self.stock[low + 1] | self.stock[high + 1] << 8
            new = self.code[low + 1] | self.code[high + 1] << 8
            self.assertEqual((stock, new), (1000, 500))
            self.assertEqual(self.code[low], 0x74)
            self.assertEqual(self.code[high], 0x74)

    def test_version_text(self):
        def text(code):  # Straight-line builder B981..B9CF: MOV DPTR / MOV A / CLR A / MOVX only.
            pc, a, dptr, memory = 0xB981, 0, 0, {}
            while pc < 0xB9D0:
                op = code[pc]
                if op == 0x90:
                    dptr, pc = code[pc + 1] << 8 | code[pc + 2], pc + 3
                elif op == 0x74:
                    a, pc = code[pc + 1], pc + 2
                elif op == 0xE4:
                    a, pc = 0, pc + 1
                elif op == 0xF0:
                    memory[dptr], pc = a, pc + 1
                else:
                    raise AssertionError(f"Unexpected opcode {op:02X} at {pc:04X}")
            self.assertEqual(set(memory), set(range(0x1004, 0x100F)))  # No write outside the buffer.
            return bytes(memory[i] for i in range(0x1004, 0x100E)).decode()
        self.assertEqual(text(self.stock), "FW: V1.1.1")
        self.assertEqual(text(self.code), "FW: V1.1.2")
        self.assertEqual(self.manifest["receiver_version_text"], "FW: V1.1.2")

    def test_stock_scan_activation_restored(self):
        for offset in (0x0971, 0x09BD):
            self.assertEqual(self.code[offset:offset + 3], self.stock[offset:offset + 3])
            self.assertEqual(self.code[offset], 0x90)


if __name__ == "__main__":
    unittest.main()
