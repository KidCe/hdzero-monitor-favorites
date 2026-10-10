# HDZero Monitor: UART and FPGA JTAG access

Date: 2026-10-08. Scope: access strategy for eight Monitor Favorites; installed firmware reported as 1.1.1. Research only; no connection, transmission, flash operation, or physical measurement was performed.

AI assistance: This research note was written with substantial assistance from OpenAI Codex under the user's direction. Hardware assumptions remain unverified.

## Recommended order

Use offline firmware analysis and receive-only UART observation together. The former identifies candidate code; the latter can reveal boot messages and correlate channel changes with running behavior. Neither requires an experimental firmware write. Preserve the installed state before any later modification, including device-specific settings that an official update file might omit.

Treat FPGA JTAG as a later identification/recovery option. Its usefulness depends on where the pads connect and what the device permits. A successful scan alone would not locate the Monitor's Favorites implementation. This recommendation is an engineering inference, not a claim that the UART exposes a shell or that the FPGA owns channel selection.

For flash identification and backups, prioritize the existing USB/CH341 programmer interface before attaching to additional board pads. The current [implementation plan](hdzero-monitor-implementation-plan.md) reflects the user's request to start there; passive UART remains useful for runtime evidence and JTAG stays a later option.

## Measure before attaching an adapter

The photographed `RX TX GND` and `TDO TDI TCK TMS` labels are candidates. Their owner, direction, operating voltage, and multiplexed function have not been established. Unpowered continuity checks can establish ground and accessible routing; powered scope observations can establish signal amplitude and activity. Do not probe hidden BGA balls directly. A 20 MHz scope can help identify slow serial activity and bit timing; it does not establish a complete high-speed bus protocol.

GW2A core voltage and I/O-bank voltage are separate supplies. The manufacturer's recommended ranges therefore do not establish the voltage of these Monitor pads. Measure the actual interface supply and use a compatible receiver/level translator or a JTAG adapter with the appropriate target-voltage reference. Ensure a grounded bench scope's ground clip connects to verified circuit ground. [GW2A data sheet, DS102-2.7.8E, §3.1.2, printed p27 / PDF p37](https://cdn.gowinsemi.com.cn/DS102E.pdf#page=37).

For the first UART capture, connect only the verified device transmit signal to the adapter's RX input, plus verified ground. Leave adapter TX, VCC, RTS, and DTR disconnected. This prevents intentional commands and adapter power injection; input loading and electrical compatibility still matter. FTDI explicitly distinguishes RX input from TX output, and its 3.3 V TTL cable still exposes a **5 V power output**. Its label is not proof of safe target wiring. [FTDI cable data sheet, Table 4.1](https://ftdichip.com/Support/Documents/DataSheets/Cables/DS_TTL-232R_CABLES.pdf), [FTDI TTL-232R-3V3 specification](https://ftdichip.com/products/ttl-232r-3v3/).

## What verified FPGA JTAG could provide

| Access | Meaning and limitation |
| --- | --- |
| IDCODE/status | GW2A(R)-18/18C IDCODE: `0x0000081B` (shared family). Status: bit14 security, bit15 encryption format. [UG290, §7.2.4, pp53 and83](https://cdn.gowinsemi.com.cn/UG290E.pdf#page=65). |
| Boundary scan | Matching device/package description for pin tests; short scan chain for external SPI flash. [UG290, §9, pp120–121](https://cdn.gowinsemi.com.cn/UG290E.pdf#page=132). |
| SRAM configuration readback | Security must be disabled; default protected reads return ones. Read flow issues configuration-enable/address-initialize. This does not establish passive runtime capture. [UG290, §7.2.4, pp56–58](https://cdn.gowinsemi.com.cn/UG290E.pdf#page=68). |
| External SPI flash | Distinct from configuration SRAM; needs connected configuration pins and a suitable access method. Readability does not prove unencrypted contents. [UG290, §7.2.4, pp73–80](https://cdn.gowinsemi.com.cn/UG290E.pdf#page=85). |
| Reused JTAG pins | `JTAGSEL_N` reclaims multiplexed pins and changes their function. Failed scan alone is inconclusive. [UG290, §4.2, p30](https://cdn.gowinsemi.com.cn/UG290E.pdf#page=42). |

A Gowin TAP does not automatically provide MStar CPU memory access, breakpoints, or executable debugging. The `CPU configuration` term in Gowin documentation names a parallel bitstream-loading interface. Gowin's internal signal analyzer requires Control/AO cores and an instrumented design/netlist; attaching JTAG does not create that instrumentation in an unknown production image. A recovered bitstream also does not reproduce the original HDL source. [UG290, glossary p4](https://cdn.gowinsemi.com.cn/UG290E.pdf#page=16), [GAO SUG114-3.5E, §§2–3 and3.1.3, pp3–5 and26](https://cdn.gowinsemi.com.cn/SUG114E.pdf#page=13). These access limitations are inferences from the documented interfaces; the actual Monitor pad owner remains unknown.

## Actions that change state

These are documented actions to distinguish during a future procedure, **not actions executed or instructions to try now**.

| Action in Gowin tools | Consequence |
| --- | --- |
| Native `Read Device Code` | Reads ID, user code, and status; actively drives the TAP. Separate user-code/status reads also exist. |
| `Reprogram` | Reloads configuration from flash into SRAM; interrupts/restarts FPGA logic. |
| `SRAM Erase`, `SRAM Program` | Clears/replaces the active FPGA design, even without writing persistent flash. |
| `exFlash Export thru GAO-Bridge` | Exports flash bytes **after loading a JTAG-to-SPI bridge into SRAM**. A command described as reading/exporting can therefore replace the active FPGA design. |
| External-flash erase/program operations, including boundary-scan variants | Changes persistent flash. Verification appended to a combined operation does not make it read-only. |
| I/O state editor applied during operation | Changes pin values; can affect other components. |
| Security key writing/locking | Writes one-way key bits or permanently locks key access. Avoid as a discovery/recovery step. |

Sources: [SUG502-2.5.2E, Table3-1 pp15–16, method notes p21, §§3.5–3.6 pp26–28](https://cdn.gowinsemi.com.cn/SUG502E.pdf#page=25), [UG290, §3.2.3, p9, one-way key bits](https://cdn.gowinsemi.com.cn/UG290E.pdf#page=21). Even a native read changes TAP state; “read” and “does not write flash” are narrower claims than “does not disturb the board.”

For Favorites, seek evidence identifying the button-to-channel mapping and the existing tuning command before choosing a patch target. UART logs can help establish that evidence. FPGA readback or boundary scan cannot by themselves replace that analysis.

## Source snapshots and review paths

The CDN links are mutable. The PDFs were retrieved on 2026-10-08 and pinned here by their cover versions and SHA256. Website release dates sometimes differ slightly from PDF cover dates; the versions below refer to the downloaded covers.

| Document | Cover version/date | SHA256 |
| --- | --- | --- |
| UG290E.pdf | UG290-2.9.1E, 2026-07-31 | `f5b43ee2d790fce73a0621d1480c193b02cee3b52bfb8a1a34e5509b5f806012` |
| SUG502E.pdf | SUG502-2.5.2E, 2026-09-22 | `5fa4d7815b80d9a2e113814fd9b9d720a9bbcbfba6fd9e3ecece3fb8a63737c3` |
| DS102E.pdf | DS102-2.7.8E, 2026-07-10 | `33249041ce2b2200ebe770d5607a066cfc156db22b8628d7e34772513b25dc9d` |
| SUG114E.pdf | SUG114-3.5E, 2026-09-22 | `a7a936192fb88b6961efbddd60554091ef37c7aa181cd4cfb006f494cbace6ae` |

A private local review cache (not published) holds the PDFs. The first three PDFs have same-name `.txt` extracts. `SUG502E.txt` lines1167–1169 contain the GAO-Bridge prerequisite; PDF p31 is printed p21. FTDI observations were checked against the manufacturer's indexed data sheet/product text; its PDF download returned HTTP403 and was not locally pinned.
