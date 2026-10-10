# MStar Monitor payload: bounded layout findings

Date: 2026-10-09. AI assistance: OpenAI Codex performed the offline analysis and wrote this note under the user's direction. No firmware was changed.

Inputs: the hash-pinned official Monitor 1.1.1 component, SHA-256 `ccae315a799a3f9ebc46ef0516585361a9b3daea7c0b6331eaba151220db80b9`, and the [verified USB copies](usb-backup-20261009.md). The official 1.2.0 MStar component is byte-identical to 1.1.1.

## Header and CRC observations

`MCR5` markers occur at payload offsets `0`, `0x1000` and `0xC000`. At the latter two headers, the little-endian word at header `+0x14` equals the length of a region starting at header `+0x1000`; standard `zlib.crc32` of that region exactly matches the word at header `+0x1C`.

| Header offset | Region start | Exclusive region end | Region bytes | CRC32 / header value | Device region equals official |
| --- | --- | --- | ---: | --- | --- |
| `0x1000` | `0x2000` | `0xB05C` | 36,956 | `2B0B711A` | Yes |
| `0xC000` | `0xD000` | `0x42D624` | 4,326,948 | `EEC8D9BE` | Yes |

The first region begins with an ARM branch followed by `IPL_`; the second begins with repeated ARM little-endian `ldr pc` vector-style instructions. Bootloader and application are reasonable working labels. The two checksum matches establish stored-region relationships, not proof of the bootloader's enforcement, a complete integrity scheme or the semantics of other header words. In particular, header `+0x18` has not been assigned a verified meaning.

The calculation is reproducible with the component bytes in `data`:

```python
import struct
import zlib

for header in (0x1000, 0xC000):
    size = struct.unpack_from("<I", data, header + 0x14)[0]
    stored = struct.unpack_from("<I", data, header + 0x1C)[0]
    start = header + 0x1000
    assert start + size <= len(data)
    assert zlib.crc32(data[start:start + size]) & 0xFFFFFFFF == stored
```

## Candidate address mapping and channel metadata

A consistent candidate translation for the inspected application code/data is `runtime_address = payload_offset + 0x1FFFB000`. For example, a little-endian word at `0x7A9B4` contains `0x202B4C58`; the `Channel_Switch` string is at `0x2B9C58`. The same translation fits independent `Channel_ID`, `LastChannel` and `CarDV SDK` references. This is a supported analysis hypothesis for these regions, not a globally verified memory map.

At `0x7A928`–`0x7A9A8`, ARM little-endian decoding gives a coherent function with a stack prologue/epilogue, loops over 32-byte records, string accesses and a comparison call. The instruction at `0x7A978` loads the word at `0x7A9B4`, connecting that decoded code to `Channel_Switch`. Thumb decoding of the same bytes lacks that coherent flow. This establishes a useful ARM-mode region; it does not rule out Thumb code elsewhere or prove the exact CPU model.

Candidate 32-byte setting records start at `0x355574`, `0x355594` and `0x355634`. Their name pointers resolve to `Channel_Switch`, `Channel_ID` and `LastChannel`; neighboring description pointers resolve to `0:On, 1:Off`, `0:Channel_0, 1:Channel_1, 2:Channel_2` and `0:Auto, 1:Manual`. The common function-pointer values are `0x20074420` and `0x20074018`. Do not equate these descriptions with RF bands, give undocumented record fields names, or assume this table is the menu's active tuning path.

Capstone 5.0.9 was installed only into the temporary analysis directory and used for offline decoding; no package was added to the hardware utility's runtime. The Windows wheel SHA-256 is `732cedbbb56d42e723f14d7af6387f1454194a820b4b96b56d1e53f865ef85d0`, checked against [the official PyPI package](https://pypi.org/project/capstone/5.0.9/). [Capstone's Python API](https://www.capstone-engine.org/lang_python.html).

## Embedded filesystem observations

Four 512-byte-aligned boot-sector candidates have `MSDOS5.0`, the `55AA` signature and internally consistent FAT BIOS parameter blocks. Their offsets are `0x4A6000`, `0x55E000`, `0x66E000` and `0x6AE000`. The volume at `0x55E000` specifies 512-byte sectors, one sector per cluster, one reserved sector, two FATs of seven sectors, 256 root entries and 2,176 total sectors. These values place its root directory at `0x55FE00`, cluster data at `0x561E00` and exclusive volume end at `0x66E000`.

All 132 installed-versus-release differences are inside this volume. Existing directory names include `defnetconf.txt`, `defset.txt` and `TestResult.bin`; device-only entries include the two calibration filenames noted in the backup report. Do not assume that every embedded SDK resource or network feature is used by the Monitor.

## Next analysis

Trace callers of the settings accessors and of the function referencing `Channel_Switch`, then connect stock button input, displayed band/channel, saved selection and RF tuning. Validate segment copying/relocation and the integrity routine before modifying instructions. The fixed Favorites list remains `L6, L7, R1, R2, F2, F4, R7, R8`; no patch location or executable spare area is yet verified.

The subsequent [Ghidra and emulation report](ghidra-and-emulation-20261009.md) records traced settings/UART functions and 22 passing original-code checks. It confirms the packed `Display_hd_sd` / `Channel_Switch` query, without establishing the RF selection path.
