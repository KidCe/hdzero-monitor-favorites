# Monitor receiver decode and selection path

Date: 2026-10-09. Target: Monitor PCB 1R3, installed firmware 1.1.1.

## Result

Follow-up: [the decoded Favorites candidate](receiver-favorites-candidate-20261009.md) now implements an offline seven-band experiment with 1,573 passing candidate checks. This report records the earlier stock-code investigation; its statements about producing no modified image describe that stage.

The DM5680 payload from the repeated device backup decodes into coherent 8051 code using the inverse of the byte-bit permutation published in the [official VTX build script](https://github.com/hd-zero/hdzero-vtx/blob/ad396315680f64ad5797fb0fe53bbd73e9f448ba/script/post_script.py). The transformation is a bit permutation with no key. Encoding the decoded bytes again reproduces every original payload byte.

The receiver code owns a button-polling path, six-band/eight-channel selection routines, saved-selection validation, channel-label generation, and calls into two tuning paths. **221 bounded original-code checks passed in Ghidra's 8051 p-code emulator.** This establishes a much more relevant patch target than the MStar settings and DVR routines found earlier.

No USB access, hardware commands, modified firmware, update container or flash write was involved. This is a function/fragment test environment, not a complete Monitor or RF simulator. The full peripheral transactions, actual tuned frequency, display rendering, recording, power-cycle persistence and recovery remain untested.

## Reproducible input

| Item | Value |
|---|---|
| Input | `artifacts/device-backups/20261009-usb-01/5680-pass1.bin`, 1 MiB |
| Input SHA-256 | `fb35263f0bc62cc1a43889da4313af3ace756c086aad8ef69d4bc6ed515b4055` |
| Payload length | 62,003 bytes, matching the official 1.1.1 component |
| Encoded payload SHA-256 | `5d9b0f661eab91ffebf1bc978941e783b0c7ecf87c13aa768b4c1922fcb8877c` |
| Decoded SHA-256 | `ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652` |
| Ghidra language | `8051:BE:16:default`, CODE base 0 |
| Local project | `artifacts/ghidra/Monitor-DM5680-1R3.gpr` |

For decoded bits 0 through 7, the published encoded bit positions are `(7, 2, 5, 1, 3, 4, 0, 6)`. This is not a file-byte reordering. The seven vector locations `0000, 0003, 000B, 0013, 001B, 0023, 0033` become standard `LJMP` instructions targeting `0039, 8BBD, 8B36, 8BBE, 8BBC, 8BBF, 8BF7`. Startup at `0039` initializes the stack, copies initialized data and reaches the main loop at `8C2F`.

Ghidra found 183 candidate functions. Decompiler prototypes and inferred variable names are not recovered source declarations; assembly was checked for the selection and lookup paths. Generic SFR labels do not establish the physical PCB routing of the buttons or buses.

## Selection and tuning path

All following addresses belong to the decoded receiver, not the ARM application.

| Address | Observation |
|---|---|
| CODE `8C2F` | Main loop calls button polling `07B9` and service routine `6840`. |
| CODE `07B9` | Reads P1.0, P1.1, P0.6 and P0.7; edge/timing state selects calls to band step `0674` or channel step `06D6`. Button-to-pad assignment is not physically measured. |
| EXTMEM `0D85` | Packed selection: `(band_index << 3) | channel_index`, with channel index 0–7. |
| CODE `0674` | DPL zero decrements band, nonzero increments; stock wraparound covers indices 0–5. It preserves the low three channel bits. |
| CODE `06D6` | DPL zero decrements channel, nonzero increments; masks with 7 and preserves the band bits. |
| CODE `9D44` | Selection values at or above `30` hex are reset to `20` hex, corresponding to R1. Other settings are validated later in the function. |
| CODE `9F29` | Calls validation, then transfers settings through the register-write path at `7846` with device argument `50` hex. Reads at `9E12` use the corresponding read path. Actual nonvolatile-device identity and successful persistence are not established by emulation. |
| CODE `6840` → `67E7` | When the relevant input mode is active, no configuration operation is in progress, and `0D85` differs from cached selection `0760`, calls `0C74` and `5D19` with the selection in DPL. Updates cache and selects digital/analog handling from a CODE table. |
| CODE `0C74` | Reads `C6F0[selection]`; uses that RF index to load a four-byte register value from `C720 + 4 * index`, then performs a larger register sequence. |
| CODE `5D19` | Performs an initial transaction, reads a four-byte word at `EF08 + 4 * selection`, and forwards it through `A665`. The lookup fragment alone is tested; the preceding/following transactions are not replaced with success stubs. |
| CODE `B576`, fragment `B885` | Constructs letters `A B E F R L` and builds a two-character label from band index and channel index. |
| CODE `C6C0` | Forty-eight bytes select digital-capable versus analog handling. All eight requested Favorites have value 1. |

Additional consumers already seen statically: `5F26` retunes during receiver mode transitions, `6366` reads the digital-capability row before querying status, and `2DAC` reads the RF-index table during a larger initialization sequence. `6D6C` builds an internal twelve-entry candidate list (R1–R8, E1, F1, F2, F4), changes `0D85`, and directly invokes both tune paths. That routine's full purpose and trigger behavior remain to be confirmed. These paths show why translating only the main loop's tune call would be incomplete.

Static control flow now connects buttons, selection state and tuning calls. It does not prove the electrical protocol or real RF outcome. In particular, the earlier MStar UART parser is not needed to explain this receiver-local selection path.

## Favorites identities

Four-byte words below are literal bytes in image order, not MHz values or instructions to write hardware registers.

| Slot | Channel | Stock ID (hex) | RF index | RF word bytes | Second tune word bytes |
|---:|---|---|---:|---|---|
| 1 | L6 | `2D` | 17 | `4C 37 00 00` | `86 27 00 00` |
| 2 | L7 | `2E` | 18 | `AA 37 00 00` | `98 27 00 00` |
| 3 | R1 | `20` | 0 | `41 37 00 00` | `1D 28 00 00` |
| 4 | R2 | `21` | 1 | `9D 37 00 00` | `90 28 00 00` |
| 5 | F2 | `19` | 10 | `40 38 00 00` | `10 29 00 00` |
| 6 | F4 | `1B` | 11 | `A4 38 00 00` | `84 29 00 00` |
| 7 | R7 | `26` | 6 | `6C 39 00 00` | `0C 2A 00 00` |
| 8 | R8 | `27` | 7 | `C8 39 00 00` | `1F 2A 00 00` |

`tools/monitor_receiver_map.py` validates the decoded-image hash and extracts these rows from `config/favorite-channels.json`. The generated local `favorites-map.json` is analysis evidence, not a patch.

## What the emulator actually checks

| Group | Checks | Boundary |
|---|---:|---|
| Original band/channel step | 192 | Both directions for all 48 valid selections. Stop at `06C0` / `070F`, before calling `9F29`. |
| Uninitialized selection guard | 1 | Missing `EXTMEM:0D85` aborts instead of fabricating a value. |
| Band-letter initialization | 1 | Original instructions initialize six letters; stop before other OSD logic. |
| Requested Favorites lookups and labels | 24 | Eight RF-index prefixes, eight second-table fragments, eight label fragments. Each runs independently with explicit input fixtures. |
| Invalid persisted selection prefix | 3 | `30`, `37`, `FF` hex reset to R1; stop before validating unrelated settings. |
| Total | 221 | No complete hardware routine or patched image is executed. |

The harness allows only explicit EXTMEM bytes, the original CODE image and CPU state. Uninitialized memory, unknown address spaces, CODE writes and execution outside each bounded fragment stop the test. Each execution has a 200-instruction budget. No external hardware APIs are stubbed.

Ghidra's Sleigh model represents R0–R7 and directly addressed bank RAM separately. A narrow alias bridge maps INTMEM 0–7 to the bank-zero CPU registers in both directions. PSW bank changes are rejected. This is a CPU-state alias correction, not a peripheral model. Other banks, stack calls, interrupts, ports and peripheral timing are outside this harness. The deliberate missing-RAM guard logs one expected emulation failure; the script still succeeds only if its exact failure and all other checks pass. The runner rejects script failures and incomplete reports.

The independent Python host suite also passes 13 tests, including bit-position examples, full 256-byte bijection/round-trip checks, wrong-image rejection and invalid configuration rejection. These counts are separate from the 221 original-code checks.

## Reproduce

```powershell
$py = 'python'

# Use a fresh output directory; the full-array backup must remain unchanged.
& $py tools/monitor_receiver_decode.py `
  --input artifacts/device-backups/20261009-usb-01/5680-pass1.bin `
  --output-dir artifacts/firmware-analysis/new-receiver-run

& tools/Invoke-ReceiverGhidra.ps1 `
  -Image artifacts/firmware-analysis/new-receiver-run/receiver-8051.bin -Refresh

& $py tools/monitor_receiver_map.py `
  --image artifacts/firmware-analysis/new-receiver-run/receiver-8051.bin `
  --report artifacts/firmware-analysis/new-receiver-run/favorites-map.json

& $py -m unittest discover -s tests -v
```

For a new Ghidra project, omit `-Refresh` and choose an unused `-ProjectName`. Both import and refresh runner paths were exercised successfully. Latest clean-import result: `artifacts/firmware-analysis/receiver-run-20261009-164819-598/selection-tests.json`; all 221 checks passed again. Backups, decoded firmware, decompilations and Ghidra databases remain excluded from Git.

## Patch implications and next work

The receiver can represent a seventh band numerically, but the stock code cannot use it safely: the band step wraps at six, validation rejects values `30` and above, both tune paths index fixed-size tables, digital-mode logic reads another 48-row table, and OSD has only six letters. Raising one limit is insufficient.

Continue offline with a complete inventory of selection/table consumers, including calibration, mode switching, saved state and OSD. A logical Favorites slot must consistently resolve to its stock effective RF identity. Two candidate designs are a separate logical Favorites state translated before every relevant stock consumer, or extended verified selection tables with Favorites rows. Neither design has been implemented or selected as safe yet. Existing bands should remain available, as requested.

Once those consumers are accounted for, build a version-specific offline candidate with an exact byte-change manifest and compare its outputs against the stock traces for all slots, directions, wraparound and invalid saved states. Any added code/data space, branch targets and integrity fields need evidence. Do not assume zero/FF padding is available storage. Real hardware testing then requires independently established recovery and measured tuning, reacquisition, recording and persistence.

Waiting for Monitor source is no longer necessary to continue this investigation. Source would still reduce patch complexity and uncertainty. The Monitor can remain disconnected throughout the next offline steps.
