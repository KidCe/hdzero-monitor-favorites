# HDZero Goggle source reuse for the Monitor

Research date: 2026-10-08. Sources were inspected live; no device was connected, flashed, or electrically tested.

AI assistance: This research note was researched and written with substantial assistance from OpenAI Codex under the user's direction.

## Finding

The Goggle repository is valuable documentation for receiver control and some shared chips. It is not a complete, portable replacement for the Monitor firmware. The current Goggle application explicitly targets Goggles, BoxPro, and Goggles 2; it has no Monitor build target. It uses an ARMv7 Linux toolchain and Allwinner/Softwinner multimedia interfaces. A Monitor port must establish its own processor, runtime, display path, pin mapping, and peripheral firmware contracts. [Build targets](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/CMakeLists.txt#L9-L43), [toolchain setup](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/setup.sh#L1-L3), [multimedia dependencies](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/lib/softwinner/CMakeLists.txt).

There is an official public [hd-zero/monitor repository](https://github.com/hd-zero/monitor). At the inspected snapshot `4ee23d28d6d7bd938969b762e8e1919250898367`, its only file is a nine-byte README containing the repository title. It provides no firmware source. This is a scoped observation of the public repository, not proof that no Monitor source exists elsewhere. [Pinned Monitor tree](https://github.com/hd-zero/monitor/tree/4ee23d28d6d7bd938969b762e8e1919250898367).

Goggle code references below are pinned to `adb901d9493a3f3d0ca3b052eaa693e51046dd3a`, the inspected `main` snapshot.

## What is actually open

| Layer | Observed contents | Consequence |
|---|---|---|
| Application and UI | C sources, LVGL, settings, OSD, input, DVR control, recording application | UI behavior and control logic can be studied or adapted. The Linux graphics and recording backend requires replacement on a different platform. |
| Peripheral control | Source drivers for DM5680, DM6302, IT66121, IT66021, TP2825, FPGA registers, UART, I2C | Useful register sequences and host protocols exist. Their applicability must be measured on the Monitor. |
| Linux platform | Linux UAPI headers, prebuilt `.ko` modules, prebuilt Softwinner `.so` libraries | This repository is not a complete rebuildable Linux BSP/kernel/bootloader source release. |
| Receiver and FPGA/VA firmware | `HDZGOGGLE_RX.bin` and `HDZGOGGLE_VA.bin` are copied into the update package | Building the Goggle application does not rebuild these images. No FPGA HDL was found in the complete recursive source tree. |

Evidence: [application entry point](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/main.c#L128-L195), [recording sources](https://github.com/hd-zero/hdzero-goggle/tree/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/record), [drivers](https://github.com/hd-zero/hdzero-goggle/tree/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver), [kernel module binaries](https://github.com/hd-zero/hdzero-goggle/tree/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/mkapp/app/ko), [HAL packaging](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/mkapp/mkapp_ota.sh#L71-L113), [FPGA flash selection](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/mkapp/app/script/write_flashes.sh#L69-L88), [complete recursive tree](https://api.github.com/repos/hd-zero/hdzero-goggle/git/trees/adb901d9493a3f3d0ca3b052eaa693e51046dd3a?recursive=1).

## Most useful files

| File | Concrete knowledge | Monitor reuse limit |
|---|---|---|
| [`dm5680.c`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/dm5680.c) | UART command packets start `AA 55`; responses start `CC 33`. Commands cover firmware version, fan, resets, video mode, RSSI/DLQ/status, register reads/writes, VTX information, and incoming OSD. | This is the Linux host-side driver, not the receiver MCU firmware source. A matching chip marking does not guarantee the Monitor uses the same protocol or version. |
| [`uart.c`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/uart.c#L122-L129) | Goggle host links are configured as 115200 baud, 8N1. | This is a useful initial hypothesis for capture, not a verified Monitor baud rate or pad pinout. |
| [`dm6302.c`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/dm6302.c#L20-L96) | RF register access is bridged through FPGA I2C registers `0x90` through `0x9F`; [channel programming](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/dm6302.c#L191-L249), calibration and initialization sequences are visible. | The Monitor RF chip is under shielding; its identity, FPGA register bridge, and calibration conventions remain unverified. |
| [`i2c.h`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/i2c.h#L20-L62) | Goggle addresses include main FPGA `0x64`, auxiliary FPGA `0x65`, HDMI-out IT66121 `0x4C`, HDMI-in IT66021 `0x49`, and analog TP2825 `0x44`. | These are Goggle topology data. Monitor addresses must be captured or read independently; an identical address does not establish an identical register map. |
| [`it66121.c`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/it66121.c#L20-L144) | HDMI transmitter reset, register initialization, and input clock-phase control. [Datasheet and programming/register guides](https://github.com/hd-zero/hdzero-goggle/tree/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/docs) are included. | Strong candidate if the Monitor photo's IT66121FN marking is confirmed. Board reset wiring, input format, timing, clock phase, and audio still require adaptation. |
| [`hardware-goggle.c`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/hardware-goggle.c#L550-L689), [`screen-goggle.c`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/screen-goggle.c) | Source selection, resolution switching, video synchronization, FPGA timing and screen settings. | These describe the Goggle FPGA image and displays. The Monitor's Gowin part number alone does not establish compatibility. |
| [`tp2825-goggle.c`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/tp2825-goggle.c) | Analog video initialization and PAL/NTSC handling. | The provided Monitor photo shows a Techwell TW2865, not TP2825. This is a conceptual reference, not a drop-in driver. |

The ELRS [channel/frequency handling](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/elrs.c#L116-L141) is also useful for remote-channel-selection behavior, but it depends on the Goggle application's state and hardware layers.

## Other official repositories and boundaries

[`hdzero-vtx`](https://github.com/hd-zero/hdzero-vtx) is transmitter firmware. Its README explicitly says it runs on the DM5680's built-in 8051 MCU. It teaches processor/register conventions, RF setup, MSP/DisplayPort and configuration; it is not a receiver firmware target and does not disclose all silicon internals. Its GPL-3.0 license differs from the Goggle project's MIT license. [VTX README](https://github.com/hd-zero/hdzero-vtx/blob/ad396315680f64ad5797fb0fe53bbd73e9f448ba/README.md), [VTX license](https://github.com/hd-zero/hdzero-vtx/blob/ad396315680f64ad5797fb0fe53bbd73e9f448ba/LICENSE), [Goggle license](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/LICENSE).

[`hdzero-boxpro`](https://github.com/hd-zero/hdzero-boxpro), [`hdzero-goggle2`](https://github.com/hd-zero/hdzero-goggle2), and the current Goggle repository show how HDZero adapts an application across products. None of the inspected repositories supplies a Monitor target. [`hdzgoggle_toolchain`](https://github.com/hd-zero/hdzgoggle_toolchain) has a README pointing to a compiler download, not a Linux BSP source tree. [`hdzero-tooling`](https://github.com/hd-zero/hdzero-tooling) includes a Monitor shell CAD file; CAD does not provide PCB schematics or firmware.

## Practical implication

Preserving the working receiver and FPGA images should drastically reduce the scope of an initial custom control application: characterize the Monitor's existing control traffic and adapt the needed register/protocol subset. Replacing all firmware layers would also require Monitor processor startup, memory and display/DVR drivers, FPGA behavior, receiver control, and hardware initialization. The public Goggle sources cannot by themselves deliver that complete replacement. This is an engineering inference from the source boundaries above, not a completed port or confirmed Monitor electrical map.

## Focused scope: eight fixed Favorites channels

The requested feature is an eight-slot virtual `Favorites` band, selected and cycled with the existing Monitor buttons. Each build configuration specifies the slots as original channel identities, for example `{original_band, original_channel}`, mixing supported Low, F and Race entries. This does not require inventing a new RF band: the useful modification point is the mapping from a selected slot to the existing tuning routine.

The Goggle implementation demonstrates a concrete mapping, but does not establish the Monitor's layout:

| Goggle tuning arguments | Table index | Channel identities |
|---|---|---|
| `band=0`, `ch=0..7` | `0..7` | R1..R8 |
| `band=0`, `ch=8..11` | `8..11` | E1, F1, F2, F4 |
| `band=1`, `ch=0..7` | `12..19` | L1..L8 |

Sources: [band enum](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/settings.h#L251-L254), [12-entry base count](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/dm6302.h#L11), [channel labels](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/ui/page_scannow.c#L159-L186), [tuning function](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/dm6302.c#L191-L249). F8 aliases R7 at 5880 MHz; the Goggle code does not expose every F-band frequency as a distinct HDZero channel. [Frequency mapping](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/elrs.c#L57-L102).

Crucially, `DM6302_SetChannel()` selects multiple RF register values using the original band and channel, in addition to three tuning-table entries. Low-band entries, E1 and F1 follow different branches. Replacing eight frequency coefficients while retaining an unrelated band/index could therefore leave the wrong RF settings. Resolving a favorite to its original `{band, channel}` and invoking the existing tune routine preserves these distinctions. This is a design recommendation derived from the Goggle implementation, not a confirmed Monitor patch method. [RF branch logic](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/dm6302.c#L191-L249).

Two implementation scopes should be kept distinct:

- **Add a virtual Favorites band:** preserve the original bands; add a band choice, an eight-slot limit, slot-to-original-channel mapping, labels, and saved-selection behavior. Existing button handlers can wrap between slots 1 and 8. The Goggle separately implements [button cycling](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/input_device.c#L121-L154) and [tuning dispatch](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/app_state.c#L226-L233).
- **Repurpose an existing eight-slot band:** potentially reduce UI and bounds changes by replacing its mapping. It sacrifices that band's original behavior, and mixed Low/F/R slots still require the correct per-slot RF profile. A table-only patch is plausible only after confirming that the Monitor table already contains complete tuning selections or that its dispatch can be redirected safely.

On the Goggle, the Linux application chooses the band/channel and generates RF writes; the FPGA carries those writes through an I2C-to-SPI bridge. Neither that arrangement nor the presence of an 8051 firmware segment proves which Monitor component owns button cycling, labels, or channel mapping. [Goggle application dispatch](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/app_state.c#L159-L173), [bridge implementation](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/dm6302.c#L20-L96).

No confirmed patch location in a Monitor MCU binary follows from these public sources. A source-independent Favorites build could generate a deterministic patch from an identified dispatch table or function, but locating that seam requires Monitor binary cross-references or observed button/tuning traffic. A missing plain MHz table does not rule out a patch: channels may be represented as indices, calibrated RF words, instructions, or compressed data. A matching constant sequence alone would also be insufficient to establish the active call path.
