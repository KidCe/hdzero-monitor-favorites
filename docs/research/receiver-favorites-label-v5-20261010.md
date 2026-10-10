# Favorites v5: underlying channel in the status-bar label

Date: 2026-10-10. AI assistance follows the [project README disclosure](../../README.md#ai-assistance-disclosure). Offline build and tests only; not yet written to the Monitor.

## Request and result

After physical acceptance of v4 (P1–P8 correct, picture on every slot), the user asked to also show which channel each P slot corresponds to, and suggested shortening `HDZERO`. v5 shows, **for the P band only**:

| State | v4 | v5 |
|---|---|---|
| Digital | `P1 HDZERO` | `P1 L6 HDZ` |
| Analog | `P1 ANALOG` | `P1 L6 ANA` |
| No signal (busy dots) | `P1 ...` | `P1 L6 ...` |

Stock bands keep the stock label (`F4 HDZERO` etc.) byte-for-byte on the tested path.

## How the stock label works

`B717` redraws when the selection differs from cache `0FF7` (or flags `0FE5/0FE6`). It builds a buffer at XDATA `0FED`: band letter, slot digit, then a CODE string copied by `C058` to `0FEF` — `F209 " HDZERO"` / `F201 " ANALOG"` (by `075C`) on the normal path, or `F1FC "   "` plus progress dots (index 3+) on the busy path. Draw routine `B1DF` takes descriptor `0FC3..0FC7` (generic pointer, length, attribute) and column in DPL; both label draws use column `0x15`, length 9 (normal) or 6 (busy, after a 3-character clear at column `0x1B`). The buffer `0FED..0FF6` is 10 bytes, directly below cache `0FF7` and timer `0FF8..`; `B1DF` writes each character back with an attribute bit, so a CODE-memory string cannot be drawn. A wider label or an extra prefix field was rejected: the buffer is full, and column 18 belongs to a 7-character status field at column 12 (`BBE9/BC15`).

## Change

Both final label draws (`B87F` busy, `B8F8` normal; each `MOV DPL,#15h / LJMP B1DF`, only reached sequentially, no branch into the replaced bytes) become `LJMP F3C6` + 3 never-executed NOPs. The appended routine ([source](../../firmware/receiver/favorites_label.asm)) returns to the stock draw unchanged unless `0D85` is `30h..37h`. For P slots it moves suffix characters 3..5 to 6..8 (NUL → space), writes spaces at 2 and 5, the underlying stock band letter (CODE letter table `F383`) at 3 and digit at 4 from an appended 8-byte stock-ID table (`F3BE`), and sets length 9. Writes stay within `0FED..0FF5` and `0FC6`; only A, R7, DPTR and C are used; it is a tail jump, so stack depth is unchanged.

| Item | Value |
|---|---|
| Decoded receiver | 62,506 bytes, SHA-256 `16f20e266954506273403da9536fce2cdc42ebb1e29216e25272d0e2a2231372` |
| Changed original bytes / appended bytes | 67 / 503 (v4: 55 / 395) |
| Projected 1 MiB array | `6a79dbebf85968f5a02a87883bb3249926703418f7012790012e4954e74f4d88`, 568 bytes differ from stock, 245 pages |
| Package (not for the official updater) | `15ebd3911fc80303ca2452d7a409e56694f6a5fdd8d085fd0e50f4b31f7689fd`, accepted by the isolated official parser |

The hand-encoded independent generator and the assembled recovered source match byte-exactly. Official 1.2.0's 63,159-byte receiver remains larger than v5, consistent with the earlier loading inference.

## Tests

69 host tests pass. New: an instruction-level interpreter executes the generated routine from both hook sites for all eight slots (digital, analog, 0–4 busy dots, short suffix with NUL) and checks the exact drawn text, length 9 and the write set; for all 48 stock IDs and invalid IDs (`38h`, `3Fh`, `FFh`) it checks zero writes and the unchanged stock length. The interpreter implements only the routine's opcodes; it does not run `B1DF`, the MStar OSD or the surrounding redraw logic. The write tool and flash plan pin v5 and accept the physically verified v4 array as an upgrade preimage (new test: v4 → v5 on the NOR model).

## Physical write

2026-10-09 23:18:59–23:19:48 UTC (01:19 local, 10 Oct), explicit user go-ahead: preimage read twice as v4 (`e3f54fe3…`), 246/246 operations (1 erase, 245 pages) verified, protocol and independent full reads both `6a79dbeb…`, status `00/00`, cleanup succeeded. Evidence: `artifacts/device-backups/20261009-231858-receiver-write-favorites-v5/`. User-reported shortly after the write: the status bar showed `P1 L6 HDZ`. The Monitor was then switched off to cool down after a long session; after cooling and a power cycle the user tested again and reported **everything working: P1–P8 labels show the correct underlying channels and reception works** (user acceptance of v5). The user noted that scan does not work in the P band — this is the intentional v4 guard (stock scan list excludes Lowband and would leave P) — and asked for a favorites scan and a shorter long-press (~1.5 s instead of ~3 s).

## Not validated

Actual rendering on the Monitor, recording/OSD overlays, analog mode label on hardware, and any display path that redraws the label outside `B87F/B8F8` (AV/PAL/NTSC paths `B640/B714` intentionally unchanged).

Artifacts (private): `artifacts/firmware-analysis/20261010-label-v5/` (`candidate/`, `favorites-build-v5/`, `favorites-package-v5/`).
