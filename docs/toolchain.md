# Toolchain

Windows, 64-bit Python 3.11+. Hardware tools need the WCH CH341 driver DLL (`CH341DLLA64.DLL`, pinned by SHA-256) and exactly one CH341 device (`1A86:5512`) connected; close the HDZero Programmer first. Many tools pin SHA-256 hashes of the official 1.1.1 firmware and of the **development Monitor's backups**; on another device, make your own backups and adjust the pins deliberately. Firmware files, backups and generated sources live in the git-ignored `artifacts/` directory.

> These are research tools. Every write-capable path defaults to a dry run and needs an explicit hash confirmation. Read the code before pointing it at your Monitor.

## Hardware access (Monitor USB)

| Tool | Purpose |
|---|---|
| `monitor_usb_probe.py` | Descriptor check, flash IDs, 64-byte prefixes. No write commands. `--identify-only` does not touch the SPI routing. |
| `monitor_usb_backup.py` | Reads all three flashes twice, compares byte-for-byte, writes `manifest.json`. No write commands. |
| `monitor_usb_receiver_preflight.py` | Read-only receiver session: JEDEC, status registers, SFDP, two full reads. |
| `install_favorites.py` | **Installer for other users.** Needs only the official 1.1.1 file and the release receiver image (no device backups). Read-only compatibility check of all three flashes (IDs, FPGA/MStar first 64 KiB vs. official), version policy for the installed receiver (official 1.1.1 / known Favorites builds; 1.2.0 only with `--allow-replace-1.2.0`; unknown refused; `--recover-interrupted` for an interrupted write), dry run by default, `--execute` with typed confirmation, logs and receiver backup in `install-logs/`. Uses the same session code as the research writer. |
| `monitor_usb_receiver_write.py` | **Receiver-only writer** (research version, pinned to the development device's backups). Default: read-only dry run (identity, status `00/00`, two full reads, validated plan). With `--execute-write --confirm-after-sha256 <expected array hash>`: erases only block 0 (64 KiB), programs pages, verifies each page, the full array and an independent final read. Modes `favorites` and `restore` (back to stock; accepts an interrupted block-0 state). Only exact whitelisted SPI command shapes reach the DLL. |

## Offline analysis

| Tool | Purpose |
|---|---|
| `setup_offline_tools.py` | Installs hash-pinned portable Ghidra 12.1.4, JDK 21, Unicorn 2.1.4 into `%USERPROFILE%\.cache\hdzero-monitor-tools` |
| `monitor_offline_prepare.py`, `offline_firmware.py` | Validate and extract the MStar ARM application |
| `Invoke-MonitorGhidra.ps1`, `ghidra/Monitor*.java` | MStar Ghidra project, exports |
| `monitor_function_emulator.py` | Executes original ARM functions in Unicorn with strict memory checks |
| `monitor_receiver_decode.py` | Decodes the receiver payload (bit permutation), checks the round trip |
| `Invoke-ReceiverGhidra.ps1`, `ghidra/Receiver*.java` | 8051 project, exports, Ghidra p-code tests of original and candidate code |
| `monitor_receiver_map.py` | Maps the configured Favorites to stock IDs and table rows |
| `loading_integrity_audit.py`, `receiver_consumer_audit.py` | File-only audits used in the research notes |
| `picoscope_ch341_capture.py` | PicoScope 2205A capture via the legacy `ps2000` API (`--profile data|cs`), optional fixed SPI burst on an isolated external CH341 |

## Building the firmware

```powershell
python tools/setup_receiver_assembler.py
# Decoded stock receiver (from your own backup, via monitor_receiver_decode.py):
$stock = 'artifacts/firmware-analysis/20261009-dm5680/receiver-8051.bin'

# 1. Independent generator: hand-encoded patch + appended code -> decoded image + manifest
python tools/monitor_receiver_candidate.py --stock $stock --output-dir artifacts/firmware-analysis/new/candidate

# 2. Recovered-source rebuild: Ghidra instruction export -> assembly -> naken_asm; must equal step 1 byte-for-byte
& tools/Invoke-ReceiverSourceExport.ps1 -OutputDirectory artifacts/firmware-analysis/new/src
python tools/monitor_receiver_source.py --stock $stock --inventory artifacts/firmware-analysis/new/src/instructions.json `
  --output-dir artifacts/firmware-analysis/new/favorites-build --flavor favorites

# 3a. Release container: official FPGA + MStar 1.1.1, modified receiver
python tools/monitor_update_package.py --official HDZero_Monitor-v1.1.1.bin `
  --receiver artifacts/firmware-analysis/new/favorites-build/receiver-rebuilt.bin --official-mstar --output-dir dist/new
# 3b. Personal container preserving your installed MStar state: --device-mstar <your 8339 backup>

# 4. Flash plan simulation against the local NOR model
python tools/monitor_receiver_flash_plan.py --backups <backup dir> --receiver <receiver-rebuilt.bin> --mode favorites --output-dir <new dir>

# 5. Tests (most skip without the private fixtures)
python -m unittest discover -s tests -v
```

`monitor_package_compatibility.py` runs the official programmer's file parser in isolation (no DLL, no USB) and projects the resulting flash arrays against a backup; it refuses packages that would alter the installed MStar/FPGA bytes of that backup (by design for personal packages).

## Release bundle

`make_release_bundle.py` assembles `dist/HDZero-Monitor-Favorites-v<version>/` and its ZIP: the installer and every tool module it imports (found by parsing imports), the configuration, LICENSE/NOTICE, the three `.cmd` starters (they verify a real 64-bit Python 3.11+ first), `README-INSTALL.md`, `THIRD-PARTY.md` (origin of the official firmware and the WCH DLL) and `SHA256SUMS.txt`. Every bundled file is checked against its pinned SHA-256; the update file must contain the official FPGA/MStar parts and the pinned receiver.

```powershell
python tools/make_release_bundle.py --official HDZero_Monitor-v1.1.1.bin --receiver <receiver-rebuilt.bin> `
  --dll <CH341DLLA64.DLL> --update-file <HDZero_Monitor-v1.1.2-favorites.bin>
```

## Changing the Favorites

Edit [`config/favorite-channels.json`](../config/favorite-channels.json) (eight `{band, channel}` entries; only rows the stock firmware marks as HDZero-capable are accepted) and rebuild. The tools pin the current build's hashes (`FAVORITES_SHA256` in `monitor_update_package.py`, `FAVORITES_ARRAY_SHA256` in `monitor_receiver_flash_plan.py`) and the tests pin expected bytes; update them only after both build paths agree.
