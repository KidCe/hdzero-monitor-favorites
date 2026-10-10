# Ripples channel selection: implications for Monitor Favorites

Research date: 2026-10-08. Static source inspection only.

AI assistance: This research note was researched and written with substantial assistance from OpenAI Codex under the user's direction.

## Assessment

Ripples provides a useful implementation reference for a Favorites selector that crosses existing HDZero channel groups. It does not provide a Monitor firmware target or a confirmed patch location in the Monitor binary. The relevant changes are application-level channel routing and state handling. The RF tuning implementation and checked-in receiver/FPGA images remain identical to the inspected official baseline; see [the RF and hardware boundary comparison](ripples-lowband-monitor-reuse.md).

Inspected main commit: [`6528ad1f22fa629c2149bd058102de55c247637f`](https://github.com/LVTY-AI/hdzero-goggle/tree/6528ad1f22fa629c2149bd058102de55c247637f). The relevant mapping, ELRS dispatch, scan table, and lightweight retune behavior were also checked in release source [`ripples-v1.2.1`, commit `ffbf69ed03bdaf52b9de8d8b4522a11fa77c8715`](https://github.com/LVTY-AI/hdzero-goggle/tree/ffbf69ed03bdaf52b9de8d8b4522a11fa77c8715). This is source verification, not a test of installed release binaries.

## Concrete changes worth reusing

### One selection space over existing physical channel identities

[`input_device.c:84-105`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/input_device.c#L84-L105) defines a flat 20-entry channel space: R1..R8, E1, F1, F2, F4, followed by L1..L8. It converts the selection back to the original RF band and local channel. [`The dial commit path`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/input_device.c#L426-L486) checks both band and channel, persists both, and invokes the existing retune routine. Lowband no longer needs a separate menu action.

The equivalent Favorites design is an eight-entry ordered view over supported identities. The virtual Favorites slot must remain separate from the effective RF band/channel so a mapped Lowband selection does not exit Favorites mode. This is a design inference, not an existing Monitor implementation.

### The ELRS Lowband fix preserves the band

In the [official baseline](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/elrs.c#L116-L129), the HDZero channel helper updates only the channel. Its [MSP channel/frequency handlers](https://github.com/hd-zero/hdzero-goggle/blob/adb901d9493a3f3d0ca3b052eaa693e51046dd3a/src/core/elrs.c#L299-L338) map both R and L requests to local channel numbers without setting the requested band. A request for L6 while Raceband is selected can therefore leave the receiver in the Race group. Changing between R6 and L6 can also be mistaken for no change because the local channel number is identical.

Ripples [resolves the request to a scan-table entry](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/elrs.c#L387-L395), then calls [`change_channel_hdzero(band, channel)`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/elrs.c#L170-L195). The helper checks and updates both values. The same approach handles frequency requests. This explains a software restriction being removed without new Lowband RF code.

### Lightweight retuning with format-dependent recovery

The [same-protocol Auto Detect path](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/input_device.c#L150-L193) preserves the current receiver setup where practical and calls [`hdzero_switch_channel`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/app_state.c#L274-L287). That routine sets the RF channel and refreshes receiver validity flags. A lightweight retune routine already existed in the official source; Ripples improves the surrounding selection/detection flow rather than introducing a new RF command.

The author limits the reported instant-switch behavior to matching bandwidth, camera, resolution, and frame rate; different settings can require a 1-2 second relock. [Release note](https://github.com/LVTY-AI/hdzero-goggle/releases/tag/ripples-v1.1.2). This timing is an author report, not a measured Monitor result. A Favorites list changes navigation; it does not guarantee instant signal acquisition between different transmitters.

## Exact requested Favorites in the Goggle reference

The new [`scan_freq_table`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/scan_core.c#L60-L130) contains every requested HDZero channel. RF band and channel here are the Goggle driver's values, not confirmed Monitor binary identifiers. Channels are zero-based in the RF call; `scan.channel` stores a one-based local value.

| Slot | Channel | HDZero MHz | RF band | RF channel | Flat index |
|---|---|---:|---:|---:|---:|
| 1 | L6 | 5547 | 1 | 5 | 17 |
| 2 | L7 | 5584 | 1 | 6 | 18 |
| 3 | R1 | 5658 | 0 | 0 | 0 |
| 4 | R2 | 5695 | 0 | 1 | 1 |
| 5 | F2 | 5760 | 0 | 10 | 10 |
| 6 | F4 | 5800 | 0 | 11 | 11 |
| 7 | R7 | 5880 | 0 | 6 | 6 |
| 8 | R8 | 5917 | 0 | 7 | 7 |

Internally F2/F4 are part of the normal HDZero RF group; the user-facing R/F/L labels are not three equivalent RF band numbers. Do not transplant these numbers into the Monitor until its interface is identified. Also preserve protocol identity: the unified table explicitly distinguishes HDZero Low frequencies from analog Low frequencies, which differ. A bare label such as L6 is insufficient when crossing protocols.

## Remaining Monitor work

The smallest plausible implementation remains `favorite slot -> original Monitor channel identity -> stock tune path`. We need to identify the Monitor's active button/channel dispatch, validate its channel identifiers, and follow display updates and saved settings through that path. The candidate channel-related strings already found in the Monitor's 8339 payload remain useful starting points; their ownership is unproven. See [the focused Monitor specification and binary findings](hdzero-monitor-favorite-channels.md).

For this feature, the first target is a bounded channel-selection modification. A full replacement DVR/UI, a complete schematic reconstruction, or reverse engineering the HDZero RF decoding protocol is not the first requirement. Whether the required Monitor selection logic is accessible in software or partly owned by the FPGA remains unresolved. No patch image or device validation has been produced.
