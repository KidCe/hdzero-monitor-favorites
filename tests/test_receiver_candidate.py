"""Tamper/reproducibility guards for a decoded, offline-only firmware experiment."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from monitor_receiver_candidate import make_candidate, verify_candidate, digest


class CandidateInputGuards(unittest.TestCase):
    def test_unknown_image_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "pinned"):
            make_candidate(bytes(62003), {"channels": []})


class CandidateFixtureGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = ROOT / "artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin"
        if not fixture.exists():
            raise unittest.SkipTest("Private, hash-pinned device fixture is not available")
        cls.stock = fixture.read_bytes()
        cls.config = json.loads((ROOT / "config/favorite-channels.json").read_text(encoding="utf-8"))

    def test_candidate_is_deterministic_and_original_is_preserved(self):
        before = digest(self.stock)
        candidate, manifest = make_candidate(self.stock, self.config)
        self.assertEqual(digest(self.stock), before)
        self.assertEqual(manifest["candidate_sha256"], "0083c42f11e22154168bcac949acccf32b0df709af23a9a1e430b0ab278cbd33")
        self.assertEqual(manifest["changed_original_bytes"], 74)
        self.assertEqual(manifest["extension"]["bytes"], 548)
        self.assertEqual(manifest["display_labels"][:2], ["P1 L6 HDZ", "P2 L7 HDZ"])
        self.assertFalse(manifest["hardware_access"])
        self.assertFalse(manifest["installable_update"])
        self.assertEqual(verify_candidate(self.stock, candidate, manifest, self.config), manifest)

    def test_forged_hash_does_not_authorize_a_tampered_candidate(self):
        candidate, manifest = make_candidate(self.stock, self.config)
        for offset in (0, 0x0692, 62003, len(candidate) - 1):
            with self.subTest(offset=offset):
                changed = bytearray(candidate)
                changed[offset] ^= 1
                forged = copy.deepcopy(manifest)
                forged["candidate_sha256"] = digest(changed)
                with self.assertRaisesRegex(ValueError, "regenerated"):
                    verify_candidate(self.stock, bytes(changed), forged, self.config)

    def test_changed_manifest_or_configuration_is_rejected(self):
        candidate, manifest = make_candidate(self.stock, self.config)
        changed = copy.deepcopy(manifest)
        changed["analysis_only"] = False
        with self.assertRaisesRegex(ValueError, "regenerated"):
            verify_candidate(self.stock, candidate, changed, self.config)
        changed_config = copy.deepcopy(self.config)
        changed_config["channels"].reverse()
        with self.assertRaisesRegex(ValueError, "regenerated"):
            verify_candidate(self.stock, candidate, manifest, changed_config)


if __name__ == "__main__":
    unittest.main()
