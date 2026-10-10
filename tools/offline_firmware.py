"""Validate known Monitor 1.1.1 inputs and extract the unchanged ARM application."""

import hashlib
import struct
import zlib
from pathlib import Path


APPLICATION_BASE = 0x20008000  # Supported analysis mapping; hardware map unverified.
APPLICATION_OFFSET = 0xD000
APPLICATION_SIZE = 0x420624
APPLICATION_SHA256 = "cf55cfc99d8db202c9f6f93348b4241d048c2dfd1ce5b6d2c82dc6ead4607c34"
INPUTS = {
    "68ffa3d3a94058e8e605a9f48179305502893c4c426706525aac4e1df5f9e887":
        (16 * 1024 * 1024, "verified_device_mstar_array"),
    "ccae315a799a3f9ebc46ef0516585361a9b3daea7c0b6331eaba151220db80b9":
        (7306038, "official_mstar_component"),
    APPLICATION_SHA256: (APPLICATION_SIZE, "extracted_application"),
}


def load_application(path: Path):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest not in INPUTS or len(raw) != INPUTS[digest][0]:
        raise ValueError("Input is not a hash-pinned Monitor 1.1.1 image")
    kind = INPUTS[digest][1]
    regions = []
    if kind == "extracted_application":
        application = raw
    else:
        for header, start, length, crc in (
            (0x1000, 0x2000, 0x905C, 0x2B0B711A),
            (0xC000, APPLICATION_OFFSET, APPLICATION_SIZE, 0xEEC8D9BE),
        ):
            if raw[header:header + 4] != b"MCR5":
                raise ValueError("Unexpected MCR5 header")
            if struct.unpack_from("<I", raw, header + 0x14)[0] != length:
                raise ValueError("Unexpected section length")
            stored = struct.unpack_from("<I", raw, header + 0x1C)[0]
            calculated = zlib.crc32(raw[start:start + length]) & 0xFFFFFFFF
            if stored != crc or calculated != stored:
                raise ValueError("Known program-region CRC does not match")
            regions.append({"header_offset": hex(header), "data_offset": hex(start),
                            "bytes": length, "crc32": f"{calculated:08x}"})
        application = raw[APPLICATION_OFFSET:APPLICATION_OFFSET + APPLICATION_SIZE]
    if hashlib.sha256(application).hexdigest() != APPLICATION_SHA256:
        raise ValueError("Extracted application hash mismatch")
    return application, {
        "input_path": str(path.resolve()), "input_kind": kind, "input_sha256": digest,
        "application_bytes": len(application), "application_sha256": APPLICATION_SHA256,
        "application_payload_offset": None if kind == "extracted_application" else hex(APPLICATION_OFFSET),
        "candidate_runtime_base": hex(APPLICATION_BASE), "checked_program_regions": regions,
        "mapping_is_analysis_hypothesis": True, "hardware_access": False,
    }
