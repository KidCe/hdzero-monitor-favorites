# Receiver flash marking identification

Date: 2026-10-09. Prepared with substantial OpenAI Codex assistance, covered by the [project disclosure](../../README.md#ai-assistance-disclosure). Codex performed no hardware operation for this note; subsequent user measurements are attributed below.

## Conclusion

The sharp user photographs strongly support **Winbond W25Q80DVUXIE**, an 8-Mbit / 1-MiB SPI NOR flash in **USON-8, nominal 2 × 3 mm**. This is an evidence-based identification candidate. The user subsequently confirmed pin 4 as ground and reported 3.3 V at pin 8; dimensions and SPI wiring remain unmeasured.

The photographed package left of DM5680 reads approximately **`8N80A` / `0E418G`**, preceded by a small circular emblem. The decisive match is the two-line marking scheme, rather than treating `8N80A` as a full part number:

| Evidence | Manufacturer reference | Assessment |
|---|---|---|
| Fixed `8N` and `0E` prefixes; five/six-character lines | `8Nyww` / `0Exxxx` identifies W25Q80DVUXIE | Strong match |
| Rectangular body with four edge contacts at each end | USON-8, nominal 2 × 3 mm, 0.5-mm contact pitch | Visually consistent; dimensions unmeasured |
| Receiver USB JEDEC `EF4014` and matching 1-MiB arrays | W25Q80DV documents that ID and capacity | Independent corroboration; USB target has not been physically continuity-mapped to this package |

These references were visually checked on **Winbond Rev N pp.6, 64 and 67**. The same marking scheme appears in **manufacturer-authored Rev F p.70 (2015)**, so it is not a recent marking change. [Winbond Rev N](https://www.winbond.com/resource-files/W25Q80DV_revN_04242026%20Plus.pdf), [Rev F on TI's document mirror](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/166/w25q80dv_5F00_revf_5F00_02112015.pdf#page=70), [local USB evidence](receiver-usb-preflight-20261009.md).

## Alternatives checked

Other manufacturer-authored marking tables use distinct prefixes:

- W25Q80BV USON automotive variants: `8DxxA/B/J` / `0Gxxxx`, not the observed scheme. [Official Winbond Rev C1 pp.65–66](https://www.winbond.com/upload/technical-support/f0f72951-b845-42ea-9010-faaeab26872f.pdf#page=65).
- W25Q80JVUXIQ: `*8Pyww` / `0Qxxxx`. [Winbond-authored datasheet, LCSC mirror, p.69](https://datasheet.lcsc.com/lcsc/2411121027_Winbond-W25Q80JVZPIQ-TR_C19420203.pdf#page=69).
- W25Q80RVXHJQ: `V4ywH` / `JQxxxx`, in XSON-8. [Winbond Rev E, DigiKey mirror, p.80](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/8919/W25Q80RV.pdf#page=80).

No primary marking evidence was found supporting a different manufacturer for the photographed code. An ID alone cannot establish authenticity or exclude a compatible replacement.

## Unresolved details and conditional pin map

Winbond defines `y` as year, `ww` as week and `xxxx` as lot ID. The apparent final `0A` is not a clear decimal week; neither its character reading nor encoding is resolved. **Do not infer 2018/week 10, a revision A, or a manufacturing date.** The emblem was not independently authenticated as a manufacturer logo.

For this candidate, the manufacturer specifies 2.7–3.6 V operation. From above, after establishing the physical pin-1 index: **1 /CS, 2 DO/IO1, 3 /WP/IO2, 4 GND, 5 DI/IO0, 6 CLK, 7 /HOLD/IO3, 8 VCC**. The candidate's reference pinout is not measured Monitor wiring. [Winbond Rev N pp.5–7](https://www.winbond.com/resource-files/W25Q80DV_revN_04242026%20Plus.pdf#page=6).

The subsequently supplied user-marked image highlights a feature inside the lower-left portion of the body and the lower-left silkscreen corner. Together they suggest pin 1 at the lower-left edge contact in the displayed photo. This is an orientation hypothesis, requiring an electrical ground check before using it for connections.

If that hypothesis is correct, the upper row, left to right, is `8 VCC / 7 HOLD / 6 CLK / 5 DI`; the lower row is `1 CS / 2 DO / 3 WP / 4 GND`. The next measurement is resistance from the **lower-right edge contact** to established board ground (for example the Monitor's battery-input negative terminal), with **battery and Monitor USB removed**, external adapter disconnected and residual voltage checked to be negligible before selecting resistance mode. Record the reading and compare with shorted meter leads. Do not treat a continuity beep alone as proof or infer VCC from this measurement.

The USON reference has 0.5-mm contact pitch and a 2 × 3-mm body. If measured dimensions confirm it, an ordinary SOIC-8 clip intended for 1.27-mm pitch will not fit. Appropriate microprobes or fine temporary wires require a separate connection plan. [Winbond Rev N p.64](https://www.winbond.com/resource-files/W25Q80DV_revN_04242026%20Plus.pdf#page=64).

## User ground and supply confirmations

The user subsequently reported: **"ja pin 4 ist gnd"**. This confirms the expected lower-right ground contact according to the user's check and supports the proposed orientation. No numerical resistance, instrument trace or independent Codex measurement was supplied. It does not establish the supply voltage, every SPI connection or recovery access.

The measurement instruction supplied before the result was: with this orientation, the candidate's **pin 8 / VCC is the upper-left contact in the supplied photographs**, on the row nearest RXD/TXD. Measure DC voltage from that contact to the confirmed board ground with the Monitor powered through its normal battery input. Keep built-in USB and the external CH341 disconnected. Set the meter to DC voltage, attach the ground lead while power is off, then use an insulated fine probe at pin 8 without bridging adjacent contacts. The identified candidate's documented operating range is 2.7–3.6 V; approximately 3.3 V was the expectation before measurement. Do not supply programmer power or connect SPI lines during this measurement. [Winbond Rev N pp.5–6 and 54](https://www.winbond.com/resource-files/W25Q80DV_revN_04242026%20Plus.pdf#page=54).

After the supply measurement instruction above, the user reported **"ja 3,3v"**. This records a user-reported 3.3 V supply at pin 8 relative to pin 4, consistent with the candidate's operating range. No instrument trace, voltage tolerance or transient measurement was supplied. This does not establish the external adapter's SPI output levels or a safe in-circuit power arrangement.

The recorded all-FF SFDP response remains unexplained and does not override the marking evidence or prove absent SFDP. Electrical checks and external-read recovery verification remain as described in the [external-access research](external-ch341-recovery-references-20261009.md).

Source provenance: Rev N was inspected from the previously cached official PDF, SHA-256 `a8a4f7188bdaeb4bc4ee5ab532083c2f34d2bf717160415bd8212d889b97189e`; its relevant pages were rendered and inspected. Mirrors above contain manufacturer-authored documents, not secondary interpretations. Observations use the two sharp user images with filenames ending `c8a30e47-696c-4915-9a3f-c08fc810f2f7.png` and `04e0de98-2403-4b93-aa1e-09b4319135ad.png`.

All three original user-supplied images, including the subsequent marked-corner image ending `36786b45-e106-45aa-9ab2-092138f4d1f5.png`, were preserved byte-for-byte with SHA-256 records in private `artifacts/firmware-analysis/20261009-flash-marking-photos/`. No component identification or marking interpretation is based on the earlier generated annotation image. Ground continuity and 3.3 V board supply are user-reported; actual adapter signal levels and independent recovery remain unmeasured/unvalidated.
