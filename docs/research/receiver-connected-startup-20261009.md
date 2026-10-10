# Receiver Favorites: connected CPU paths and startup boundary

Date: 2026-10-09. Target: installed Monitor 1R3 / receiver firmware 1.1.1, Favorites candidate v4.

The firmware bytes are unchanged from the [settings/scan candidate](receiver-settings-scan-20261009.md). P1–P8 remain L6, L7, R1, R2, F2, F4, R7, R8. This follow-up tests interactions between recovered routines, rather than adding features. AI assistance follows the project README disclosure.

## Connected CPU execution

The v4 suite passes **5,735 checks**, comprising the prior 4,583 checks and **1,152 connected sessions**. The report is `artifacts/firmware-analysis/candidate-run-20261009-182947-828/candidate-tests.json`. Candidate SHA-256 remains `7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16`.

| Connected path | Cases | Verified behavior |
|---|---:|---|
| Band/channel step → settings-save entry → complete validator → return | 448 | All 56 selections, both directions, valid and erased other fields; actual nested calls and return addresses |
| Classified P long press → idle scan service → release → channel step → save validator | 32 | One RAM instance across stages; P is retained during held/idle stages and steps correctly on release |
| Input-mode/scan/cache gate → receiver RF-index lookup when needed | 672 | Analog input, active scan or unchanged cache skips tuning; changed digital selection reaches the expected RF index |

`ReceiverConnectedTests.java` executes actual 8051 `LCALL`/`RET` instructions. SP begins at `40`, as observed in startup. Tests verify live and maximum SP and the bytes of nested return addresses. Execution permits only each stage's code ranges, its explicit RAM locations and stack bytes `41..48`. Bank-zero RAM/register aliases remain explicit.

The harness schedules separate stages by setting PC; it does not run the entire Monitor main loop or physical button classification. It never injects a new RAM state between held/idle/release stages. Save execution stops at `9F2F`, before the real delay and bus writes. RF lookup stops at `0C83`, before hardware transactions. No EEPROM acknowledgment, RF lock, display frame or elapsed device timing is fabricated.

## Runtime initialization model

Startup jumps from `0000` to `0039`, sets SP to `40`, calls the pure hook at `C683`, copies 34 CODE bytes from `F211..F232` to EXTMEM `10DA..10FB`, clears internal RAM and EXTMEM `0001..10D9`, initializes selected globals, then reaches main at `8C2F`. The first main instruction calls hardware setup `7A76`; the startup test stops before that call.

Ghidra's generic 8051 model requires explicit architectural support for this path:

- Direct SFR `81` must alias the SP CPU register.
- Bank-zero internal bytes `00..07` must alias R0–R7. Host snapshots explicitly take these eight bytes from the CPU registers because host reads bypass execution filters.
- Startup bit operands 4, 5, 8 and 9 must alias bits in internal bytes `20/21`.
- `MOVX @R0,A` at `0059` must use the P2 high byte from SFR `A0`. Generic Sleigh's `RiX` operand uses only R0. The harness checks exact opcode `F2` and executes the standard `P2:R0` write for that instruction, then advances PC by one. It rejects any destination outside the expected 34-byte sequence.

These are narrowly declared CPU-model adapters. They do not stand in for a peripheral operation, a successful hardware boot, or proof that device ROM loads appended CODE. Existing selection tests use `MOVX @DPTR` and are not changed by this paged-address adapter.

Run the separate comparison with existing validated Ghidra projects:

```powershell
& tools/Invoke-ReceiverStartupGhidra.ps1
```

The startup runner rejects script errors even when headless Ghidra itself exits with code zero. It compares both images against independently constructed expected RAM, then compares their complete modeled startup state for identical initial RAM patterns.

**All four startup cases passed**: stock and Favorites, each with initial RAM filled with `A5` or `5A`. Each reaches `8C2F` after 14,041 modeled instructions, including 34 explicit paged-MOVX instructions. SP reaches `42` during the actual hook call and returns to `40`. The entire 4,352-byte EXTMEM fixture and 256-byte internal CPU/RAM view match their independent oracle and match between images for each fill. The 4,451 p-code external-write bytes exclude the separately counted 34 adapter writes. Report: `artifacts/firmware-analysis/startup-run-20261009-184329-159/comparison.json`.

## Remaining device boundary

The experimental update package remains byte-identical to the prior v4 package, SHA-256 `06edaccf86a6f3ae7e6de0146e54027bc7a4de2372436fcb6d22213d4de2d12b`. The original file-parser and offline flash projection accept its structure; no device programming took place.

Still required: actual appended CODE loading, RF reception across all Favorites, display/recording behavior, complete mode transitions, saved selection retention, and demonstrated recovery independent of a working application. `feature_acceptance` and `ready_for_device_use` remain false.

The [deferred faster-switching task](../tasks/fast-channel-switching.md) starts only after physical Favorites validation. It is not part of the current firmware change.
