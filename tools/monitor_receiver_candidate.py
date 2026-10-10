"""Build or verify a decoded, offline-only seven-band receiver experiment."""

import argparse
import hashlib
import json
from pathlib import Path

from monitor_receiver_decode import DECODED_SHA256, PAYLOAD_SIZE
from monitor_receiver_map import build_mapping, validate_config

FLAG_BASE = PAYLOAD_SIZE
INDEX_BASE = FLAG_BASE + 56
SECOND_BASE = INDEX_BASE + 56
LETTER_BASE = SECOND_BASE + 56 * 4
LABEL_IDS = LETTER_BASE + 7
LABEL_ROUTINE = LABEL_IDS + 8
LABEL_ROUTINE_BYTES = 100
SCAN_LIST_HOOK = LABEL_ROUTINE + LABEL_ROUTINE_BYTES
SCAN_LIST_HOOK_BYTES = 97
CANDIDATE_SIZE = SCAN_LIST_HOOK + SCAN_LIST_HOOK_BYTES
# Built-in scan list after the v6 replacement of E1/F1 (stock IDs, written to 0816..0821).
SCAN_LIST = (0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x19, 0x2D, 0x2E, 0x1B)
LABEL_ORIGINAL = bytes.fromhex("900d85e0c423541f24e7f582e4340ff583e0900fedf0")
LABEL_DRAW_ORIGINAL = "75821502b1df"  # MOV DPL,#15h ; LJMP B1DF (status-bar label field, column 21)
# Long-press threshold in tick counter units, compared at 0951/0954 (up) and 099D/09A0 (down).
LONG_PRESS_STOCK, LONG_PRESS = 1000, 500


def favorites_label_routine(ids_base, letter_base):
    """P band only: rewrite 'Pn' + 7 suffix chars into 'Pn Xd ' + first 3 suffix chars, length 9.

    Entered by LJMP instead of the stock final label draw. Buffer 0FED..0FF5 is
    rebuilt by stock code immediately before; NUL suffix bytes become spaces.
    """
    def mov_dptr(address):
        return "90" + address.to_bytes(2, "big").hex()

    def copy_space(source, destination):  # MOVX A,@src ; JNZ +2 ; MOV A,#' ' ; MOVX @dst,A
        return mov_dptr(source) + "e0" + "7002" + "7420" + mov_dptr(destination) + "f0"

    head = mov_dptr(0x0D85) + "e0" + "c3" + "9430"        # A = selection - 30h
    body_a = "ff" + "c3" + "9408"                           # R7 = slot; slot < 8 ?
    body_b = (copy_space(0x0FF2, 0x0FF5) + copy_space(0x0FF1, 0x0FF4) + copy_space(0x0FF0, 0x0FF3)
              + "7420" + mov_dptr(0x0FEF) + "f0" + mov_dptr(0x0FF2) + "f0"
              + "ef" + mov_dptr(ids_base) + "93" + "ff"        # R7 = underlying stock ID
              + "5407" + "2431" + mov_dptr(0x0FF1) + "f0"      # digit
              + "ef" + "c4" + "23" + "541f" + mov_dptr(letter_base) + "93" + mov_dptr(0x0FF0) + "f0"
              + mov_dptr(0x0FC6) + "7409" + "f0")               # draw length 9
    tail = "758215" + "02b1df"                               # stock column 21 and draw
    b, c = bytes.fromhex(body_b), bytes.fromhex(body_a)
    # JC skips body_a + JNC + body_b; JNC skips body_b. Displacements are from the next instruction.
    code = (bytes.fromhex(head) + bytes([0x40, len(c) + 2 + len(b)]) + c + bytes([0x50, len(b)]) + b
            + bytes.fromhex(tail))
    if len(code) != LABEL_ROUTINE_BYTES or max(len(c) + 2 + len(b), len(b)) > 127:
        raise ValueError("Unexpected label routine layout")
    return code


def favorites_scan_list(identities):
    """Same frequencies and order as SCAN_LIST; Favorites appear as their P IDs."""
    slots = {identity: 0x30 + slot for slot, identity in enumerate(identities)}
    return tuple(slots.get(identity, identity) for identity in SCAN_LIST)


def scan_list_hook(p_list):
    """Replaces the first list write at 6D6C. P1..P8 selected: write p_list and continue at 6DAC.

    Otherwise perform the replaced MOV DPTR,#0816 / MOV A,#20h and continue at 6D71.
    Only A, DPTR and C are used, as in the stock initializer.
    """
    p_block = b"".join(bytes([0x90, 0x08, 0x16 + i, 0x74, value, 0xF0]) for i, value in enumerate(p_list))
    p_block += bytes.fromhex("026dac")
    upper = bytes.fromhex("c39408")                       # CLR C ; SUBB A,#8
    stock = bytes.fromhex("900816" + "7420" + "026d71")
    code = (bytes.fromhex("900d85" + "e0" + "c3" + "9430")    # A = selection - 30h
            + bytes([0x40, len(upper) + 2 + len(p_block)]) + upper
            + bytes([0x50, len(p_block)]) + p_block + stock)
    if len(code) != SCAN_LIST_HOOK_BYTES or len(upper) + 2 + len(p_block) > 127:
        raise ValueError("Unexpected scan-list hook layout")
    return code


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make_candidate(stock, config):
    mapping = build_mapping(stock, config)  # Pins the entire unchanged input and supported rows.
    identities = validate_config(config)
    if CANDIDATE_SIZE > 65536:
        raise ValueError("Experiment exceeds the modeled 16-bit CODE address range")
    candidate = bytearray(stock)
    changes = []

    def replace(offset, original, replacement, purpose):
        original, replacement = bytes.fromhex(original), bytes.fromhex(replacement)
        if len(original) != len(replacement) or stock[offset:offset + len(original)] != original:
            raise ValueError(f"Unexpected original bytes or replacement length at {offset:#x}")
        candidate[offset:offset + len(original)] = replacement
        changes.append({"offset": offset, "original_hex": original.hex(),
                        "replacement_hex": replacement.hex(), "purpose": purpose})

    def pointer(base):
        return "90" + base.to_bytes(2, "big").hex()

    replace(0x0691, "bd0618", "bd0718", "Band-up wraps after seventh band")
    replace(0x06A2, "24f9", "24f8", "Band-down range includes seventh band")
    replace(0x06A9, "7405", "7406", "Band-down wraps to Favorites")
    replace(0x075B, "be3000", "be3800", "Secondary linear-selection path accepts 56 rows")
    replace(0x9D4E, "bf3000", "bf3800", "Loaded selection validation accepts Favorites IDs")
    for offset in (0x0C7B, 0x2DBC):
        replace(offset, "90c6f0", pointer(INDEX_BASE), "RF-index lookup uses extended table")
    replace(0x0777, "90c6c0", pointer(FLAG_BASE), "Secondary selection uses extended capability table")
    for low, high in ((0x600C, 0x6010), (0x636A, 0x636E), (0x646A, 0x646E), (0x682B, 0x682F)):
        replace(low, "24c0", f"24{FLAG_BASE & 255:02x}", "Capability table base low byte")
        replace(high, "34c6", f"34{FLAG_BASE >> 8:02x}", "Capability table base high byte with carry")
    replace(0x5D3A, "2408", f"24{SECOND_BASE & 255:02x}", "Second tune table base low byte")
    replace(0x5D3E, "74ef", f"74{SECOND_BASE >> 8:02x}", "Second tune table base high byte")
    # Same-size label rewrite: stock selection -> band index -> CODE letter table -> OSD buffer.
    label = bytes.fromhex("900d85e0c423541f" + pointer(LETTER_BASE) + "93900fedf0")
    label += bytes(len(LABEL_ORIGINAL) - len(label))  # 8051 NOPs, preserving next instruction address.
    for offset in (0xB7AB, 0xB885):
        replace(offset, LABEL_ORIGINAL.hex(), label.hex(), "Seven-band CODE letter lookup; P denotes Favorites")
    # Built-in scan list 0816..0821: E1 (10h) and F1 (18h) become F2/L6; the following INC yields L7.
    # Scan list is then R1-R8, F2, L6, L7, F4, i.e. all eight Favorites. E1/F1 (RF index 8/9)
    # and L6/L7 (17/18) share the same 0C74 profile group (8, 9 or >= 12).
    replace(0x6D98, "7410", "7419", "Scan list entry 9: E1 replaced by F2")
    replace(0x6D9E, "7418", "742d", "Scan list entry 10: F1 replaced by L6; entry 11 INC gives L7")
    # Display-only version text built at 1004 by B981 ("FW: V1.0.0", then digits 1009/100B/100D := '1').
    # The third digit keeps its initial value: initial '0' -> '2', late store retargeted from 100D to 100B.
    replace(0xB9BA, "7430", "7432", "Version text third digit initial value '2'")
    replace(0xB9CC, "90100d", "90100b", "Version text: late '1' store no longer overwrites third digit")
    replace(0x6D6C, "9008167420", "02" + SCAN_LIST_HOOK.to_bytes(2, "big").hex() + "0000",
            "Scan list uses P IDs for Favorites when the scan starts in the P band")
    for low, high in ((0x0951, 0x0954), (0x099D, 0x09A0)):
        replace(low, f"74{LONG_PRESS_STOCK & 255:02x}", f"74{LONG_PRESS & 255:02x}", "Long-press threshold low byte")
        replace(high, f"74{LONG_PRESS_STOCK >> 8:02x}", f"74{LONG_PRESS >> 8:02x}", "Long-press threshold high byte")
    for offset in (0xB87F, 0xB8F8):  # Busy (no-signal) and normal label draws; both LJMP tails.
        replace(offset, LABEL_DRAW_ORIGINAL, "02" + LABEL_ROUTINE.to_bytes(2, "big").hex() + "000000",
                "Favorites label shows underlying channel; stock bands unchanged")

    tables = (
        stock[0xC6C0:0xC6F0] + bytes(stock[0xC6C0 + identity] for identity in identities)
        + stock[0xC6F0:0xC720] + bytes(stock[0xC6F0 + identity] for identity in identities)
        + stock[0xEF08:0xEFC8] + b"".join(stock[0xEF08 + 4 * identity:0xEF0C + 4 * identity] for identity in identities)
        + b"ABEFRLP"
    )
    label_code = bytes(identities) + favorites_label_routine(LABEL_IDS, LETTER_BASE)
    p_scan_list = favorites_scan_list(identities)
    label_code += scan_list_hook(p_scan_list)
    candidate.extend(tables+label_code)
    if len(candidate) != CANDIDATE_SIZE:
        raise ValueError("Unexpected extension size")
    manifest = {
        "format": "hdzero-monitor-offline-candidate-v5", "analysis_only": True,
        "hardware_access": False, "installable_update": False,
        "input_sha256": DECODED_SHA256, "input_bytes": PAYLOAD_SIZE,
        "candidate_sha256": digest(candidate), "candidate_bytes": len(candidate),
        "favorites_stock_ids": identities, "favorites": mapping["slots"],
        "logical_favorites_ids": list(range(48, 56)),
        "display_labels": [f"P{i} {slot['label']} HDZ" for i, slot in enumerate(mapping["slots"], 1)],
        "changes": changes,
        "extension": {"offset": PAYLOAD_SIZE, "bytes": len(tables+label_code),
                      "sha256": digest(tables+label_code),
                      "label_ids": LABEL_IDS, "label_routine": LABEL_ROUTINE, "scan_list_hook": SCAN_LIST_HOOK,
                      "flag_base": FLAG_BASE, "index_base": INDEX_BASE,
                      "second_base": SECOND_BASE, "letter_base": LETTER_BASE,
                      "table_bytes":len(tables)},
        "scan_list": ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "F2", "L6", "L7", "F4"],
        "long_press_threshold_ticks": LONG_PRESS,
        "receiver_version_text": "FW: V1.1.2",
        "favorites_scan_list": [f"P{identity - 0x2F}" if identity >= 0x30 else "ABEFRL"[identity >> 3] + str((identity & 7) + 1)
                                for identity in p_scan_list],
        "favorites_long_press": "Stock scan activation in every band; started in P, Favorites are scanned and selected as P slots",
        "changed_original_bytes": sum(a != b for a, b in zip(stock, candidate)),
        "unverified": ["Availability and loading of appended CODE data on the device",
                       "Indirect selection aliases and computed control-flow completeness",
                       "Full peripheral transactions, persistence and receiver mode behavior",
                       "Update-container integrity, hardware recovery and physical operation"],
    }
    return bytes(candidate), manifest


def verify_candidate(stock, candidate, manifest, config):
    expected, expected_manifest = make_candidate(stock, config)
    if candidate != expected or manifest != expected_manifest:
        raise ValueError("Candidate or manifest differs from independently regenerated experiment")
    return expected_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config/favorite-channels.json")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output-dir", type=Path)
    group.add_argument("--verify-dir", type=Path)
    args = parser.parse_args()
    stock = args.stock.read_bytes()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    filename = "receiver-candidate-ANALYSIS-ONLY.bin"
    if args.verify_dir:
        manifest = verify_candidate(stock, (args.verify_dir / filename).read_bytes(),
                                    json.loads((args.verify_dir / "manifest.json").read_text(encoding="utf-8")), config)
    else:
        candidate, manifest = make_candidate(stock, config)
        args.output_dir.mkdir(parents=True, exist_ok=False)
        (args.output_dir / filename).write_bytes(candidate)
        (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in
                      ("analysis_only", "installable_update", "candidate_sha256", "candidate_bytes",
                       "changed_original_bytes", "logical_favorites_ids")}, indent=2))


if __name__ == "__main__":
    main()
