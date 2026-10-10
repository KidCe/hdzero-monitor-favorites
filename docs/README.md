# Documentation

Start with [project-history.md](project-history.md) (the story) and [firmware-internals.md](firmware-internals.md) (the consolidated technical reference). [toolchain.md](toolchain.md) explains the tools.

The research notes below are **dated lab notes**. Each records what was known and verified at that moment, including limits that later work resolved — for example, notes from 2026-10-09 still say "not device-validated" for firmware that was later flashed and accepted. Later notes link back to earlier ones.

## Research notes (chronological)

| Date | Note | Topic |
|---|---|---|
| 10-08 | [hdzero-monitor-feasibility.md](research/hdzero-monitor-feasibility.md) | What is open, what is not; options for custom software |
| 10-08 | [hdzero-monitor-favorite-channels.md](research/hdzero-monitor-favorite-channels.md) | Favorites specification |
| 10-08 | [hdzero-goggle-source-reuse.md](research/hdzero-goggle-source-reuse.md) | What the open Goggle firmware can and cannot provide |
| 10-08 | [ripples-favorites-monitor-findings.md](research/ripples-favorites-monitor-findings.md), [ripples-lowband-monitor-reuse.md](research/ripples-lowband-monitor-reuse.md) | Design lessons from the Ripples Goggle fork |
| 10-08 | [hdzero-monitor-jtag-access.md](research/hdzero-monitor-jtag-access.md) | UART/JTAG pads and safe probing |
| 10-08 | [hdzero-monitor-implementation-plan.md](research/hdzero-monitor-implementation-plan.md) | Original plan; official programmer internals |
| 10-08 | [usb-probe-identify-20261008.json](research/usb-probe-identify-20261008.json), [usb-probe-flash-prefixes-20261008.json](research/usb-probe-flash-prefixes-20261008.json) | First USB descriptor and flash-ID reads |
| 10-09 | [monitor-flash-capacities.md](research/monitor-flash-capacities.md) | JEDEC IDs and capacities from Winbond datasheets |
| 10-09 | [usb-backup-20261009.md](research/usb-backup-20261009.md) | Two full backups of all three flashes |
| 10-09 | [mstar-payload-layout-20261009.md](research/mstar-payload-layout-20261009.md), [hdzero-monitor-firmware-comparison.json](research/hdzero-monitor-firmware-comparison.json) | MStar headers, CRC regions, 1.1.1 vs 1.2.0 |
| 10-09 | [ghidra-and-emulation-20261009.md](research/ghidra-and-emulation-20261009.md), [offline-preparation-results.json](research/offline-preparation-results.json) | Ghidra project and Unicorn ARM harness for the MStar application |
| 10-09 | [receiver-8051-selection-20261009.md](research/receiver-8051-selection-20261009.md) | **Receiver decode** and the selection/tuning path (221 checks) |
| 10-09 | [receiver-favorites-candidate-20261009.md](research/receiver-favorites-candidate-20261009.md), [receiver-favorites-candidate-results.json](research/receiver-favorites-candidate-results.json) | First Favorites candidate |
| 10-09 | [receiver-settings-scan-20261009.md](research/receiver-settings-scan-20261009.md), [receiver-settings-scan-results.json](research/receiver-settings-scan-results.json) | v4: saved state and long-press scan guard (5,735 checks) |
| 10-09 | [receiver-connected-startup-20261009.md](research/receiver-connected-startup-20261009.md) | Connected CPU sessions and startup comparisons |
| 10-09 | [receiver-mode-consumers-20261009.md](research/receiver-mode-consumers-20261009.md) | Audit of every selection consumer and computed jump |
| 10-09 | [receiver-source-rebuild-20261009.md](research/receiver-source-rebuild-20261009.md), [receiver-source-rebuild-results.json](research/receiver-source-rebuild-results.json) | Byte-exact rebuild from recovered assembly; packages |
| 10-09 | [receiver-loading-integrity-20261009.md](research/receiver-loading-integrity-20261009.md) | Is appended CODE loaded? Integrity checks? |
| 10-09 | [receiver-flash-restore-preparation-20261009.md](research/receiver-flash-restore-preparation-20261009.md) | Flash plan, NOR model, write tool, **first flash and restore test** |
| 10-09 | [receiver-usb-preflight-20261009.md](research/receiver-usb-preflight-20261009.md) | Read-only status/SFDP preflight |
| 10-09 | [receiver-flash-marking-20261009.md](research/receiver-flash-marking-20261009.md) | W25Q80DV USON-8 identification from photos |
| 10-09 | [external-ch341-recovery-references-20261009.md](research/external-ch341-recovery-references-20261009.md) | External programmer investigation; why it was ruled out |
| 10-09 | [picoscope-external-adapter-20261009.md](research/picoscope-external-adapter-20261009.md) | PicoScope 2205A API measurements of the adapter |
| 10-09 | [picoscope-mcp-evaluation-20261009.md](research/picoscope-mcp-evaluation-20261009.md) | Review of a third-party PicoScope MCP server |
| 10-10 | [receiver-favorites-label-v5-20261010.md](research/receiver-favorites-label-v5-20261010.md) | v5: `P1 L6 HDZ` label |
| 10-10 | [receiver-favorites-scan-v6-20261010.md](research/receiver-favorites-scan-v6-20261010.md) | v6: favorites in scan, faster long press, version text |
| 10-10 | [receiver-favorites-pscan-v7-20261010.md](research/receiver-favorites-pscan-v7-20261010.md) | v7: scan stays in P |

## Tasks

- [tasks/fast-channel-switching.md](tasks/fast-channel-switching.md) — FUT-001, faster channel switching, with first timing findings.
