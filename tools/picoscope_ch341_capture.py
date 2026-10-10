"""Capture channel A from the installed PicoScope 2205A API.

Optional excitation is one fixed JEDEC-read burst on a physically isolated
external CH341. No Monitor routing, flash writes or scope signal generator.
The physical 10x probe setting is supplied by the user, not detected by the API.
"""

import argparse
import csv
import ctypes as C
import hashlib
import json
import os
import statistics
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

from monitor_usb_probe import EXPECTED_DLL_SHA256, bind, require_success, verify_usb_environment

PICO_HASH = "b96b1517178f76942362c9bde034337cc180406d7abdd933b624e7eb199ee755"
FIXED_READ = b"\x9f" * 256  # Longer fixed read burst for acquisition timing diagnosis.
ADC_MAX = 32767
PROBE_FACTOR = 10
INPUT_RANGE_VOLTS = 1  # Range enum 6: +/-1 V at input, +/-10 V at probe tip.
SAMPLES = 8000
TIMEBASE = 4
# Data lines: rising trigger, 80 ns samples. CS: falling trigger, slower
# timebase so one 8,000-sample block spans the whole burst assertion.
PROFILES = {"data": {"timebase": 4, "falling": False}, "cs": {"timebase": 7, "falling": True}}


def interval_seconds(interval_ns):
    # ps2000_get_timebase returns interval in ns regardless of time_units.
    # time_units only advises ps2000_get_times_and_values output scaling.
    if interval_ns <= 0:
        raise ValueError("Nonpositive sample interval")
    return interval_ns * 1e-9


def checked_dll(path, expected_hash):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
        raise ValueError("Installed DLL differs from the reviewed hash")
    return C.WinDLL(str(path.resolve()))


class BareSpi:
    """External adapter only. No CH341SetOutput binding or target routing."""

    def __init__(self, path):
        self.dll = checked_dll(path, EXPECTED_DLL_SHA256)
        u32, ptr, boolean = C.c_uint32, C.c_void_p, C.c_int32
        self.open_device = bind(self.dll, "CH341OpenDevice", ptr, u32)
        self.close_device = bind(self.dll, "CH341CloseDevice", None, u32)
        self.descriptor = bind(self.dll, "CH341GetDeviceDescr", boolean, u32, ptr, C.POINTER(u32))
        self.timeout = bind(self.dll, "CH341SetTimeout", boolean, u32, u32, u32)
        self.stream = bind(self.dll, "CH341SetStream", boolean, u32, u32)
        self.transfer = bind(self.dll, "CH341StreamSPI4", boolean, u32, u32, u32, ptr)
        self.opened = False

    def open(self):
        verify_usb_environment()
        handle = self.open_device(0)
        if handle in (None, C.c_void_p(-1).value):
            raise RuntimeError("Cannot open external CH341")
        self.opened = True
        require_success(self.timeout(0, 3000, 3000), "Set CH341 timeouts")
        buf, length = C.create_string_buffer(256), C.c_uint32(256)
        require_success(self.descriptor(0, buf, C.byref(length)), "Read CH341 descriptor")
        if not 18 <= length.value <= 256 or buf.raw[:2] != b"\x12\x01":
            raise RuntimeError("Invalid CH341 descriptor")
        if struct.unpack_from("<HH", buf.raw, 8) != (0x1A86, 0x5512):
            raise RuntimeError("Wrong CH341 USB mode")

    def pulse(self):
        if not self.opened:
            raise RuntimeError("External CH341 is not open")
        buf = C.create_string_buffer(FIXED_READ, len(FIXED_READ))
        try:
            require_success(self.stream(0, 0x81), "Set SPI stream mode")
            require_success(self.transfer(0, 0x80, len(FIXED_READ), buf), "Fixed JEDEC burst")
        finally:
            require_success(self.stream(0, 0x80), "Restore SPI stream mode")
        return buf.raw.hex()  # Floating MISO is not a chip identity.

    def close(self):
        if self.opened:
            self.close_device(0)
            self.opened = False


class Pico2205A:
    def __init__(self, path):
        self.search_path = os.add_dll_directory(str(path.resolve().parent))
        self.dll = checked_dll(path, PICO_HASH)
        i16, i32, ptr = C.c_int16, C.c_int32, C.c_void_p
        self.open_unit = bind(self.dll, "ps2000_open_unit", i16)
        self.info = bind(self.dll, "ps2000_get_unit_info", i16, i16, ptr, i16, i16)
        self.channel = bind(self.dll, "ps2000_set_channel", i16, i16, i16, i16, i16, i16)
        self.timebase = bind(self.dll, "ps2000_get_timebase", i16, i16, i16, i32, ptr, ptr, i16, ptr)
        self.trigger = bind(self.dll, "ps2000_set_trigger", i16, i16, i16, i16, i16, i16, i16)
        self.run = bind(self.dll, "ps2000_run_block", i16, i16, i32, i16, i16, ptr)
        self.ready = bind(self.dll, "ps2000_ready", i16, i16)
        self.values = bind(self.dll, "ps2000_get_values", i32, i16, ptr, ptr, ptr, ptr, ptr, i32)
        self.stop = bind(self.dll, "ps2000_stop", i16, i16)
        self.close_unit = bind(self.dll, "ps2000_close_unit", i16, i16)
        self.handle = 0

    def open(self):
        self.handle = self.open_unit()
        if self.handle <= 0:
            raise RuntimeError("Cannot open PicoScope; its application may have the device open")
        buf = C.create_string_buffer(256)
        require_success(self.info(self.handle, buf, len(buf), 3), "Read PicoScope variant")
        if buf.value != b"2205A":
            raise RuntimeError("This capture is reviewed for the connected 2205A only")
        require_success(self.channel(self.handle, 0, 1, 1, 6), "Configure channel A DC +/-1 V")
        require_success(self.channel(self.handle, 1, 0, 1, 6), "Disable unused channel B")

    def capture(self, pulse=None, timebase=TIMEBASE, falling=False):
        interval, units, max_samples = C.c_int32(), C.c_int16(), C.c_int32()
        require_success(self.timebase(self.handle, timebase, SAMPLES, C.byref(interval),
                                     C.byref(units), 1, C.byref(max_samples)), "Query timebase")
        if units.value not in range(6) or interval.value <= 0 or max_samples.value < SAMPLES:
            raise RuntimeError("Invalid or insufficient capture timebase")
        seconds = interval_seconds(interval.value)
        threshold = round(2 / (INPUT_RANGE_VOLTS * PROBE_FACTOR) * ADC_MAX)
        # -10% pretrigger; 1 s auto trigger. A flat trace cannot prove a triggered burst.
        require_success(self.trigger(self.handle, 0 if pulse else 5, threshold, int(falling), -10, 1000),
                        "Configure trigger")
        indisposed = C.c_int32()
        try:
            require_success(self.run(self.handle, SAMPLES, timebase, 1, C.byref(indisposed)),
                            "Arm block capture")
            if pulse:
                time.sleep(0.1)  # Let the separate USB scope finish arming before excitation.
            response = pulse() if pulse else None
            deadline = time.monotonic() + 5
            while True:
                ready = self.ready(self.handle)
                if ready < 0:
                    raise RuntimeError("PicoScope readiness failed")
                if ready > 0:
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("PicoScope capture did not finish")
                time.sleep(0.01)
            buf, overflow = (C.c_int16 * SAMPLES)(), C.c_int16()
            count = self.values(self.handle, buf, None, None, None, C.byref(overflow), SAMPLES)
            if count != SAMPLES:
                raise RuntimeError(f"Incomplete capture: {count}/{SAMPLES}")
            return list(buf), seconds, overflow.value, response
        finally:
            require_success(self.stop(self.handle), "Stop PicoScope acquisition")

    def close(self):
        try:
            if self.handle > 0:
                handle, self.handle = self.handle, 0
                require_success(self.close_unit(handle), "Close PicoScope")
        finally:
            self.search_path.close()


def summarize(raw, overflow, profile="data"):
    volts = [v * INPUT_RANGE_VOLTS * PROBE_FACTOR / ADC_MAX for v in raw]
    high, low = [v for v in volts if v > 2], [v for v in volts if v < 1]
    transitions = sum((a > 2) != (b > 2) for a, b in zip(volts, volts[1:]))
    if profile == "cs":
        # Idle-high start, then at least one assertion. Two edges suffice.
        runs, start = [], 0
        for i in range(1, len(volts) + 1):
            if i == len(volts) or (volts[i] > 2) != (volts[start] > 2):
                runs.append((volts[start] > 2, start, i - start))
                start = i
        lows = [n for is_high, _, n in runs if not is_high]
        return volts, {
            "min_volts": min(volts), "max_volts": max(volts),
            "high_median_volts": statistics.median(high) if high else None,
            "low_median_volts": statistics.median(low) if low else None,
            "transitions_at_2V": transitions, "overflow_bits": overflow,
            "falling_edges": sum(a > 2 >= b for a, b in zip(volts, volts[1:])),
            "rising_edges": sum(a <= 2 < b for a, b in zip(volts, volts[1:])),
            "idle_high_at_start": volts[0] > 2,
            "low_runs_samples": lows[:64], "returned_high_at_end": volts[-1] > 2,
            "observed_assertion": volts[0] > 2 and bool(lows) and not overflow,
        }
    return volts, {
        "min_volts": min(volts), "max_volts": max(volts),
        "high_median_volts": statistics.median(high) if high else None,
        "low_median_volts": statistics.median(low) if low else None,
        "transitions_at_2V": transitions, "overflow_bits": overflow,
        "observed_switching": transitions >= 4 and bool(high) and bool(low) and not overflow,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pico-dll", type=Path, required=True)
    parser.add_argument("--ch341-dll", type=Path)
    parser.add_argument("--isolated-adapter", action="store_true",
                        help="Assert adapter has no connections to Monitor or any flash")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", choices=sorted(PROFILES), default="data",
                        help="data: rising trigger, 80 ns; cs: falling trigger, long window")
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    if args.ch341_dll and not args.isolated_adapter:
        parser.error("SPI excitation requires physical isolation confirmation")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "probe_factor_user_reported": PROBE_FACTOR,
              "input_range_volts": INPUT_RANGE_VOLTS, "timebase": profile["timebase"],
              "profile": args.profile, "trigger_falling": profile["falling"],
              "pico_dll_sha256": PICO_HASH, "captures": [], "success": False,
              "spi_excitation": bool(args.ch341_dll), "monitor_routing": False,
              "spi_command_hex": FIXED_READ.hex() if args.ch341_dll else None}
    scope = spi = None
    try:
        scope = Pico2205A(args.pico_dll)
        scope.open()
        if args.ch341_dll:
            spi = BareSpi(args.ch341_dll)
            spi.open()
        for index in range(3):
            raw, seconds, overflow, response = scope.capture(spi.pulse if spi else None, **profile)
            volts, summary = summarize(raw, overflow, args.profile)
            summary.update(sample_interval_seconds=seconds, samples=len(raw), floating_miso=response)
            report["captures"].append(summary)
            with (args.output_dir / f"capture-{index + 1}.csv").open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["sample", "time_seconds_from_block_start", "adc", "probe_tip_volts"])
                writer.writerows((i, i * seconds, adc, v) for i, (adc, v) in enumerate(zip(raw, volts)))
            print(json.dumps(summary), flush=True)
        report["success"] = True
    except Exception as error:
        report["error"] = str(error)
    finally:
        report["cleanup_errors"] = []
        for device in (spi, scope):
            if device is not None:
                try:
                    device.close()
                except Exception as error:
                    report["cleanup_errors"].append(str(error))
                    report["success"] = False
        (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
