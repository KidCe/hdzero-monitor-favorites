"""Read-only, bounded receiver consumer inventory; no USB or hardware access."""

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK_HASH = "ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652"
CANDIDATE_HASH = "7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16"
INVENTORY_HASH = "3cefed4ac7397e2da1c0ba3f1c020fc511c6e0dd51c5d4e3081c14c607fcbd4b"
WATCHED = (0xD85, 0x767, 0x768, 0x76E)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def hits(data, pattern):
    return [offset for offset in range(len(data)) if data.startswith(pattern, offset)]


def straight_line_accesses(instructions):
    """Track literal DPTR plus INC until control transfer or a DPTR byte write.

    This deliberately does not propagate state across a branch/call or through
    dynamic DPL/DPH arithmetic. Its rows are positive observations, never proof
    that all possible aliases have been excluded.
    """
    result = []
    address = origin = previous_end = None
    for row in instructions:
        offset, assembly = row["offset"], row["assembly"]
        if previous_end != offset:
            address = origin = None
        previous_end = offset + len(bytes.fromhex(row["bytes_hex"]))
        match = re.fullmatch(r"MOV DPTR,#0x([0-9a-f]+)", assembly)
        if match:
            address, origin = int(match[1], 16), offset
        elif assembly == "INC DPTR" and address is not None:
            address = (address + 1) & 0xFFFF
        elif assembly in ("MOVX @DPTR,A", "MOVX A,@DPTR") and address is not None:
            if address in WATCHED:
                result.append({"offset": offset, "bytes_hex": row["bytes_hex"],
                               "assembly": assembly, "external_address": address,
                               "literal_origin": origin})
        # MOV DPL/DPH, POP, arithmetic or register copies destroy this narrow
        # model. Conditional branches end the known straight-line segment too.
        if (re.match(r"(?:MOV|POP|INC|DEC|ANL|ORL|XRL) (?:DPL|DPH)[,#]?", assembly)
                or assembly.startswith(("LCALL ", "ACALL ", "LJMP ", "AJMP ",
                                        "SJMP ", "JMP ", "JZ ", "JNZ ", "JC ",
                                        "JNC ", "JB ", "JNB ", "JBC ",
                                        "CJNE ", "DJNZ "))
                or assembly in ("RET", "RETI")):
            address = origin = None
    return result


def audit():
    inventory_path = ROOT / "artifacts/firmware-analysis/20261009-recovered-source/instructions.json"
    stock_path = ROOT / "artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin"
    candidate_path = ROOT / "artifacts/firmware-analysis/20261009-favorites-candidate-v4/receiver-candidate-ANALYSIS-ONLY.bin"
    stock, candidate = stock_path.read_bytes(), candidate_path.read_bytes()
    inventory_bytes = inventory_path.read_bytes()
    if sha(inventory_bytes) != INVENTORY_HASH:
        raise ValueError("Recovered instruction inventory differs from the pinned export")
    inventory = json.loads(inventory_bytes.decode("utf-8"))
    rows = inventory["instructions"]
    if sha(stock) != STOCK_HASH or sha(candidate) != CANDIDATE_HASH:
        raise ValueError("The analysis accepts only the pinned stock/v4 images")
    if inventory["image_sha256"] != STOCK_HASH:
        raise ValueError("Inventory belongs to a different image")
    for row in rows:
        expected = bytes.fromhex(row["bytes_hex"])
        if stock[row["offset"]:row["offset"] + len(expected)] != expected:
            raise ValueError(f"Inventory bytes differ at {row['offset']:04X}")

    literals = {f"{address:04X}": [row for row in rows
                 if row["bytes_hex"] == "90" + address.to_bytes(2, "big").hex()]
                for address in WATCHED}
    accesses = straight_line_accesses(rows)
    # Split low/high dispatch tables are decoded from actual CODE bytes.
    split_dispatches = []
    for pc, low_base, high_base in ((0x6900, 0x6901, 0x6909), (0x93A7, 0x93A8, 0x93B0)):
        targets = [stock[low_base + index] | (stock[high_base + index] << 8)
                   for index in range(8)]
        split_dispatches.append({"jump_offset": pc, "low_base": low_base,
                                 "high_base": high_base, "targets": targets})
    fixed_dispatches = []
    for pc, base, stride, count, opcode in ((0x8E39, 0x8E3A, 2, 4, 0x80),
                                           (0x9A08, 0x9A09, 3, 6, 0x02),
                                           (0xBD40, 0xBD41, 3, 4, 0x02)):
        targets = []
        for index in range(count):
            entry = base + stride * index
            if stock[entry] != opcode:
                raise ValueError(f"Unexpected jump-table opcode at {entry:04X}")
            if opcode == 0x80:
                relative = stock[entry + 1]
                targets.append((entry + 2 + (relative if relative < 128 else relative - 256)) & 0xFFFF)
            else:
                targets.append(int.from_bytes(stock[entry + 1:entry + 3], "big"))
        fixed_dispatches.append({"jump_offset": pc, "base": base, "stride": stride,
                                 "count": count, "targets": targets})
    # Every recovered indirect JMP belongs to one of these five tables.
    computed = [row["offset"] for row in rows if row["assembly"] == "JMP @A+DPTR"]
    if sorted(computed) != sorted(d["jump_offset"] for d in split_dispatches + fixed_dispatches):
        raise ValueError("Unexpected computed jump requires review")

    flags = []
    for low, high in ((0x600C, 0x6010), (0x636A, 0x636E), (0x646A, 0x646E), (0x682B, 0x682F)):
        if candidate[low] != 0x24 or candidate[high] != 0x34:
            raise ValueError("Unexpected capability address arithmetic")
        flags.append({"low_instruction": low, "high_instruction": high,
                      "candidate_base": candidate[low + 1] | candidate[high + 1] << 8})
    flags.append({"pointer_instruction": 0x777,
                  "candidate_base": int.from_bytes(candidate[0x778:0x77A], "big")})
    if any(row["candidate_base"] != 0xF233 for row in flags):
        raise ValueError("Capability consumer still uses the old table")

    return {
        "format": "hdzero-receiver-consumer-audit-v1", "hardware_access": False,
        "firmware_modified": False, "stock_sha256": sha(stock),
        "candidate_sha256": sha(candidate), "inventory_sha256": sha(inventory_path.read_bytes()),
        "recovered_instructions": len(rows), "instruction_bytes": inventory["instruction_bytes"],
        "image_bytes": len(stock), "literal_dptr_references": literals,
        "bounded_straight_line_accesses": accesses,
        "computed_dispatches": split_dispatches + fixed_dispatches,
        "linear_step_0725_raw_references": {
            pattern: hits(stock, bytes.fromhex(pattern))
            for pattern in ("120725", "020725", "0725", "2507")},
        "capability_table_consumers": flags,
        "generic_pointer_write_helper": {"entry": 0xC29F, "external_write": 0xC2B8,
            "direct_calls": [row["offset"] for row in rows if row["assembly"] == "LCALL 0xc29f"]},
        "limits": ["No dynamic pointer or register-value propagation",
                   "Calls and conditional branches end the straight-line DPTR model",
                   "Recovered instruction inventory is incomplete; undisassembled bytes remain",
                   "No peripheral, RF, display or physical input acceptance"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    if args.output.exists():
        raise ValueError("Refusing to overwrite an earlier evidence report")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output),
                      "literal_counts": {key: len(value) for key, value in result["literal_dptr_references"].items()},
                      "computed_dispatches": len(result["computed_dispatches"]),
                      "linear_step_raw_references": result["linear_step_0725_raw_references"],
                      "hardware_access": False}, indent=2))


if __name__ == "__main__":
    main()
