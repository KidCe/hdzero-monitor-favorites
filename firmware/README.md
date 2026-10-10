# Receiver firmware sources

8051 assembly for the HDZero Monitor DM5680 receiver (official 1.1.1 base). Build constants (`SELECTION_STATE`, table addresses, `P_SCAN_*`, …) are supplied by [`tools/monitor_receiver_source.py`](../tools/monitor_receiver_source.py), which also generates the remaining recovered source partitions locally from a Ghidra instruction export and requires a byte-exact match with the independent generator.

## New routines (MIT, original work)

| File | Since | Purpose |
|---|---|---|
| [`receiver/favorites_label.asm`](receiver/favorites_label.asm) | v5 | Status label `P1 L6 HDZ` for the P band; hooked at the final label draws `B87F`/`B8F8` |
| [`receiver/favorites_scan_list.asm`](receiver/favorites_scan_list.asm) | v7 | Scan list with P IDs when the scan starts in P; hooked at `6D6C` |
| [`receiver/favorites_scan_guards.asm`](receiver/favorites_scan_guards.asm) | v4–v5 | *Historical*: blocked the stock scan in P. Removed in v6 and no longer included in builds |

## Recovered stock routines (see [NOTICE](../NOTICE.md))

`receiver/band_step.asm` (`0674`), `receiver/channel_step.asm` (`06D6`) and `receiver/settings_validate.asm` (`9D44`) are commented reconstructions of official 1.1.1 code, preserving the original instruction widths, registers and memory locations. Build constants turn them into the six-band (stock) or seven-band (Favorites) variant. They are included for interoperability and documentation and are not covered by the MIT license.

The complete recovered source (28,350 instructions, 77.9 % of the receiver bytes; the rest kept as explicit `.db` data) is not published; it is regenerated locally. It is recovered assembly, not HDZero's original C source. See [docs/firmware-internals.md](../docs/firmware-internals.md) for the memory map and the full patch list.
