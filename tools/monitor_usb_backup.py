"""Read two complete copies of the Monitor's three SPI flash arrays.

Only the previously audited bus routing, JEDEC ID and READ 03 path is used.
No flash erase/program/write-enable, security or status-register writes exist.
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from monitor_usb_probe import Bridge, MAX_READ_BYTES, reference_payloads


TARGET_INFO = {
    "fpga": ("EF4018", 16 * 1024 * 1024),
    "5680": ("EF4014", 1024 * 1024),
    "8339": ("EF4018", 16 * 1024 * 1024),
}


def validate_target(bridge, name):
    bridge.select(name)
    first, second = bridge.jedec_id(), bridge.jedec_id()
    expected, capacity = TARGET_INFO[name]
    if first != second or first != expected:
        raise RuntimeError(f"Unexpected or unstable {name} JEDEC ID: {first}/{second}")
    return capacity


def checked_read(bridge, address, size):
    data = bridge.read(address, size)
    if len(data) != size:
        raise RuntimeError(f"Short read at 0x{address:X}: {len(data)} of {size} bytes")
    return data


def check_chunk_size(bridge, capacity, chunk_size):
    # Compare reads at different boundaries and at both ends of the chip.
    positions = (0, min(0x10000, capacity - chunk_size), capacity - chunk_size)
    for start in positions:
        large = checked_read(bridge, start, chunk_size)
        small = b"".join(
            checked_read(bridge, start + offset, min(256, chunk_size - offset))
            for offset in range(0, chunk_size, 256)
        )
        if large != small:
            raise RuntimeError(f"Read size/boundary check failed at 0x{start:X}")


def dump_target(bridge, name, pass_number, output_dir, chunk_size, reference):
    capacity = validate_target(bridge, name)
    check_chunk_size(bridge, capacity, chunk_size)
    partial = output_dir / f"{name}-pass{pass_number}.partial"
    final = output_dir / f"{name}-pass{pass_number}.bin"
    if final.exists():
        raise FileExistsError(final)
    digest = hashlib.sha256()
    payload_digest = hashlib.sha256()
    reference_size = len(reference)
    start_time = time.monotonic()
    next_progress = 0
    with partial.open("xb") as stream:
        for address in range(0, capacity, chunk_size):
            size = min(chunk_size, capacity - address)
            data = checked_read(bridge, address, size)
            stream.write(data)
            digest.update(data)
            if address < reference_size:
                payload_digest.update(data[: min(size, reference_size - address)])
            completed = address + size
            if completed >= next_progress or completed == capacity:
                seconds = time.monotonic() - start_time
                print(f"{name} pass {pass_number}: {completed}/{capacity} bytes, {seconds:.1f}s", flush=True)
                next_progress = completed + 1024 * 1024
        stream.flush()
    if partial.stat().st_size != capacity:
        raise RuntimeError("Output file size does not match the identified capacity")
    partial.rename(final)
    return {
        "file": final.name,
        "bytes": capacity,
        "sha256": digest.hexdigest(),
        "seconds": round(time.monotonic() - start_time, 3),
        "payload_bytes": reference_size,
        "matches_official_payload": payload_digest.hexdigest() == hashlib.sha256(reference).hexdigest(),
    }


def compare_files(first, second, capacity):
    if first.stat().st_size != capacity or second.stat().st_size != capacity:
        raise RuntimeError("Cannot verify files with unexpected lengths")
    with first.open("rb") as a, second.open("rb") as b:
        offset = 0
        while offset < capacity:
            left, right = a.read(65536), b.read(65536)
            if left != right:
                for index, (x, y) in enumerate(zip(left, right)):
                    if x != y:
                        return {"byte_equal": False, "first_difference": offset + index}
                return {"byte_equal": False, "first_difference": offset + min(len(left), len(right))}
            offset += len(left)
    return {"byte_equal": True}


def acquire(dll_path, name, pass_number, output_dir, chunk_size, reference):
    bridge = Bridge(dll_path)
    try:
        bridge.open()
        return dump_target(bridge, name, pass_number, output_dir, chunk_size, reference)
    finally:
        bridge.close()  # Release routing while the DLL handle is still open.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--chunk-size", type=int, choices=(256, 512, 1024), default=1024)
    args = parser.parse_args()
    if args.chunk_size > MAX_READ_BYTES:
        raise ValueError("Chunk size exceeds the bridge's reviewed limit")
    version, references = reference_payloads(args.baseline)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest_path = args.output_dir / "manifest.json"
    manifest = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_version": version,
        "scope": "Main SPI flash arrays; no OTP/security registers or write/recovery test",
        "chunk_size": args.chunk_size,
        "flash_mutation_commands_implemented": False,
        "bus_release_between_acquisitions": True,
        "success": False,
        "targets": {name: {"jedec_id": identity, "capacity_bytes": capacity, "passes": []}
                    for name, (identity, capacity) in TARGET_INFO.items()},
    }

    def save_manifest():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    save_manifest()
    return_code = 1
    try:
        # Small receiver flash first, then the two large arrays. Reopen/release
        # the bridge for every target acquisition instead of recycling buffers.
        for pass_number in (1, 2):
            for name in ("5680", "fpga", "8339"):
                record = acquire(args.dll, name, pass_number, args.output_dir, args.chunk_size, references[name])
                manifest["targets"][name]["passes"].append(record)
                save_manifest()
        for name, target in manifest["targets"].items():
            files = [args.output_dir / record["file"] for record in target["passes"]]
            target["comparison"] = compare_files(*files, target["capacity_bytes"])
            save_manifest()
            if not target["comparison"]["byte_equal"]:
                raise RuntimeError(f"The two full {name} reads differ; neither is a verified backup")
        manifest["success"] = True
        return_code = 0
    except KeyboardInterrupt:
        manifest["error"] = "Acquisition interrupted; incomplete files are not verified backups"
        return_code = 130
    except Exception as error:
        manifest["error"] = str(error)
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
    finally:
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        save_manifest()
    print(f"Verified complete backup: {manifest['success']}; manifest: {manifest_path}", flush=True)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
