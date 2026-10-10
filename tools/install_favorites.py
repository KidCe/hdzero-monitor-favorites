"""Install or uninstall the HDZero Monitor Favorites receiver firmware over the Monitor's USB port.

Only the DM5680 receiver flash is written (its first 64 KiB block); FPGA and MStar are only read.
Every run first checks, read-only, that this is a compatible Monitor:
  * exactly one CH341 (1A86:5512), HDZero Programmer closed, pinned WCH DLL
  * flash IDs EF4014 (receiver), EF4018 (FPGA), EF4018 (MStar)
  * the first 64 KiB of FPGA and MStar equal official 1.1.1 (identical in 1.2.0)
  * receiver status registers 00/00 and two identical full receiver reads
  * the installed receiver is official 1.1.1 or a known Favorites build
Without --execute nothing is written. A copy of the installed receiver is saved in the log directory.
Windows, 64-bit Python. Use at your own risk; see README.md.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from monitor_usb_probe import Bridge
from monitor_update_package import FAVORITES_SHA256, OFFICIAL_SHA256, digest, split_container
from monitor_receiver_flash_plan import BACKUPS, CAPACITY, TARGET, projected_favorites
from monitor_usb_receiver_write import ReceiverWriteBridge, run

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = {"5680": "EF4014", "fpga": "EF4018", "8339": "EF4018"}
COMPARE_BYTES = 65536  # FPGA/MStar prefix compared with official 1.1.1; device-specific MStar data starts far later
MODES = {"install": "favorites", "uninstall": "restore"}
# Release bundle layout: these files sit in <bundle>/files and are used when no path is given.
BUNDLED = {"dll": "CH341DLLA64.DLL", "official": "HDZero_Monitor-v1.1.1-official.bin",
           "receiver": "receiver-dm5680-decoded-v1.1.2-favorites.bin"}


def bundled_path(root, key):
    """Path of a file shipped in the release bundle, or None when running from the repository."""
    path = root / "files" / BUNDLED[key]
    return path if path.is_file() else None


def load_inputs(official_bytes, receiver_bytes, config):
    """Offline checks. Returns the stock receiver array, the Favorites array and the official parts."""
    if digest(official_bytes) != OFFICIAL_SHA256:
        raise ValueError("--official must be the official HDZero Monitor 1.1.1 update file (HDZero_Monitor.bin, release v1.1.1)")
    _, parts = split_container(official_bytes)
    stock = parts[TARGET] + b"\xff" * (CAPACITY - len(parts[TARGET]))
    if digest(stock) != BACKUPS[TARGET][1]:
        raise ValueError("Official receiver payload does not give the expected stock flash content")
    if digest(receiver_bytes) != FAVORITES_SHA256:
        raise ValueError("--receiver is not the Favorites receiver image this installer was built for")
    favorites = projected_favorites(stock, receiver_bytes, config)  # Also regenerates and compares the image.
    return stock, favorites, parts


def check_device(bridge, parts):
    """Read-only compatibility check of all three flash chips. Always releases the bus."""
    report = {"compatible": False}
    try:
        report["usb"] = bridge.open()
        for name in ("5680", "fpga", "8339"):
            bridge.select(name)
            first, second = bridge.jedec_id(), bridge.jedec_id()
            if first != second or first != EXPECTED_IDS[name]:
                raise RuntimeError(f"{name} flash ID {first}/{second}, expected {EXPECTED_IDS[name]}: not a compatible Monitor")
            entry = {"jedec_id": first}
            if name != TARGET:
                data = b"".join(bridge.read(address, 1024) for address in range(0, COMPARE_BYTES, 1024))
                entry["first_64k_equals_official"] = data == parts[name][:COMPARE_BYTES]
                if not entry["first_64k_equals_official"]:
                    raise RuntimeError(f"{name} firmware differs from official 1.1.1/1.2.0: not a compatible Monitor")
            report[name] = entry
        report["compatible"] = True
    finally:
        bridge.close()
    return report


def preimage_decision(installed, mode, allow_120=False, recover=False):
    """Return None if the installed receiver may be replaced in this mode ("favorites"/"restore"), else the reason."""
    if installed in ("official-1.1.1", "favorites-current", "favorites-previous"):
        return None  # Supported; an already-installed target gives an empty plan.
    if installed == "official-1.2.0":
        if mode == "restore":
            return "The Monitor runs official 1.2.0, not Favorites: nothing to uninstall."
        if not allow_120:
            return ("The Monitor runs official 1.2.0. This build is based on 1.1.1; installing replaces the 1.2.0 "
                    "receiver (FPGA/MStar of 1.2.0 are identical to 1.1.1). Re-run with --allow-replace-1.2.0, "
                    "or install official 1.1.1 with the HDZero Programmer first.")
        return None
    if installed == "unknown-block0":
        if not recover:
            return ("Unrecognized receiver firmware. Only if a previous installation was interrupted, run "
                    "--mode uninstall --recover-interrupted to restore the official 1.1.1 receiver.")
        return None
    return f"Receiver flash content not recognized ({installed}): refusing."


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dll", type=Path, default=bundled_path(ROOT, "dll"),
                        help="CH341DLLA64.DLL (SHA-256 pinned); default: the copy in the release bundle")
    parser.add_argument("--official", type=Path, default=bundled_path(ROOT, "official"),
                        help="Official HDZero Monitor 1.1.1 update file; default: the copy in the release bundle")
    parser.add_argument("--receiver", type=Path, default=bundled_path(ROOT, "receiver"),
                        help="Favorites receiver image (receiver-dm5680-decoded-*.bin); also used to recognize installed builds")
    parser.add_argument("--mode", choices=sorted(MODES), default="install")
    parser.add_argument("--execute", action="store_true", help="Actually write. Without it: checks and dry run only")
    parser.add_argument("--yes", action="store_true", help="Do not ask for typed confirmation")
    parser.add_argument("--allow-replace-1.2.0", dest="allow_120", action="store_true",
                        help="Allow replacing an official 1.2.0 receiver")
    parser.add_argument("--recover-interrupted", dest="recover", action="store_true",
                        help="Allow replacing an unrecognized receiver firmware area (after an interrupted write)")
    parser.add_argument("--log-dir", type=Path, default=Path("install-logs"))
    args = parser.parse_args(argv)
    missing = [name for name in ("dll", "official", "receiver") if getattr(args, name) is None]
    if missing:
        parser.error("missing " + ", ".join("--" + name for name in missing)
                     + " (not running from a release bundle with a files/ folder)")
    mode = MODES[args.mode]

    config = json.loads((ROOT / "config/favorite-channels.json").read_text(encoding="utf-8"))
    try:
        stock, favorites, parts = load_inputs(args.official.read_bytes(), args.receiver.read_bytes(), config)
    except (OSError, ValueError) as error:
        print(f"Input check failed: {error}", file=sys.stderr)
        return 2
    print("Input files OK: official 1.1.1 and Favorites image verified.")

    session = args.log_dir / (datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + f"-{args.mode}")
    session.mkdir(parents=True, exist_ok=False)
    try:
        compat = check_device(Bridge(args.dll), parts)
    except Exception as error:
        (session / "compatibility.json").write_text(json.dumps({"compatible": False, "error": str(error)}, indent=2))
        print(f"Compatibility check failed: {error}", file=sys.stderr)
        return 3
    (session / "compatibility.json").write_text(json.dumps(compat, indent=2) + "\n", encoding="utf-8")
    print("Monitor compatible: flash IDs and FPGA/MStar firmware match official 1.1.1.")

    unlock = args.allow_120 or args.recover
    dry = run(ReceiverWriteBridge(args.dll), stock, favorites, mode, session / "dry-run",
              require_known_preimage=True, any_block0_preimage=unlock)
    installed = dry.get("installed_receiver", "not read")
    print(f"Installed receiver: {installed}")
    # The friendlier per-version message takes precedence over the session's generic refusal.
    reason = preimage_decision(installed, mode, args.allow_120, args.recover) if "installed_receiver" in dry else None
    if not dry["success"] or reason:
        print(f"Stopped before writing: {reason or dry.get('error')}", file=sys.stderr)
        return 4
    if dry["plan_operations"] == 0:
        print("Nothing to do: the requested firmware is already installed.")
        return 0
    print(f"Plan: erase receiver block 0 and program {dry['plan_program_pages']} pages "
          f"({'install Favorites' if mode == 'favorites' else 'restore official 1.1.1 receiver'}).")
    if not args.execute:
        print(f"Dry run complete, nothing written. Log and receiver backup: {session}. Re-run with --execute to write.")
        return 0
    word = args.mode.upper()
    if not args.yes:
        print("Keep the Monitor powered and connected until the tool finishes (about one minute).")
        if input(f"Type {word} to write the receiver flash: ").strip() != word:
            print("Cancelled, nothing written.")
            return 1
    result = run(ReceiverWriteBridge(args.dll), stock, favorites, mode, session / "write", execute_write=True,
                 require_known_preimage=True, any_block0_preimage=unlock)
    if not result["success"]:
        print(f"WRITE FAILED: {result.get('error')}", file=sys.stderr)
        if result.get("mutation_started"):
            print("Do not power off. Run: install_favorites.py --mode uninstall --recover-interrupted --execute "
                  "(same --dll/--official/--receiver) to restore the official 1.1.1 receiver.", file=sys.stderr)
        return 5
    print(f"Done and verified ({result['after_sha256'][:12]}...). Power-cycle the Monitor. Log: {session}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
