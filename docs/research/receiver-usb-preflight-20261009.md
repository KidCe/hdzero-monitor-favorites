# Receiver USB preflight on the connected Monitor

Date: 2026-10-09, acquisition 17:28:17–17:28:40 UTC. Target: Monitor 1R3 / installed 1.1.1. AI assistance follows the project README disclosure.

## Observed result

The receiver-only read acquisition completed successfully through the Monitor's built-in CH341 USB bridge. Windows showed exactly one `VID_1A86 / PID_5512` device and no running HDZeroProgrammer process. The pinned native DLL and the actual USB descriptor were checked before flash routing.

Two independent full-array reads within this session each returned 1,048,576 bytes. Both are byte-identical to one another and to the previously verified original receiver backup. An additional file-only comparison confirmed this independently of the acquisition report.

Receiver-array SHA-256:

`fb35263f0bc62cc1a43889da4313af3ace756c086aad8ef69d4bc6ed515b4055`

| Observation | Result |
|---|---|
| JEDEC identity, checked twice | `EF4014`, matching the receiver backup |
| Status commands `05` / `35`, before and after | `00` / `00`, unchanged |
| BUSY / WEL under the recorded Winbond-family interpretation | Both clear |
| SFDP command `5A`, two matching reads | 256 bytes of `FF`; no valid `SFDP` signature |
| Full-array classification | Original stock image |
| Bus release and handle cleanup | Native calls completed successfully |
| Subsequent normal operation | User confirmed normal picture/menu and button response |

The SFDP response supplies no usable parameter table. It does not establish the exact chip suffix, prove that this chip lacks SFDP support, or justify programming parameters by itself. No additional probe opcode or status-write command was attempted.

Private evidence: `artifacts/device-backups/20261009-192817-receiver-preflight/`, containing `preflight.json`, `sfdp.bin` and both `5680-current-pass*.bin` files. The SFDP SHA-256 is `3d6876a0146de8576eb2395a858de1213d1b92c65b779df3a331cfd5a4584546`.

## Plans checked against the live snapshot

The file-only planner independently revalidated the previous six backup files and regenerated Favorites v4 before consuming the newly acquired receiver snapshot. A local NOR simulation of the Favorites plan completed with its expected full-array hash:

`e3f54fe342ee806812d8da887c94cef8633480e9d48fbdb4763ce603c27d0634`

That simulated plan erases the first 64 KiB block and programs 244 pages. A separate restoration plan using the second current read correctly produced **zero mutations**, because the connected Monitor already contains the original image. This no-op is not a physical restoration test. Earlier candidate-to-stock and interrupted-state restoration checks remain local simulations, as described in [the preparation report](receiver-flash-restore-preparation-20261009.md).

Private plan evidence: `artifacts/firmware-analysis/20261009-live-preimage-plans/{favorites,restore-current}/`. Neither invocation opens USB or loads the native DLL.

## Remaining boundary before programming

No Write Enable, erase, program, protection-write or security-write command was issued in this session. GPIO routing actively handed over the receiver SPI bus during reads, then released it. Normal operation after release was confirmed by the user; a cold-boot test was not performed.

Read acquisition while the installed application works does not prove access after receiver firmware failure, successful erase/program, or recovery after an interrupted write. The exact flash marking, board arbitration/power behavior and an application-independent recovery path still need evidence. The user's external CH341 can help establish a separate access route after its voltage levels and the flash wiring are verified; the Monitor-specific GPIO routing must not be reused on that external adapter.

Favorites v4 is unchanged. Real RF operation, appended CODE loading, saved-state retention, mode transitions, recording and physical restoration remain untested. A native receiver-only programming adapter is still absent. The next useful physical investigation is identifying the receiver flash variant and establishing recovery access before writing the candidate.
