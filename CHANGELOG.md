# Changelog

Release versions follow the receiver's version text. Internal build numbers (v4–v7) refer to the research notes. All builds are based on official HDZero Monitor firmware 1.1.1.

## 1.1.2-favorites (2026-10-10) — internal build v7

First public release.

- **Favorites band `P`**: P1–P8 = L6, L7, R1, R2, F2, F4, R7, R8, after the six stock bands. *(v4)*
- **Status label** shows slot and real channel: `P1 L6 HDZ` / `P1 L6 ANA` / `P1 L6 ...`; stock bands unchanged. *(v5)*
- **Scan list** `R1–R8, F2, L6, L7, F4` (E1/F1 replaced by L6/L7); long press starts the stock scan in every band again. *(v6)*
- **Long press to scan halved** (1000 → 500 ticks, ~3 s → ~1.5 s). *(v6)*
- **Version text** `FW: V1.1.2`. *(v6)*
- **Scan started in P stays in P**: favorites are scanned as P slots, starting at the current slot. *(v7)*

Receiver image: decoded SHA-256 `0083c42f11e22154168bcac949acccf32b0df709af23a9a1e430b0ab278cbd33` (62,551 bytes).

## Internal history (development device only)

| Build | Date (UTC) | Change | Device result |
|---|---|---|---|
| v4 | 2026-10-09 20:17 | P band, long-press scan suppressed in P | Accepted; restore to stock tested 20:27, re-applied 20:42 |
| v5 | 2026-10-09 23:19 | Label `P1 L6 HDZ` | Accepted |
| v6 | 2026-10-09 23:51 | Scan list with L6/L7, faster long press, `V1.1.2`, P guard removed | Accepted |
| v7 | 2026-10-10 00:08 | Scan from P stays in P | Accepted |

Earlier offline-only candidates (v2, v3) were never written to a device.
