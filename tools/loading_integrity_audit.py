"""Reproduce bounded CODE-loading evidence from pinned files without hardware access."""

import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path


PINS = {
    'v111': '6b7f7cd53be329eaa4059b7b40c2e3e8f2fad1d8ecd94bfe0cb7a228131f7041',
    'v120': '3db0a81fe43869085b5455031c34bc69f19c998606c2fedf4085eb150fac8725',
    'v4': '7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16',
    'backup': 'fb35263f0bc62cc1a43889da4313af3ace756c086aad8ef69d4bc6ed515b4055',
    'programmer': '8f52d51212fc57169e932802391c8aaaa011b3aedc6ee4b46fb892836f10d280',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pinned(path, name):
    data = path.read_bytes()
    if digest(data) != PINS[name]:
        raise ValueError(f'Unexpected {name} input: {path}')
    return data


def split(data):
    lengths = struct.unpack_from('<3I', data, 2)
    if sum(lengths) + 14 != len(data):
        raise ValueError('Inconsistent container extent')
    pos, result = 14, {}
    for name, size in zip(('receiver', 'fpga', 'mstar'), lengths):
        result[name] = data[pos:pos + size]
        pos += size
    return result


def decode(data):
    # Inverse of the pinned official VTX build script's permutation.
    positions = (7, 2, 5, 1, 3, 4, 0, 6)
    table = bytes(sum(((value >> source) & 1) << target
                      for target, source in enumerate(positions))
                  for value in range(256))
    return data.translate(table)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace
    recovered = root / 'artifacts/firmware-analysis/20261009-recovered-source'
    stock = split(pinned(recovered / 'HDZero_Monitor-v1.1.1.bin', 'v111'))
    newer = split(pinned(recovered / 'HDZero_Monitor-v1.2.0.bin', 'v120'))
    candidate = pinned(root / 'artifacts/firmware-analysis/20261009-favorites-candidate-v4/receiver-candidate-ANALYSIS-ONLY.bin', 'v4')
    backup = pinned(root / 'artifacts/device-backups/20261009-usb-01/5680-pass1.bin', 'backup')
    programmer = pinned(recovered / 'programmer-ch341.py', 'programmer')
    observations = []
    for version, parts in (('1.1.1', stock), ('1.2.0', newer)):
        raw = decode(parts['receiver'])
        if raw[0x4F] != 0x90 or raw[0x46:0x48] != bytes.fromhex('7922'):
            raise ValueError('Expected startup initializer instructions absent')
        source = int.from_bytes(raw[0x50:0x52], 'big')
        observations.append({'version': version, 'encoded_bytes': len(raw),
                             'decoded_sha256': digest(raw), 'reset_0_2_hex': raw[:3].hex(),
                             'initializer_source': hex(source), 'initializer_bytes': 34,
                             'initializer_last_CODE_address': hex(source + 33),
                             'initializer_hex': raw[source:source + 34].hex(),
                             'initializer_reaches_image_end': source + 34 == len(raw)})
    crc_regions = []
    for header in (0x1000, 0xC000):
        data = stock['mstar']
        size, stored = struct.unpack_from('<I', data, header + 0x14)[0], struct.unpack_from('<I', data, header + 0x1C)[0]
        actual = zlib.crc32(data[header + 0x1000:header + 0x1000 + size]) & 0xFFFFFFFF
        if actual != stored:
            raise ValueError('MStar region CRC mismatch')
        crc_regions.append({'header_offset': hex(header), 'region_bytes': size, 'crc32': f'{actual:08x}'})
    report = {'format': 'monitor-loading-integrity-evidence-v1', 'hardware_access': False,
              'device_loading_verified': False, 'device_integrity_verified': False,
              'input_pins': PINS, 'release_startup': observations,
              'candidate_bytes': len(candidate), 'candidate_last_CODE_address': hex(len(candidate) - 1),
              'v120_bytes_beyond_candidate': len(newer['receiver']) - len(candidate),
              'candidate_bytes_below_64k': 65536 - len(candidate),
              'unchanged_official_components': {name: stock[name] == newer[name] for name in ('fpga', 'mstar')},
              'backup_prefix_exact_official_receiver': backup[:len(stock['receiver'])] == stock['receiver'],
              'backup_tail_non_ff_bytes': sum(value != 255 for value in backup[len(stock['receiver']):]),
              'backup_tail_starts': hex(len(stock['receiver'])),
              'container_header_hex': pinned(recovered / 'HDZero_Monitor-v1.1.1.bin', 'v111')[:14].hex(),
              'flash_first_16_encoded_hex': backup[:16].hex(),
              'flash_first_16_decoded_hex': decode(backup[:16]).hex(),
              'programmer_source_bytes': len(programmer), 'mstar_crc_regions': crc_regions,
              'limits': ['Release comparison does not establish board revision compatibility.',
                         'No dump of DM5680 internal boot ROM or boot SPI capture exists.',
                         'Unchanged MStar CRC regions do not establish receiver integrity rules.']}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    if args.report.exists():
        raise ValueError('Refusing to overwrite an existing report')
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
