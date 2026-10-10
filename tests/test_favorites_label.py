"""Executes the v5 Favorites label routine from the generated image in a minimal 8051 interpreter.

Only the opcodes used on this path are implemented; anything else fails the test.
Buffers are fixtures equivalent to what the stock code builds before the hooked draws.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from monitor_receiver_candidate import LABEL_ROUTINE, make_candidate

STOCK = ROOT / "artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin"
DRAW = 0xB1DF
BUFFER, DESCRIPTOR_LENGTH, SELECTION = 0x0FED, 0x0FC6, 0x0D85
LETTERS = "ABEFRL"


class Mini8051:
    def __init__(self, code, xdata):
        self.code, self.x = code, dict(xdata)
        self.a = self.c = self.r7 = self.dptr = 0
        self.dpl_written = None
        self.writes = []

    def run(self, pc, limit=500):
        code = self.code
        for _ in range(limit):
            if pc == DRAW:
                return
            op = code[pc]
            if op == 0x90:
                self.dptr, pc = code[pc + 1] << 8 | code[pc + 2], pc + 3
            elif op == 0xE0:
                self.a, pc = self.x.get(self.dptr, 0), pc + 1
            elif op == 0xF0:
                self.x[self.dptr] = self.a
                self.writes.append(self.dptr)
                pc += 1
            elif op == 0xC3:
                self.c, pc = 0, pc + 1
            elif op == 0x94:
                value = self.a - code[pc + 1] - self.c
                self.c, self.a, pc = int(value < 0), value & 0xFF, pc + 2
            elif op in (0x40, 0x50, 0x70):
                taken = {0x40: self.c == 1, 0x50: self.c == 0, 0x70: self.a != 0}[op]
                rel = code[pc + 1] - 256 if code[pc + 1] > 127 else code[pc + 1]
                pc = pc + 2 + (rel if taken else 0)
            elif op == 0xFF:
                self.r7, pc = self.a, pc + 1
            elif op == 0xEF:
                self.a, pc = self.r7, pc + 1
            elif op == 0x74:
                self.a, pc = code[pc + 1], pc + 2
            elif op == 0x93:
                self.a, pc = code[(self.a + self.dptr) & 0xFFFF], pc + 1
            elif op == 0x54:
                self.a, pc = self.a & code[pc + 1], pc + 2
            elif op == 0x24:
                value = self.a + code[pc + 1]
                self.c, self.a, pc = int(value > 255), value & 0xFF, pc + 2
            elif op == 0xC4:
                self.a, pc = ((self.a << 4) | (self.a >> 4)) & 0xFF, pc + 1
            elif op == 0x23:
                self.a, pc = ((self.a << 1) | (self.a >> 7)) & 0xFF, pc + 1
            elif op == 0x75 and code[pc + 1] == 0x82:
                self.dpl_written, pc = code[pc + 2], pc + 3
            elif op == 0x02:
                pc = code[pc + 1] << 8 | code[pc + 2]
            else:
                raise AssertionError(f"Unexpected opcode {op:02X} at {pc:04X}")
        raise AssertionError("Instruction limit exceeded")


class FavoritesLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not STOCK.exists():
            raise unittest.SkipTest("Private stock receiver fixture unavailable")
        cls.stock = STOCK.read_bytes()
        config = json.loads((ROOT / "config/favorite-channels.json").read_text(encoding="utf-8"))
        cls.code, cls.manifest = make_candidate(cls.stock, config)
        cls.slots = [slot["label"] for slot in cls.manifest["favorites"]]

    def string(self, address):
        end = self.stock.index(0, address)
        return self.stock[address:end].decode("ascii")

    def label(self, selection, suffix, hook, length):
        """Run from the hooked draw site; return drawn text, length and written addresses."""
        letter = "P" if selection >= 0x30 else LETTERS[selection >> 3]
        raw = (letter + str((selection & 7) + 1) + suffix).encode("ascii") + b"\x00"
        xdata = {SELECTION: selection, DESCRIPTOR_LENGTH: length}
        xdata.update({BUFFER + i: value for i, value in enumerate(raw)})
        cpu = Mini8051(self.code, xdata)
        cpu.run(hook)
        self.assertEqual(cpu.dpl_written, 0x15)
        drawn = cpu.x[DESCRIPTOR_LENGTH]
        return bytes(cpu.x.get(BUFFER + i, 0) for i in range(drawn)), drawn, cpu.writes

    def test_hooks_jump_to_routine(self):
        for hook in (0xB87F, 0xB8F8):
            self.assertEqual(self.code[hook:hook + 6], bytes([0x02, LABEL_ROUTINE >> 8, LABEL_ROUTINE & 255, 0, 0, 0]))

    def test_normal_digital_and_analog_for_every_slot(self):
        for suffix_address, mode in ((0xF209, "HDZ"), (0xF201, "ANA")):
            suffix = self.string(suffix_address)
            for slot, channel in enumerate(self.slots):
                with self.subTest(slot=slot + 1, mode=mode):
                    text, length, writes = self.label(0x30 + slot, suffix, 0xB8F8, 9)
                    self.assertEqual(text.decode(), f"P{slot + 1} {channel} {mode}")
                    self.assertEqual(length, 9)
                    self.assertTrue(all(BUFFER <= a <= BUFFER + 8 or a == DESCRIPTOR_LENGTH for a in writes))

    def test_busy_dots_for_every_slot(self):
        # Stock busy path: strcpy of the three-space string, then dots from buffer index 3.
        spaces = self.string(0xF1FC)
        for dots in range(5):
            suffix = bytearray(spaces.encode() + b"\x00")
            for index in range(dots):
                if 1 + index >= len(suffix):
                    suffix.append(0)
                suffix[1 + index] = ord(".")
            for slot, channel in enumerate(self.slots):
                with self.subTest(slot=slot + 1, dots=dots):
                    text, length, _ = self.label(0x30 + slot, suffix.rstrip(b"\x00").decode(), 0xB87F, 6)
                    shown = ("." * min(dots, 3)).ljust(3)
                    self.assertEqual(text.decode(), f"P{slot + 1} {channel} {shown}")
                    self.assertEqual(length, 9)

    def test_nul_after_short_suffix_is_drawn_as_space(self):
        text, _, _ = self.label(0x30, " .", 0xB87F, 6)  # NUL at buffer index 4
        self.assertEqual(text.decode(), f"P1 {self.slots[0]} .  ")

    def test_stock_bands_and_invalid_ids_are_untouched(self):
        suffix = self.string(0xF209)
        for selection in list(range(0x30)) + [0x38, 0x3F, 0xFF]:
            for hook, length in ((0xB8F8, 9), (0xB87F, 6)):
                with self.subTest(selection=hex(selection), hook=hex(hook)):
                    letter = "P" if selection >= 0x30 else LETTERS[selection >> 3]
                    raw = (letter + str((selection & 7) + 1) + suffix).encode()
                    text, drawn, writes = self.label(selection, suffix, hook, length)
                    self.assertEqual(writes, [])
                    self.assertEqual(drawn, length)
                    self.assertEqual(text, raw[:length])


if __name__ == "__main__":
    unittest.main()
