"""Compile and simulate a receiver-only flash/restore plan. No native transport.

The command line operates on local files and an in-memory NOR model only. It
cannot load a DLL, open USB, or execute SPI commands on a physical device.
"""

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

from monitor_package_compatibility import BACKUPS
from monitor_receiver_candidate import make_candidate
from monitor_receiver_decode import DECODE_TABLE, ENCODE_TABLE, PAYLOAD_SIZE
from monitor_update_package import FAVORITES_SHA256, digest

CAPACITY = 1048576
ERASE_BYTES = 65536
PAGE_BYTES = 256
READ_BYTES = 1024
TARGET = "5680"
JEDEC = "EF4014"
FAVORITES_ARRAY_SHA256 = "f88d9c72f839db94d940c84d6d11ffc4273834ce8df6e3b78d8e32125ce51e4c"  # v7
# Earlier Favorites arrays physically written and verified; accepted as preimages for an upgrade.
# Official 1.2.0 receiver array (payload + FF). FPGA/MStar of 1.2.0 equal 1.1.1; only the receiver differs.
OFFICIAL_120_ARRAY_SHA256 = "a2bca537c11f0145f8911777ff4f22913dee29ed9a2b6c24d6663cc20516aa6b"
PREVIOUS_FAVORITES_ARRAY_SHA256 = ("e3f54fe342ee806812d8da887c94cef8633480e9d48fbdb4763ce603c27d0634",  # v4
                                   "6a79dbebf85968f5a02a87883bb3249926703418f7012790012e4954e74f4d88",  # v5
                                   "f6501fa2fd4ba6c1ca23378d091c4f45f4b915eddbc550e2444192cef9e3a2c2")  # v6


def verified_backups(directory):
    """Recheck all six immutable main-array copies; metadata alone is insufficient."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("success") is not True:
        raise ValueError("Backup acquisition did not complete successfully")
    result = {}
    for name, (capacity, pinned) in BACKUPS.items():
        target = manifest.get("targets", {}).get(name, {})
        if target.get("comparison", {}).get("byte_equal") is not True:
            raise ValueError(f"Backup comparison missing for {name}")
        arrays = [(directory / f"{name}-pass{number}.bin").read_bytes() for number in (1, 2)]
        if any(len(array) != capacity or digest(array) != pinned for array in arrays) or arrays[0] != arrays[1]:
            raise ValueError(f"Pinned full-array backup changed: {name}")
        result[name] = arrays[0]
    return result


def projected_favorites(stock_array, receiver, config):
    if len(stock_array) != CAPACITY or digest(stock_array) != BACKUPS[TARGET][1]:
        raise ValueError("Unrecognized stock receiver array")
    stock = stock_array[:PAYLOAD_SIZE].translate(DECODE_TABLE)
    independent, _ = make_candidate(stock, config)
    if receiver != independent or digest(receiver) != FAVORITES_SHA256:
        raise ValueError("Receiver differs from the independently generated v4 Favorites")
    projected = bytearray(stock_array)
    projected[:ERASE_BYTES] = b"\xff" * ERASE_BYTES
    projected[:len(receiver)] = receiver.translate(ENCODE_TABLE)
    return bytes(projected)


@dataclass(frozen=True)
class Operation:
    kind: str
    address: int
    data: bytes = b""

    def record(self):
        return {"kind": self.kind, "address": self.address, "bytes": len(self.data),
                "data_hex": self.data.hex(), "data_sha256": digest(self.data)}


@dataclass(frozen=True)
class FlashPlan:
    mode: str
    before: bytes
    after: bytes
    operations: tuple
    any_block0_preimage: bool = False  # Explicit opt-in: replace an unrecognized block 0

    def record(self):
        return {"format": "hdzero-receiver-flash-plan-v1", "mode": self.mode, "any_block0_preimage": self.any_block0_preimage, "target": TARGET,
                "jedec_id": JEDEC, "capacity_bytes": CAPACITY,
                "before_sha256": digest(self.before), "after_sha256": digest(self.after),
                "changed_bytes": sum(a != b for a, b in zip(self.before, self.after)),
                "erase_range": [0, ERASE_BYTES] if self.operations else None,
                "program_pages": sum(op.kind == "program" for op in self.operations),
                "other_flash_targets_touched": [], "outside_first_block_equal": self.before[ERASE_BYTES:] == self.after[ERASE_BYTES:],
                "hardware_access": False, "ready_for_device_use": False,
                "required_native_adapter": "tools/monitor_usb_receiver_write.py; offline-tested only, not validated on hardware",
                "operations": [op.record() for op in self.operations]}


def make_plan(mode, stock, favorites, current, any_block0_preimage=False):
    if any(type(value) is not bytes for value in (stock, favorites, current)):
        raise ValueError("Plan snapshots must be immutable bytes")
    if mode not in ("favorites", "restore"):
        raise ValueError("Unknown plan mode")
    if len(stock) != CAPACITY or digest(stock) != BACKUPS[TARGET][1]:
        raise ValueError("Stock full-array backup is not pinned")
    if len(favorites) != CAPACITY or digest(favorites) != FAVORITES_ARRAY_SHA256:
        raise ValueError("Favorites projected full array is not pinned")
    if len(current) != CAPACITY:
        raise ValueError("Current-state file must contain the complete receiver array")
    if current[ERASE_BYTES:] != stock[ERASE_BYTES:] or favorites[ERASE_BYTES:] != stock[ERASE_BYTES:]:
        raise ValueError("Current state differs outside the permitted first block")
    known = current in (stock, favorites) or digest(current) in PREVIOUS_FAVORITES_ARRAY_SHA256
    if mode == "favorites" and not known and not any_block0_preimage:
        raise ValueError("Favorites requires the exact stock or a known earlier Favorites preimage")
    after = favorites if mode == "favorites" else stock
    operations = []
    if current != after:
        operations.append(Operation("erase", 0))
        for offset in range(0, ERASE_BYTES, PAGE_BYTES):
            page = after[offset:offset + PAGE_BYTES]
            if page != b"\xff" * PAGE_BYTES:
                operations.append(Operation("program", offset, page))
    return FlashPlan(mode, current, after, tuple(operations), bool(any_block0_preimage))


def validate_plan(plan):
    """Rebuild the whole operation stream before permitting even simulated mutation."""
    if type(plan) is not FlashPlan or type(plan.before) is not bytes or type(plan.after) is not bytes or type(plan.operations) is not tuple:
        raise ValueError("Plan and snapshots must be immutable reviewed types")
    if plan.mode not in ("favorites", "restore") or len(plan.before) != CAPACITY or len(plan.after) != CAPACITY:
        raise ValueError("Invalid plan shape")
    expected_after = BACKUPS[TARGET][1] if plan.mode == "restore" else FAVORITES_ARRAY_SHA256
    if digest(plan.after) != expected_after or plan.before[ERASE_BYTES:] != plan.after[ERASE_BYTES:]:
        raise ValueError("Invalid plan destination or preservation boundary")
    known = (BACKUPS[TARGET][1], FAVORITES_ARRAY_SHA256) + PREVIOUS_FAVORITES_ARRAY_SHA256
    if plan.mode == "favorites" and digest(plan.before) not in known and plan.any_block0_preimage is not True:
        raise ValueError("Invalid Favorites preimage")
    expected = []
    if plan.before != plan.after:
        expected.append(Operation("erase", 0))
        expected.extend(Operation("program", offset, plan.after[offset:offset + PAGE_BYTES])
                        for offset in range(0, ERASE_BYTES, PAGE_BYTES)
                        if plan.after[offset:offset + PAGE_BYTES] != b"\xff" * PAGE_BYTES)
    if plan.operations != tuple(expected):
        raise ValueError("Plan operations are missing, reordered or changed")


class NorModel:
    """Simplified NOR behavior; one command is one complete CS-delimited transaction.

    This deliberately models only the protocol used by the plan, not the board,
    analog power behavior, bus arbitration, timing or every Winbond variant.
    """
    def __init__(self, data, *, write_protected=False, wel_missing=False, stuck_busy=False,
                 fail_program=None, corrupt_program=None, wrong_identity=False, sr2=0):
        if len(data) != CAPACITY:
            raise ValueError("NOR fixture must be one complete receiver array")
        self.data = bytearray(data)
        self.write_protected, self.wel_missing = write_protected, wel_missing
        self.stuck_busy, self.fail_program, self.corrupt_program = stuck_busy, fail_program, corrupt_program
        self.wrong_identity, self.sr2 = wrong_identity, sr2
        self.wel = False
        self.busy = 0
        self.programs = 0
        self.mutations = 0
        self.released = False
        self.closed = False
        self.transactions = []

    def transfer(self, command):
        if self.closed or not command:
            raise ValueError("Closed or empty simulation transaction")
        opcode = command[0]
        self.transactions.append({"opcode": f"{opcode:02X}", "address": int.from_bytes(command[1:4], "big")
                                  if opcode in (0x03, 0x02, 0xd8) and len(command) >= 4 else None,
                                  "bytes": len(command)})
        if opcode == 0x9f and command == b"\x9f" * 6:
            return command[:1] + (bytes.fromhex("123456") if self.wrong_identity else bytes.fromhex(JEDEC)) + bytes(2)
        if opcode == 0x05 and command == b"\x05\x00":
            status = (1 if self.busy else 0) | (2 if self.wel else 0) | (4 if self.write_protected else 0)
            if self.busy and not self.stuck_busy:
                self.busy -= 1
            return bytes([0, status])
        if opcode == 0x35 and command == b"\x35\x00":
            return bytes([0, self.sr2])
        if self.busy:
            raise RuntimeError("Simulation command issued while BUSY")
        if opcode in (0x06, 0x04) and len(command) == 1:
            self.wel = opcode == 0x06 and not self.wel_missing
            return bytes(1)
        if opcode in (0x03, 0x02, 0xd8) and len(command) >= 4:
            address = int.from_bytes(command[1:4], "big")
            if opcode == 0x03:
                length = len(command) - 4
                if not 0 < length <= READ_BYTES or address + length > CAPACITY or any(command[4:]):
                    raise ValueError("Invalid simulation read")
                return bytes(4) + self.data[address:address + length]
            if not self.wel or self.write_protected:
                raise RuntimeError("Mutation without WEL or with protection")
            if opcode == 0xd8 and command == b"\xd8\x00\x00\x00":
                self.data[:ERASE_BYTES] = b"\xff" * ERASE_BYTES
            elif opcode == 0x02 and len(command) == PAGE_BYTES + 4 and address % PAGE_BYTES == 0 and address + PAGE_BYTES <= ERASE_BYTES:
                self.programs += 1
                if self.programs == self.fail_program:
                    raise RuntimeError("Injected interruption before page program")
                for index, value in enumerate(command[4:]):
                    self.data[address + index] &= value
                if self.programs == self.corrupt_program:
                    self.data[address] ^= 1
            else:
                raise ValueError("Simulation mutation escaped the first-block/page boundary")
            self.wel = False
            self.busy = 2
            self.mutations += 1
            return bytes(len(command))
        raise ValueError("Unimplemented simulation opcode or malformed command")

    def close(self):
        # Logical cleanup events only; no GPIO/DLL calls or bus ownership model.
        self.released = True
        self.closed = True


def simulate(plan, model, poll_budget=64):
    """Local-only protocol exercise; deliberately rejects other transport classes."""
    validate_plan(plan)
    if type(model) is not NorModel:
        raise TypeError("Only the local NOR model is supported by simulate()")
    if not isinstance(poll_budget, int) or not 1 <= poll_budget <= 1024:
        raise ValueError("Status-poll budget must be bounded")
    try:
        report = execute(plan, model, poll_budget=poll_budget)
    finally:
        model.close()
    report.update(device_validated=False, simulated_mutations=model.mutations,
                  simulated_program_pages=model.programs, final_model_sha256=digest(model.data),
                  logical_release_before_close=model.released and model.closed,
                  transaction_count=len(model.transactions), transactions=model.transactions)
    return report


def execute(plan, transport, *, poll_budget=64, busy_deadlines=None, poll_interval=0.0,
            clock=time.monotonic, sleep=time.sleep, progress=None, hardware_access=False):
    """Shared receiver-only protocol. The caller owns opening, routing and cleanup.

    `transport.transfer(command)` must perform exactly one CS-delimited transaction.
    `busy_deadlines` maps "status"/"erase"/"program" to wall-clock seconds; None
    bounds BUSY polling by `poll_budget` only (local model ticks).
    """
    validate_plan(plan)
    if not isinstance(poll_budget, int) or not 1 <= poll_budget <= 100000:
        raise ValueError("Status-poll budget must be bounded")
    report = {"mode": plan.mode, "hardware_access": hardware_access, "success": False,
              "ready_for_device_use": False, "full_readback_equal": False,
              "operations_total": len(plan.operations), "operations_completed": 0,
              "mutation_started": False, "mutations_issued": 0, "program_pages_issued": 0}
    stage = "initial status"

    def note(stage_name):
        if progress is not None:
            progress(dict(report, stage=stage_name))

    def status():
        return transport.transfer(b"\x05\x00")[1]

    def ready(kind="status"):
        deadline = None if busy_deadlines is None else clock() + busy_deadlines[kind]
        for _ in range(poll_budget):
            if status() & 1 == 0:
                return
            if deadline is not None and clock() >= deadline:
                raise TimeoutError(f"BUSY wall-clock deadline exceeded after {kind}")
            if poll_interval:
                sleep(poll_interval)
        raise TimeoutError("BUSY poll budget exhausted")

    def read(address, length):
        return bytes(transport.transfer(b"\x03" + address.to_bytes(3, "big") + bytes(length))[4:])

    def full_read():
        return b"".join(read(offset, min(READ_BYTES, CAPACITY - offset)) for offset in range(0, CAPACITY, READ_BYTES))

    def enable_write():
        ready()
        if status() & 0xfc:
            raise RuntimeError("Status protection or unknown bits set")
        transport.transfer(b"\x06")
        if status() & 3 != 2:
            raise RuntimeError("WEL was not established")

    try:
        ready()
        stage = "target identity"
        if transport.transfer(b"\x9f" * 6)[1:4].hex().upper() != JEDEC:
            raise RuntimeError("Unexpected JEDEC ID")
        stage = "full preimage"
        if full_read() != plan.before:
            raise RuntimeError("Current full array differs from plan preimage")
        for operation in plan.operations:
            stage = f"{operation.kind} 0x{operation.address:05X}"
            enable_write()
            opcode = b"\xd8" if operation.kind == "erase" else b"\x02"
            report.update(mutation_started=True, mutations_issued=report["mutations_issued"] + 1)
            if operation.kind == "program":
                report["program_pages_issued"] += 1
            note(stage)
            transport.transfer(opcode + operation.address.to_bytes(3, "big") + operation.data)
            ready(operation.kind)
            if status() & 2:
                raise RuntimeError("WEL did not clear after mutation")
            if operation.kind == "erase":
                if any(read(offset, READ_BYTES) != b"\xff" * READ_BYTES for offset in range(0, ERASE_BYTES, READ_BYTES)):
                    raise RuntimeError("Erase readback mismatch")
            elif read(operation.address, PAGE_BYTES) != operation.data:
                raise RuntimeError("Page readback mismatch")
            report["operations_completed"] += 1
        stage = "full final readback"
        actual = full_read()
        if actual != plan.after:
            raise RuntimeError("Full final array readback mismatch")
        transport.transfer(b"\x04")
        if status() & 3:
            raise RuntimeError("Final write-disable status failed")
        report.update(success=True, full_readback_equal=True, final_sha256=digest(actual))
    except (RuntimeError, ValueError, TimeoutError, OSError) as error:
        report.update(error=str(error), failed_stage=stage)
    note("finished")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backups", type=Path, required=True)
    parser.add_argument("--receiver", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config/favorite-channels.json")
    parser.add_argument("--mode", choices=("favorites", "restore"), required=True)
    parser.add_argument("--current-array", type=Path, help="Local full-array snapshot; restore permits interruption only within block zero")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError("Use a new output directory")
    backups = verified_backups(args.backups)
    stock = backups[TARGET]
    favorites = projected_favorites(stock, args.receiver.read_bytes(), json.loads(args.config.read_text(encoding="utf-8")))
    current = args.current_array.read_bytes() if args.current_array else (stock if args.mode == "favorites" else favorites)
    plan = make_plan(args.mode, stock, favorites, current)
    report = simulate(plan, NorModel(current))
    if not report["success"]:
        raise RuntimeError(report["error"])
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "plan.json").write_text(json.dumps(plan.record(), indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "simulation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "expected-array.bin").write_bytes(plan.after)
    print(json.dumps({key: value for key, value in report.items() if key != "transactions"}, indent=2))


if __name__ == "__main__":
    main()
