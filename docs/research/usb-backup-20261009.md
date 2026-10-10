# HDZero Monitor USB backup: 2026-10-09

AI assistance: OpenAI Codex implemented the bounded read tools, performed the authorized USB acquisition and wrote this report under the user's direction.

## Result

All three main SPI flash arrays were read twice in separate acquisitions through the Monitor's existing USB connection. The two copies of each target are byte-identical over the complete documented capacity. Acquisition finished successfully at `2026-10-09T08:23:50.341878+00:00`; it started at `08:11:39.745333+00:00`. Total binary output is 66 MiB.

The local backup directory is `artifacts/device-backups/20261009-usb-01`. It contains six `.bin` files, `manifest.json` and `verification.json`. Raw device backups are excluded from Git. The manifest has `success: true` and `byte_equal: true` for all three targets. A subsequent offline check independently recalculated all six file hashes and verified their recorded sizes.

| Target | JEDEC ID | Bytes per copy | SHA-256 of either full copy | Exact official 1.1.1 payload match |
| --- | --- | ---: | --- | --- |
| DM5680 | `EF4014` | 1,048,576 | `fb35263f0bc62cc1a43889da4313af3ace756c086aad8ef69d4bc6ed515b4055` | Yes |
| FPGA | `EF4018` | 16,777,216 | `a4b2b1cec69c5d042af51a439c472c127abf0c3d6f5ee9a8006956e212c6c36a` | Yes |
| MStar 8339 | `EF4018` | 16,777,216 | `68ffa3d3a94058e8e605a9f48179305502893c4c426706525aac4e1df5f9e887` | No: 132 differing bytes in one embedded filesystem |

All bytes beyond the respective official payload lengths are `FF`, in both copies of all three targets. The official payload sizes are 62,003, 907,418 and 7,306,038 bytes respectively; they are not the flash capacities.

## Connection and acquisition checks

The native USB descriptor was verified as CH341 `1A86:5512`; see [the descriptor report](usb-probe-identify-20261009.json). Exactly one matching present device was required, and HDZeroProgrammer was closed. No driver was installed or changed.

The installed x64 `CH341DLLA64.DLL` matched SHA-256 `7d7dd5405b88b2b0140fbc07251ced4f9774b81d0fcf45d59fa92222f4420971`, previously compared with the official programmer's bundled DLL. The routing and SPI protocol follow the inspected [official programmer source](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py).

Before each acquisition, the target's JEDEC ID was read twice and checked against the supported ID/capacity pair. At the beginning, near `0x10000` and at the end of each array, a 1,024-byte read was compared with four 256-byte reads. All boundary checks passed. Every native transfer and stream-mode change required a successful DLL return. Bus release occurred before closing each acquisition handle; no cleanup error was reported.

The only SPI commands implemented are JEDEC ID `9F` and array READ `03`. GPIO routing actively hands the flash bus to the bridge. No flash write-enable, program, erase, status-register write or security-register write was implemented or issued.

## MStar differences from the update file

The installed MStar payload SHA-256 is `756c823eba7408dab750fca775f980cb6faeae7289ac80ccfddf3f087dda96f4`. It differs from the official component at 132 bytes in 68 contiguous ranges. The first differing offset is `0x55E218`; the last exclusive end is `0x563C05`. All are within the embedded FAT volume starting at `0x55E000`.

Offline directory decoding finds the same existing files as the official volume, plus entries named `LDWS_Calibration.bin` and `FCWS_Calibration.bin` in the device copies. Differences include allocation/directory metadata and a byte in the latter file's data area. These names are SDK artifacts; they do not establish that automotive calibration functionality is active on the Monitor. No file contents or calibration values are published here.

Both CRC-covered regions identified in [the layout note](mstar-payload-layout-20261009.md) are byte-identical to the official component. This includes the candidate application region containing the channel strings. The full device copies remain the authoritative backup; replacing them with a release payload would discard the observed filesystem state.

## Validation and limits

Seven host tests passed before acquisition. They cover unknown IDs, inconsistent read sizes, interrupted output, full-file differences, rejection of write opcodes, address bounds and cleanup ordering. Actual hardware evidence consists of the six successful acquisitions and their full comparisons.

This is a verified reproducible acquisition of the three main SPI arrays. OTP/security registers, other nonvolatile storage and CPU RAM were not read. Restore/erase/program was not tested, and independence of USB recovery from a failed application remains unproven. No Favorites patch has been built or flashed. Normal video reception and menu operation after acquisition have not been independently observed by Codex.
