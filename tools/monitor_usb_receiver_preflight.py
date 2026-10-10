"""Receiver-only read preflight for a later, explicitly started USB session.

Imports perform no hardware access. The CLI reads identity, status, SFDP and two
complete receiver arrays; it contains no flash mutation or write-enable opcode.
Target selection still actively hands the board bus to the CH341 bridge.
"""

import argparse
import ctypes
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from monitor_usb_probe import Bridge, require_success
from monitor_receiver_flash_plan import (CAPACITY, ERASE_BYTES, JEDEC, READ_BYTES,
                                        TARGET, projected_favorites, verified_backups)
from monitor_update_package import digest


class ReceiverReadBridge(Bridge):
    def select(self, name):
        if name != TARGET:
            raise ValueError("Receiver preflight cannot select another flash target")
        super().select(name)

    def _diagnostic_transaction(self, command):
        # Validate before touching native functions. Only read-only commands are admitted.
        valid = command in (b"\x05\x00", b"\x35\x00")
        if len(command) >= 6 and command[0] == 0x5a:
            address = int.from_bytes(command[1:4], "big")
            length = len(command) - 5
            valid = command[4] == 0 and not any(command[5:]) and address + length <= 256
        if not valid or not self.opened or not self.routed:
            raise ValueError("Diagnostic command is outside the reviewed read-only scope")
        buffer = ctypes.create_string_buffer(command, len(command))
        require_success(self.set_stream(0, 0x81), "Set diagnostic SPI stream")
        try:
            require_success(self.transfer(0, 0x80, len(command), buffer), "Read flash diagnostic")
            return buffer.raw
        finally:
            require_success(self.set_stream(0, 0x80), "Restore diagnostic stream")

    def status(self):
        return {"sr1": self._diagnostic_transaction(b"\x05\x00")[1],
                "sr2": self._diagnostic_transaction(b"\x35\x00")[1]}

    def sfdp(self):
        return self._diagnostic_transaction(b"\x5a\x00\x00\x00\x00" + bytes(256))[5:]

    def read(self, address, length):
        if type(address) is not int or type(length) is not int or address < 0 or length < 1 or address + length > CAPACITY:
            raise ValueError("Receiver read exceeds the full-array bound")
        return super().read(address, length)


def status_summary(values):
    sr1, sr2 = values["sr1"], values["sr2"]
    return {"sr1_hex": f"{sr1:02X}", "sr2_hex": f"{sr2:02X}",
            "busy": bool(sr1 & 1), "wel": bool(sr1 & 2),
            "sr1_protection_or_other_bits": f"{sr1 & 0xfc:02X}",
            "sr2_cmp": bool(sr2 & 0x40), "sr2_suspend": bool(sr2 & 0x80),
            "sr2_quad_enable": bool(sr2 & 2),
            "interpretation": "Winbond W25Q80 family hypothesis; exact chip variant is not established by JEDEC alone"}


def acquire(bridge, stock, favorites, output, deadline_seconds=120):
    """Bridge injection lets tests validate lifecycle/errors without loading a DLL."""
    if type(deadline_seconds) is not int or not 1 <= deadline_seconds <= 600:
        raise ValueError("Read-session deadline must be 1..600 seconds")
    output.mkdir(parents=True, exist_ok=False)
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "success": False,
              "hardware_access": isinstance(bridge, ReceiverReadBridge),
              "simulation": not isinstance(bridge, ReceiverReadBridge),
              "session_deadline_seconds": deadline_seconds,
              "flash_mutation_commands_implemented": False, "flash_targets_selected": [TARGET],
              "independent_recovery_validated": False, "ready_for_device_use": False,
              "scope": "Read-only array/status/SFDP acquisition; GPIO bus handover is active"}
    report_path = output / "preflight.json"

    def save():
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    save()
    deadline = time.monotonic() + deadline_seconds

    def check_deadline():
        if time.monotonic() >= deadline:
            raise TimeoutError("Receiver read-session deadline exceeded")

    try:
        check_deadline()
        report["usb"] = bridge.open()
        check_deadline()
        bridge.select(TARGET)
        first, second = bridge.jedec_id(), bridge.jedec_id()
        if first != JEDEC or second != JEDEC:
            raise RuntimeError("Receiver identity is unexpected or unstable")
        report["jedec_id"] = first
        check_deadline()
        start_status = bridge.status()
        report["start_status"] = status_summary(start_status)
        if start_status["sr1"] & 1 or start_status["sr2"] & 0x80:
            raise RuntimeError("Receiver reports BUSY or suspended operation; stop the read session")
        sfdp = bridge.sfdp()
        repeated_sfdp = bridge.sfdp()
        check_deadline()
        if len(sfdp) != 256 or sfdp != repeated_sfdp:
            raise RuntimeError("SFDP returned an unexpected length or unstable bytes")
        (output / "sfdp.bin").write_bytes(sfdp)
        report["sfdp"] = {"bytes": len(sfdp), "sha256": digest(sfdp), "signature_valid": sfdp[:4] == b"SFDP",
                          "header_hex": sfdp[:16].hex(), "parameters_interpreted": False}
        # A missing SFDP signature is retained as evidence, not converted into write eligibility.
        passes = []
        for number in (1, 2):
            partial = output / f"5680-current-pass{number}.partial"
            with partial.open("xb") as stream:
                for address in range(0, CAPACITY, READ_BYTES):
                    check_deadline()
                    data = bridge.read(address, min(READ_BYTES, CAPACITY - address))
                    if len(data) != min(READ_BYTES, CAPACITY - address):
                        raise RuntimeError(f"Short array read at {address:#x}")
                    stream.write(data)
            final = output / f"5680-current-pass{number}.bin"
            partial.rename(final)
            data = final.read_bytes()
            passes.append(data)
            report.setdefault("passes", []).append({"file": final.name, "bytes": len(data), "sha256": digest(data)})
            save()
        if passes[0] != passes[1]:
            raise RuntimeError("Complete receiver acquisition passes differ")
        current = passes[0]
        end_status = bridge.status()
        check_deadline()
        report["end_status"] = status_summary(end_status)
        if end_status != start_status or end_status["sr1"] & 1 or end_status["sr2"] & 0x80:
            raise RuntimeError("Receiver status changed during acquisition")
        classification = "stock" if current == stock else "favorites_v4" if current == favorites else \
            "unknown_first_block" if current[ERASE_BYTES:] == stock[ERASE_BYTES:] else "unknown_outside_first_block"
        report.update(full_passes_equal=True, image_classification=classification,
                      stock_preimage_confirmed=current == stock,
                      outside_first_block_equal=current[ERASE_BYTES:] == stock[ERASE_BYTES:],
                      compared_baseline_sha256=digest(stock), success=True)
    except (RuntimeError, ValueError, OSError) as error:
        report["error"] = str(error)
    finally:
        try:
            bridge.close()
            report["cleanup_success"] = True
        except Exception as error:
            report.update(cleanup_success=False, cleanup_error=str(error), success=False)
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--backups", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--deadline-seconds", type=int, default=120)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError("Use a new preflight directory")
    stock = verified_backups(args.backups)[TARGET]
    config = json.loads((Path(__file__).resolve().parents[1] / "config/favorite-channels.json").read_text(encoding="utf-8"))
    favorites = projected_favorites(stock, args.receiver.read_bytes(), config)
    # This is the sole construction point of a native bridge. It is not invoked by imports/tests.
    bridge = ReceiverReadBridge(args.dll)
    report = acquire(bridge, stock, favorites, args.output_dir, args.deadline_seconds)
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
