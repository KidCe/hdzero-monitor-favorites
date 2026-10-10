"""Prepare an unchanged, hash-pinned application fixture for Ghidra/emulation."""

import argparse
import json
from pathlib import Path

from offline_firmware import load_application


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    application, metadata = load_application(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / "mstar-application.bin").write_bytes(application)
    (args.output_dir / "input.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
