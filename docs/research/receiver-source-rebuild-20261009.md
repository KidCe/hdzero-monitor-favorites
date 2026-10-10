# Receiver source rebuild and experimental update packaging

Date: 2026-10-09. Target: HDZero Monitor 1R3, installed firmware 1.1.1.

AI assistance: Reverse-engineering tools, recovered assembly and documentation were developed with substantial assistance from OpenAI Codex under the user's direction.

## Result

Current follow-up: [saved settings and long-press scan guard](receiver-settings-scan-20261009.md) supersedes the candidate hashes, package paths and test counts below. This report retains the earlier v2 evidence.

The stock receiver now rebuilds byte for byte from **28,350 recovered 8051 assembly instructions**, plus explicit data/unresolved bytes. A Favorites build from assembly reproduces the independently tested decoded candidate exactly. Both builds have standard-format Monitor update packages, and the isolated original programmer file-parser accepts both packages without loading its DLL or opening USB.

This advances the requested maintainable firmware beyond binary-byte replacement. The two short selection routines are checked-in, commented assembly with named labels and parameters. The remaining recovered address partitions are generated locally as editable assembly. Their complete source includes are assembled by a separate, pinned native assembler; the expected stock/candidate binaries are only independent comparison oracles, not the assembler's inputs.

**Device operation is still unverified.** CODE loading after the old payload end, integrated mode/scan behavior, persistent settings, hardware tuning and independent recovery remain open. A parser-compatible file is not proof that it boots or receives correctly. The current packages are labeled `UNVALIDATED` and their manifests explicitly say `ready_for_device_use: false`. No device write occurred.

## What was reconstructed

| Measure | Result |
|---|---:|
| Original receiver bytes | 62,003 |
| Recovered instruction bytes | 48,283 |
| Original-image coverage by assembly instructions | 77.872% |
| Data/unresolved bytes retained explicitly | 13,720 |
| Recovered instructions | 28,350 |
| Source address partitions | 12, plus Favorites tables when enabled |

The coverage is a byte count of Ghidra-analyzed instructions, **not a percentage of semantically understood original source**. Original C declarations, names and build settings have not been recovered. Data, tables and unresolved gaps are emitted as `.db` directives. Numeric locations and fixed partition boundaries preserve existing ABI and control flow; expanding a routine requires a deliberate layout/branch review.

This reconstruction covers the **receiver component**. The FPGA remains its existing bitstream; the MStar remains the installed binary payload. The combined multi-component Monitor update has not been mostly reconstructed as source. That distinction is part of the remaining scope, not a claim that the full goal is complete.

`firmware/receiver/band_step.asm` and `channel_step.asm` describe the known short-step behavior, preserve the original save/refresh calls, and expose the band-count constants. The module names assigned to generated address partitions describe the region, not recovered original C module boundaries.

## Independent assembly and exact checks

The portable [naken_asm Windows build](https://www.mikekohn.net/micro/naken_asm.php), published as `naken_asm-2024-11-03.zip`, supports 8051 and raw binary output. We pin this acquisition:

| Artifact | SHA-256 |
|---|---|
| Download archive | `8c4e7b3ba2a9782922bd6d02592ca4b974bb986bba4b757abdf0c50a3cfbca08` |
| Assembler executable | `c2e2d8b4b546d3fcdf96b6bec6341f96c3bb8095cf7a7abbaaeb044c71af1089` |
| Rebuilt stock receiver | `ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652` |
| Rebuilt Favorites receiver | `7dba09cf8a62394e90df8a85917918c8fa187899afee4803ed6f6a7d723a1e81` |

Ghidra prints some direct SFR operands using names that also denote architectural registers. For example the original instruction at `06FD` is `53 E0 07`, the three-byte direct-ACC form, while `ANL A,#7` normally assembles as the two-byte form `54 07`. The source exporter preserves the addressing form according to the original opcode. Similar distinctions apply to PUSH/POP ACC and carry-bit versus carry-register instructions. The first mismatching reconstruction was rejected rather than accepted as equivalent behavior.

The final assembler result must match every independently expected byte. Wrong stock input, changed instruction bytes, overlaps, unexpected text, different tool hash and output mismatch reject the build. Failed builds leave no success manifest; existing successful outputs cannot be overwritten. The stock build proves the syntax/address translations across the complete exported instruction set, and the Favorites build proves the source changes reproduce the candidate now covered by 1,629 bounded instruction checks. The host suite now passes **27 tests**, including actual native assembly and package-geometry checks.

The added 56 candidate checks execute the idle path of main-loop scan service `6D6C` through its return boundary at `766D`. With `0767`, `0768` and `076E` zero, it initializes the stock scan list but preserves both current selection `0D85` and cached selection `0760`, including P1–P8. Long-press scan/configuration still requires separate investigation: button polling sets those flags at `0971`/`09BD`; active scan branches perform peripheral calls and can choose stock channels.

## Update packages and preserved device state

The [official programmer's `parse_monitor_fw`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py) reads three little-endian lengths after a two-byte prefix and then the receiver, FPGA and MStar payloads. The packager preserves prefix `01 00`, applies the published bit permutation to the rebuilt receiver, and updates the receiver length. The FPGA bytes come unchanged from the hash-pinned official 1.1.1 release. The MStar payload is extracted from the hash-pinned installed backup to preserve its 132 filesystem differences.

| Package | Bytes | SHA-256 |
|---|---:|---|
| Stock with installed MStar state | 8,275,473 | `8fb0d959612eebe6988e30feae5bccb9f4a3987649e4d578e0ab0f81f553ba0c` |
| Favorites with installed MStar state | 8,275,816 | `2671445f1f2cd650086ea344ecc77f219c90a32551c164f699317aff6f76adea` |

Compatibility checking uses only the unchanged `parse_monitor_fw` function extracted from the inspected official source, pinned to source-file SHA-256 `8f52d51212fc57169e932802391c8aaaa011b3aedc6ee4b46fb892836f10d280`. The module, its constructor, global objects, programmer GUI and hardware functions are not imported or executed. The independent strict parser additionally rejects truncated/extra data and invalid component sizes.

The page/block simulation reproduces the inspected writer's 256-byte program pages and 64 KiB erase blocks using private bytearrays. It then compares the entire projected arrays with the full installed backups:

| Target | Stock package changed bytes | Favorites package changed bytes | Favorites erase bytes | Favorites page bytes |
|---|---:|---:|---:|---:|
| Receiver, 1 MiB array | 0 | 392 (49 changed + 343 appended) | 65,536 | 62,464 |
| FPGA, 16 MiB array | 0 | 0 | 917,504 | 907,520 |
| MStar, 16 MiB array | 0 | 0 | 7,340,032 | 7,306,240 |

Both packages are accepted by the original file-parser. The projected stock arrays exactly match all three backup hashes. The projected Favorites receiver array hash is `af559f787e88a727eb461d4c7da435f56dee69e8632a9e131f347262bb704ca7`; FPGA and MStar remain equal to their full backups. These are software projections, not performed erase/program/readback operations. The official update workflow writes all three components even when two are unchanged; a future targeted device tool and recovery route still require verification.

## Local evidence and reproduction

The clean instruction export was repeated through `tools/Invoke-ReceiverSourceExport.ps1` at `artifacts/firmware-analysis/20261009-recovered-source-repro/instructions.json`. Successful build reports and complete generated source trees are at:

- `artifacts/firmware-analysis/20261009-recovered-source/stock-build-v4/`
- `artifacts/firmware-analysis/20261009-recovered-source/favorites-build/`
- `artifacts/firmware-analysis/20261009-recovered-source/stock-package/`
- `artifacts/firmware-analysis/20261009-recovered-source/favorites-package/`

The package directories contain `package.json`, `compatibility.json` and the respective `HDZero_Monitor-*-UNVALIDATED.bin`. A [compact evidence summary](receiver-source-rebuild-results.json) records the final hashes and validation boundaries. Raw firmware, generated complete source and private evidence remain in ignored artifact directories; tools and the two commented recovered selection routines are repository files.

```powershell
$py = 'python'
$stock = 'artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin'
$work = 'artifacts/firmware-analysis/new-source-rebuild'

& $py tools/setup_receiver_assembler.py
& tools/Invoke-ReceiverSourceExport.ps1 -OutputDirectory $work
& $py tools/monitor_receiver_source.py --stock $stock `
  --inventory "$work/instructions.json" --output-dir "$work/stock-build"
& $py tools/monitor_receiver_source.py --stock $stock `
  --inventory "$work/instructions.json" --output-dir "$work/favorites-build" --flavor favorites

# Requires the pinned official asset and complete installed MStar backup.
& $py tools/monitor_update_package.py `
  --official artifacts/firmware-analysis/20261009-recovered-source/HDZero_Monitor-v1.1.1.bin `
  --receiver "$work/favorites-build/receiver-rebuilt.bin" `
  --device-mstar artifacts/device-backups/20261009-usb-01/8339-pass1.bin `
  --output-dir "$work/favorites-package"

& $py tools/monitor_package_compatibility.py `
  --official-source artifacts/firmware-analysis/20261009-recovered-source/programmer-ch341.py `
  --package "$work/favorites-package/HDZero_Monitor-favorites-UNVALIDATED.bin" `
  --backups artifacts/device-backups/20261009-usb-01 `
  --report "$work/favorites-package/compatibility.json"
& $py -m unittest discover -s tests -v
```

These commands access files and local analysis tools only. Input hashes and expected bytes are version-specific; additional features need their own reviewed source change, independent expected image/mapping, relevant tests and updated package acceptance pins.

## Next work

There is additional static loading evidence from the official [Monitor 1.2.0 asset](https://github.com/hd-zero/monitor/releases/download/v1.2.0/HDZero_Monitor.bin), SHA-256 `3db0a81fe43869085b5455031c34bc69f19c998606c2fedf4085eb150fac8725`. Its FPGA and MStar components are byte-identical to official 1.1.1, while its decoded receiver is 63,159 bytes (`F6B7`), 813 bytes larger than our candidate. Its startup instruction at `004F` loads DPTR with `F695`; the 34-byte initializer reaches `F6B6`, above our highest appended address `F389`. This supports the inference that CODE loading is not fixed to the old 62,003-byte application extent. It is release/startup evidence, not an observed boot or runtime CODE read on this 1R3 Monitor. Local evidence: `artifacts/firmware-analysis/20261009-recovered-source/larger-release-evidence.json`.

Resolve the receiver's mode/scan and saved-state paths in the reconstructed source, and investigate CODE loading through `F389`. These offline tasks still allow progress while the Monitor remains disconnected. A later boot SPI observation or verified runtime CODE read may be needed to settle the loading boundary. Completion of the requested working firmware still requires appropriate device/recovery evidence and real Favorites operation.
