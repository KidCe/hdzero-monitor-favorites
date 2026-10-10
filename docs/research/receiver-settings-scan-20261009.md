# Receiver Favorites: saved settings and long-press scan guard

Date: 2026-10-09. Target: Monitor PCB 1R3, installed firmware 1.1.1.

AI assistance: Analysis, recovered assembly, new guards and tests were developed with substantial assistance from OpenAI Codex under the user's direction.

## Current result

The **v4** offline candidate retains P1–P8 = **L6, L7, R1, R2, F2, F4, R7, R8**. A long channel-button press now skips stock automatic-scan activation when a P selection is active. Other IDs retain stock activation. The release-edge channel-step path remains available in P mode. Physical button timing remains unverified.

Native assembly reproduces the independently generated candidate exactly: SHA-256 `7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16`, 62,398 bytes (`F3BE`). It changes 55 original bytes in 22 spans and appends 395 bytes: 343 table bytes and 52 new executable guard bytes. Guards need no extra RAM or stack.

**5,735 bounded actual-instruction checks passed**, plus 221 stock checks, 47 Python host tests and four separate C-runtime startup comparisons. The [connected/startup follow-up](receiver-connected-startup-20261009.md) adds 1,152 connected CPU sessions to the 4,583 fragment checks described below. The [flash/restore follow-up](receiver-flash-restore-preparation-20261009.md) adds 20 host checks and further consumer/loading evidence without changing firmware. These are bounded CPU/host checks, not integrated Monitor or hardware acceptance. Reports keep `feature_acceptance: false`.

## Scan reconstruction and change

The main loop calls `6D6C` on every iteration. Its fixed scan list at EXTMEM `0816..0821` contains R1–R8, E1, F1, F2, F4, excluding Lowband. Flags `0767/0768` enter this scan regardless of band. Cancellation at `7646..766A` copies its first entry R1 (`20`) into selection `0D85` and cache `0760` before initialization.

Button paths `0965/09B1` check active/busy state, then activate at `0971/09BD`. Both follow an equal `CJNE` against 1, establishing carry=0. The candidate replaces each activation site's three-byte DPTR setup with an `LJMP` to a 26-byte guard:

- Up: `F38A..F3A3`, stock continuation `0974`.
- Down: `F3A4..F3BD`, stock continuation `09C0`.
- P IDs `30..37` jump to post-activation continuation `09CB`, preserving scan flags, selection and R0–R7.
- Other byte values restore the original DPTR and continue activation. Both exits restore carry=0; continuation reloads A and DPTR before using them.

Source: [favorites_scan_guards.asm](../../firmware/receiver/favorites_scan_guards.asm). Independently hand-encoded expected bytes are compared with native assembly output. That comparison rejected an early relative-branch error before emulator/package acceptance. Current tools accept only v4; older v2/v3 artifacts remain historical experiments.

This guards the identified button activation sites and leaves the internal stock scan unchanged. An unidentified flag producer could still force that scan and leave P mode. Other literal flag accesses in the generated listing are reads, release clearing or initialization clearing; indirect aliases remain unresolved.

## Saved-state evidence

`9F29` calls validator `9D44`, then prepares the selection write at `9F32..9F5D`: device address `50`, register offset 0, data equal to the logical selection. Tests stop before helper `7846`; no P-to-stock translation occurs in this descriptor.

`9E12` prepares a read from address `50`, offset 0, through `79B5`. Its returned byte is stored directly into selection at `9E27..9E2E`. Tests supply that return byte explicitly; they do not simulate a successful bus read.

The complete validator `9D44..9E11` accepts selections below `38`. Valid P values survive remaining checks. Correcting another field preserves P1 and sets correction flag `0D8F` and returned DPL to 1. Stock defaults/widths are retained in [settings_validate.asm](../../firmware/receiver/settings_validate.asm). D8C remains untouched as in stock.

An unrelated static inconsistency remains: the save routine prepares D8B and D8D writes at offset `14` both times, while loading reads D8D from offset `15`. This describes the existing descriptor code, not a measured EEPROM fault or a Favorites fix. Bus acknowledgment, chip identity, retention and complete mode transitions remain unverified.

## Checks and boundary

| Checks | Count |
|---|---:|
| Prior selection, tuning, labels, capabilities, idle scan and loaded-selection prefixes | 1,629 |
| Write descriptor and read-value store for all 56 selections | 112 |
| Complete validator for every selection byte | 256 |
| Eight other saved fields, all 256 values with P1 selected | 2,048 |
| Guarded long press: every selection byte, both directions; R0–R7/carry preserved | 512 |
| P1–P8 release-edge prefixes reach channel-step call, both directions | 16 |
| Forced internal scan entry/cancellation observations, unresolved behavior | 10 |
| **Fragment total** | **4,583** |
| Connected selection/save, held/idle/release and mode/cache sessions | 1,152 |
| **Current candidate suite total** | **5,735** |

Candidate report: `artifacts/firmware-analysis/candidate-run-20261009-182947-828/candidate-tests.json`. Stock report: `artifacts/firmware-analysis/receiver-run-20261009-181938-763/selection-tests.json`. The intentional missing-RAM error at `06DF` is checked as a negative result, not ignored. Separate startup reports and explicit CPU-model adapters are described in the follow-up.

Guard tests allow only the original activation region plus that direction's exact 26-byte guard. Other execution addresses and undeclared memory are rejected. Ghidra's pseudo-block decoder needs lookahead beyond the final instruction: 16 read-only FF bytes are supplied after the payload, matching projected blank flash. Execution into them is prohibited. This is a decoder fixture, not proof of device CODE loading. Hash-verified guards are explicitly disassembled because automatic analysis can classify appended code as data.

## Experimental package and remaining work

Current package: `artifacts/firmware-analysis/20261009-scan-guard/favorites-package-v4/HDZero_Monitor-favorites-UNVALIDATED.bin`, 8,275,868 bytes, SHA-256 `06edaccf86a6f3ae7e6de0146e54027bc7a4de2372436fcb6d22213d4de2d12b`.

The isolated original file-parser accepts it. Projected receiver array changes 450 bytes, SHA-256 `e3f54fe342ee806812d8da887c94cef8633480e9d48fbdb4763ce603c27d0634`. Receiver erase geometry remains one 64 KiB block; programmed pages occupy 62,464 bytes. Entire FPGA/MStar projections match installed backups, preserving 132 MStar filesystem differences. These operations have not happened on hardware.

Assembly builds: `artifacts/firmware-analysis/20261009-scan-guard/stock-build/` and `favorites-build-v4/`. The [source rebuild report](receiver-source-rebuild-20261009.md) describes the common method and historical v2 packages. [Current evidence](receiver-settings-scan-results.json) records v4.

No USB device was opened or Monitor memory written. Integrated mode/button operation, CODE loading through `F3BD`, actual retention, reception and independent recovery remain open. This package is not approved for device use.

```powershell
& tools/Invoke-ReceiverCandidateGhidra.ps1 `
  -Stock artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin `
  -CandidateDirectory artifacts/firmware-analysis/20261009-favorites-candidate-v4 `
  -Refresh
```
