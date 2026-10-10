# Ripples Lowband and RF changes: relevance to Monitor Favorites

Research date: 2026-10-08. Static source and Git object comparison only; no device interaction, firmware patching, or physical validation.

AI assistance: This research note was researched and written with substantial assistance from OpenAI Codex under the user's direction.

## Snapshots and result

Inspected [LVTY-AI/hdzero-goggle](https://github.com/LVTY-AI/hdzero-goggle), default branch `main`, pinned to commit [`6528ad1f22fa629c2149bd058102de55c247637f`](https://github.com/LVTY-AI/hdzero-goggle/tree/6528ad1f22fa629c2149bd058102de55c247637f), committed 2026-10-08. Compared against official [`hd-zero/hdzero-goggle` at `adb901d9493a3f3d0ca3b052eaa693e51046dd3a`](https://github.com/hd-zero/hdzero-goggle/tree/adb901d9493a3f3d0ca3b052eaa693e51046dd3a). The `ripples-v1.2.1` source tag, commit [`ffbf69ed03bdaf52b9de8d8b4522a11fa77c8715`](https://github.com/LVTY-AI/hdzero-goggle/tree/ffbf69ed03bdaf52b9de8d8b4522a11fa77c8715), was also checked for RF source and HAL blobs.

**The inspected Ripples source does not add Lowband RF tuning support or replace receiver/FPGA firmware. Its RF tuning driver and checked-in hardware images are byte-identical to the official baseline.** This supports interpreting easier Lowband selection as application behavior and routing, rather than a new RF implementation. It does not establish that a Monitor runs the same receiver firmware, FPGA image, or control protocol.

## Exact comparison evidence

GitHub recursive trees were complete (`truncated=false`). Matching Git blob IDs identify identical file bytes; matching subtree IDs cover identical descendant contents. The table records repository objects, not a comparison of installed firmware or every downloadable release artifact. [Official tree](https://api.github.com/repos/hd-zero/hdzero-goggle/git/trees/adb901d9493a3f3d0ca3b052eaa693e51046dd3a?recursive=1), [Ripples main tree](https://api.github.com/repos/LVTY-AI/hdzero-goggle/git/trees/6528ad1f22fa629c2149bd058102de55c247637f?recursive=1), [Ripples 1.2.1 tree](https://api.github.com/repos/LVTY-AI/hdzero-goggle/git/trees/ffbf69ed03bdaf52b9de8d8b4522a11fa77c8715?recursive=1).

| Object | Official and Ripples Git object ID | Finding |
|---|---|---|
| `src/driver/dm6302.c` | `4013e531f3c8eda1bd333408a442ed71e244e00e` | Identical RF source, 64,234 bytes; also identical in the 1.2.1 tag. |
| `src/driver/i2c.h` | `ead6600257b7b66fd2819e5dc6955a53e81632b6` | Identical device addresses and macros; also identical in the tag. |
| `mkapp/hal` subtree | `ee521c63942467f64303480f4927908f50b47f63` | Entire main HAL directory matches official, including binaries and version files. |
| All three target RX images | `c642ecfefd50d823e9f346521389786bb93e3953` | Same 7,805-byte receiver image for Goggle, BoxPro and Goggle 2 in main and the tag. |
| Goggle VA image | `504f6014db5ba473e56a55839c5130ca4379faa4` | Identical, 2,322,718 bytes; same in the tag. |
| BoxPro VA image | `ad2c208da11c7fb24836958acff679bd4b52de3f` | Identical, 2,322,718 bytes; same in the tag. |
| Goggle 2 VA image | `09ad4d67809221111c9c610729575706098549fb` | Identical, 5,143,040 bytes; same in the tag. |
| `lib/softwinner` subtree | `4d8cfa6538fcf8b0ebff91a9b05ea5a29ed02426` | Same vendor interface headers and prebuilt multimedia libraries. |
| `lib/linux` subtree | `ada34f93c9cf5b4f21ce7f7cb6fe2a718e2d4d11` | Same Linux interface headers. |
| `mkapp/app/ko` subtree | `6bc651b6bef0c5c5b50bcd1596b04b11ce4b10e6` | Same prebuilt kernel modules. |

The changed drivers do not reveal a new receiver protocol:

- [`dm5680.c`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/driver/dm5680.c#L237-L269): changes add explicit platform includes and host-emulator initialization/thread handling. The command framing and command bodies remain unchanged from the official snapshot.
- [`i2c.c`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/driver/i2c.c#L1-L5): the only difference is a comment explaining the emulator's replacement bus driver.
- [`uart.c`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/driver/uart.c#L13-L20): adds a missing baud constant definition for macOS/BSD compilation; it does not change the Goggle receiver's UART configuration.
- In [`hardware-goggle.c`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/driver/hardware-goggle.c), reviewed changes concern display cache invalidation, analog standard handling/retiming, HDMI reacquisition, playback, and OSD readback. [`HDZero_open`, `HDZero_Close` and RF/video detection](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/driver/hardware-goggle.c#L736-L823) retain the official RF logic.

## What the radio still does

The unchanged [`dm6302.c`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/driver/dm6302.c#L98-L249) contains 20 tuning entries covering R1..R8, E1, F1/F2/F4 and L1..L8. All requested favorites `L6,L7,R1,R2,F2,F4,R7,R8` already fall within those entries. Lowband remains a distinct original tuning profile; selecting it adds a table offset and changes several RF register values. The fork has not turned arbitrary F-band frequencies into supported HDZero channels, nor reduced this to a simple MHz table.

`SPI_Write()` still sends RF register operations through the Goggle FPGA's I2C bridge. Bandwidth changes still close and reopen the receiver, run RF initialization, and set the baseband bandwidth; camera-mode changes still retime the display. Consequently, faster same-format channel transitions do not imply universally instantaneous transitions between different video formats or bandwidths. [Bridge implementation](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/driver/dm6302.c#L20-L96), [bandwidth and camera-mode handling](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/driver/hardware-goggle.c#L736-L823).

## Source boundaries and Monitor reuse

The build still targets Goggle, BoxPro and Goggle 2. It supplies no Monitor target, MStar/8339 Monitor SDK, full Linux BSP rebuild, FPGA HDL, or real receiver-MCU rebuild path in the inspected tree. RX/VA binaries are [copied into the package](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/mkapp/mkapp_ota.sh#L71-L113). Vendor libraries remain [prebuilt imports](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/lib/softwinner/CMakeLists.txt#L17-L86).

The new [`src/platform`](https://github.com/LVTY-AI/hdzero-goggle/tree/6528ad1f22fa629c2149bd058102de55c247637f/src/platform) directory provides desktop operating-system compatibility. [`dm5680_emu.c`](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/emulator/dm5680_emu.c) is a host mock answering simulated UART commands, not source firmware for the physical DM5680. The [emulator build](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/CMakeLists.txt#L119-L136) swaps actual bus drivers for mocks; emulator behavior cannot verify Monitor RF operation.

Ripples is useful as a reference for removing application-level selection restrictions while preserving original tuning identities. It does not remove the Monitor-specific work of identifying the active button/channel-dispatch code and connecting it to the existing tuning path. In particular, unchanged Goggle FPGA/RX blobs cannot be transplanted into the Monitor merely because some chips share names. An eight-slot Favorites mapping remains a plausible small modification, but no working Monitor patch is demonstrated by this repository.
