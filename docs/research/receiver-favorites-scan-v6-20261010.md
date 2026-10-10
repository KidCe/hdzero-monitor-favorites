# Favorites v6: Favorites in the built-in scan, shorter long press, version text V1.1.2

Date: 2026-10-10. AI assistance follows the [project README disclosure](../../README.md#ai-assistance-disclosure). Offline build and tests; not yet written to the Monitor.

## User requests

After accepting v5, the user asked for scanning in the P band and a shorter long press (~1.5 s instead of ~3 s). Instead of a separate Favorites scan, the user proposed replacing the never-used E1 and F1 in the built-in scan with L6 and L7, and accepted that a scan started in P ends on a stock channel (option a). The user also asked to change the shown version to V1.1.2 if ultra-low-risk (not 1.2.x, which would appear newer than the latest official release).

## Changes (relative to v5)

| Change | Bytes | Detail |
|---|---|---|
| Scan list | `6D99: 10→19`, `6D9F: 18→2D` | Initializer `6D6C` writes `0816..0821` each scan start. Entry 9 E1→F2, entry 10 F1→L6, entry 11 is `INC A` → L7, entry 12 F4. List: **R1–R8, F2, L6, L7, F4** — contains all eight Favorites; length stays 12; first entry (cancel target) stays R1. |
| P scan guards removed | `0971`, `09BD` restored to stock; 52 appended bytes dropped | Long press starts the stock scan in every band again. A scan started in P ends on the found stock channel (e.g. `L6 HDZERO`). |
| Long-press threshold | `0952/0955` and `099E/09A1`: `03E8 → 01F4` | Elapsed tick count (`10DE` minus press time `001C`/`0020`) must exceed 1000 → now 500, both buttons. The tick period is not established; the ratio halves the user's observed ~3 s to ~1.5 s. Short-press debounce (5 ticks) unchanged. Applies to all bands. |
| Version text | `B9BB: 30→32`, `B9CE: 0D→0B` | `B981` builds `FW: V1.0.0` at XDATA `1004..100E`, then stores `'1'` to `1009/100B/100D`; drawn by `B1DF` at column 21. Third digit now keeps its initial value `'2'`; the late store hits `100B` twice. Result **`FW: V1.1.2`**. The buffer has no other reader in the recovered listing (only caller `5ED1`). This changes only this receiver-drawn text, not any version reported by the MStar menu or the official programmer. |

**RF profile evidence:** `0C74` selects a register profile for RF index 8, 9 or ≥ 12. E1 = 8 and F1 = 9 (stock scan members) and L6 = 17, L7 = 18 are all in that group, so the scan's profile mix is unchanged. Whether the scan-tune path `2DAC` applies the profile itself was not traced; the argument is equivalence with the stock E1/F1 entries.

## Build and tests

| Item | Value |
|---|---|
| Decoded receiver | 62,454 bytes, `d12c1bb9a87e40b9b6deaa4c410500781bcc571acb033177c90c86ca5216161f`; 69 changed original bytes, 451 appended |
| Projected 1 MiB array | `f6501fa2fd4ba6c1ca23378d091c4f45f4b915eddbc550e2444192cef9e3a2c2`, 518 bytes differ from stock, 244 pages |
| Package (parser-compatible, not for the official updater) | `63228a2863bef5c05f68f5c4fd0ead496e0c149525650bf9192955eddb1b1574` |

Independent hand-encoded generator and assembled recovered source match byte-exactly. **74 host tests pass** (two consecutive runs). New `tests/test_scan_list.py` interprets the actual initializer bytes (stock list R1–R8, E1, F1, F2, F4; new list as above), checks the RF-profile group of replaced entries, both thresholds 1000 → 500, restored activation sites, and the version builder (stock `FW: V1.1.1`, new `FW: V1.1.2`, writes only inside `1004..100E`). The write tool accepts the physically verified v4 and v5 arrays as upgrade preimages. A stuck-BUSY write test was made deterministic (wall clock now expires before the poll budget).

## Physical write

2026-10-09 23:50:52–23:51:42 UTC, explicit user go-ahead: preimage read twice as v5 (`6a79dbeb…`), 245/245 operations (1 erase, 244 pages) verified, protocol and independent full reads both `f6501fa2…`, status `00/00`, cleanup succeeded. Evidence: `artifacts/device-backups/20261009-235052-receiver-write-favorites-v6/`. User-reported after power cycle: scan starts in the P band, the new hold time is "very good", and a scan found L7 and ended on stock `L7` as designed (option a). Observed: after the scan locks a channel the screen goes black, then nothing for a moment, then the picture appears, about 2 s; the user suspects RSSI detection first, then analog/HDZero decision. The user confirmed seeing `V1.1.2` on the device. The user dropped the fixed-mode idea. Next user wishes: stay in P after a scan started in P (option b), and investigate a fixed HDZero-only/analog-only mode instead of `RF AUTO` for faster switching/scan settle.

## Not validated

Scan behavior on hardware (detection of L6/L7, timing), the actual new hold time, where/when the version text appears, and that no other code path depends on the removed P guard. Intermediate build `20261010-scan-v6/` (without the version change) is superseded and was never written.

Artifacts (private): `artifacts/firmware-analysis/20261010-scan-v6b/`.
