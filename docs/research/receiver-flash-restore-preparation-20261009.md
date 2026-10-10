# Receiver-only flash and restoration preparation

Date: 2026-10-09. Target: installed Monitor 1R3 / 1.1.1 and Favorites v4. This work remained offline. AI assistance follows the project README disclosure.

Subsequent device session: the [receiver USB preflight](receiver-usb-preflight-20261009.md) completed successfully with two full reads matching the original backup, unchanged status and normal operation confirmed by the user. SFDP returned only `FF` bytes. The offline results below remain historical; hardware programming and independent recovery are still unvalidated.

## Update: native receiver-only write adapter (offline-tested, 2026-10-09 evening)

External in-circuit access was ruled out the same evening: the receiver flash VCC is part of the board-wide 3.3 V rail (see the [external-access notes](external-ch341-recovery-references-20261009.md)). The built-in, GPIO-routed CH341 path is therefore the chosen recovery route. Its independence from receiver firmware contents is an inference from the hardware bus handover, not yet demonstrated after a failed write.

[`tools/monitor_usb_receiver_write.py`](../../tools/monitor_usb_receiver_write.py) implements the adapter. The protocol previously in `simulate()` now lives in a shared `execute()` in the plan module, so the simulation and the native session run the identical sequence; `simulate()` still accepts only the local NOR model.

- **Default is a read-only dry run:** JEDEC twice, SR1/SR2 must be exactly `00/00`, two full reads must match, then `make_plan`/`validate_plan` and saved `plan.json`. No `06`/`02`/`D8` is sent.
- **Writing** needs `--execute-write` plus `--confirm-after-sha256` equal to the mode's expected full-array hash (Favorites `e3f54fe3…`, restore `fb35263f…`). Mutating opcodes are additionally rejected unless the session is armed, and disarmed on close.
- Every native transaction passes an exact-shape filter first: `05 00`, `35 00`, `9F×6`, `06`, `04`, `D8 000000` only, `02` with a page-aligned address inside block 0 and exactly 256 bytes, `03` reads ≤1 KiB within 1 MiB with zero dummy bytes. Chip/sector erase, status writes and anything else never reach the DLL.
- BUSY polling uses wall-clock deadlines (erase 6 s, page 0.5 s; datasheet maxima 2 s / 3 ms). The pre-write session deadline is checked only before mutation, so a started block is never deliberately abandoned.
- After the protocol's own full readback, an independent full pass is saved as `5680-after.bin` and must equal the expected array; status must return to `00/00`. Progress is written to `write-session.json` after every mutation. On failure after mutation began, the report says to rerun `--mode restore` before power-cycling.
- GPIO release precedes handle close on every path (inherited from the validated read bridge).

Seven new tests run the **real bridge code** with only the DLL entry points replaced by the NOR model: dry run without mutation, Favorites then restore round-trip (244/243 pages), interruption at page 20 followed by successful restore, stuck BUSY hitting the wall-clock deadline, SR2/protection/preimage mismatches stopping before mutation, arming and command-shape rejection before native I/O, and CLI confirmation mismatch. **Whole suite: 63 tests pass.**

**First hardware dry run (read-only), 20:05:56–20:06:17 UTC:** only the Monitor's CH341 present (`1A86:5512`; external breakout unplugged by the user), mode `favorites`, no `--execute-write`. JEDEC `EF4014` twice, SR1/SR2 `00/00`, two full reads equal and equal to stock (`fb35263f…`), plan validated with 245 operations (1 erase, 244 pages), no mutation opcode issued, release/close succeeded. About 10 s per full 1 MiB read. Evidence: `artifacts/device-backups/20261009-200556-receiver-write-dryrun-favorites/`.

**First physical write (Favorites v4), 20:17:15–20:18:06 UTC, 51 s, explicit user go-ahead:** same single Monitor CH341, stock preimage confirmed by two full reads, 245/245 operations (1 block erase, 244 pages) each verified, protocol full readback and an independent full read both `e3f54fe3…`, status `00/00` before and after, release/close succeeded. Evidence: `artifacts/device-backups/20261009-201715-receiver-write-favorites/` (`write-session.json`, `plan.json`, `5680-before-pass1/2.bin`, `5680-after.bin`). User-reported after a full power cycle: the Monitor boots normally, the new **P band** is present, P1–P8 map exactly to L6, L7, R1, R2, F2, F4, R7, R8, and every P channel showed a picture. This is the first physical evidence that the appended CODE loads and the Favorites selection/RF tuning work. Long-press, saved state across power cycles, mode transitions and recording are not yet reported. **Physical restore test, 20:27:07–20:27:57 UTC, 50 s, explicit user go-ahead:** preimage read twice as Favorites `e3f54fe3…`, 244/244 operations (1 erase, 243 pages) verified, protocol and independent full reads both stock `fb35263f…`, status `00/00` before/after, cleanup succeeded. Evidence: `artifacts/device-backups/20261009-202706-receiver-write-restore/`. User-reported after a power cycle: normal boot, P band gone, picture on R2. **The built-in USB route has now physically demonstrated write, verified readback, and restoration from a non-stock image to exact stock, both booting correctly.** The user decided not to force an interrupted-write test (unnecessary risk). **Favorites v4 re-applied 20:42:10–20:43:01 UTC** (`20261009-204210-receiver-write-favorites`), stock preimage → `e3f54fe3…`, 245/245 operations, status `00/00`, cleanup succeeded; this is the Monitor's current receiver state. Still undemonstrated: recovery after an interrupted real write (deliberately not tested) or from an image that fails to boot, cold-boot behavior over longer periods, and the remaining Favorites real-device matrix (long-press, saved state, mode transitions, recording).

Still not validated:  real erase/program timing, the DM5680's behavior while its flash changes during bus handover and after release, and recovery after an interrupted real write. A power cycle after a successful write is expected to be needed to load the new code (as with the official updater); this is an inference.

## Result

The receiver-only plan and local NOR simulation reproduce both the candidate's projected full array and restoration of the complete original receiver backup. A newly prepared read-only USB preflight can collect the missing flash status/SFDP evidence in the next device session. It has not been run against hardware.

**47 host tests pass**, including 13 flash-plan/protocol failure checks and seven preflight lifecycle/input checks. The unchanged candidate retains its earlier 5,735 bounded CPU checks and four C-runtime startup comparisons. These counts measure different test scopes and must not be added into a hardware acceptance claim.

The [mode-consumer audit](receiver-mode-consumers-20261009.md) found no new demonstrated v4 defect. The [loading/integrity investigation](receiver-loading-integrity-20261009.md) supports the available CODE extent but retains actual device loading/integrity as unresolved. Firmware v4 and its package are unchanged.

## Receiver-only mutation footprint

The official Monitor updater writes all three component arrays and leaves its readback loop commented out. A focused receiver-only transport would avoid those unrelated erases. The preparation here describes and simulates that narrower operation; it does not implement a native programmer. [Pinned official source](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py).

| Plan | First block | Programmed 256-byte pages | Complete 1 MiB expected-array SHA-256 |
|---|---|---:|---|
| Favorites | Erase `00000..0FFFF`, rebuild candidate, retain `FF` tail | 244 | `e3f54fe342ee806812d8da887c94cef8633480e9d48fbdb4763ce603c27d0634` |
| Restore | Erase the same block, rebuild original, retain `FF` tail | 243 | `fb35263f0bc62cc1a43889da4313af3ace756c086aad8ef69d4bc6ed515b4055` |

Only 450 bytes differ in the candidate array, but erase granularity still affects 65,536 bytes. An interrupted operation can therefore damage original executable code throughout this block. Exact page restoration and a full-array readback are required; a matching payload prefix or byte-sum is insufficient.

All bytes after the first block are preserved. The plans select only `5680` / JEDEC `EF4014`, never FPGA or MStar. The latter components' current filesystem or calibration contents therefore need no rewriting. This preservation is a plan/simulation result, not an observed board write.

## Input and operation guards

`tools/monitor_receiver_flash_plan.py` independently rechecks all six full backup copies and their successful acquisition manifest. It regenerates the decoded candidate from the pinned stock bytes and Favorites configuration, then checks the v4 hash. It compiles exact erase/page operations from the desired full-array image.

Favorites requires the complete original receiver preimage. Restoration also permits a saved interrupted state that differs within the first block only; changes elsewhere require investigation. Restoration of an already original array is a verified no-op. Before simulation, the complete operation sequence is regenerated; reordered, missing, changed or out-of-range operations are rejected.

The simulated protocol reads identity and the full preimage, checks BUSY/protection and WEL, erases only block zero, verifies that entire block is `FF`, programs aligned pages and verifies each page, then compares the entire final 1 MiB array and disables writes. Failed identity/preimage/WEL/protection checks stop before erase. BUSY timeout, program interruption and page corruption stop without automatic retry or automatic restoration. A separate restoration simulation succeeds from a deliberately interrupted state.

For a future native transport, these commands must remain separate CS-delimited transfers. WEL is required before each erase/program and clears when the operation completes; page programs must not wrap across a 256-byte page. [Winbond family reference, W25Q80BV Rev C1](https://www.winbond.com/upload/technical-support/f0f72951-b845-42ea-9010-faaeab26872f.pdf), sections 7.2.5, 7.2.17 and 7.2.21. The matching-capacity DV family document is already recorded in [the flash-capacity note](monitor-flash-capacities.md). JEDEC identifies the family/density, not this chip's exact suffix.

The NOR model intentionally simplifies BUSY into logical polling ticks and applies mutations immediately. It does not simulate erase/program power failure within individual cells, voltage, board bus arbitration or USB transfer timing. The poll count bounds a local simulation only. A native driver must use checked native returns, bounded USB waits and wall-clock deadlines. Logical release-before-close events in the model are not physical recovery evidence.

## Reproduce the local plans

```powershell
$flashPlanPython = 'python'
& $flashPlanPython tools/monitor_receiver_flash_plan.py `
  --backups artifacts/device-backups/20261009-usb-01 `
  --receiver artifacts/firmware-analysis/20261009-scan-guard/favorites-build-v4/receiver-rebuilt.bin `
  --mode favorites --output-dir artifacts/firmware-analysis/new-flash-plan/favorites
& $flashPlanPython tools/monitor_receiver_flash_plan.py `
  --backups artifacts/device-backups/20261009-usb-01 `
  --receiver artifacts/firmware-analysis/20261009-scan-guard/favorites-build-v4/receiver-rebuilt.bin `
  --mode restore --output-dir artifacts/firmware-analysis/new-flash-plan/restore
```

Existing evidence is in `artifacts/firmware-analysis/20261009-receiver-flash-plan/{favorites,restore}/`: `plan.json`, `simulation.json`, `expected-array.bin`. These are private local files, not commands to flash hardware. Plan creation requires a new output directory and imports no USB/DLL module.

## First USB step once the user returns

`tools/monitor_usb_receiver_preflight.py` is a **read-only acquisition tool**, with no Write Enable, program, erase, protection-write or security-write opcode. It uses the pinned DLL/device-descriptor checks from the previously validated bridge and limits routing to the receiver. New native diagnostic commands `05/35` read status and `5A` reads the bounded first 256 SFDP bytes with its required dummy byte. No hardware call occurs on import.

The tool captures two matching SFDP reads and two matching full receiver-array reads, retains raw SFDP, checks status before/after and always releases routing before closing. A BUSY/suspended state, unstable data, short read or cleanup error prevents successful verification. A 120-second session deadline is checked between bounded native transfers; cleanup still runs on timeout. An invalid SFDP signature remains recorded evidence; it never establishes permission or eligibility to program. A stable unknown array is classified explicitly and does not become an approved preimage.

[Winbond SFDP command reference](https://www.winbond.com/upload/technical-support/f0f72951-b845-42ea-9010-faaeab26872f.pdf), section 7.2.32. Parameters are captured, not yet interpreted; SFDP contents and the exact variant require real-device evidence before a native write adapter is finalized.

The next session starts with closing HDZeroProgrammer, confirming one intended CH341 device and stable normal Monitor power, then running this bounded read acquisition into a new directory. The tool's existing `--dll`, `--backups`, `--receiver`, `--output-dir` arguments make the result reproducible. Do not run it automatically on a timer or during the user's absence.

After acquisition, examine actual protection/SFDP parameters, confirm the stock preimage and establish recovery access that remains usable without working receiver application code. A read through the current application proves neither that independence nor working erase/program. A spare flash/unit or an independently established SPI access route can provide recovery evidence. Only then finalize and review the native receiver-only write adapter against the prepared plan; that adapter is not implemented or validated by this offline work.

The subsequent hardware matrix includes cold boot, all eight channels, analog/digital roundtrip, no-signal transitions, normal/busy labels, short/held button actions, recording, saved selection after power cycle and exact restoration. The [consumer audit](receiver-mode-consumers-20261009.md) identifies the corresponding paths. Faster switching remains deferred.

## Status

No USB device was opened, no flash status/SFDP was actually read, and no device memory was written in this work. The offline plans are tested; the preflight's native diagnostic additions, physical programming, CODE loading and recovery remain unvalidated. A complete physical Monitor emulator and exhaustive symbolic propagation of every indirect pointer remain possible larger projects, rather than prerequisites to the next focused device investigation.
