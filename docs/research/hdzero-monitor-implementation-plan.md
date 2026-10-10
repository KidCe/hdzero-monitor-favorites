# HDZero Monitor Favorites: implementation and recovery plan

Date: 2026-10-08; hardware and layout evidence updated 2026-10-09.

AI assistance: This investigation and plan was researched and written with substantial assistance from OpenAI Codex under the user's direction.

## Target and present evidence

The user reports installed Monitor firmware **1.1.1**, a basic 20 MHz oscilloscope and other basic instruments. The target remains eight fixed Favorites: `L6, L7, R1, R2, F2, F4, R7, R8`, using stock controls and an additional virtual band. The existing USB connection has now been identified and all three main SPI arrays have been read twice with complete byte equality. A decoded offline candidate exists; no device patch or restore test has occurred. The user confirmed normal picture/menu and button operation after the subsequent receiver USB preflight.

The current priority is integrated offline mode/button/boot analysis and establishing recovery independence before any device write. A bounded selection-layer modification and source build already exist. The [USB backup report](usb-backup-20261009.md) records capacities, hashes and the 132 MStar filesystem differences from the release. The [layout note](mstar-payload-layout-20261009.md) identifies two exact CRC-covered regions and candidate ARM code/settings references. Passive UART captures provide additional runtime evidence if needed. JTAG is an optional additional interface, not a prerequisite for modifying an ordinary application binary.

The [ARM analysis report](ghidra-and-emulation-20261009.md) records 22 original-code checks for MStar settings and UART helpers. The [receiver report](receiver-8051-selection-20261009.md) identifies the decoded DM5680 button-to-selection-to-tuning path, with 221 stock checks. The [current v4 candidate report](receiver-settings-scan-20261009.md) records a seventh band, suppression of P-band long-press stock scanning, 55 changed original bytes, 343 appended table bytes and 52 guard bytes. The [connected/startup follow-up](receiver-connected-startup-20261009.md) records 5,735 bounded actual-instruction checks including 1,152 connected CPU sessions, and four separate C-runtime startup comparisons. The [source rebuild report](receiver-source-rebuild-20261009.md) describes byte-exact native assembly and experimental update packaging; the current package and 27 host checks are recorded in the v4 report. Integrated Monitor/RF simulation, complete source recovery of all components, actual settings retention, ROM CODE loading and device recovery/operation remain unverified. [Faster channel switching](../tasks/fast-channel-switching.md) is deferred until physical Favorites acceptance.

## Version-specific offline result

The [additional offline preparation](receiver-flash-restore-preparation-20261009.md) records 47 passing host tests, a bounded mode/indirect-consumer audit, raw receiver loading/integrity evidence and exact receiver-only apply/restore plans. Its [machine-readable status](offline-preparation-results.json) describes that completed offline batch, with device validation false. The subsequent [receiver USB preflight](receiver-usb-preflight-20261009.md) successfully captured unchanged status and two full original arrays; SFDP returned only `FF` bytes. Native programming still needs exact flash identification, recovery evidence and adapter finalization. The next physical step is the [external CH341 identification and electrical investigation](external-ch341-recovery-references-20261009.md); no external hardware operation has occurred.

Downloaded the official [v1.1.1 release asset](https://github.com/hd-zero/monitor/releases/download/v1.1.1/HDZero_Monitor.bin) and compared it with the previously downloaded [v1.2.0 asset](https://github.com/hd-zero/monitor/releases/download/v1.2.0/HDZero_Monitor.bin). The 14-byte container layout follows the official [`parse_monitor_fw`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L100-L118). Declared lengths exactly match both file lengths.

| Official asset | Total bytes | SHA-256 |
|---|---:|---|
| v1.1.1 | 8,275,473 | `6b7f7cd53be329eaa4059b7b40c2e3e8f2fad1d8ecd94bfe0cb7a228131f7041` |
| v1.2.0 | 8,276,629 | `3db0a81fe43869085b5455031c34bc69f19c998606c2fedf4085eb150fac8725` |

The FPGA and 8339 payloads are byte-identical between these two releases. Only the 5680 payload differs. The [machine-readable comparison](hdzero-monitor-firmware-comparison.json) records offsets, lengths, and component hashes. These are release-file findings; an installed version label does not establish the full contents of the device's flash.

The shared 8339 payload contains the candidate channel strings already documented in [the Favorites specification](hdzero-monitor-favorite-channels.md). Additional findings:

| String | Payload-relative offset | Meaning of the evidence |
|---|---:|---|
| `UART>` | 2,816,161 | Candidate command-console prompt; reachability unproven. |
| `Memory Dump` | 2,816,414 | Candidate memory-read command description; interface and address semantics unproven. |
| `CRC32 Check fail` | 41,444 | Candidate integrity-check failure message; active enforcement, coverage and checksum storage unproven. |

These strings justify tracing console initialization and integrity-check code. They do not authorize blindly sending SDK commands, prove that UART provides a shell, or prove that a checksum-free patch will boot.

## First hardware session: existing USB connection

The user explicitly suggested prioritizing the same USB connection used for updates. This route successfully identified and read all three main arrays on 2026-10-09. The inspected programmer uses the CH341 bridge to issue SPI transactions and GPIO target selection, and it also exposes known I2C settings reads. This interface does not by itself establish a serial console, CPU debugger or RAM access. The steps below describe the acquisition method; target identification and repeated full-array backup are now complete.

1. Power the Monitor normally and connect a USB data cable. The [official update instructions](https://docs.hd-zero.com/monitor-firmware-update) require a powered Monitor and USB connection. Do not start an update workflow.
2. Enumerate the USB device and verify its identity and driver. A read-only Windows enumeration on 2026-10-08 found no present CH341/WCH matching entry at that moment; this is not a device connection test.
3. Prepare a separate connection/identification utility using the inspected bridge path, with explicit device selection and no erase/program/write-enable implementation. Read the JEDEC ID of each selected flash target and restore bus ownership after the session.
4. Once target identification, geometry and transport return values are established, implement chunked readback and the repeated full-dump validation described below. Target selection actively changes hardware routing even though no flash bytes are programmed.
5. Use UART later if flash analysis leaves code ownership, load addresses or runtime channel messages unclear. USB is the preferred first backup interface; UART provides different evidence rather than replacing that backup route.

## Optional runtime investigation: passive UART

1. With power disconnected, establish the labeled ground using known circuit ground and identify the RX/TX pad positions. Inspect the pads' routing; their proximity to the MStar is an inference about ownership.
2. Power the Monitor normally and probe RX and TX relative to that ground with the oscilloscope. Capture startup activity and establish signal amplitude, polarity, idle level and approximate bit period. Do not assume 3.3 V, 5 V, RS-232 levels or a particular baud rate from the labels. A 20 MHz scope should be adequate for an initial low-speed UART investigation; actual signaling determines adequacy.
3. Once the signaling is identified as UART at a compatible level, use a suitable receive-only input. For a USB TTL-UART adapter, connect circuit GND to adapter GND and the confirmed board transmit pad to adapter RX. Leave adapter TX and its power/VCC wire physically disconnected. Power the Monitor through its normal input. A logic analyzer can observe both pad signals without sending characters.
4. Begin capturing before power-on. Save raw bytes and, where possible, the sampled waveform. Derive the baud rate from the trace. Goggle 115200 8N1 is only a reference hypothesis, not a Monitor setting.
5. Capture a few stock channel changes with timestamped button actions and the displayed original channel. Include R1 to R2, a transition to F2, F2 to L6, L6 to L7 and L7 to R7, as practical with stock controls. The last pair distinguishes band identity from the shared local channel number. Start with recording off to simplify interpretation.

Success means a reproducible trace with verified electrical and framing parameters. If no serial log appears, record that result and inspect the other labeled UART pairs before resorting to active commands. A disabled console, binary protocol, multiplexed pad or different owner remains possible. Passive I2C/SPI captures can then connect button events to inter-chip activity.

## Backups and independent recovery before a patch

The official USB programmer already multiplexes access to the three flash targets. Its [`flash_read_page`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L298-L311) issues SPI READ `0x03`. This makes a dedicated backup path plausible, but the existing GUI is not a validated backup tool.

Relevant source audit:

- [`flash_switch0/1/2` and `flash_release`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L167-L177) change GPIO outputs and bus ownership. Reading the flash contents still requires this active hardware handover.
- [`connect_monitor`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L360-L371) selects one target and expects JEDEC ID `0xEF4018`. This is not evidence of the other targets' capacities or IDs.
- The read helper returns no byte array and accumulates a fixed 256-byte checksum. A robust dump path must extract returned SPI bytes, validate transport results and lengths, and identify the actual chip geometry.
- [`fw_write_to_flash`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L373-L393) erases/programs blocks; its readback loop is commented out. It is unsuitable as a read-only backup path.
- [`MONITOR_UPDATE`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L585-L601) writes all three components and closes the CH341 handle before calling release. A new tool must review cleanup ordering and restore bus ownership while the handle is usable, including failure paths.

A dedicated dump implementation should select the explicitly identified device, expose only verified read operations and required bus selection, contain no erase/program/write-enable workflow, have timeouts and checked return values, and always restore ownership on exit. Determine each target's full capacity and address width from verified identification/documentation; do not use update payload lengths or Python buffer allocations as flash capacity.

Read each entire flash twice in separate acquisition passes, compare all bytes and record hashes, device IDs and bus settings. Include data outside the update payload, since it may contain settings, boot information or calibration. Two identical dumps establish reproducibility, not necessarily correct wiring or completeness; check their content against the expected component structure too.

Establish that the recovery transport can select and access the application flash independently of a working application image. Preserve the stock images and full dumps. A spare flash or spare unit is preferable for validating erase/program/readback and restoration. If USB recovery depends on the failed component, identify an independent flash access route before the first persistent modification. External SPI access requires confirmed pinout, voltage and isolation from other bus masters; an in-circuit clip alone is not a recovery guarantee.

## Focused binary work

1. The ARM application and bit-permuted 8051 receiver images now have coherent, independently tested analysis mappings. Continue in the receiver project for RF channel selection; retain the MStar project for DVR/interface questions.
2. Inventory every consumer of receiver selection `EXTMEM:0D85` and the tables at CODE `C6C0`, `C6F0`, `C720` and `EF08`, including calibration, digital/analog transitions, display and saved state. Keep decompiler guesses separate from assembly evidence.
3. Extend the original-code harness around the identified selection/tuning boundary. Compare each Favorites slot with its stock identity. The current fragments validate lookup values, not completed peripheral transactions; a passive hardware trace can establish that remaining runtime boundary.
4. Locate the integrity-check routine and determine the exact algorithm, covered bytes and header fields before repackaging modified code. Absence of host-side signature checks does not prove absence of device-side validation.
5. The decoded candidate keeps logical Favorites IDs separate from effective RF indices by extending verified lookup tables, and adjusts selection limits and both OSD labels in place. Establish that its appended CODE data is actually loaded/mapped. Continue tracing indirect consumers, mode changes and the internal stock scan/configuration list. Arbitrary zero/FF padding is not proof of usable storage.
6. If a verified debug interface permits a controlled RAM experiment, and the relevant code actually runs in writable RAM, consider a temporary patch before a flash patch. This requires verified addresses, instruction alignment, permissions and cache handling. It is conditional; the discovered console strings do not yet establish this capability.
7. The decoded candidate builder records exact changes and independently regenerates the candidate. The recovered assembly build reproduces both stock and Favorites images; the separate offline packager emits standard-format experimental updates while retaining installed MStar filesystem state. The original file-parser accepts these packages and array projections preserve unaffected bytes. Verified loading, integrity rules, independent recovery and real operation are still required before device use; no new hardware programming tool exists.

Ghidra supports raw binaries and decompilation, but raw import requires the correct processor/language specification and a justified memory layout. Its output can help reconstruct logic; it does not restore the original source tree, comments, exact names or build environment. [Official Ghidra import guide](https://ghidra.re/ghidra_docs/GhidraClass/Beginner/Introduction_to_Ghidra_Student_Guide.html).

## Where JTAG fits

The `TDO/TDI/TCK/TMS` group plausibly belongs to the Gowin FPGA. Confirm ownership and I/O voltage before any active probe. FPGA identification/configuration access does not automatically expose MStar CPU registers or application RAM. Treat readback, debug-core access and flash programming as separate capabilities with distinct prerequisites; see [the official-documentation JTAG investigation](hdzero-monitor-jtag-access.md).

JTAG is useful if it establishes a needed recovery or control path. It is not the first tool for finding a menu function in the MStar binary, and automatic programming, erase, reconfiguration or boundary-scan output driving are outside the initial measurement session.

There is a concrete tool-mode trap: Gowin Programmer's `exFlash Export thru GAO-Bridge` reads flash into a binary file, but GAO-Bridge first loads a JTAG-to-SPI design into FPGA SRAM. Thus a flash export can replace the running FPGA configuration even though it does not program the flash. Native ID/status reads are separate operations. SRAM readback can also be blocked by the bitstream security setting; the actual Monitor setting is unknown. [Gowin Programmer SUG502, section 3.4, Table 3-1 and notes](https://cdn.gowinsemi.com.cn/SUG502E.pdf), [Gowin Configuration Guide UG290, section 7.2.4](https://cdn.gowinsemi.com.cn/UG290E.pdf).
