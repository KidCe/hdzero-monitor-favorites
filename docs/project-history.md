# How we got here

This is the story of the project, from "can we add a Favorites band to a device without source code?" to a flashed, verified and restorable firmware. Times are UTC. Each step links the detailed research note.

## The goal

The HDZero Monitor has six bands (A, B, E, F, R, L) of eight channels. The channel set used by the Aircrasher race management — mainly in Germany and at events such as the MultiGP European Championship — is spread across bands: **L6, L7, R1, R2, F2, F4, R7, R8**. Switching between them means changing bands and channels repeatedly. The goal: a seventh band that contains exactly these eight channels, operated with the stock buttons.

## 1. Feasibility without source (2026-10-08)

The official [hd-zero/monitor](https://github.com/hd-zero/monitor) repository contains only a README; firmware is published as binaries. We studied what *is* open: the MIT-licensed HDZero Goggle firmware, the Ripples Goggle fork (which already merges Lowband into one channel space), the HDZero Programmer (update container and USB access) and the VTX build scripts. Conclusion: no reusable Monitor source, but enough public knowledge to analyze the binary. Notes: [feasibility](research/hdzero-monitor-feasibility.md), [Goggle source reuse](research/hdzero-goggle-source-reuse.md), [Ripples findings](research/ripples-favorites-monitor-findings.md), [Ripples Lowband](research/ripples-lowband-monitor-reuse.md), [Favorites specification](research/hdzero-monitor-favorite-channels.md), [UART/JTAG options](research/hdzero-monitor-jtag-access.md), [implementation plan](research/hdzero-monitor-implementation-plan.md).

## 2. Back up everything first (2026-10-08/09)

Before touching anything, we wrote read-only USB tools. The Monitor's built-in CH341 bridge routes the SPI bus to one of three flash chips via GPIO outputs (values taken from the official programmer). A descriptor-only probe, then ID/prefix reads, then **two complete reads of all three flash chips** (08:11–08:23 on 10-09): DM5680 receiver (1 MiB), FPGA (16 MiB) and MStar (16 MiB). Both copies were byte-identical. Receiver and FPGA matched official 1.1.1 exactly; the MStar differed in 132 bytes of an embedded filesystem (device state). Notes: [flash capacities](research/monitor-flash-capacities.md), [USB backup](research/usb-backup-20261009.md), [MStar layout](research/mstar-payload-layout-20261009.md).

## 3. A detour through the MStar (2026-10-09)

The MStar holds the largest program (an ARM application, ~4.3 MB). We set up portable Ghidra 12.1.4, mapped the application at `0x20008000`, and built a Unicorn-based harness that executes original ARM functions with strict memory checks (22 checks passed). We found settings and UART handling — but **not** the channel-selection logic. Note: [Ghidra and emulation](research/ghidra-and-emulation-20261009.md).

## 4. The breakthrough: the receiver is an 8051 (2026-10-09)

The 62 KB DM5680 receiver payload looked like noise until we applied the inverse of the **bit permutation** used in HDZero's VTX build script (`post_script.py`): it decoded into clean **8051 code**, and re-encoding reproduced every byte. In Ghidra's 8051 analysis we found the button polling, the six-band/eight-channel selection byte `(band << 3) | channel` at XDATA `0D85`, the band and channel step routines, saved-selection validation, the channel-label writer and two tuning paths. **221 bounded checks** ran original code in Ghidra's p-code emulator. Note: [receiver selection path](research/receiver-8051-selection-20261009.md).

## 5. Building the Favorites candidate (2026-10-09)

Design: logical IDs `0x30–0x37` (band 6, "P"), extended copies of the capability, RF-index and second-tune tables appended after the original code (each P row copies its real channel's row), seven-band limits in the step and validation routines, a seven-letter label table, and guards so a long press does not start the stock scan in P (the stock scan list had no Lowband and would leave P). Candidates v2–v4 were checked with **5,735 bounded instruction-level tests** (including 1,152 connected CPU sessions) and audits of every consumer of the selection byte. Notes: [candidate](research/receiver-favorites-candidate-20261009.md), [settings and scan guard](research/receiver-settings-scan-20261009.md), [connected/startup checks](research/receiver-connected-startup-20261009.md), [mode consumers](research/receiver-mode-consumers-20261009.md).

## 6. Reproducible builds (2026-10-09)

A Ghidra export of 28,350 recovered instructions (77.9 % of the receiver bytes) became assembly source; the portable `naken_asm` rebuilds the stock image **byte-exactly**, and the Favorites image must equal the independently hand-encoded generator output. A packager writes the standard update container; the official programmer's own file parser (run in isolation) accepts it. Official 1.2.0, whose receiver is larger, supported that appended CODE beyond the old end is loaded. Notes: [source rebuild](research/receiver-source-rebuild-20261009.md), [loading/integrity](research/receiver-loading-integrity-20261009.md).

## 7. Find a recovery route before writing (2026-10-09)

We refused to flash without a way back. A local NOR-flash model rehearsed the exact receiver-only plan (erase only block 0, program pages, verify) including interrupted writes and restore. A read-only USB preflight read status registers and SFDP. Then an **independent** route: photos identified the receiver flash as a Winbond **W25Q80DV in USON-8**; a separate CH341 breakout was measured with a **PicoScope 2205A** driven directly through its API (MOSI, SCK, CS0 and VDD: clean 3.3 V, SPI mode 0). Finally a multimeter showed the flash VCC is the **board-wide 3.3 V rail** (shared with the FPGA JTAG header), so powering the flash externally in-circuit would back-feed the whole board. External programming was ruled out; the built-in, GPIO-routed USB path became the recovery route. Notes: [flash marking](research/receiver-flash-marking-20261009.md), [USB preflight](research/receiver-usb-preflight-20261009.md), [external CH341](research/external-ch341-recovery-references-20261009.md), [PicoScope measurements](research/picoscope-external-adapter-20261009.md), [flash/restore preparation](research/receiver-flash-restore-preparation-20261009.md).

## 8. First flash, restore test, re-flash (2026-10-09 evening)

A receiver-only write tool shares one protocol implementation with the simulation: a read-only dry run by default, strict command whitelist (block-0 erase, page program, reads, status), wall-clock BUSY deadlines, explicit hash confirmation, two full readbacks.

- 20:05 dry run: two full reads equal to stock, plan validated.
- **20:17 Favorites v4 written** (51 s, 245 verified operations). After a power cycle: P band present, P1–P8 correctly mapped, **picture on every slot**.
- **20:27 restore to stock** (verified), stock firmware boots normally → the restore path works on real hardware.
- 20:42 v4 re-applied.

## 9. Polishing with the user (2026-10-09/10)

- **v5 (23:19)** — status label shows the real channel: `P1 L6 HDZ`. The 9-character label buffer was full, so in P the mode text is shortened to three letters, inside the existing field.
- **v6 (23:51)** — the user's idea: replace the never-used E1/F1 in the built-in scan with L6/L7 (two bytes, thanks to the list's `INC A` trick), remove the P scan guard, halve the long-press threshold (1000 → 500 ticks), version text `V1.1.2`.
- **v7 (10-10 00:08)** — a scan started in P uses a P-ID version of the same list, so it starts at the current slot and lands on `P2 L7 HDZ` instead of stock L7.

Every version was built two independent ways, tested on the host, written with verified readback and accepted on the device by the user.

## Lessons learned

- **Back up first, twice.** Every later decision relied on the byte-identical backups.
- **Look for the right processor.** The biggest binary (MStar) was not where the feature lived; the small 8051 receiver was.
- **Never trust one generator.** Two independent builds caught a relative-branch error before it reached hardware.
- **Measure the recovery route.** A plausible external programmer setup turned out to back-power the whole board.
- **Small, reversible steps** with explicit approval for every write made it possible to iterate four firmware versions in one evening.
