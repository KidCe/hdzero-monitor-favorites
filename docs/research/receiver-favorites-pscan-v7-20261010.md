# Favorites v7: a scan started in the P band stays in the P band

Date: 2026-10-10. AI assistance follows the [project README disclosure](../../README.md#ai-assistance-disclosure). Offline build and tests; not yet written to the Monitor.

## Request

v6 was accepted on the device (scan starts in P, hold time good, `V1.1.2` visible); a scan from P ended on stock `L7`. The user asked that a scan started in the P band ends on the matching P slot.

## How the built-in scan works (relevant part)

- `6D6C` runs on every main-loop pass. It first rewrites the 12-entry scan list `0816..0821`, clears per-entry results, and only then checks the activation flags `0767/0768`.
- With a flag set, **the whole scan runs inside this call**: start index `0853` = position of the current selection in the list (`6FA0`, `FF` if absent); then for each of the 12 entries `SELECTION_STATE := entry`, full tune `0C74` + second tune `5D19`, `delay(250)` (`702F`), measurements into `0822/082E/083A`.
- From the start index in the button's direction it takes the first entry with a result, sets mode `075C` (2/3/…), writes the entry to `SELECTION_STATE` and cache `0760` (`7273`, `73E7`, `74E5`), retunes via `2DAC`, then waits for button release. Release before a result (`7646`) selects entry 0.
- `2DAC` uses the entry only for the extended RF-index lookup (`2DBC`, already patched) and as a non-zero flag (`0727` → `1281/16B7` test zero/non-zero). `0C74` and `5D19` use the extended tables. P IDs are therefore valid list entries.

## Change

`6D6C` (`MOV DPTR,#0816 / MOV A,#20h`) becomes `LJMP F3F6` + 2 unexecuted NOPs. The routine ([source](../../firmware/receiver/favorites_scan_list.asm)) checks the selection: for `30h..37h` it writes the same 12 frequencies in the same order with Favorites as P IDs — **P3 P4 R3 R4 R5 R6 P7 P8 P5 P1 P2 P6** — and continues at `6DAC`; otherwise it performs the replaced instructions and continues at `6D71` (unchanged stock list R1–R8, F2, L6, L7, F4). Only A, DPTR and C are used; no RAM is added.

Effects in P: the scan starts after the current slot, a found Favorite is selected as its P slot (label `P2 L7 HDZ`), release-before-result selects P3 (R1). R3–R6 cannot be represented in P and are still scanned as stock channels; a hit there leaves P.

| Item | Value |
|---|---|
| Decoded receiver | 62,551 bytes, `0083c42f11e22154168bcac949acccf32b0df709af23a9a1e430b0ab278cbd33`; 74 changed original bytes, 548 appended |
| Projected 1 MiB array | `f88d9c72f839db94d940c84d6d11ffc4273834ce8df6e3b78d8e32125ce51e4c`, 620 bytes differ from stock, 245 pages |
| Package (parser-compatible, not for the official updater) | `ed21a729b55f65e821b6de68658529b7230481258dba046370ddef403e2d0e6c` |

Hand-encoded generator and assembled source match byte-exactly; still below official 1.2.0's 63,159-byte receiver. **76 host tests pass** (two runs). The scan test now executes `6D6C` including the hook for every selection: P1–P8 → P list (same frequency per position, all eight P IDs, current slot present); all 48 stock IDs and invalid values → stock list; writes only to `0816..0821`, read only of `0D85`. The write tool accepts v4, v5 and v6 arrays as upgrade preimages.

**Physical write** 2026-10-10 00:07:49–00:08:39 UTC, explicit user go-ahead: preimage read twice as v6 (`f6501fa2…`), 246/246 operations (1 erase, 245 pages) verified, protocol and independent full reads both `f88d9c72…`, status `00/00`, cleanup succeeded. Evidence: `artifacts/device-backups/20261010-000749-receiver-write-favorites-v7/`. User-reported after a power cycle: everything works; a scan started in P with a quad on L7 ends on **`P2 L7 HDZ`**; a scan started in the F band ends on stock `L7` (unchanged behavior). The user releases the button as soon as "scanning" appears; the scan then runs to completion, so the cancel path `7635/7646` is not the release itself. It is the fallback when a pass ends without a result and the activation flags are already clear (selects list entry 0, P3 in P); exactly when the flags are cleared during a scan was not traced. Not yet observed: scan with no transmitter.

Not validated on hardware: P-band scan result, start position, release-before-result behavior.

Artifacts (private): `artifacts/firmware-analysis/20261010-pscan-v7/`.
