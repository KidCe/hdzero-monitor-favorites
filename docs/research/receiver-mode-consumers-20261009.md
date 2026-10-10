# Receiver Favorites: mode, selection and indirect-consumer audit

Date: 2026-10-09. Target: Monitor PCB 1R3 / installed 1.1.1 receiver, Favorites v4. This is offline static analysis; no USB, hardware access or firmware modification occurred. AI assistance follows the project README disclosure.

## Result and evidence boundary

No additional active selection writer or missed capability-table relocation was identified in the recovered instruction inventory. The decoded mode dispatches retain the logical P selection and send it through the already extended lookup routines. This reduces specific uncertainties; it does not prove complete mode operation on the Monitor.

Primary inputs are the local, hash-pinned [stock instruction inventory](../../artifacts/firmware-analysis/20261009-recovered-source/instructions.json), decoded [stock image](../../artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin), and [v4 image](../../artifacts/firmware-analysis/20261009-favorites-candidate-v4/receiver-candidate-ANALYSIS-ONLY.bin). All addresses below refer to CODE unless explicitly marked EXTMEM. Bytes were checked against the stock inventory and actual v4 payload, rather than inferred from function names.

- Stock SHA-256: `ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652`.
- Candidate SHA-256: `7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16`.
- Inventory: 28,350 recovered instructions / 48,283 bytes of the 62,003-byte stock image. Remaining bytes include data and unresolved regions, so this is not proof that every executable path has been recovered.

The read-only [audit script](../../tools/receiver_consumer_audit.py) validates both hashes and every stock inventory instruction. Its [JSON evidence](../../artifacts/firmware-analysis/20261009-mode-consumers/consumer-audit.json) records literal references, bounded straight-line memory accesses, five decoded jump tables and capability-base checks. Its DPTR model stops at branches, calls and dynamic DPL/DPH writes; it cannot exclude dynamic aliases. These are static observations, not additions to the 5,735 CPU-execution test count.

```powershell
& python `
  tools/receiver_consumer_audit.py --output artifacts/firmware-analysis/new-consumer-audit.json
```

The script refuses to overwrite an existing evidence report. It accepts only the current pinned stock and v4 hashes.

## Selection writers and scan producers

Stock contains 42 recovered literal `MOV DPTR,#0D85` instructions, opcode bytes `90 0D 85`. The bounded audit identifies these twelve writes to EXTMEM `0D85`:

| Write instruction | Meaning established by surrounding bytes |
|---|---|
| `06BF`, `070E` | Band/channel step results; both call save entry `9F29` |
| `0748`, `0755`, `0764` | Secondary linear-step increment/decrement and range reset in `0725` |
| `700B`, `7276`, `73EA`, `74E8`, `7658` | Stock scan changes and final/cancellation selections |
| `9D58` | Invalid-selection default `20` in validator |
| `9E2D` | Settings load: returned bus value in R4 is stored directly |

`5F15`, `61C1` and `681F` load the selection and then change DPTR to cache `0760` before writing; they are not selection writes. The nearby literal `0D84` at `9CC1` is an OSD scratch byte. Its write at `9CC4` is followed by dynamic buffer-address construction, not `INC DPTR` into `0D85`.

Scan flags `0767` and `0768` have respectively twelve and thirteen literal references. Known writes comprise button activation (`0976` / `09C2`), button release clearing (`0B7B` / `0B8C`) and runtime initialization clearing (`69C8` / `69C4`). Both activations are reached through the existing v4 P guards. Literal `076E` writes at `097E` / `09CA` activate scan state; `69CC`, `73B9`, `74B4`, `7622` and `763F` clear it. Other recovered literal references read flags. No second literal activation producer was found.

The unchanged stock scan remains capable of replacing P with a stock channel if its flags are set through an unresolved path. Therefore the appropriate claim remains "the identified button activation sites are guarded," rather than "every possible scan entry is prevented." The [existing scan report](receiver-settings-scan-20261009.md) contains bounded execution evidence for these guards and forced stock scan limitations.

## Mode transitions and table consumers

`5D67` calls settings load (`5D71: 12 9E 12`) and then runtime initialization (`5D74: 12 69 7C`). This order matters: initialization clears scan flags and cached state, while the recovered literal writer inventory identifies no selection reset there. The resulting selection is subsequently passed as a logical ID.

`67E7` checks EXTMEM `0D86`; value 1 returns at `67EF`. Active scan flags return at `67FC`; unchanged selection/cache returns at `680B`. A changed selection reaches `680E: 12 0C 74`, then `6817: 12 5D 19`. Selection is copied to cache `0760` at `6826` only after those calls. The existing connected suite covers the entry gates and actual first nested lookup, stopping before peripheral operations.

`5F26` changes receiver/source state according to `075C/075D`. For states 2 or 3 it reads capability at `6008..6018`, loads the selection into R6, passes it to full initialization (`604B: 12 2D AC`) and reads the current selection again for tuning (`6054: 12 0C 74`). The state-zero path passes selection to the second tune routine at `5FF5`. At `61C1..61D0`, it updates the cached selection and cached state; it does not directly translate or overwrite `0D85`.

All five selection-based capability consumers address appended base `F233` in v4:

| Consumer | Actual v4 address-building operands |
|---|---|
| Secondary linear step `0777` | `90 F2 33` |
| State transition `600C/6010` | `24 33` / `34 F2` |
| Capability check `636A/636E` | `24 33` / `34 F2` |
| State selection `646A/646E` | `24 33` / `34 F2` |
| Changed-channel dispatch `682B/682F` | `24 33` / `34 F2` |

P entries copy the capability of their underlying stock channels; all eight configured entries have value 1. They therefore take the existing nonzero-capability path at `683A` to `6312`, rather than reading beyond the original 48-row table. `6312` selects state 2 and tail-calls `5F26`; `6466` selects the state-3 path through `634A` for nonzero capability. Those physical source/receiver meanings and their full I/O effects still require device observation.

Refresh `61D2` writes mode `0758=1` and invalidates cached mode `0759=FF` when DPL is nonzero; it calls display/peripheral configuration. The display formatter `B717` compares the logical selection with display cache `0FF7`, then reaches normal label writer `B885` or busy/timed label logic `B7AB`. Both label writers are already changed in v4. No additional formatter with a literal selection reference was identified.

## Computed jumps and dormant linear stepping

Every recovered `JMP @A+DPTR` is accounted for by one of these bounded tables:

| Jump | Input / encoding | Decoded destinations |
|---|---|---|
| `6900` | Mode `0758`, 0–7; split low/high tables `6901/6909`, otherwise fallback | `6911,6919,6949,6921,6939,6929,6931,6941` |
| `8E39` | Parser state, four two-byte relative jumps at `8E3A` | `8E42,8E4D,8E60,8E7E` |
| `93A7` | OSD/parser state, 0–7; split tables `93A8/93B0` | `93B8,93D8,9406,944F,94B1,94F0,952F,954F` |
| `9A08` | Character command `F9..FE`; six three-byte long jumps at `9A09` | `9B9B,9B5B,9B1B,9ADB,9A9B,9A5B` |
| `BD40` | State `10FB`, 0–3; four three-byte long jumps at `BD41` | `BD4D,BE5B,BD6F,BDD0` |

None targets `0725`. The entire pinned stock payload also contains no raw `12 07 25`, `02 07 25`, `07 25` or `25 07` sequence. This excludes literal long calls/jumps and simple stored addresses to that entry; it does not exclude a target synthesized by arithmetic, a computed return or execution in unresolved regions.

The dormant `0725` path already has its limit raised in v4 (`075B: BE 38 00`, stock `BE 30 00`). Its retained unsigned decrement limitation is separate: decrementing selection zero produces `FF`, and the out-of-range branch resets it to zero rather than the final selection. When `075C` is nonzero and capability filtering is active, A1's zero capability can repeat that loop. The observed user button paths call `0674/06D6`, not `0725`. No current evidence warrants expanding Favorites scope with a fix to this unreferenced path. Revisit it if a concrete caller is found.

## Dynamic pointers: narrowed, still unresolved

Generic pointer helper `C29F` has 27 recovered direct callers. Its external-memory write is `C2B8: F0`; it selects memory spaces using B tag bits, so a literal `0D85` search alone cannot establish complete alias coverage.

Several concrete caller groups can be narrowed:

- OSD character conversion sets base `0D47` and external-memory tag zero at `995F..996B`; `9A3D..9C1E` write characters through that pointer plus output offset `0D7E`. The normal bounded output is the OSD text buffer. No P-specific length increase was introduced by the one-character P label. Corrupted lengths or offsets are not excluded by this audit.
- Register/readback helpers at `A523..A532` and `A62A..A639` use pointers held at `0DAB` and `0DA8`. Visible literal initialization groups write `0713/0717` (`192A/191D`, repeated in RF paths), `071F/071B` (`24A7/249A`, repeated), or `0847/084B` (`7065/7058`, scan scratch), with tag zero. These destinations do not overlap selection or scan flags. Indirect changes to those pointer globals are not fully resolved.
- Generic string-copy and fill callers (`C09D`, `C1D0`) retain caller-supplied pointers/lengths. Other uses include OSD glyph writes (`B22F`). This pass does not attempt complete symbolic propagation of all arguments or prove those routines cannot alias unrelated state.

The adjacent OSD scratch pointer `0D84` is passed in an I/O descriptor at `9D0B..9D21` with length one. That is positive evidence for a single-byte scratch operation, not proof of every bus or bulk-copy path.

## Focused next validation

Keep the current v4 firmware bytes. There is no newly demonstrated Favorites defect to fix in this pass. The useful next evidence is behavior at real mode boundaries, once hardware work is authorized:

1. For P1, P2 and at least one Race/F favorite, switch digital → analog → digital and check that selection is retained and the returned digital image uses the selected frequency.
2. Check no-signal → signal-found → signal-lost transitions without pressing channel buttons. Confirm P labeling and actual reception stay consistent; those transitions traverse `5F26/6366` and hardware capability branches.
3. Change P channels while recording and with normal/busy display states, then verify P1–P8 label correspondence. The two recovered label writers are patched; MStar rendering and recording were not simulated.
4. Test short and held button actions in P and a stock band, including release during receiver state changes. Verify P wrap and absence of stock scan entry.
5. Retain the existing cold-start, saved-selection, full-array readback and independent recovery checks. A passing static consumer audit cannot substitute for them.

Full symbolic recovery of every generic pointer call and peripheral implementation would be a much larger project. The unresolved boundary is explicitly recorded so it can be targeted if a device observation reveals a failure; this report does not claim that all offline reverse-engineering possibilities are exhausted.
