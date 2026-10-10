# HDZero Monitor: eight fixed favorite channels

Date: 2026-10-08.

AI assistance: This specification and investigation note was written with substantial assistance from OpenAI Codex under the user's direction.

## User requirement

The only requested feature is an ordered list of exactly eight favorite channels, mixing existing Low, Fatshark, and Race band channels. The list may be fixed when producing the firmware. No on-device favorites editor is required. Selecting a virtual Favorites band should let the existing channel controls cycle through those eight entries without repeatedly changing physical bands.

The user confirmed this exact order: **L6, L7, R1, R2, F2, F4, R7, R8**. It is recorded in [the Favorites configuration](../../config/favorite-channels.json). The decoded offline candidate builder consumes this configuration; the stock Monitor firmware does not consume this JSON file.

| Favorite slot | Original channel |
|---|---|
| 1 | L6 |
| 2 | L7 |
| 3 | R1 |
| 4 | R2 |
| 5 | F2 |
| 6 | F4 |
| 7 | R7 |
| 8 | R8 |

## Proposed behavior

- Add a virtual `Favorites` band selectable through the existing band-selection gesture.
- In that band, the existing channel controls select slots 1 through 8, wrapping according to the existing button behavior.
- Each slot resolves to an existing physical `{band, channel}` pair before invoking the stock channel-selection path.
- Keep the selected favorite slot distinct from the effective RF channel. Otherwise switching to a mapped Low/Race/Fatshark entry could accidentally exit the Favorites mode.
- Use an English display identifier, for example `P1` through `P8`, with the original channel name where the available OSD permits. The display must distinguish a favorite slot from a stock channel.
- Preserve the stock behavior for the rest of the device, including the existing handling of channel changes during recording and HDZero/analog auto-detection.
- Use the existing settings-persistence policy where practical; include range validation for saved band/slot values. Do not add a new settings UI.

Keeping the stock bands and adding a virtual band is the preferred design. Repurposing the eight slots of an existing band could be a smaller proof of concept, but would change that band's normal meaning and requires an explicit design decision before producing a usable image.

## Why this is a smaller project

The requested change concerns channel selection, its stored state, and its display. It does not require a new general-purpose UI, DVR backend, or replacement video pipeline. The first objective is to locate one stock channel-selection path and place a favorites mapping immediately before it. Whether the patch can remain in a software component, or needs FPGA changes, is still unknown.

With application source and a working build environment, this is an ordinary bounded feature. Without source, locating and validating the patch points is the substantial part of the work. A small final patch does not imply a quick or already proven reverse-engineering process.

## What the Goggle source establishes

The Goggle has explicit mappings between existing channel identities and internal RF indices. Its [`elrs.c`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/elrs.c#L56-L114) shows how band/channel names map to frequencies and HDZero indices. This is a useful reference for expressing favorites as existing channel identities.

The [`DM6302_SetChannel`](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/driver/dm6302.c#L191-L249) path uses more than frequency words. It also applies band/channel-dependent RF register values, including special handling for Low band and some E/F entries. Therefore replacing only eight frequency constants inside a stock band is not an adequate implementation strategy. Resolving a favorite to an original supported channel and reusing the original tune sequence is the preferred seam.

The Goggle code is evidence of its own behavior, not proof that the Monitor shares its indices, register map, or control ownership. See [the source reuse assessment](hdzero-goggle-source-reuse.md).

The [Ripples source investigation](ripples-favorites-monitor-findings.md) adds a concrete reference for crossing Low and normal HDZero groups without a separate band menu. It maps a flat selection back to the original RF band/channel and fixes ELRS commands that previously changed only the local channel number. Its unchanged RF driver and checked-in receiver/FPGA images support pursuing a small selection-layer modification; they do not identify the Monitor patch point or establish binary compatibility.

The official [Monitor operation documentation](https://docs.hd-zero.com/monitor-operation) describes separate band/channel controls, HDZero support for E1, F1/F2/F4, R1-R8 and L1-L8, and RF HDZero/analog auto-switching. The favorites configuration must use supported original channel identities. An F-band slot number must not be assumed to be a supported HDZero channel simply because it is supported in analog mode.

## Focused static inspection performed

Input: official [Monitor v1.2.0 firmware](https://github.com/hd-zero/monitor/releases/tag/v1.2.0), SHA-256 `3db0a81fe43869085b5455031c34bc69f19c998606c2fedf4085eb150fac8725`.

The three component payloads were inspected offline. Exact searches for the complete eight-entry analog frequency sequences from the Goggle reference, encoded as 16-bit and 32-bit integers in either byte order, found no matches. Searches for the complete first Goggle RF PLL row in selected integer encodings also found no matches. This rules out only those exact contiguous representations; it does not establish that the data is absent or that no small patch exists. FPGA bitstreams in particular need not contain register tables as ordinary byte arrays.

The `8339` payload contains these candidate strings at offsets relative to that payload:

| Candidate | Offset |
|---|---:|
| `Channel_Switch` | 2,858,072 |
| `Channel_ID` | 2,858,087 |
| `LastChannel` | 2,858,247 |
| `Channel  F2` | 2,875,945 |
| `Channel  F4` | 2,875,957 |

Nearby strings include `VRX_OSD`, `Display_hd_sd`, and a path ending in `statevideofunc.c`. These provide useful candidates for disassembler cross-references into application-specific channel handling. SDK remnants or unused functions are possible; string presence alone does not identify the active Monitor channel-control path. It would be premature to assign all band/channel ownership to the MStar, DM5680, or FPGA.

That initial static inspection produced no executable patch, modified firmware image, flash write, hardware test or confirmed patch offset. Subsequent receiver analysis and the decoded offline candidate are described below.

## Next evidence required

The user has since confirmed installed version **1.1.1**. Offline comparison found that official 1.1.1 and 1.2.0 contain byte-identical FPGA and 8339 payloads; only the 5680 payload differs. The MStar string findings above therefore also apply to the official 1.1.1 asset. On 2026-10-09, [repeated device backups](usb-backup-20261009.md) confirmed that both identified MStar program regions match the official payload. The [ARM report](ghidra-and-emulation-20261009.md) records 22 original-code checks. The [receiver report](receiver-8051-selection-20261009.md) identifies the receiver-local selection/tuning call path and verifies all eight requested stock IDs with 221 bounded 8051 checks. The subsequent [decoded offline candidate](receiver-favorites-candidate-20261009.md) adds P1–P8 and passes 1,573 bounded checks, including RF profile and calibration-table fragments. Full peripheral behavior, loading of its appended CODE data and device operation remain untested. The current investigation order is recorded in [the implementation and recovery plan](hdzero-monitor-implementation-plan.md).

1. The active receiver button/band/channel dispatch is located and a seventh-band offline candidate exists. Extend the inventory beyond literal references and resolve full mode/scan behavior and appended CODE loading.
2. Stock IDs for the Favorites are now established. Extend the harness and follow complete tuning, calibration, display and saved-state handling; lookup-fragment tests do not establish the real RF outcome.
3. Main-array backups and the reported firmware version are now recorded. Independently establish recovery before testing a device patch.
4. Produce a version-specific patch only after identifying its input hash, expected original bytes, replacement logic, image-integrity requirements, and unaffected components.
5. Validate all eight slots on hardware, including Low/F/R transitions, both channel directions, wraparound, display identity, and power-cycle persistence. Confirm ordinary recording and signal reacquisition behave like the stock channel-change path.

If the software path cannot be established statically, passive captures of a few stock band/channel changes are the next targeted measurement. A full board schematic reconstruction is not the first requirement for this feature.
