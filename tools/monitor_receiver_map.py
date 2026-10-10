"""Extract stock receiver identities and tune-table values for the Favorites plan."""

import argparse
import hashlib
import json
from pathlib import Path

from monitor_receiver_decode import DECODED_SHA256, PAYLOAD_SIZE

BANDS = "ABEFRL"


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("Favorites configuration must be an object")
    channels = config.get("channels")
    if not isinstance(channels, list) or len(channels) != 8:
        raise ValueError("Favorites must contain exactly eight channels")
    identities = []
    for entry in channels:
        if (not isinstance(entry, dict) or entry.get("band") not in tuple(BANDS)
                or type(entry.get("channel")) is not int or not 1 <= entry["channel"] <= 8):
            raise ValueError("Each entry needs a stock band and a channel from 1 through 8")
        identities.append((BANDS.index(entry["band"]) << 3) | (entry["channel"] - 1))
    return identities


def build_mapping(image, config):
    if len(image) != PAYLOAD_SIZE or hashlib.sha256(image).hexdigest() != DECODED_SHA256:
        raise ValueError("Only the pinned, decoded stock receiver image is accepted")
    slots = []
    for slot, identity in enumerate(validate_config(config), 1):
        rf_index = image[0xC6F0 + identity]
        flag = image[0xC6C0 + identity]
        if flag != 1 or rf_index >= 20:
            raise ValueError("Favorites entry is outside the inspected HDZero-capable table rows")
        slots.append({
            "slot": slot, "label": BANDS[identity >> 3] + str((identity & 7) + 1),
            "stock_identity": identity, "stock_identity_hex": f"0x{identity:02x}",
            "rf_table_index": rf_index,
            "rf_register_word_hex": image[0xC720 + 4 * rf_index:0xC724 + 4 * rf_index].hex(),
            "second_tune_word_hex": image[0xEF08 + 4 * identity:0xEF0C + 4 * identity].hex(),
            "digital_mode_flag": flag,
        })
    return {
        "image_sha256": DECODED_SHA256, "band_order": BANDS, "selection_ram": "EXTMEM:0x0d85",
        "band_step": "CODE:0x0674", "channel_step": "CODE:0x06d6",
        "validation": "CODE:0x9d44", "tune_dispatch": "CODE:0x67e7",
        "slots": slots, "hardware_access": False, "patch_created": False,
        "limits": "Stock identities and literal table values only. Peripheral behavior is not simulated. "
                  "A virtual Favorites identity must not be passed to the 48-row stock tables.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config/favorite-channels.json")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = build_mapping(args.image.read_bytes(), json.loads(args.config.read_text(encoding="utf-8")))
    with args.report.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
