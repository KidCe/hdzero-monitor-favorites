# Offline Ghidra analysis and original-function emulation

Date: 2026-10-09. Target: Monitor PCB 1R3, firmware 1.1.1, Favorites `L6, L7, R1, R2, F2, F4, R7, R8`.

Follow-up: [receiver decode and selection analysis](receiver-8051-selection-20261009.md) now establishes a receiver-local button/selection/tuning call path and 221 passing 8051 fragment checks. The ARM results below describe the earlier MStar stage; its missing RF link is addressed by the receiver investigation, without claiming a complete hardware simulator or working patch.

## Result and limits

A local Ghidra project and reproducible Unicorn ARM function harness are now available. **22 original-code checks passed**, including a deliberate access to unmodeled RAM that was correctly blocked. The harness runs actual instructions extracted from the device backup, rather than a Python rewrite of their behavior. No USB access, device commands, firmware writes or patched images were involved in this phase.

This establishes an offline test environment for small functions. It does **not** establish a working Favorites patch, a complete Monitor simulator, a validated RF channel index map, or recovery after a failed flash. Display, FPGA, RF reception, peripheral timing and DVR behavior are not modeled. The stock button-to-tune path remains the main missing link.

## Inputs and mapping

The input is the repeated, byte-equal `8339-pass1.bin` acquisition described in [the backup report](usb-backup-20261009.md). Its SHA-256 is `68ffa3d3a94058e8e605a9f48179305502893c4c426706525aac4e1df5f9e887`.

The application is extracted from payload offset `0xD000`, length `0x420624` (4,326,948 bytes), after checking both previously identified CRC-covered regions. Application SHA-256: `cf55cfc99d8db202c9f6f93348b4241d048c2dfd1ce5b6d2c82dc6ead4607c34`. These application bytes match the official component. Extraction does not alter the input or produce an update container.

Ghidra import: `ARM:LE:32:v7`, little endian, default compiler specification, application base `0x20008000`. For the inspected application, candidate runtime address = MStar payload offset + `0x1FFFB000`. Literal pointers, coherent ARM control flow and successful original-function execution support this mapping. It remains an analysis mapping rather than a fully verified physical memory map. Ghidra's extra uninitialized block ending at `0x21000000` is a navigation aid, not evidence of installed RAM capacity; the emulator does not map that entire block.

Project: `artifacts/ghidra/Monitor-1R3.gpr`. Derived images, raw decompilations and the Ghidra database are excluded from Git. The initial analysis found approximately 10,000 candidate functions. Their boundaries, names and inferred signatures are not equivalent to recovered source code; tail branches can cause Ghidra to merge shared code into a caller.

## Functions and data traced

All addresses below use the candidate mapping.

| Address | Observed behavior | Relevance / remaining uncertainty |
|---|---|---|
| `0x20075928` | Searches 32-byte settings records for `Display_hd_sd` and `Channel_Switch`; returns `2 * Channel_Switch + bool(Display_hd_sd)` for the tested values. | Verified with original instructions for all four 0/1 combinations. This is a settings query, not a tune function. |
| `0x2023EDC0` | Property dispatcher: `0xD1` reaches the packed settings query; `0x7C` and `0x7D` read bytes 0 and 1 of a RAM structure. | Original-code tests confirm these paths. The two bytes must not yet be labeled as band/channel. Its `0xD8` path references `AutoScan`, not `LastChannel`. |
| `0x20074CB4` | Returns structure pointer `0x20431DD4`. | Explains the dispatcher RAM dependency; structure ownership is still being traced. |
| `0x20350574`, `0x20350594`, `0x20350634` | Settings records named `Channel_Switch`, `Channel_ID`, `LastChannel`. | Names and locations confirmed statically; menu names alone do not prove RF semantics. |
| `0x20084500` | Draws a “Channel Occupied” panel from a count, entry indices and per-entry status. | Connects channel labels to OSD drawing; producer of occupancy data not yet established. |
| `0x20351BD4` | Forty 32-byte label slots: A1–A8, B1–B8, E1–E8, R1–R8, F1–F8, each including its frequency text. | Label data, not a verified hardware tuning table. It contains no Low band. |
| `0x2007F8D0` | Initializes UART instance 3 with callback `0x2007F8C8`, which leads to a software receive ring. | Called from the main application task at `0x2007692C`; pad routing and peer chip remain unknown. |
| `0x2007F954` | Parses received bytes starting with `0x3C`, accumulates XOR over subsequent fields, dispatches type values 1, 2, 3, 4 and `0xFF`. | Empty/noise/bad-checksum paths tested with the original parser and ring reader. No valid command was sent to hardware. |
| `0x2007FC2C` | Computes XOR of `count` bytes starting at `buffer + 1`. | Four original-code cases confirm that the start marker is excluded. |
| `0x20434DED` | Type-2 parser path copies a received byte here after checksum success; video-state code reads/resets it. | This currently looks like an application/video control state, not an established RF channel identifier. |
| `0x2007FC50`…`0x2007FD7C` | Parser handlers construct responses beginning with `0x3E`; send path `0x2007F940` reaches UART writer `0x2021AAD0`. | Protocol direction is established statically. Meaning of requests, responses and physical endpoints is not established. |

Two tempting leads are insufficient for an RF patch: `Scan Channels: [ch,RSSI]` occurs beside `wlan_scan_netwrok` diagnostics, while the `Frequency %d` reference at `0x201E2BAC` leads into a clock/register routine. Neither is a confirmed HDZero tuning function. The five-band description belongs to a record named `PassWordkey`; its presentation must not be assumed to reflect a conventional band-setting field. Exact string cross-references to the isolated `Channel F2/F4` labels were not found; this does not prove the labels are unreachable.

## Original-code tests

| Checks | Count | What is actually validated |
|---|---:|---|
| Packed display/switch getter | 4 | Correct return values for both input bits; original comparison routine executes. |
| Property `0xD1` | 4 | Original dispatch reaches the same result. |
| Properties `0x7C` / `0x7D` | 6 | Correct byte reads for three explicitly supplied RAM fixtures, including 255/254. These are byte-reader tests, not valid channel-range claims. |
| Unmodeled settings RAM | 1 | Original getter stops at `0x20431DD4` instead of silently receiving fabricated zeroes. |
| UART XOR helper | 4 | Zero-length and selected packet checksums. |
| UART empty/noise/bad checksum | 3 | Original parser/ring reader returns zero; its dispatch state is reset and the reported control byte stays zero. |

The image is readable/executable and CPU writes to it are prohibited. The stack is readable/writable and non-executable. Only explicitly declared RAM bytes are permitted, even where page alignment requires mapping a larger page. Instruction execution outside the original image and unknown/protected memory accesses stop the run. Each call is bounded to 100,000 instructions and one second. No hardware API is replaced with a success-returning stub.

Latest full local result: `artifacts/firmware-analysis/20261009/original-function-tests-v2.json`. The independent host guard suite also passes **9 tests** (seven existing USB-backup fake-bridge checks plus two offline guards). These counts describe different suites and neither represents physical validation.

## Reproduce locally

The current PC has hash-pinned portable Ghidra 12.1.4, JDK 21 and Unicorn 2.1.4 under `%USERPROFILE%\.cache\hdzero-monitor-tools`. Installation changes are scoped to that directory; global Java/PATH settings were not changed. Tool provenance is in `tools/setup_offline_tools.py` and the local `tools.json`. See the [official Ghidra release](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build) and [Unicorn documentation](https://www.unicorn-engine.org/docs/tutorial.html).

From the workspace, using the installed Python executable:

```powershell
$py = 'python'

# Use a new output directory/report filename for each run.
& $py tools/monitor_offline_prepare.py `
  --input artifacts/device-backups/20261009-usb-01/8339-pass1.bin `
  --output-dir artifacts/firmware-analysis/new-run

& $py tools/monitor_function_emulator.py `
  --input artifacts/firmware-analysis/new-run/mstar-application.bin `
  --report artifacts/firmware-analysis/new-run/function-tests.json

# The existing project can be re-exported without repeating the full analysis.
& tools/Invoke-MonitorGhidra.ps1 `
  -Application artifacts/firmware-analysis/new-run/mstar-application.bin -Refresh

& $py -m unittest discover -s tests -v
```

For a new project, omit `-Refresh` and choose an unused `-ProjectName`. The import runner verifies the fixture hash and checks that both Ghidra scripts finished; a headless exit code alone is not sufficient evidence. The fixture loader accepts only the known device array, official MStar component or unchanged extracted application. It intentionally rejects modified images at this baseline stage. Future candidate-image tests need a separately guarded patch manifest and an explicit candidate loading path.

## Next implementation work

1. Trace stock button events and GPIO/I2C calls through the receiver/FPGA interface. Determine whether the MStar selects channels or receives channel/status information from another component. The UART parser found here must not be treated as that interface without further evidence.
2. Establish Monitor-specific identifiers for Low, Race and F channels and preserve the complete stock tuning sequence. An OSD text change alone cannot implement Favorites.
3. Expand the original-function harness at the verified selection boundary. Compare stock traces with proposed `Favorites slot -> original channel identity` traces for every slot, both directions, wraparound and invalid persisted values. Declare any hardware boundary explicitly; do not hide it behind a dummy success.
4. Produce a version-specific offline patch only after those traces identify a bounded hook, storage, branch reach and integrity behavior. Keep changes separate from original fixtures and compare all changed bytes.
5. Before a device write, verify recovery independence and then measure real Low/F/R tuning, video reacquisition, recording and persistence. Function emulation cannot substitute for those checks.

No further USB session is needed for the work above until an actual hardware observation is required. The Monitor can remain disconnected and powered off during offline analysis.
