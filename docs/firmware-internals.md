# HDZero Monitor firmware internals

Consolidated reverse-engineering knowledge for **Monitor PCB 1R3, official firmware 1.1.1**, as used by Favorites v1.1.2 (internal build v7). Addresses are hexadecimal. "Established" means checked against code and/or device behavior; anything else is marked as inference. Detailed evidence is in the [research notes](README.md).

## Hardware and flash

| Part | Role | Flash (JEDEC) | Official 1.1.1 payload |
|---|---|---|---|
| **DM5680** receiver, 8051 core | Channel selection, RF tuning, buttons, scan, status-bar text | Winbond W25Q80DV, 1 MiB (`EF4014`), USON-8 | 62,003 bytes, bit-permuted |
| **Gowin GW2A** FPGA | HDZero video decoding | 16 MiB (`EF4018`) | 907,418 bytes |
| **MStar 8339**, ARM | Display output, probably UI and recording (largely not analyzed; roles partly inferred) | 16 MiB (`EF4018`) | 7,306,038 bytes |
| **CH341** USB bridge (`1A86:5512`) | USB access to the three flashes and FPGA I²C settings | — | — |

The CH341's upper GPIOs route the SPI bus: `CH341SetOutput(0, 0x03, 0xFF00, value)` with `0x4300` receiver, `0x8300` FPGA, `0xC800` MStar, `0xC200` release (values from the official programmer). Bus ownership switches in hardware, independent of the receiver firmware content (inference, consistent with the successful restore). The receiver flash VCC is the board-wide 3.3 V rail, so external in-circuit programming would back-power the board.

All bytes after each payload are `FF`. The MStar backup of the development Monitor differs from the official component in 132 bytes of an embedded filesystem (device state); its two CRC-covered program regions (`MCR5` headers at `0x1000`, `0xC000`) match.

## Update container (HDZero Programmer)

`01 00` + three little-endian 32-bit lengths + payloads in the order **receiver (5680), FPGA, MStar (8339)**. The programmer's `fw_write_to_flash` erases 64 KiB blocks and programs 256-byte pages from address 0 for each part; its readback loop is commented out. The container adds no checksum or signature. The official GUI offers *Load Local Firmware* on the Monitor tab.

## Receiver payload encoding

Each byte is stored through a fixed **bit permutation** (from HDZero's VTX `post_script.py`); no key, no checksum. Decoding the 1.1.1 payload gives 8051 CODE starting with `LJMP 0039`; re-encoding reproduces every byte. Implementation: [`tools/monitor_receiver_decode.py`](../tools/monitor_receiver_decode.py).

## 8051 memory map (XDATA, established unless noted)

| Address | Meaning |
|---|---|
| `0D85` | **Selection** = `(band << 3) \| channel`, bands A=0, B=1, E=2, F=3, R=4, L=5 (Favorites: P=6 → `30–37`) |
| `0D86` | Input path; value 1 takes the label branch showing PAL/NTSC (inference: AV input) |
| `075C` | Detected video mode; 0 → label "ANALOG", non-zero → "HDZERO"; the scan sets 2/3 |
| `0767` / `0768` | Scan activation flags (up / down), set by a long press; `0765`, `076E` scan session flags |
| `0816–0821` | Scan list, 12 selection IDs, rewritten on every main-loop pass |
| `0822` / `082E` / `083A` | Per-entry scan results; `0853` start index |
| `0FE7–0FEC` | Band letters `ABEFRL` (rewritten on every label pass) |
| `0FED–0FF6` | Channel-label buffer (10 bytes); `0FF7` label cache, `0FF8–0FFB` busy timer, `0FFC` dot counter |
| `0FC3–0FC7` | Draw descriptor: generic pointer (lo, hi, tag), length, attribute |
| `1004–100E` | Version text `FW: V1.1.x` |
| `10DE–10E1` | 32-bit tick counter |
| `001C` / `0020`, `002C` / `002D` | Button press timestamps and states |

## CODE tables

| Address | Contents |
|---|---|
| `C6C0` | Capability flag per selection ID (48) |
| `C6F0` | RF index per selection ID (48): E1=8, F1=9, F2=10, F4=11, R1–R8=0–7, L1–L8=12–19 |
| `C720` | RF register words, 4 bytes per RF index |
| `C770`, `C7C0` | Calibration words by RF index |
| `EF08` | Second tune word per selection ID, 4 bytes (48) |
| `F1CA` … `F209` | Strings `RF AUTO`, `  AV IN`, `   PAL   `, `   NTSC  `, ` ANALOG`, ` HDZERO` |

## Key routines

| Address | Role |
|---|---|
| `0674` / `06D6` | Band step / channel step (button handlers); channel step calls save `9F29` then refresh `61D2` |
| `0725` | Secondary linear selection (no literal caller found) |
| `0880–09DF` | Button timing: debounce 5 ticks; **long press > 1000 ticks** sets scan flags at `0971` / `09BD` |
| `0C74` | Full RF tune by selection ID; register profile for RF index 8, 9 or ≥ 12 differs from the rest |
| `2DAC` | Scan tune (RF index lookup at `2DBC`, ID also used as a non-zero flag) |
| `3D7C` | `delay(n)`: busy wait, n × 2,746-iteration inner loop (plausibly milliseconds) |
| `5D19` | Second tune lookup |
| `5E31` | `delay(1000)` in the startup sequence; `5ED1` shows the version text |
| `61D2` | Receiver refresh after a selection change |
| `6D6C` | Scan service, called every main-loop pass: rewrites the list, and when a flag is set runs the **whole scan inside this call**: for each entry `0C74` + `5D19` + `delay(250)`, then picks the next entry with a result in the button's direction, writes it to `0D85`/`0760` (`7273`, `73E7`, `74E5`); fallback `7646` selects entry 0 |
| `7846` | Builds and sends a peripheral message (used by the save for device `0x50`) |
| `9D44` / `9E12` / `9F29` | Settings validate / load / save; the save writes nine fields, each after `delay(20)` |
| `B1DF` | Draw text from the descriptor at column `DPL`; writes each character back with an attribute bit, so the source must be XDATA |
| `B576` / `B717` | Label pass / label formatter (redraws when `0D85` ≠ cache `0FF7`) |
| `B7AB` / `B885` | Busy / normal label letter+digit writers; `B87F` / `B8F8` the final label draws |
| `B981` | Builds the version text |

Status bar columns (row 1): 0–9 battery/voltage, 12–18 status message, **21–29 channel label**, 40–43 icons, 46–52 `RF AUTO` / `AV IN`.

## Favorites implementation (v7 = release 1.1.2)

Decoded image 62,551 bytes, SHA-256 `0083c42f11e22154168bcac949acccf32b0df709af23a9a1e430b0ab278cbd33`. Appended at `F233` (548 bytes):

| Address | Contents |
|---|---|
| `F233` | Capability table, 56 rows (48 stock + 8 copied) |
| `F26B` | RF-index table, 56 rows |
| `F2A3` | Second tune table, 56 × 4 bytes |
| `F383` | Letters `ABEFRLP` |
| `F38A` | Underlying stock ID per P slot (8 bytes) |
| `F392` | Label routine ([source](../firmware/receiver/favorites_label.asm)): in P rewrites `Pn HDZERO` → `Pn L6 HDZ` |
| `F3F6` | Scan-list routine ([source](../firmware/receiver/favorites_scan_list.asm)): in P writes the list with P IDs |

Patched original bytes (74 bytes in 31 spans), generated by [`tools/monitor_receiver_candidate.py`](../tools/monitor_receiver_candidate.py):

| CODE offset | Original | Replacement | Purpose |
|---|---|---|---|
| `0691` | `bd0618` | `bd0718` | Band-up wraps after seventh band |
| `06A2` | `24f9` | `24f8` | Band-down range includes seventh band |
| `06A9` | `7405` | `7406` | Band-down wraps to Favorites |
| `075B` | `be3000` | `be3800` | Secondary linear-selection path accepts 56 rows |
| `0777` | `90c6c0` | `90f233` | Secondary selection uses extended capability table |
| `0951` | `74e8` | `74f4` | Long-press threshold low byte |
| `0954` | `7403` | `7401` | Long-press threshold high byte |
| `099D` | `74e8` | `74f4` | Long-press threshold low byte |
| `09A0` | `7403` | `7401` | Long-press threshold high byte |
| `0C7B` | `90c6f0` | `90f26b` | RF-index lookup uses extended table |
| `2DBC` | `90c6f0` | `90f26b` | RF-index lookup uses extended table |
| `5D3A` | `2408` | `24a3` | Second tune table base low byte |
| `5D3E` | `74ef` | `74f2` | Second tune table base high byte |
| `600C` | `24c0` | `2433` | Capability table base low byte |
| `6010` | `34c6` | `34f2` | Capability table base high byte with carry |
| `636A` | `24c0` | `2433` | Capability table base low byte |
| `636E` | `34c6` | `34f2` | Capability table base high byte with carry |
| `646A` | `24c0` | `2433` | Capability table base low byte |
| `646E` | `34c6` | `34f2` | Capability table base high byte with carry |
| `682B` | `24c0` | `2433` | Capability table base low byte |
| `682F` | `34c6` | `34f2` | Capability table base high byte with carry |
| `6D6C` | `9008167420` | `02f3f60000` | Scan list uses P IDs for Favorites when the scan starts in the P band |
| `6D98` | `7410` | `7419` | Scan list entry 9: E1 replaced by F2 |
| `6D9E` | `7418` | `742d` | Scan list entry 10: F1 replaced by L6; entry 11 INC gives L7 |
| `9D4E` | `bf3000` | `bf3800` | Loaded selection validation accepts Favorites IDs |
| `B7AB` | `900d85e0c423541f24e7f582e4340ff583e0900fedf0` | `900d85e0c423541f90f38393900fedf0000000000000` | Seven-band CODE letter lookup; P denotes Favorites |
| `B87F` | `75821502b1df` | `02f392000000` | Favorites label shows underlying channel; stock bands unchanged |
| `B885` | `900d85e0c423541f24e7f582e4340ff583e0900fedf0` | `900d85e0c423541f90f38393900fedf0000000000000` | Seven-band CODE letter lookup; P denotes Favorites |
| `B8F8` | `75821502b1df` | `02f392000000` | Favorites label shows underlying channel; stock bands unchanged |
| `B9BA` | `7430` | `7432` | Version text third digit initial value '2' |
| `B9CC` | `90100d` | `90100b` | Version text: late '1' store no longer overwrites third digit |

Version history of the receiver image: [v4](research/receiver-settings-scan-20261009.md) (P band, scan guard) → [v5](research/receiver-favorites-label-v5-20261010.md) (label) → [v6](research/receiver-favorites-scan-v6-20261010.md) (scan list, long press, version text) → [v7](research/receiver-favorites-pscan-v7-20261010.md) (scan stays in P).

## Timing (for faster switching)

See [FUT-001](tasks/fast-channel-switching.md): channel step waits ~9 × `delay(20)` in the settings save before retuning; the scan spends `delay(250)` per entry; status-module timers compare against 100/250/500 ticks (not yet traced); FPGA video lock and MStar format switching are outside the receiver code.
