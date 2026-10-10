# PicoScope API and isolated external-adapter MOSI measurement

Date: 2026-10-09. AI assistance follows the [project disclosure](../../README.md#ai-assistance-disclosure).

## Result

Native Python/ctypes access to the user's **PicoScope 2205A** works through the installed 64-bit `ps2000.dll`. Three active captures of the isolated external CH341's user-confirmed MOSI contact show switching with approximately **0.009 V low**, **3.262 V high**, and observed extrema **−0.082 V to +3.352 V**. Each capture contains 8,000 samples at **80 ns** spacing, with no reported input overflow. This supports a 3.3 V MOSI signal under this unloaded test arrangement. It does not validate SCK, CS, power-up transients, a loaded bus, adapter power output or in-circuit recovery.

The user confirmed no connection to the Monitor, probe tip on MOSI, ground on adapter GND, and the physical probe switched to 10×. Probe attenuation and contact identity are user-provided physical facts; the API cannot detect them. The capture selects channel A, DC coupling, ±1 V at the scope input and applies the 10× factor in voltage conversion (±10 V at the probe tip). Channel B is disabled. The API test does not require the PicoScope application to run.

## Hardware and software evidence

- Windows identifies the Pico device as `VID_0CE9&PID_1007`; the driver reports variant `2205A` and library version `3.0.150.6187`.
- Installed library: `C:\Program Files\Pico Technology\PicoScope 7 T&M Stable\ps2000.dll`, SHA-256 `b96b1517178f76942362c9bde034337cc180406d7abdd933b624e7eb199ee755`.
- The external CH341 remains `1A86:5512`, on the USB instance identified after the user's SPI-jumper change. Its sharp original photo shows the yellow `SPI INTERFACE` row, left to right: `GND, VDD, CS0, CS1, CS2, SCK, MOSI, MISO` (an earlier transcription read the second label as `RD`; an enlarged crop of the same photo reads `VDD`). MOSI is second from the right. Below the row, a 3-pin `PWR-SEL` jumper selects `VCC` (up) or `+5V` (down); in the photo its jumper appears to sit on the `VCC` side. A separate 2×3 header near the CH341 is marked `5V` / `V3 VCC`. The photo cannot establish which voltage actually reaches `VDD`. Labels do not by themselves establish every electrical connection.
- Private evidence is in `artifacts/firmware-analysis/20261009-picoscope-api/`: identification, preserved original adapter photo with provenance, raw integer ADC/voltage CSVs and reports. The authoritative active dataset is `mosi-active-settled/`, started at 18:48:44 UTC.

## Capture and excitation boundaries

The new [capture utility](../../tools/picoscope_ch341_capture.py) binds only the required scope acquisition functions. It binds no scope signal-generator function. Its optional independent `BareSpi` implementation uses the pinned installed WCH DLL and accepts no arbitrary command. It sends a fixed 256-byte `9F` read burst using automatic CS0. The adapter has no connected flash; returned all-FF MISO is therefore not an identification result. The `--isolated-adapter` switch records a required physical assertion, not an electronically verified condition.

`BareSpi` does not bind `CH341SetOutput` or use any Monitor-specific GPIO selection/release. There is no write-enable, erase, program, protection-write or status-write command. Three captures issued three bounded fixed read bursts. Scope acquisition is stopped after each capture; both devices are closed afterward, with no recorded cleanup errors. Native CH341 calls use 3-second USB timeouts; scope readiness polling has a 5-second deadline.

Initial six-byte bursts produced flat high traces. After the user reconfirmed the contact, extending the burst and allowing 100 ms for the scope to arm produced switching in all three captures. This establishes that the subsequent acquisition worked; it does not isolate which timing change was decisive. The initial passive report also used an incorrect time-unit conversion; that dataset is explicitly marked as having a superseded time axis. Legacy `ps2000_get_timebase` returns its sample interval in nanoseconds regardless of its separate suggested time-units output. Current active timing uses the documented interpretation.

Seven focused host tests pass: 10× scaling, legacy interval conversion, rejection of flat/overflowed traces as switching evidence, exact fixed read payload, stream restoration after failure, no excitation while closed, and acquisition stop after an excitation failure. These are software checks, separate from the real captures.

## SCK measurement

The user confirmed the probe tip moved to **SCK** (third pin from right), with ground, 10× setting and Monitor isolation unchanged. Three captures with unchanged settings (`sck-active-settled/`, started 19:11:36 UTC) show:

| Measure | Result |
| --- | --- |
| Low / high median | **0.009 V / 3.262 V** |
| Extrema | **−0.082 V to +3.352 V** |
| 2-V transitions | 1,341 / 1,414 / 1,264 |
| Overflow | 0 in all three |
| Idle level before burst | low (≈64 µs pretrigger, all three) |

Medians/extrema equal MOSI's because the 8-bit ADC quantizes to the same codes. Clock pulses are grouped as 8 pulses per byte (about 5 µs per byte), with high phases of 3–4 samples (240–320 ns) and rising-to-rising spacing of mostly 8 samples (640 ns), i.e. roughly **1.3–1.6 MHz**, with irregular bit spacing and inter-byte gaps. Longer gaps of about 6 µs and 40–100 µs separate bursts of about 32 bytes, consistent with USB packet scheduling. Idle-low SCK is consistent with SPI mode 0. The 640 µs window covers only part of the 256-byte burst.

At 80 ns sampling a clock period spans only about 8 samples; edge rise times, overshoot and ringing are not resolved. This supports 3.3 V SCK switching under this unloaded setup only. Plot: `sck-measurement.png` / `.svg` in the evidence root.

## CS0 measurement

The user confirmed the probe tip moved to **CS0** (third from left), other conditions unchanged. Three captures with `--profile cs` (`cs0-active-settled/`) show for every capture: idle high before the burst, **exactly one falling and one rising edge**, and a continuous low assertion of **2.026 / 1.998 / 1.969 ms** for the 256-byte burst (about 1 Mbit/s effective including USB gaps). High level 3.17–3.35 V before and after; low ≤0.10 V throughout the assertion; no sample between 0.5 and 2.8 V (edges faster than one 640 ns sample); no overflow. CS0 therefore stays asserted across the USB-packet gaps seen on SCK, within the 640 ns resolution: a deassertion shorter than about 1 µs could not be excluded. Plot: `cs0-measurement.png` / `.svg`.

Together, MOSI, SCK and CS0 show unloaded 3.3 V push-pull-like levels, SPI mode 0 idle states, active-low CS covering a full transfer. MISO input threshold, VDD output and behavior under load remain unmeasured.

## VDD measurement

The user confirmed the probe tip on **VDD** (second from left), other conditions unchanged, jumpers not changed. Three passive, untriggered captures without any CH341 access (`vdd-passive/`) show every sample between **3.17 and 3.35 V**, median **3.26 V**, no transitions, no overflow. One ADC step is about 0.09 V at the probe tip, so this distinguishes 3.3 V from 5 V but is not a precision DC value; a multimeter would give a better absolute reading. With the current jumper positions the flash-power output is therefore **3.3 V, unloaded**. Its current capability, load regulation and behavior when connected to an externally powered rail (back-feeding into the Monitor's 3.3 V net) are untested. Do not move the `PWR-SEL` or `5V` / `V3 VCC` jumpers without repeating this measurement.

## Next steps

The isolated adapter characterization is complete for MOSI, SCK, CS0 and VDD. MISO input threshold and loaded behavior remain unmeasured. The next work is the in-circuit access plan in the [external-access investigation](external-ch341-recovery-references-20261009.md): USON-8 contact method, whether to supply flash VCC from the adapter or the Monitor, back-powering of the Monitor's 3.3 V rail, and keeping the receiver CPU off the SPI bus.

CS0 method used `--profile cs`: falling 2-V trigger, timebase 7 (expected 640 ns, about 5.1 ms window) to include the entire burst assertion. Its summary reports idle-high start, edge counts and low-run lengths; `observed_assertion` replaces the four-transition switching check. At 640 ns sampling, CS deassertions shorter than about 1 µs between USB packets could be missed. Two new host tests cover the CS summary and the falling-trigger/timebase arming (9 PicoScope tests pass). Measure the adapter's intended flash-power output separately. No Monitor connection should follow solely from the MOSI result; rail back-powering and bus ownership still require investigation under the [external-access plan](external-ch341-recovery-references-20261009.md).

The scope's displayed calibration date is historical and no independent instrument/probe calibration was checked. 80 ns samples and the probe setup cannot exclude narrower transient peaks. Reported extrema describe these recordings only.

## Primary references

[Pico's API/model table](https://www.picotech.com/library/knowledge-bases/oscilloscopes/picosdk-and-picoscope-models) identifies `ps2000` for 2205A. The [manufacturer programmer's guide](https://www.picotech.com/download/manuals/ps2000pg.en-10.pdf) defines acquisition, scaling to ±32767 ADC counts, nanosecond sample intervals, and triggering. Function signatures were checked against [Pico's Python bindings](https://github.com/picotech/picosdk-python-wrappers/blob/master/picosdk/ps2000.py) and [block example](https://github.com/picotech/picosdk-python-wrappers/blob/master/ps2000Examples/ps2000BlockExample.py). These sources were checked on this date. The implementation is a focused local ctypes wrapper rather than an installation of the full SDK or GUI automation.
