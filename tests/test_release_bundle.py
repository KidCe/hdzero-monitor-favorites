"""All-in-one release bundle: pinned inputs, complete tool closure, provenance, launchers, working defaults."""
import hashlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_release_bundle as bundle

OFFICIAL = ROOT / "artifacts/firmware-analysis/20261009-recovered-source/HDZero_Monitor-v1.1.1.bin"
RECEIVER = ROOT / "artifacts/firmware-analysis/20261010-pscan-v7/favorites-build-v7/receiver-rebuilt.bin"
UPDATE = ROOT / "dist/v1.1.2-favorites/HDZero_Monitor-v1.1.2-favorites.bin"
DLLS = sorted(Path(r"C:\Windows\System32\DriverStore\FileRepository").glob("ch341wdm.inf_amd64_*/CH341DLLA64.DLL"))


class ReleaseBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (OFFICIAL.exists() and RECEIVER.exists() and UPDATE.exists() and DLLS):
            raise unittest.SkipTest("Official firmware, release build or installed WCH DLL unavailable")
        cls.dll = next((p for p in DLLS if bundle.sha256(p) == bundle.EXPECTED_DLL_SHA256), None)
        if cls.dll is None:
            raise unittest.SkipTest("Pinned WCH DLL not installed")
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder, cls.archive = bundle.build(OFFICIAL, RECEIVER, cls.dll, UPDATE, Path(cls.temp.name))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_contents_and_checksums(self):
        expected = {"files/" + name for name in bundle.BUNDLED.values()} | {
            f"files/{bundle.UPDATE_FILE}", "README-INSTALL.md", "THIRD-PARTY.md", "LICENSE", "NOTICE.md",
            "SHA256SUMS.txt", "config/favorite-channels.json", "1-check.cmd", "2-install.cmd", "3-uninstall.cmd"}
        present = {p.relative_to(self.folder).as_posix() for p in self.folder.rglob("*") if p.is_file()}
        self.assertTrue(expected <= present, expected - present)
        for line in (self.folder / "SHA256SUMS.txt").read_text().splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((self.folder / name).read_bytes()).hexdigest(), digest, name)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual({n.split("/", 1)[1] for n in archive.namelist()}, present)

    def test_tool_closure_and_bundled_defaults_work(self):
        tools = {p.stem for p in (self.folder / "tools").glob("*.py")}
        self.assertTrue({"install_favorites", "monitor_usb_probe", "monitor_usb_receiver_write",
                         "monitor_receiver_flash_plan", "monitor_receiver_candidate"} <= tools)
        self.assertNotIn("make_release_bundle", tools)
        script = ("import sys; sys.path.insert(0, sys.argv[1]); import install_favorites as i; "
                  "print(all(i.bundled_path(i.ROOT, k) for k in i.BUNDLED))")
        result = subprocess.run([sys.executable, "-I", "-c", script, str(self.folder / "tools")],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.stdout.strip(), "True", result.stderr)
        result = subprocess.run([sys.executable, str(self.folder / "tools" / "install_favorites.py"), "--help"],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_provenance_and_launchers(self):
        notes = (self.folder / "THIRD-PARTY.md").read_text(encoding="utf-8")
        for text in ("hd-zero/monitor/releases/tag/v1.1.1", "WCH", bundle.OFFICIAL_SHA256, bundle.EXPECTED_DLL_SHA256):
            self.assertIn(text, notes)
        install = (self.folder / "2-install.cmd").read_bytes()
        self.assertIn(b"\r\n", install)
        self.assertIn(b"tools\\install_favorites.py --execute", install)
        self.assertIn(b"--mode uninstall --execute", (self.folder / "3-uninstall.cmd").read_bytes())
        self.assertNotIn(b"--execute", (self.folder / "1-check.cmd").read_bytes())

    def test_wrong_inputs_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            for args in ((RECEIVER, RECEIVER, self.dll, UPDATE), (OFFICIAL, OFFICIAL, self.dll, UPDATE),
                         (OFFICIAL, RECEIVER, RECEIVER, UPDATE), (OFFICIAL, RECEIVER, self.dll, OFFICIAL)):
                with self.subTest(args=[a.name for a in args]), self.assertRaises(ValueError):
                    bundle.build(*args, Path(directory))


if __name__ == "__main__":
    unittest.main()
