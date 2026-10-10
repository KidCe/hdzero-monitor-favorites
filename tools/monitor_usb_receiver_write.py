"""Receiver-only flash write/restore through the Monitor's built-in CH341 bridge.

Imports perform no hardware access. Without --execute-write the CLI is a
read-only dry run: identity, status, two full reads and a validated plan. With
--execute-write it erases only the first 64 KiB block of the 5680 receiver flash
and programs the reviewed pages, verifying every step and the final full array.
Never use this on an external breakout: target selection drives Monitor GPIOs.
"""

import argparse
import ctypes
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from monitor_usb_probe import require_success
from monitor_usb_receiver_preflight import ReceiverReadBridge, status_summary
from monitor_receiver_flash_plan import (CAPACITY, ERASE_BYTES, FAVORITES_ARRAY_SHA256, JEDEC, PAGE_BYTES,
                                        READ_BYTES, TARGET, BACKUPS, OFFICIAL_120_ARRAY_SHA256,
                                        PREVIOUS_FAVORITES_ARRAY_SHA256, execute, make_plan, projected_favorites,
                                        validate_plan, verified_backups)
from monitor_update_package import digest

EXPECTED_AFTER = {"favorites": FAVORITES_ARRAY_SHA256, "restore": BACKUPS[TARGET][1]}
# W25Q80DV maxima: page program 3 ms, 64 KiB block erase 2 s. Generous USB-latency margins.
BUSY_DEADLINES = {"status": 1.0, "program": 0.5, "erase": 6.0}
POLL_BUDGET = 20000
MUTATING_OPCODES = (0x06, 0x02, 0xd8)


def admissible(command):
    """Exact reviewed command shapes; everything else is rejected before native I/O."""
    if command in (b"\x05\x00", b"\x35\x00", b"\x9f" * 6, b"\x06", b"\x04", b"\xd8\x00\x00\x00"):
        return True
    if len(command) < 5 or command[0] not in (0x03, 0x02):
        return False
    address = int.from_bytes(command[1:4], "big")
    if command[0] == 0x03:
        length = len(command) - 4
        return 0 < length <= READ_BYTES and address + length <= CAPACITY and not any(command[4:])
    return len(command) == PAGE_BYTES + 4 and address % PAGE_BYTES == 0 and address + PAGE_BYTES <= ERASE_BYTES


class ReceiverWriteBridge(ReceiverReadBridge):
    """Receiver-only transport. Mutating opcodes additionally require explicit arming."""

    mutation_armed = False

    def spi(self, command):
        if type(command) is not bytes or not admissible(command):
            raise ValueError("Command is outside the reviewed receiver write scope")
        if command[0] in MUTATING_OPCODES and not self.mutation_armed:
            raise ValueError("Mutation attempted while the write session is not armed")
        if not self.opened or not self.routed:
            raise ValueError("Receiver bus is not open and selected")
        buffer = ctypes.create_string_buffer(command, len(command))
        require_success(self.set_stream(0, 0x81), "Set SPI stream mode")
        try:
            # self.transfer is the bound native CH341StreamSPI4: one call, one CS0 assertion.
            require_success(self.transfer(0, 0x80, len(command), buffer), "Receiver SPI transaction")
            return buffer.raw
        finally:
            require_success(self.set_stream(0, 0x80), "Restore stream mode")

    def close(self):
        self.mutation_armed = False
        super().close()


class SpiTransport:
    """Adapts a bridge's validated `spi` to the protocol's `transfer` interface."""

    def __init__(self, bridge):
        self.transfer = bridge.spi


def classify_receiver(current, stock, favorites):
    """Name the installed receiver array. Only block 0 can differ between known versions."""
    known = {digest(stock): "official-1.1.1", digest(favorites): "favorites-current",
             OFFICIAL_120_ARRAY_SHA256: "official-1.2.0"}
    known.update({value: "favorites-previous" for value in PREVIOUS_FAVORITES_ARRAY_SHA256})
    if digest(current) in known:
        return known[digest(current)]
    return "unknown-block0" if current[ERASE_BYTES:] == stock[ERASE_BYTES:] else "unknown"


def run(bridge, stock, favorites, mode, output, *, execute_write=False, deadline_seconds=180,
        busy_deadlines=BUSY_DEADLINES, poll_interval=0.002, require_known_preimage=False,
        any_block0_preimage=False):
    """require_known_preimage refuses official 1.2.0 or unrecognized receiver content unless
    any_block0_preimage explicitly allows replacing block 0 (the area outside block 0 must still match)."""
    """Bridge injection lets tests exercise the full lifecycle on a local NOR model."""
    if mode not in EXPECTED_AFTER:
        raise ValueError("Unknown write mode")
    if type(deadline_seconds) is not int or not 30 <= deadline_seconds <= 900:
        raise ValueError("Pre-write session deadline must be 30..900 seconds")
    output.mkdir(parents=True, exist_ok=False)
    report = {"started_utc": datetime.now(timezone.utc).isoformat(), "mode": mode, "success": False,
              "execute_write_requested": bool(execute_write), "flash_targets_selected": [TARGET],
              "hardware_access": isinstance(bridge, ReceiverWriteBridge),
              "expected_after_sha256": EXPECTED_AFTER[mode], "mutation_started": False,
              "scope": "Receiver 5680 only; erase limited to block 0x00000-0x0FFFF"}
    path = output / "write-session.json"

    def save(extra=None):
        if extra is not None:
            report["protocol_progress"] = {k: v for k, v in extra.items() if k != "error"}
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    save()
    deadline = time.monotonic() + deadline_seconds

    def check_deadline():
        # Only enforced before mutation; aborting mid-block would leave more damage.
        if time.monotonic() >= deadline:
            raise TimeoutError("Pre-write session deadline exceeded")

    try:
        report["usb"] = bridge.open()
        bridge.select(TARGET)
        ids = (bridge.jedec_id(), bridge.jedec_id())
        if ids != (JEDEC, JEDEC):
            raise RuntimeError("Receiver identity is unexpected or unstable")
        start_status = bridge.status()
        report["start_status"] = status_summary(start_status)
        if start_status != {"sr1": 0, "sr2": 0}:
            # Matches the observed 00/00 preflight; any protection/CMP/SRL/suspend change stops here.
            raise RuntimeError("Receiver status differs from the reviewed 00/00 state")
        passes = []
        for number in (1, 2):
            data = bytearray()
            for address in range(0, CAPACITY, READ_BYTES):
                check_deadline()
                chunk = bridge.read(address, READ_BYTES)
                if len(chunk) != READ_BYTES:
                    raise RuntimeError(f"Short receiver read at {address:#x}")
                data += chunk
            data = bytes(data)
            (output / f"5680-before-pass{number}.bin").write_bytes(data)
            passes.append(data)
        if passes[0] != passes[1]:
            raise RuntimeError("Pre-write full receiver reads differ")
        current = passes[0]
        report["before_sha256"] = digest(current)
        report["installed_receiver"] = installed = classify_receiver(current, stock, favorites)
        if require_known_preimage and installed in ("official-1.2.0", "unknown-block0", "unknown") \
                and not any_block0_preimage:
            raise RuntimeError(f"Installed receiver firmware is not supported for this operation: {installed}")
        plan = make_plan(mode, stock, favorites, current, any_block0_preimage=any_block0_preimage)
        validate_plan(plan)
        (output / "plan.json").write_text(json.dumps(plan.record(), indent=2) + "\n", encoding="utf-8")
        report.update(plan_operations=len(plan.operations),
                      plan_program_pages=sum(op.kind == "program" for op in plan.operations))
        save()
        check_deadline()
        if not execute_write:
            report.update(success=True, dry_run=True, result="Plan validated; no mutation command issued")
            return report
        bridge.mutation_armed = True
        protocol = execute(plan, SpiTransport(bridge), poll_budget=POLL_BUDGET, busy_deadlines=busy_deadlines,
                           poll_interval=poll_interval, progress=save, hardware_access=report["hardware_access"])
        bridge.mutation_armed = False
        report["protocol"] = protocol
        report["mutation_started"] = protocol["mutation_started"]
        if not protocol["success"]:
            raise RuntimeError(f"Protocol stopped at {protocol.get('failed_stage')}: {protocol.get('error')}")
        # Independent post-write pass, saved for evidence; written with the bus still routed.
        after = b"".join(bridge.read(address, READ_BYTES) for address in range(0, CAPACITY, READ_BYTES))
        (output / "5680-after.bin").write_bytes(after)
        report["after_sha256"] = digest(after)
        if after != plan.after or digest(after) != EXPECTED_AFTER[mode]:
            raise RuntimeError("Independent post-write read differs from the expected array")
        end_status = bridge.status()
        report["end_status"] = status_summary(end_status)
        if end_status != {"sr1": 0, "sr2": 0}:
            raise RuntimeError("Receiver status after writing differs from 00/00")
        report.update(success=True, dry_run=False)
    except (RuntimeError, ValueError, TimeoutError, OSError) as error:
        report["error"] = str(error)
        if report["mutation_started"]:
            report["recovery_hint"] = ("Receiver block 0 may be incomplete. Before power-cycling, rerun this "
                                       "tool with --mode restore; it accepts a block-0-only interrupted state.")
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
    parser.add_argument("--mode", choices=sorted(EXPECTED_AFTER), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--execute-write", action="store_true",
                        help="Actually erase/program block 0; otherwise read-only dry run")
    parser.add_argument("--confirm-after-sha256",
                        help="Required with --execute-write: the expected final full-array SHA-256 for --mode")
    args = parser.parse_args()
    if args.execute_write and args.confirm_after_sha256 != EXPECTED_AFTER[args.mode]:
        parser.error("--execute-write requires --confirm-after-sha256 matching the mode's expected array")
    if args.output_dir.exists():
        raise FileExistsError("Use a new write-session directory")
    stock = verified_backups(args.backups)[TARGET]
    config = json.loads((Path(__file__).resolve().parents[1] / "config/favorite-channels.json").read_text(encoding="utf-8"))
    favorites = projected_favorites(stock, args.receiver.read_bytes(), config)
    if digest(favorites) != FAVORITES_ARRAY_SHA256:
        raise ValueError("Projected Favorites array differs from the pinned v4 array")
    # Sole construction point of a native bridge; never reached by imports or tests.
    bridge = ReceiverWriteBridge(args.dll)
    report = run(bridge, stock, favorites, args.mode, args.output_dir, execute_write=args.execute_write)
    print(json.dumps({k: v for k, v in report.items() if k != "protocol_progress"}, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
