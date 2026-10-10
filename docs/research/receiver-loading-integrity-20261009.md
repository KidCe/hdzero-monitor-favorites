# Receiver CODE loading and integrity: bounded offline evidence

Date: 2026-10-09. Target: HDZero Monitor 1R3, installed firmware 1.1.1. Candidate: Favorites v4, P1–P8 = L6, L7, R1, R2, F2, F4, R7, R8.

AI assistance: OpenAI Codex performed this file-only investigation and wrote the analysis tool and note under the user's direction. No hardware APIs, programmer DLLs, USB access or flash operations were performed.

## Finding

The available evidence supports placing the additional receiver CODE at `F233`–`F3BD`: the candidate fits below both the programmer's 64 KiB receiver limit and CODE addresses required by the official 1.2.0 release. However, **loading these bytes on this particular Monitor and any device-side integrity enforcement remain unverified**. The update container's receiver length is host-side metadata; it is not a length header stored ahead of the receiver code in its SPI flash.

There is no offline evidence requiring a change to MStar checksums for the current receiver-only modification. Its two previously identified CRC-covered regions and the FPGA image remain unchanged. That is a scoped result, not proof that the receiver has no separate integrity check.

## Raw flash layout and host update path

The installed 1 MiB receiver array exactly matches the official encoded 1.1.1 component in its first 62,003 bytes. Every byte from array offset `F233` to `FFFFF` is `FF`. At flash offset zero the encoded bytes start `04 00 9A`, which decode to `02 00 39` / `LJMP 0039`. The update container instead starts with `01 00` and three little-endian lengths, totaling 14 header bytes. These are distinct layouts; no separate bootloader image or metadata is present in the acquired receiver main-array tail. This does not inventory internal ROM or separate flash registers.

In the pinned official programmer source, `parse_monitor_fw` consumes the container header and returns separate payload buffers. `fw_write_to_flash` programs each buffer from SPI address zero in 256-byte pages, erasing 64 KiB blocks and padding a final page with `FF`. The Monitor update path supplies all three component buffers. Neither the container header nor a new receiver checksum is written by these inspected functions. Their Monitor readback loop is commented out. The variables named `write_crc`/`read_crc` accumulate byte sums in separate helpers; they do not establish device boot verification. [Pinned programmer source](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py).

The official VTX post-build script transforms each input byte by a fixed bit permutation and emits the transformed binary. No signature or checksum is added by that function. This explains the transformation that reproduces the Monitor component exactly; it does not establish the Monitor boot controller's behavior. [Pinned encoding implementation](https://github.com/hd-zero/hdzero-vtx/blob/ad396315680f64ad5797fb0fe53bbd73e9f448ba/script/post_script.py).

## Larger official receiver: direct CODE-read evidence

The comparison was rerun against the current v4 image; earlier notes about an 813-byte margin applied to an older candidate.

| Image | Decoded bytes | Inclusive final CODE address | Startup initializer source | Inclusive initializer end |
| --- | ---: | --- | --- | --- |
| Official 1.1.1 | 62,003 | `F232` | `F211` | `F232` |
| Favorites v4 | 62,398 | `F3BD` | `F211`, unchanged | `F232`, unchanged |
| Official 1.2.0 | 63,159 | `F6B6` | `F695` | `F6B6` |

In both releases the decoded instruction at `0046` is `MOV R1,#22` (34 bytes), and `004F` loads DPTR with the initializer address above. The startup loop at `0057`–`0063` uses `MOVC A,@A+DPTR` at `0058`, then increments DPTR, so it requires CODE reads all the way to the listed initializer end. Both 34-byte initializer contents are byte-identical. The v4 image therefore ends **761 bytes below** a CODE address required during official 1.2.0 startup, with **3,138 bytes remaining** below 65,536.

The 1.2.0 release's FPGA and MStar components are byte-identical to official 1.1.1. This rules out the simple explanation that a changed FPGA or MStar payload is required merely because the official receiver became larger. It supports an inference that a fixed 62,003-byte extent is not universal across the released system. It does not prove that 1.2.0 was physically tested on this board revision, that the same DM5680 internal ROM is used across revisions, or that the boot engine copies a whole 64 KiB block. Fixed-block loading, execute-in-place behavior and another loader mechanism remain hypotheses. [Official 1.1.1 asset](https://github.com/hd-zero/monitor/releases/download/v1.1.1/HDZero_Monitor.bin), [official 1.2.0 asset](https://github.com/hd-zero/monitor/releases/download/v1.2.0/HDZero_Monitor.bin).

## Integrity boundaries

The unchanged MStar payload contains standard CRC32 matches for regions described in the [MStar layout report](mstar-payload-layout-20261009.md): 36,956 bytes beginning at payload `2000` match stored `2B0B711A`, and 4,326,948 bytes beginning at `D000` match stored `EEC8D9BE`. These relationships concern that component. They do not cover the separate receiver SPI payload in the inspected update layout.

A bounded search of MStar ASCII data found generic `BOOT CheckSum`, firmware-update and boot messages. A read-only Ghidra export queried their candidate runtime addresses `202AB427`, `202AB478`, `202ABFED` and `202AC022`, using the previously supported mapping for the application. No references were recovered for those exact targets in the existing analysis. Therefore none of these strings has been connected to DM5680 loading or integrity, and they are not evidence for a receiver checksum algorithm. The unmodified FPGA remains an opaque bitstream; its equality across releases cannot reveal its boot logic.

The receiver instruction inventory covers 48,283 of 62,003 original bytes. The reset/startup emulator described in [the connected/startup report](receiver-connected-startup-20261009.md) executes code after the fixture has already been mapped into CODE space. It cannot establish the preceding physical ROM/FPGA loading stage. Neither partial instruction coverage nor a successful emulator run proves the absence of a hidden check.

## Evidence and reproduction

`tools/loading_integrity_audit.py` pins every binary input and repeats the container split, byte permutation, whole receiver-tail check, startup initializer range, component comparison and MStar CRC calculations. It imports no hardware utility. Its first report is `artifacts/firmware-analysis/20261009-loading-integrity/evidence.json`. The read-only MStar export and headless log are in the same directory under `mstar-refs/` and `mstar-refs.log`; they retain the unsuccessful reference query as a bounded negative result.

| Input | SHA-256 |
| --- | --- |
| Official 1.1.1 container | `6b7f7cd53be329eaa4059b7b40c2e3e8f2fad1d8ecd94bfe0cb7a228131f7041` |
| Official 1.2.0 container | `3db0a81fe43869085b5455031c34bc69f19c998606c2fedf4085eb150fac8725` |
| Decoded 1.1.1 receiver | `ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652` |
| Decoded 1.2.0 receiver | `846fb02167e2eee5e960000ed00ab3fa6fc1910e7b3a848b9e1da2854e20c9eb` |
| Decoded Favorites v4 | `7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16` |
| Installed receiver main array | `fb35263f0bc62cc1a43889da4313af3ace756c086aad8ef69d4bc6ed515b4055` |
| Local pinned programmer source | `8f52d51212fc57169e932802391c8aaaa011b3aedc6ee4b46fb892836f10d280` |

```powershell
$loadingPython = 'python'
& $loadingPython tools/loading_integrity_audit.py `
  --report artifacts/firmware-analysis/new-loading-integrity/evidence.json
```

The script refuses a changed input hash or an existing report path. Analysis outputs remain separate from update packages.

## Next evidence needed

The current receiver layout does not need another relocation or MStar CRC patch on the evidence available. Before relying on it physically, retain the verified originals and validate the programming/recovery route with exact readback; the original Monitor writer does not provide that verification itself.

To settle loading before modifying the device, a boot-time receiver SPI capture would be useful: record the read commands and ranges after a real power cycle, with USB absent. A capture that only shows many clocks or unverified MOSI/MISO is insufficient. A verified read covering `F3BD` would support availability but must still be connected to CODE loading; a bounded runtime CODE read or observation of the candidate guard's execution would be stronger. Internal ROM documentation or a dump could also answer the question, but neither is present in the existing backup.

To settle actual acceptance, the candidate must boot and execute its appended table/guard code on this Monitor, followed by RF, display, persistence and restoration checks. These are device steps; the offline evidence above must not be relabeled as their completion.
