# Receiver Favorites: decoded offline candidate

Date: 2026-10-09. Monitor PCB 1R3, firmware 1.1.1.

AI assistance: Analysis, implementation and documentation were developed with substantial assistance from OpenAI Codex under the user's direction.

## Result and boundary

Current follow-up: [saved settings and long-press scan guard](receiver-settings-scan-20261009.md) supersedes the candidate hashes, package paths and test counts below. This report retains the earlier v2 evidence.

Follow-up: the [source rebuild and update-packaging report](receiver-source-rebuild-20261009.md) now records byte-exact assembly builds and standard-format experimental packages. The decoded candidate builder described here remains offline-only; the separate packager is also offline and does not establish device operation.

A reproducible decoded receiver candidate adds logical band index 6, displayed as **P1–P8**, for **L6, L7, R1, R2, F2, F4, R7, R8**. It retains the 48 stock selections and reuses their RF indices, tune words and capability flags. **1,629 bounded actual-instruction checks passed** in Ghidra's 8051 p-code emulator. The unchanged receiver baseline still passes 221 checks; the separate Python suite now passes 27 tests with the private fixtures and portable assembler present.

This is an offline experiment. The builder produces decoded analysis bytes and a change manifest, not an encoded receiver payload or installable Monitor update. No USB connection, hardware write, boot, physical tuning, complete display rendering, persistence or recovery test occurred. The most immediate remaining device prerequisite is whether CODE data appended after the original payload is available at runtime.

## Exact candidate

| Item | Value |
|---|---|
| Stock decoded bytes | 62,003 (`0xF233`) |
| Stock decoded SHA-256 | `ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652` |
| Candidate bytes | 62,346 (`0xF38A`) |
| Candidate SHA-256 | `7dba09cf8a62394e90df8a85917918c8fa187899afee4803ed6f6a7d723a1e81` |
| Replacements | 20 spans, 49 changed original bytes |
| Appended data | 343 bytes, no added function or RAM state |
| Logical Favorites IDs | `30`–`37` hex |
| Effective stock IDs | `2D, 2E, 20, 21, 19, 1B, 26, 27` hex |
| Local candidate directory | `artifacts/firmware-analysis/20261009-favorites-candidate-v2/` |

The exact byte replacements, original-byte expectations, appended-data hash and mapping are recorded in `manifest.json`. `tools/monitor_receiver_candidate.py` pins the entire stock input and checks each expected replacement span. Verification independently regenerates both the complete candidate and manifest; changing a candidate byte and updating its recorded hash does not pass verification. Stock backups and analysis fixtures are preserved.

An earlier local draft missed the computed capability-table consumer at `6466`. Only the candidate with the hash above is accepted by the final runner. Raw candidate images, private backups, Ghidra databases and decompilations remain excluded from Git.

## Design and identified consumers

The selection byte remains `(band << 3) | channel`. Favorites retain logical IDs 48–55, so a short channel step stays in band P. Consumers use copied stock rows from extended tables; the RF driver receives the same RF index as the selected original channel.

| Appended CODE range, end exclusive | Contents |
|---|---|
| `F233`–`F26B` | 56 capability flags: unchanged 48 rows plus eight Favorites rows |
| `F26B`–`F2A3` | 56 RF indices with the same arrangement |
| `F2A3`–`F383` | 56 four-byte second tune words |
| `F383`–`F38A` | Letters `ABEFRLP` |

The old tables at `C6C0`, `C6F0`, `C720` and `EF08` remain byte-identical. Selection limits and wraparound are adjusted in `0674`, the secondary linear path `0725`, and loaded-state validation `9D44`. Both RF-index consumers (`0C74`, `2DAC`), the second tune lookup (`5D19`) and five capability consumers (`0773`, `6008`, `6366`, `6466`, `6827`) use the extended rows. Both normal and busy OSD label fragments use the seven-letter CODE table.

Each label rewrite occupies its original 22-byte span: 16 bytes of replacement instructions followed by six CPU NOPs. The next original instruction address is unchanged. No analyzed reference targets the interior of either replacement span. Literal scans and Ghidra references do not exclude computed branch targets or indirectly addressed selection aliases.

The inventory found 42 literal `MOV DPTR,#0D85` references in the stock image. All resolve to instructions after additional disassembly seeds; the `6466` consumer lies in a tail outside the initially recognized function body. The candidate inventory confirms that the two literal old RF-index pointers and the direct old capability pointer are gone. The four computed capability bases were checked separately in assembly and emulation.

## Lowband and RF profile checks

The assembly in `0C74` selects several register values according to the **mapped RF index**, including the condition `index == 8 || index == 9 || index >= 12`. The logical Favorites ID is consumed by the RF-index lookup first. Thus the P1/P2 mappings obtain the stock L6/L7 index and enter the corresponding profile branches in the tested fragments.

Five independent conditional fragments prepare register words for `44`, `4C`, `54`, `28` and `40` hex. Two further fragments read calibration words from stock tables `C770` and `C7C0` using the mapped index. Every logical selection is checked. These tests stop before the selected peripheral call; they establish prepared values and branch choice, not a completed RF transaction. Intermediate calls, delays, interrupts, transport errors and calibration completion are not modeled.

## Test coverage

| Group | Checks |
|---|---:|
| Both directions of band/channel stepping for all 56 valid selections | 224 |
| Missing-RAM rejection, original six-letter initialization, eight stock Favorites lookup/label cases, three invalid IDs | 29 |
| RF-index lookup and initialization lookup for every logical ID | 112 |
| Second tune word for every logical ID | 56 |
| Normal and busy channel label for every logical ID | 112 |
| Five capability-table consumers for every logical ID | 280 |
| Both RF frequency-word preparation fragments for every logical ID | 112 |
| Five RF profile branches for every logical ID | 280 |
| Two RF calibration-table fragments for every logical ID | 112 |
| Idle main-loop scan service preserves selection/cache for every logical ID | 56 |
| Loaded selection validation for all 256 byte values | 256 |
| Total candidate checks | **1,629** |

The harness executes the candidate instructions with explicit EXTMEM fixtures and CPU state. It rejects unknown memory, CODE writes, register-bank changes, escape from the bounded fragment and a 200-instruction budget overrun. It does not skip peripheral calls or return fabricated success from hardware APIs. Fixtures at fragment entry deliberately separate this from an integrated boot/channel-change test.

Ghidra's 8051 Sleigh model represents opcode `00` as a `nop` user operation. A narrow callback implements only that architectural no-op and verifies the current opcode is exactly `00`; other unsupported operations still fail. The existing bank-zero R0–R7/INTMEM alias bridge remains necessary. Stack calls, interrupts, other banks, ports and timing remain outside the model. One logged uninitialized-memory error is intentional: the negative check requires the exact failure at `06DF` for missing `EXTMEM:0D85`.

The runner rejects incomplete reports and checks image hash, hardware-access flag, patched-image flag, total count and every individual result. Candidate import and refresh paths were both exercised with the initial 1,181-check suite. The final 1,629-check suite passed via refresh at `artifacts/firmware-analysis/candidate-run-20261009-180014-912/candidate-tests.json`. The final stock regression passed at `artifacts/firmware-analysis/receiver-run-20261009-173758-105/selection-tests.json`. A compact [machine-readable evidence summary](receiver-favorites-candidate-results.json) records the hashes, counts and limitations. All six main-array backup hashes were rechecked and remain unchanged.

## Loading and update-format evidence

The official VTX [DM5680 board configuration](https://github.com/hd-zero/hdzero-vtx/blob/ad396315680f64ad5797fb0fe53bbd73e9f448ba/boards/DM5680.json) declares a 64 KiB CODE model. The inspected [Monitor programmer](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py) accepts declared receiver lengths below 65,536 and writes length-rounded 256-byte pages from flash offset zero. The candidate fits that host-side size constraint: the original needs 243 pages, the candidate 244. This supports format feasibility, but does not establish how the Monitor loads or maps CODE after power-on, nor whether device-side integrity checks exist.

In the pinned backup, bytes after `F233` are erased `FF`; this does not prove they are usable CODE storage. Application startup reads 34 initializer bytes at `F211`–`F232` into EXTMEM. That routine is not evidence that an external boot mechanism will load the appended data. A boot SPI trace, vendor boot documentation, or a verified runtime CODE-memory read is needed to settle that boundary. The host programmer's behavior alone cannot settle it.

## Remaining work before device use

1. Establish CODE loading/mapping through `F389`, including any device-side integrity rules, without assuming erased padding is available memory.
2. Continue tracing indirect selection consumers and full mode/scan paths. `6D6C` still writes an internal stock twelve-entry scan/configuration list; its trigger behavior is unresolved and could leave band P. The secondary linear path was not tested as a complete loop. Short band/channel controls are the covered use case.
3. Check integrated tuning, mode changes, label-buffer consumers and persistence beyond the independent fragments. The existing EEPROM-like path is not a verified successful save operation.
4. Establish independent recovery, then produce a separate explicitly reviewed update-packaging/programming path if justified. The current tools implement neither.
5. Validate all eight channels, Low/F/R transitions, both directions, power-cycle behavior, reacquisition and recording on hardware.

The source-code request remains useful, but offline progress does not depend on receiving a reply. The Monitor can remain disconnected and powered off for the current work.

## Reproduce offline

```powershell
$py = 'python'
$stock = 'artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin'
$candidate = 'artifacts/firmware-analysis/new-favorites-experiment'

& $py tools/monitor_receiver_candidate.py --stock $stock --output-dir $candidate
& $py tools/monitor_receiver_candidate.py --stock $stock --verify-dir $candidate

# Choose an unused project name for a fresh import; use -Refresh for an existing project.
& tools/Invoke-ReceiverCandidateGhidra.ps1 -Stock $stock `
  -CandidateDirectory $candidate -ProjectName Monitor-Favorites-New

& $py -m unittest discover -s tests -v
```

The builder can describe another valid eight-entry configuration, but the actual-code test runner intentionally accepts only the user's fixed order and the hash above. Changes to that order require corresponding independent expected results and a new pinned candidate hash.
