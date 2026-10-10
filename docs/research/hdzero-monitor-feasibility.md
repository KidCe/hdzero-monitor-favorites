# HDZero Monitor custom software feasibility

Research date: 2026-10-08.

This assessment combines the user's five PCB photos, live official repositories, and static analysis of an official firmware download. No Monitor was connected, measured, read out, or flashed. Device behavior and recovery remain untested.

AI assistance: This research note was researched and written with substantial assistance from OpenAI Codex under the user's direction.

## Assessment

The user has now narrowed the desired feature to eight fixed favorite channels, selectable as a virtual band through the stock controls. The broad options below are background research. The active scope is [the focused Favorites specification and investigation](hdzero-monitor-favorite-channels.md).

Custom functionality is plausible without recreating the HDZero radio or all video processing. A PC application for existing USB settings is the most direct route. Channel automation and status reporting need additional interface characterization. A replacement on-device UI or DVR application would require significantly deeper work on the MStar processor firmware. Replacing the FPGA and receiver firmware as well would be a much larger project.

The Goggle firmware is a source of peripheral control knowledge, not a Monitor firmware image that can be installed directly. See [the Goggle source reuse assessment](hdzero-goggle-source-reuse.md) for pinned driver references and source/binary boundaries.

## Public source status

The official [hd-zero/monitor](https://github.com/hd-zero/monitor/tree/4ee23d28d6d7bd938969b762e8e1919250898367) source tree has only `README.md`. Its [releases](https://github.com/hd-zero/monitor/releases) provide `HDZero_Monitor.bin`; the inspected latest release is [v1.2.0](https://github.com/hd-zero/monitor/releases/tag/v1.2.0), with the note "support 1080p24". An available binary is not an available source release.

The official [Monitor introduction](https://docs.hd-zero.com/monitor-introduction) advertises open-source software. The inspected public Monitor tree does not deliver buildable Monitor source. This discrepancy makes asking HDZero for the application source, build instructions, and permitted SDK access a sensible first step. It does not establish that source is unavailable through every other route.

The official [hdzero-programmer](https://github.com/hd-zero/hdzero-programmer/tree/85a497e5b258e1bd1137e39668e078c02f895668) does contain Python source for Monitor settings and flashing. The [update documentation](https://docs.hd-zero.com/monitor-firmware-update) confirms that the powered Monitor is updated through USB-C using this tool. The downloaded upstream Python files were inspected as text and were not executed.

## Hardware visible in the photos

All board-role assignments below are observations or inferences, not a measured schematic.

| Visible component or marking | Identification confidence | Role and relevance |
|---|---|---|
| `HDZero Monitor 1R3` | Clear | Board revision of the photographed unit. Establish compatibility before using firmware for other hardware revisions. |
| Divimath `DM5680` | Clear in `60126.jpg` | Wireless video/baseband ASIC, consistent with the separate `5680` firmware component. Divimath describes it as a proprietary wireless video transceiver. The control processor and host interfaces are distinct from the silicon's physical-layer implementation. |
| `GW2A-LV18`, `UG324...` | Clear family/package, suffix not fully established | Gowin SRAM FPGA. Its role plausibly includes video routing/timing and control glue. The precise implemented logic, peripheral map, and connections are unknown. |
| Techwell `TW2865` | Clear | Analog video decoder/audio codec with video encoder. Public register documentation exists. The Goggle uses a different analog chip, TP2825. |
| ITE `IT66121FN` | Clear | HDMI transmitter. Both Goggle code and upstream Linux provide driver examples. Input data format, reset wiring, clocks, and board timing must still be established. |
| MStar logo; 8339-family marking | MStar clear; exact part/suffix not reliably legible | Likely display/DVR processor. The official updater explicitly names an `8339` image and the image contains MStar DVR/OSD functions, supporting this interpretation. It is not proven to run the Goggle's Linux environment. |
| ESMT `M15T1G1664A...` | Family readable; exact suffix uncertain | External DDR3-family memory. Which chip owns it and its bus wiring need verification. RAM does not by itself imply a general-purpose Linux platform. |
| `RX TX GND`, `RXD TXD`, `BRX BTX`, `SDA`, `SCL`, `PRG_B`, `DONE`, `3V3 GND TDO TDI TCK TMS` | Several labels clear; all connections unmeasured | Promising points for passive serial/I2C capture and FPGA debug access. Labels alone do not prove signal direction, voltage, bus owner, baud rate, or a usable debug console. |

Chip references: [Divimath ASIC descriptions](https://www.divimath.com/pages/proprietary-asics), [Gowin GW2A family](https://www.gowinsemi.com/en/product/arora-ii-fpga/), [Renesas TW2865 datasheet](https://www.renesas.com/en/document/dst/tw2865-datasheet), [upstream IT66121 driver](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/bridge/ite-it66121.c), [ESMT family datasheet](https://www.esmt.com.tw/upload/pdf/ESMT/datasheets/M15T1G1664A%282M%29.pdf). The memory reference documents the family, not the exact photographed suffix.

## Important result: three separate firmware components

The programmer's [`parse_monitor_fw`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L100-L118) skips two initial bytes, reads three unsigned 32-bit little-endian lengths, then reads the `5680`, FPGA, and `8339` payloads sequentially. Its [Monitor update path](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L585-L603) selects and writes those three flash targets separately.

The downloaded [v1.2.0 release asset](https://github.com/hd-zero/monitor/releases/download/v1.2.0/HDZero_Monitor.bin) was inspected offline:

- Total file length: 8,276,629 bytes.
- SHA-256: `3db0a81fe43869085b5455031c34bc69f19c998606c2fedf4085eb150fac8725`.
- First 14 bytes: `0100b7f600009ad80d00367b6f00`.
- The 14-byte header plus the three declared payload lengths exactly equals the downloaded file size.

| Component name from official updater | File offset, zero-based | Length in bytes |
|---|---:|---:|
| `5680` | 14 | 63,159 |
| FPGA | 63,173 | 907,418 |
| `8339` | 970,591 | 7,306,038 |

The `8339` payload begins with ASCII `MCR5`. Static printable-string inspection found the following byte offsets relative to that payload:

| String | Payload-relative offset |
|---|---:|
| `CarDV SDK` | 2,831,303 and 2,857,226 |
| `Divimath HDZero` | 2,836,955 |
| `MStar eCos` | 3,164,692 |
| `20171212-rtos` | 3,169,694 |

Additional strings include `AHC_OSDSetFont`, `AHC_OSDDrawBuffer`, `AHC_UARTLogTxTask_Task_init`, and UART command/help text. These are useful starting points for locating display and console code in a disassembler. They do not establish that the corresponding functions or console are reachable on this board. Embedded SDK strings can refer to unused features.

**Inference:** the Monitor likely uses an MStar DVR SDK with an eCos/RTOS environment, rather than the Goggle's ARM/Linux/Softwinner application platform. This is strong static evidence, but a boot log and identification of executable sections/ISA are still needed. An apparent XZ signature failed a decompression check and was not treated as a valid compressed section.

This split may let a project keep the receiver and FPGA images while modifying only the application processor image. It does not establish a supported plugin mechanism, compatibility of mixed versions, or a working recovery method. The inspected host update code exposes direct SPI erase/write operations and no host-side cryptographic signature check; device boot-time verification has not been investigated.

## USB settings are already described in source

[`frame_monitor.py`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/frame_monitor.py#L19-L48) uses CH341 I2C functions to address the FPGA at 7-bit address `0x65`. These are the existing Monitor interface values, not guessed Goggle addresses:

| Setting | Write register | Read register | Range used by official UI |
|---|---:|---:|---|
| Heartbeat | `0x13` | Not shown | Incrementing byte, wraps before 255 |
| Brightness | `0x14` | `0x22` | 0-254 |
| Contrast | `0x15` | `0x23` | 0-254 |
| Saturation | `0x16` | `0x24` | 0-254 |
| Backlight | `0x17` | `0x25` | 1-100 |
| Battery cell count | `0x18` | `0x26` | 1 means Auto; 2-6 select cell count |
| Warning cell voltage | `0x19` | `0x27` | 28-42, displayed as tenths of a volt |
| FC OSD visibility | `0x1A` | `0x28` | 0 or 1 |
| FPGA version | Not shown | `0xFF` | One byte |

Read definitions: [`ch341.py`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L38-L46) and [`read_setting`](https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py#L141-L156).

The shown interface toggles FC OSD visibility; it does not expose arbitrary text drawing. It also does not show channel selection, RSSI/DLQ reads, or DVR control. Those functions cannot be claimed as implemented USB features from this source alone.

The source includes flash-target switching, JEDEC identification, and an SPI page-read function. This makes a backup tool plausible. A stock GUI connection is not strictly passive: `connect_monitor` switches a flash target, and other GUI paths write settings/heartbeat values. A backup implementation needs separate review and real readback verification before being called safe or complete. An official update image is not a substitute for a complete dump of device-specific settings/calibration and boot data.

## Required reverse engineering by goal

| Goal | What must be understood | Scope estimate |
|---|---|---|
| Own PC settings tool | CH341 transport, connection lifecycle, existing settings register semantics and persistence | Low; substantial protocol information is already public. |
| External channel automation, race integration, signal logging | Monitor-specific channel/status interface, control ownership, button behavior, lock timing, and whether Goggle DM5680/DM6302 protocols match | Moderate and conditional. It could avoid replacing firmware entirely. |
| Custom on-screen menu, local channel scan, or altered DVR policy | Which processor/FPGA owns each function; MStar image layout, ISA, boot/runtime, control and rendering APIs, and verified recovery | High without application source/SDK. A narrow binary patch may be easier than a full rewrite but remains version-specific. |
| Entire application processor firmware replacement | Startup, clocks, DRAM as applicable, storage, panel output, media encoder, input, and interprocessor drivers | Very high without a suitable SDK/BSP; public Goggle code does not supply this platform. |
| Replacement FPGA and receiver firmware too | Board pin constraints, video timing, memory/control logic, receiver initialization and calibration, equivalent processing behavior | Much larger embedded/FPGA project. No need to take this route for ordinary control/UI improvements. |

These are engineering estimates, not schedules. The exact effort depends on the desired first feature and on SDK/source access.

## Recommended next investigation

1. Request the Monitor application source and build instructions from HDZero, including the MStar 8339 SDK/toolchain and the FPGA register contract. The official open-source description makes this a particularly useful route.
2. Identify the exact installed firmware and hardware revision. Inspect USB identity. Build and verify complete backups of all flash targets before any patch experiment; establish independent recovery.
3. Measure the labeled UART and I2C signal levels, then passively capture boot, band/channel changes, input changes, and recording start/stop. Use a logic analyzer and receive-only serial capture first; the signal voltage is unknown and must not be assumed to be 5 V or 3.3 V.
4. Compare Monitor captures with Goggle `AA 55` / `CC 33` UART framing and FPGA RF-control sequences. Goggle 115200 8N1 is a starting hypothesis, not a verified Monitor configuration. Avoid blindly replaying Goggle calibration/register writes.
5. Implement one bounded feature through a verified existing control interface. Only proceed to MStar patching or a replacement application if that feature needs internal code changes.

Useful equipment would be a multimeter, logic analyzer with suitable input voltage support, and an appropriate UART interface after level measurement. FPGA JTAG or an external flash programmer becomes relevant only if the verified USB backup/recovery route is insufficient. RF shield removal is not required for the first interface investigation.

No code implementation, firmware compatibility test, or physical Monitor validation is claimed by this assessment.
