"""Receiver-only protocol simulation, interruption and exact restoration checks."""
import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from monitor_receiver_flash_plan import (CAPACITY, ERASE_BYTES, FlashPlan, Operation, NorModel,
                                        make_plan, projected_favorites, simulate, validate_plan,
                                        verified_backups)


class ReceiverFlashPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = ROOT / "artifacts/device-backups/20261009-usb-01"
        receiver = ROOT / "artifacts/firmware-analysis/20261010-pscan-v7/favorites-build-v7/receiver-rebuilt.bin"
        if not (directory / "manifest.json").exists() or not receiver.exists():
            raise unittest.SkipTest("Private verified backup/source fixtures unavailable")
        cls.backups = verified_backups(directory)
        cls.stock = cls.backups["5680"]
        cls.receiver = receiver.read_bytes()
        cls.config = json.loads((ROOT / "config/favorite-channels.json").read_text(encoding="utf-8"))
        cls.favorites = projected_favorites(cls.stock, cls.receiver, cls.config)
        cls.plan = make_plan("favorites", cls.stock, cls.favorites, cls.stock)

    def test_apply_and_restore_compare_entire_arrays(self):
        model = NorModel(self.stock)
        result = simulate(self.plan, model)
        self.assertTrue(result["success"])
        self.assertEqual(bytes(model.data), self.favorites)
        self.assertEqual(result["simulated_program_pages"], 245)
        self.assertEqual(model.data[ERASE_BYTES:], self.stock[ERASE_BYTES:])
        self.assertTrue(model.closed and model.released)
        restore = make_plan("restore", self.stock, self.favorites, bytes(model.data))
        restored = NorModel(bytes(model.data))
        self.assertTrue(simulate(restore, restored)["success"])
        self.assertEqual(bytes(restored.data), self.stock)
        self.assertEqual(restored.programs, 243)

    def test_partial_program_interruption_can_restore_exact_backup(self):
        model = NorModel(self.stock, fail_program=20)
        result = simulate(self.plan, model)
        self.assertFalse(result["success"])
        self.assertTrue(result["mutation_started"])
        self.assertTrue(model.closed)
        partial = bytes(model.data)
        self.assertNotEqual(partial, self.stock)
        self.assertNotEqual(partial, self.favorites)
        restore = make_plan("restore", self.stock, self.favorites, partial)
        resumed = NorModel(partial)
        self.assertTrue(simulate(restore, resumed)["success"])
        self.assertEqual(bytes(resumed.data), self.stock)

    def test_wrong_identity_stops_before_mutation(self):
        model = NorModel(self.stock, wrong_identity=True)
        result = simulate(self.plan, model)
        self.assertFalse(result["success"])
        self.assertFalse(result["mutation_started"])
        self.assertEqual(bytes(model.data), self.stock)
        self.assertTrue(model.closed)

    def test_stale_preimage_stops_before_mutation(self):
        changed = bytearray(self.stock)
        changed[123] ^= 1
        model = NorModel(changed)
        result = simulate(self.plan, model)
        self.assertFalse(result["success"])
        self.assertFalse(result["mutation_started"])
        self.assertIn("preimage", result["error"])

    def test_protection_and_missing_wel_stop_before_erase(self):
        for options in ({"write_protected": True}, {"wel_missing": True}):
            with self.subTest(options=options):
                model = NorModel(self.stock, **options)
                result = simulate(self.plan, model)
                self.assertFalse(result["success"])
                self.assertFalse(result["mutation_started"])
                self.assertEqual(bytes(model.data), self.stock)

    def test_busy_timeout_stops_programming_and_records_incomplete_state(self):
        model = NorModel(self.stock, stuck_busy=True)
        result = simulate(self.plan, model, poll_budget=5)
        self.assertFalse(result["success"])
        self.assertIn("BUSY", result["error"])
        self.assertEqual(model.mutations, 1)
        self.assertEqual(model.programs, 0)
        self.assertTrue(model.closed)

    def test_corrupted_page_is_detected_before_next_page(self):
        model = NorModel(self.stock, corrupt_program=7)
        result = simulate(self.plan, model)
        self.assertFalse(result["success"])
        self.assertIn("Page readback", result["error"])
        self.assertEqual(model.programs, 7)
        self.assertTrue(model.closed)

    def test_restore_of_stock_is_a_verified_noop(self):
        plan = make_plan("restore", self.stock, self.favorites, self.stock)
        self.assertEqual(plan.operations, ())
        model = NorModel(self.stock)
        self.assertTrue(simulate(plan, model)["success"])
        self.assertEqual(model.mutations, 0)

    def test_changed_tail_and_unknown_apply_state_are_rejected(self):
        for offset in (10, ERASE_BYTES, CAPACITY - 1):
            changed = bytearray(self.stock)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                make_plan("favorites", self.stock, self.favorites, bytes(changed))
            if offset >= ERASE_BYTES:
                with self.assertRaises(ValueError):
                    make_plan("restore", self.stock, self.favorites, bytes(changed))

    def test_tampered_operation_order_data_and_addresses_are_rejected(self):
        operations = self.plan.operations
        variants = (operations[1:], tuple(reversed(operations)), operations + (Operation("erase", ERASE_BYTES),),
                    (operations[0], Operation("program", 1, operations[1].data)) + operations[2:],
                    (operations[0], Operation("program", 0, b"\xff" * 256)) + operations[2:])
        for altered in variants:
            with self.subTest(first=altered[0].kind), self.assertRaises(ValueError):
                simulate(replace(self.plan, operations=altered), NorModel(self.stock))

    def test_unrecognized_source_candidate_and_arrays_are_rejected(self):
        changed = bytearray(self.receiver)
        changed[-1] ^= 1
        with self.assertRaises(ValueError):
            projected_favorites(self.stock, bytes(changed), self.config)
        for array in (self.stock[:-1], bytes(CAPACITY)):
            with self.assertRaises(ValueError):
                make_plan("restore", array, self.favorites, self.stock)

    def test_non_simulated_transport_is_rejected(self):
        class MustNotRun:
            def transfer(self, command):
                raise AssertionError("Transport must not be invoked")
        with self.assertRaises(TypeError):
            simulate(self.plan, MustNotRun())

    def test_malformed_mutations_never_escape_first_block_or_page(self):
        commands = (b"\xc7", b"\x01\x00", b"\xd8\x01\x00\x00",
                    b"\x02\x00\x00\x01" + bytes(256), b"\x02\x00\xff\x00" + bytes(257))
        for command in commands:
            with self.subTest(opcode=command[0]):
                model = NorModel(self.stock)
                model.transfer(b"\x06")
                with self.assertRaises(ValueError):
                    model.transfer(command)
                self.assertEqual(model.mutations, 0)
                self.assertEqual(bytes(model.data), self.stock)


if __name__ == "__main__":
    unittest.main()
