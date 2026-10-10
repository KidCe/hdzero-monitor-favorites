# Notice

## Not affiliated with HDZero

This is an independent community project. It is not affiliated with, endorsed by or supported by HDZero / Divimath. "HDZero" and related names are used only to identify the hardware and firmware this project works with. Do not contact HDZero support about problems caused by this firmware.

## HDZero firmware rights

The official HDZero Monitor firmware is distributed by HDZero as release binaries ([hd-zero/monitor releases](https://github.com/hd-zero/monitor/releases)). The `hd-zero/monitor` and `hd-zero/hdzero-programmer` repositories carry no license file at the time of writing. All rights in the official firmware remain with their owner.

- The **release binaries** of this project contain the official Monitor 1.1.1 FPGA and MStar components unchanged and a modified DM5680 receiver component. They are published as an unofficial community modification. If the rights holder objects, they will be removed.
- `firmware/receiver/band_step.asm`, `channel_step.asm` and `settings_validate.asm` are short, commented routines **recovered from the official 1.1.1 receiver firmware** for interoperability and documentation. They are not covered by this repository's MIT license.
- The complete recovered receiver source (about 28,000 instructions), Ghidra databases, official firmware files and device backups are **not** part of this repository. The tools regenerate them locally from a user-supplied official firmware file and/or device backup.

## Original work (MIT)

Everything else — the Python/PowerShell tools, Ghidra scripts, tests, the new firmware routines (`favorites_label.asm`, `favorites_scan_list.asm`, `favorites_scan_guards.asm`), configuration and documentation — is original work licensed under the [MIT License](LICENSE).

## Referenced third-party sources

Research notes cite and link (but do not copy) the [HDZero VTX build script](https://github.com/hd-zero/hdzero-vtx) for the receiver payload bit permutation, the [HDZero Programmer](https://github.com/hd-zero/hdzero-programmer) for the update container and CH341 routing, the MIT-licensed [HDZero Goggle firmware](https://github.com/hd-zero/hdzero-goggle) and the [Ripples Goggle fork](https://github.com/LVTY-AI/hdzero-goggle) for design references, and Winbond/WCH/Gowin/Pico datasheets.
