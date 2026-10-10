# HDZero Monitor SPI flash capacities

Date: 2026-10-09. AI assistance: OpenAI Codex researched the primary datasheets and wrote this note under the maintainer's direction. This research performed no hardware operations.

The [recorded USB probe](usb-probe-flash-prefixes-20261008.json) reported the following JEDEC IDs. Its two matching 64-byte prefix reads establish a limited observation, not a full backup.

| Programmer target | Observed JEDEC ID | Density supported by Winbond's identification tables | Full main-array bytes | Valid inclusive address range |
| --- | --- | --- | ---: | --- |
| `fpga` | `EF4018` | 128 Mbit / 16 MiB | 16,777,216 | `0x000000`–`0xFFFFFF` |
| `5680` | `EF4014` | 8 Mbit / 1 MiB | 1,048,576 | `0x000000`–`0x0FFFFF` |
| `8339` | `EF4018` | 128 Mbit / 16 MiB | 16,777,216 | `0x000000`–`0xFFFFFF` |

Winbond's **W25Q128JV Revision M**, dated 2024-12-24, documents `EF` + `4018` in §8.1.1, printed p.21 (PDF p.22); §1–2, printed p.4 (PDF p.5), gives the 128 Mbit density. The full range appears in §7.1.8, printed p.18 (PDF p.19). [Official datasheet](https://www.winbond.com/resource-files/W25Q128JV%20RevM%2012242024%20Plus.pdf#page=22).

Winbond's **W25Q80DV Preliminary Revision N**, dated 2026-04-24, documents `EF` + `4014` in §8.1, p.17; §1–2, p.5, explicitly gives 1,048,576 bytes. Its protection table, p.15, confirms the full range. PDF page numbers equal printed page numbers in this document. [Official datasheet](https://www.winbond.com/resource-files/W25Q80DV_revN_04242026%20Plus.pdf#page=17).

These are matching family references, not proof of the chips' exact suffix, package, generation, or speed grade. In particular, the JV identification table groups several ordering variants under `4018`.

One complete main-array pass across all three targets is therefore **34,603,008 bytes / 33 MiB**; two independent passes total 66 MiB. Official update payload lengths are smaller and must not determine backup length. Unexamined bytes beyond the update payload may contain other data and should be preserved.

## Read-address bounds

Standard SPI `03h` uses three address bytes, most significant byte first, followed immediately by read clocks; it requires no dummy byte. The address increments while chip select remains low. Raising chip select ends the command. See JV §8.2.6, printed p.28 (PDF p.29), and DV “Read Data (03h)”, p.25. [JV read command](https://www.winbond.com/resource-files/W25Q128JV%20RevM%2012242024%20Plus.pdf#page=29), [DV read command](https://www.winbond.com/resource-files/W25Q80DV_revN_04242026%20Plus.pdf#page=25).

Every chunk must satisfy `offset >= 0`, `length > 0`, and `offset + length <= capacity`. A 24-bit command does not give the 1 MiB chip a 16 MiB array. The 16 MiB exclusive end, `0x1000000`, is a stopping condition and cannot be transmitted as a three-byte start address. No four-byte address mode is needed for either density. The documented read sequence requires no Write Enable, status-register write, program, or erase command; adapter selection and cleanup remain separate operations to audit.

A main-array `03h` dump does not include separate status, security, unique-ID, or SFDP registers. Optional SFDP confirmation uses the separate `5Ah` command, three address bytes and eight dummy clocks: JV §8.2.28, printed p.51 (PDF p.52), and DV “Read SFDP Register (5Ah)”, p.49. [JV SFDP](https://www.winbond.com/resource-files/W25Q128JV%20RevM%2012242024%20Plus.pdf#page=52), [DV SFDP](https://www.winbond.com/resource-files/W25Q80DV_revN_04242026%20Plus.pdf#page=49). No SFDP access was performed for this note.

## Reproducible source snapshots

The PDFs were downloaded from Winbond's public documentation links and extracted with `pypdf`. Local PDF and UTF-8 text extracts were kept in a private temporary review cache (not published):

| Snapshot | PDF SHA-256 |
| --- | --- |
| `W25Q128JV-RevM.pdf` / `.txt` | `b51bb4303e17a17750c9cbcafc9a776dea842a8971d7cdd5edc70ff738efb1fe` |
| `W25Q80DV-RevN.pdf` / `.txt` | `a8a4f7188bdaeb4bc4ee5ab532083c2f34d2bf717160415bd8212d889b97189e` |
