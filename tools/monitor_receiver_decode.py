"""Undo the published DM5680 byte-bit permutation for offline Monitor analysis."""

import argparse
import hashlib
import json
from pathlib import Path


SOURCE = "https://github.com/hd-zero/hdzero-vtx/blob/ad396315680f64ad5797fb0fe53bbd73e9f448ba/script/post_script.py"
ARRAY_SHA256 = "fb35263f0bc62cc1a43889da4313af3ace756c086aad8ef69d4bc6ed515b4055"
PAYLOAD_SIZE = 62003
DECODED_SHA256 = "ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652"
# Published encoded bit positions corresponding to decoded bits 0 through 7.
ENCODED_BITS = (7, 2, 5, 1, 3, 4, 0, 6)
ENCODE_TABLE = bytes(sum(((value >> bit) & 1) << destination
                         for bit, destination in enumerate(ENCODED_BITS)) for value in range(256))
DECODE_TABLE = bytes(sum(((value >> source) & 1) << bit
                         for bit, source in enumerate(ENCODED_BITS)) for value in range(256))


def decode_array(raw):
    if len(raw) != 1024 * 1024 or hashlib.sha256(raw).hexdigest() != ARRAY_SHA256:
        raise ValueError("Input must be the pinned Monitor 1.1.1 DM5680 full-array backup")
    payload = raw[:PAYLOAD_SIZE]
    decoded = payload.translate(DECODE_TABLE)
    if hashlib.sha256(decoded).hexdigest() != DECODED_SHA256:
        raise ValueError("Decoded image does not match the inspected fixture")
    if decoded.translate(ENCODE_TABLE) != payload:
        raise ValueError("Byte permutation round trip failed")
    vectors = []
    for offset in (0, 3, 0x0B, 0x13, 0x1B, 0x23, 0x33):
        target = int.from_bytes(decoded[offset + 1:offset + 3], "big")
        if decoded[offset] != 2 or target >= len(decoded):
            raise ValueError("Expected coherent 8051 LJMP vectors")
        vectors.append({"offset": hex(offset), "target": hex(target)})
    return decoded, {"input_sha256": ARRAY_SHA256, "input_bytes": len(raw),
                     "encoded_payload_bytes": PAYLOAD_SIZE,
                     "encoded_payload_sha256": hashlib.sha256(payload).hexdigest(),
                     "decoded_sha256": DECODED_SHA256, "transform_source": SOURCE,
                     "round_trip_equal": True, "vectors": vectors,
                     "hardware_access": False, "output_is_analysis_fixture_only": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    decoded, metadata = decode_array(args.input.read_bytes())
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "receiver-8051.bin").write_bytes(decoded)
    (args.output_dir / "decode.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
