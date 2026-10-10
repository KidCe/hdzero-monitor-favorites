"""Assemble the all-in-one release bundle (installer + all required files) as a folder and ZIP.

Every bundled file is checked against its pinned SHA-256 before it is copied. The bundle contains
third-party files (official HDZero firmware, WCH CH341 DLL); THIRD-PARTY.md records their origin.
"""

import argparse
import ast
import hashlib
import shutil
import zipfile
from pathlib import Path

from install_favorites import BUNDLED
from monitor_receiver_decode import DECODE_TABLE
from monitor_update_package import FAVORITES_SHA256, OFFICIAL_SHA256, split_container
from monitor_usb_probe import EXPECTED_DLL_SHA256

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.1.2"
NAME = f"HDZero-Monitor-Favorites-v{VERSION}"
UPDATE_FILE = f"HDZero_Monitor-v{VERSION}-favorites.bin"
OFFICIAL_URL = "https://github.com/hd-zero/monitor/releases/tag/v1.1.1"

LAUNCHERS = {
    "1-check.cmd": ("Compatibility check and dry run. Nothing is written.", ""),
    "2-install.cmd": ("Install the Favorites firmware (asks for confirmation).", " --execute"),
    "3-uninstall.cmd": ("Restore the official 1.1.1 receiver firmware (asks for confirmation).", " --mode uninstall --execute"),
}
LAUNCHER = """@echo off
rem {comment}
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY goto nopython
rem The Microsoft Store "python" placeholder fails this check, as do 32-bit or old versions.
%PY% -c "import sys, struct; sys.exit(0 if sys.version_info >= (3, 11) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if errorlevel 1 goto nopython
%PY% tools\\install_favorites.py{arguments} %*
echo.
pause
exit /b
:nopython
echo 64-bit Python 3.11 or newer is required: https://www.python.org/downloads/
echo During installation tick "Add python.exe to PATH", then run this file again.
pause
exit /b 1
"""

README = f"""# HDZero Monitor Favorites {VERSION} — installer package

Unofficial community firmware for the HDZero Monitor (based on official 1.1.1). Adds a Favorites band
P1–P8 = L6, L7, R1, R2, F2, F4, R7, R8, shows `P1 L6 HDZ`, includes the favorites in the scan and
starts the scan with a shorter long press. Project and full documentation: see the GitHub repository.

## Requirements

- Windows PC, **64-bit Python 3.11+** (https://www.python.org/downloads/, tick "Add python.exe to PATH")
- WCH CH341 USB driver installed (it is installed together with the HDZero Programmer)
- HDZero Programmer **closed**, only the Monitor connected by USB (no other CH341 adapter), Monitor powered

## Steps

1. Double-click **`1-check.cmd`**. It checks the files, checks that your Monitor and its installed firmware
   are compatible, reads the receiver twice and shows the plan. Nothing is written.
2. If the check passes, double-click **`2-install.cmd`** and type `INSTALL` when asked. Keep the Monitor
   powered and connected until it reports success (about one minute), then power-cycle the Monitor.
3. To go back, double-click **`3-uninstall.cmd`** and type `UNINSTALL`.

Every run writes a log and a copy of the previous receiver firmware to `install-logs/`. Keep it.
If a write is ever interrupted, do not power off; run in a terminal from this folder:
`python tools\\install_favorites.py --mode uninstall --recover-interrupted --execute`.

The installer only writes the receiver flash. It refuses unknown hardware or firmware states; an official
1.2.0 receiver is only replaced with `--allow-replace-1.2.0`. Alternative without compatibility checks:
`files/{UPDATE_FILE}` with the HDZero Programmer (*Monitor* tab → *Load Local Firmware*); not tested by us.

Use at your own risk. Not affiliated with HDZero. See LICENSE, NOTICE.md and THIRD-PARTY.md.
"""


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tool_closure(start="install_favorites"):
    """Local tool modules imported (transitively) by the installer."""
    seen, pending = set(), [start]
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        tree = ast.parse((ROOT / "tools" / f"{name}.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
            pending += [module for module in modules if (ROOT / "tools" / f"{module}.py").is_file()]
    return sorted(seen)


def check_inputs(official, receiver, dll, update):
    if sha256(official) != OFFICIAL_SHA256:
        raise ValueError("Official file is not HDZero Monitor 1.1.1")
    if sha256(receiver) != FAVORITES_SHA256:
        raise ValueError("Receiver image is not the pinned Favorites build")
    if sha256(dll) != EXPECTED_DLL_SHA256:
        raise ValueError("CH341DLLA64.DLL differs from the pinned WCH/HDZero Programmer copy")
    _, base = split_container(official.read_bytes())
    _, mine = split_container(update.read_bytes())
    if mine["fpga"] != base["fpga"] or mine["8339"] != base["8339"]:
        raise ValueError("Update file FPGA/MStar parts differ from official 1.1.1")
    if hashlib.sha256(mine["5680"].translate(DECODE_TABLE)).hexdigest() != FAVORITES_SHA256:
        raise ValueError("Update file receiver part is not the pinned Favorites build")


def third_party(official, dll):
    return f"""# Third-party files in this package

| File | Origin | SHA-256 |
|---|---|---|
| `files/{BUNDLED['official']}` | Official HDZero Monitor firmware **v1.1.1**, unmodified, downloaded as `HDZero_Monitor.bin` from {OFFICIAL_URL}. Used by the installer as the reference for compatibility checks and for restoring the official receiver. Rights: HDZero (no license published). | `{sha256(official)}` |
| `files/{BUNDLED['dll']}` | WCH (Nanjing Qinheng Microelectronics) CH341 interface DLL, x64, unmodified. Byte-identical to the copy shipped with the HDZero Programmer (https://github.com/hd-zero/hdzero-programmer) and to the copy installed by the WCH CH341 driver. Rights: WCH. | `{sha256(dll)}` |
| `files/{BUNDLED['receiver']}` | Modified DM5680 receiver firmware built by this project from the official 1.1.1 receiver (decoded form). | `{FAVORITES_SHA256}` |
| `files/{UPDATE_FILE}` | Official 1.1.1 update file with only the receiver part replaced by the Favorites build (FPGA and MStar parts unchanged). | see SHA256SUMS.txt |

These files are redistributed for convenience so the package works offline. If a rights holder objects,
they will be removed; the installer also accepts the files from their original sources (`--official`, `--dll`).
"""


def build(official, receiver, dll, update, output):
    check_inputs(official, receiver, dll, update)
    folder = output / NAME
    if folder.exists() or (output / f"{NAME}.zip").exists():
        raise FileExistsError(f"{folder} or its ZIP already exists")
    (folder / "files").mkdir(parents=True)
    (folder / "tools").mkdir()
    (folder / "config").mkdir()
    shutil.copyfile(official, folder / "files" / BUNDLED["official"])
    shutil.copyfile(receiver, folder / "files" / BUNDLED["receiver"])
    shutil.copyfile(dll, folder / "files" / BUNDLED["dll"])
    shutil.copyfile(update, folder / "files" / UPDATE_FILE)
    for module in tool_closure():
        shutil.copyfile(ROOT / "tools" / f"{module}.py", folder / "tools" / f"{module}.py")
    shutil.copyfile(ROOT / "config" / "favorite-channels.json", folder / "config" / "favorite-channels.json")
    for name in ("LICENSE", "NOTICE.md"):
        shutil.copyfile(ROOT / name, folder / name)
    (folder / "README-INSTALL.md").write_text(README, encoding="utf-8")
    (folder / "THIRD-PARTY.md").write_text(third_party(official, dll), encoding="utf-8")
    for name, (comment, arguments) in LAUNCHERS.items():
        (folder / name).write_bytes(LAUNCHER.format(comment=comment, arguments=arguments).replace("\n", "\r\n").encode("ascii"))
    files = sorted(p for p in folder.rglob("*") if p.is_file())
    (folder / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(p)}  {p.relative_to(folder).as_posix()}\n" for p in files), encoding="ascii")
    archive = output / f"{NAME}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            bundle.write(path, f"{NAME}/{path.relative_to(folder).as_posix()}")
    return folder, archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--update-file", type=Path, required=True, help="Release container for the HDZero Programmer")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    folder, archive = build(args.official, args.receiver, args.dll, args.update_file, args.output_dir)
    print(f"Bundle: {folder}\nZIP:    {archive} ({archive.stat().st_size:,} bytes, SHA-256 {sha256(archive)})")


if __name__ == "__main__":
    main()
