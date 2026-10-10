"""Installer for other users: input checks, device compatibility, version policy, full flow on the NOR model."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import install_favorites as installer
from monitor_receiver_flash_plan import CAPACITY, ERASE_BYTES, NorModel
from monitor_update_package import split_container
from monitor_usb_receiver_write import classify_receiver, run
from test_receiver_write import NorBackedBridge

OFFICIAL = ROOT / "artifacts/firmware-analysis/20261009-recovered-source/HDZero_Monitor-v1.1.1.bin"
OFFICIAL_120 = ROOT / "artifacts/firmware-analysis/20261009-recovered-source/HDZero_Monitor-v1.2.0.bin"
RECEIVER = ROOT / "artifacts/firmware-analysis/20261010-pscan-v7/favorites-build-v7/receiver-rebuilt.bin"


class FakeProbe:
    """Read-only bridge stand-in for the compatibility check."""

    def __init__(self, ids, contents):
        self.ids, self.contents, self.events, self.target = ids, contents, [], None

    def open(self):
        self.events.append("open")
        return {"simulation": True}

    def select(self, name):
        self.target = name
        self.events.append("select:" + name)

    def jedec_id(self):
        return self.ids[self.target]

    def read(self, address, length):
        return self.contents[self.target][address:address + length]

    def close(self):
        self.events.append("close")


class PolicyTests(unittest.TestCase):
    def test_version_policy(self):
        decide = installer.preimage_decision
        for installed in ("official-1.1.1", "favorites-current", "favorites-previous"):
            for mode in ("favorites", "restore"):
                self.assertIsNone(decide(installed, mode))
        self.assertIn("1.2.0", decide("official-1.2.0", "favorites"))
        self.assertIsNone(decide("official-1.2.0", "favorites", allow_120=True))
        self.assertIn("nothing to uninstall", decide("official-1.2.0", "restore", allow_120=True))
        self.assertIn("interrupted", decide("unknown-block0", "restore"))
        self.assertIsNone(decide("unknown-block0", "restore", recover=True))
        self.assertIsNotNone(decide("unknown-block0", "favorites", allow_120=True))
        self.assertIsNotNone(decide("unknown", "restore", allow_120=True, recover=True))


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not OFFICIAL.exists() or not RECEIVER.exists():
            raise unittest.SkipTest("Official firmware / release receiver fixtures unavailable")
        cls.official = OFFICIAL.read_bytes()
        cls.receiver = RECEIVER.read_bytes()
        cls.config = json.loads((ROOT / "config/favorite-channels.json").read_text(encoding="utf-8"))
        cls.stock, cls.favorites, cls.parts = installer.load_inputs(cls.official, cls.receiver, cls.config)

    def device(self, **overrides):
        ids = dict(installer.EXPECTED_IDS)
        contents = {"5680": self.stock, "fpga": self.parts["fpga"], "8339": self.parts["8339"]}
        for key, value in overrides.items():
            (ids if key.startswith("id_") else contents)[key.split("_", 1)[1]] = value
        return FakeProbe(ids, contents)

    def test_inputs_need_official_and_release_image(self):
        with self.assertRaisesRegex(ValueError, "official"):
            installer.load_inputs(self.official[:-1] + bytes([self.official[-1] ^ 1]), self.receiver, self.config)
        changed = bytearray(self.receiver)
        changed[100] ^= 1
        with self.assertRaisesRegex(ValueError, "receiver"):
            installer.load_inputs(self.official, bytes(changed), self.config)

    def test_compatible_device_passes_and_bus_is_released(self):
        probe = self.device()
        report = installer.check_device(probe, self.parts)
        self.assertTrue(report["compatible"])
        self.assertEqual(probe.events[-1], "close")

    def test_incompatible_devices_are_rejected(self):
        bad_fpga = bytearray(self.parts["fpga"])
        bad_fpga[0x1234] ^= 1
        bad_mstar = bytearray(self.parts["8339"])
        bad_mstar[0xFFFF] ^= 1
        cases = {"receiver id": self.device(id_5680="EF4015"), "fpga id": self.device(id_fpga="EF4017"),
                 "mstar id": self.device(id_8339="C22018"), "fpga data": self.device(c_fpga=bytes(bad_fpga)),
                 "mstar data": self.device(c_8339=bytes(bad_mstar))}
        for label, probe in cases.items():
            with self.subTest(label), self.assertRaises(RuntimeError):
                installer.check_device(probe, self.parts)
            self.assertEqual(probe.events[-1], "close")

    def session(self, array, mode, **options):
        model = NorModel(array)
        with tempfile.TemporaryDirectory() as directory:
            report = run(NorBackedBridge(model), self.stock, self.favorites, mode, Path(directory) / "s",
                         busy_deadlines={"status": 1.0, "program": 1.0, "erase": 1.0}, poll_interval=0,
                         require_known_preimage=True, **options)
        return model, report

    def test_install_and_uninstall_from_official_stock(self):
        model, report = self.session(self.stock, "favorites", execute_write=True)
        self.assertTrue(report["success"], report.get("error"))
        self.assertEqual(report["installed_receiver"], "official-1.1.1")
        self.assertEqual(bytes(model.data), self.favorites)
        model, report = self.session(bytes(model.data), "restore", execute_write=True)
        self.assertTrue(report["success"], report.get("error"))
        self.assertEqual(report["installed_receiver"], "favorites-current")
        self.assertEqual(bytes(model.data), self.stock)

    def test_official_120_needs_explicit_opt_in(self):
        if not OFFICIAL_120.exists():
            self.skipTest("Official 1.2.0 fixture unavailable")
        _, parts = split_container(OFFICIAL_120.read_bytes())
        array = parts["5680"] + b"\xff" * (CAPACITY - len(parts["5680"]))
        self.assertEqual(classify_receiver(array, self.stock, self.favorites), "official-1.2.0")
        model, report = self.session(array, "favorites", execute_write=True)
        self.assertFalse(report["success"])
        self.assertEqual(model.mutations, 0)
        model, report = self.session(array, "favorites", execute_write=True, any_block0_preimage=True)
        self.assertTrue(report["success"], report.get("error"))
        self.assertEqual(bytes(model.data), self.favorites)

    def test_unknown_receiver_is_refused_and_interrupted_state_recoverable(self):
        partial = bytearray(self.favorites)
        partial[:ERASE_BYTES // 2] = b"\xff" * (ERASE_BYTES // 2)  # Like an install interrupted mid-block.
        model, report = self.session(bytes(partial), "restore", execute_write=True)
        self.assertFalse(report["success"])
        self.assertEqual(report["installed_receiver"], "unknown-block0")
        self.assertEqual(model.mutations, 0)
        model, report = self.session(bytes(partial), "restore", execute_write=True, any_block0_preimage=True)
        self.assertTrue(report["success"], report.get("error"))
        self.assertEqual(bytes(model.data), self.stock)
        foreign = bytearray(self.stock)
        foreign[CAPACITY - 1] = 0
        model, report = self.session(bytes(foreign), "favorites", execute_write=True, any_block0_preimage=True)
        self.assertFalse(report["success"])
        self.assertEqual(model.mutations, 0)

    def test_already_installed_is_a_verified_noop(self):
        model, report = self.session(self.favorites, "favorites", execute_write=True)
        self.assertTrue(report["success"], report.get("error"))
        self.assertEqual(report["plan_operations"], 0)
        self.assertEqual(model.mutations, 0)


if __name__ == "__main__":
    unittest.main()
