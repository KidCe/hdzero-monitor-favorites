import ctypes
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import picoscope_ch341_capture as capture


class ScopeCaptureTests(unittest.TestCase):
    def test_legacy_interval_is_nanoseconds(self):
        self.assertAlmostEqual(capture.interval_seconds(80), 80e-9)
        with self.assertRaises(ValueError):
            capture.interval_seconds(0)

    def test_voltage_scaling_includes_physical_10x_factor(self):
        volts, result = capture.summarize([0, 16384, 32767, 0, 32767, 0], 0)
        self.assertAlmostEqual(volts[1], 5, places=3)
        self.assertEqual(volts[2], 10)
        self.assertTrue(result["observed_switching"])

    def test_flat_or_overflowing_trace_is_not_switching_evidence(self):
        self.assertFalse(capture.summarize([10000] * 20, 0)[1]["observed_switching"])
        self.assertFalse(capture.summarize([0, 20000] * 20, 1)[1]["observed_switching"])

    def test_cs_profile_requires_idle_high_then_assertion(self):
        high, low = 32767 // 3, 0
        result = capture.summarize([high] * 5 + [low] * 10 + [high] * 3, 0, "cs")[1]
        self.assertTrue(result["observed_assertion"])
        self.assertEqual((result["falling_edges"], result["rising_edges"]), (1, 1))
        self.assertEqual(result["low_runs_samples"], [10])
        self.assertTrue(result["returned_high_at_end"])
        self.assertFalse(capture.summarize([high] * 20, 0, "cs")[1]["observed_assertion"])
        self.assertFalse(capture.summarize([low] * 20, 0, "cs")[1]["observed_assertion"])
        self.assertFalse(capture.summarize([high] * 5 + [low] * 5, 1, "cs")[1]["observed_assertion"])

    def test_cs_profile_arms_falling_trigger_and_slow_timebase(self):
        scope = capture.Pico2205A.__new__(capture.Pico2205A)
        scope.handle = 1
        calls = {}
        def timebase(handle, tb, count, interval, units, oversample, max_samples):
            calls["timebase"] = tb
            ctypes.cast(interval, ctypes.POINTER(ctypes.c_int32))[0] = 640
            ctypes.cast(units, ctypes.POINTER(ctypes.c_int16))[0] = 2
            ctypes.cast(max_samples, ctypes.POINTER(ctypes.c_int32))[0] = 32000
            return 1
        scope.timebase = timebase
        scope.trigger = lambda *args: calls.setdefault("trigger", args) and 1
        scope.run = lambda handle, n, tb, oversample, ptr: calls.setdefault("run_tb", tb) and 1
        scope.ready = lambda handle: 1
        scope.values = lambda handle, a, b, c, d, overflow, n: n
        scope.stop = lambda handle: 1
        _, seconds, _, _ = scope.capture(lambda: None, **capture.PROFILES["cs"])
        self.assertEqual((calls["timebase"], calls["run_tb"]), (7, 7))
        self.assertEqual(calls["trigger"][3], 1)
        self.assertAlmostEqual(seconds, 640e-9)

    def test_only_fixed_read_bytes_are_sent_and_stream_restored(self):
        spi = capture.BareSpi.__new__(capture.BareSpi)
        spi.opened = True
        events = []
        spi.stream = lambda index, mode: events.append(("stream", mode)) or 1
        def transfer(index, cs, length, buffer):
            events.append(("transfer", cs, ctypes.string_at(buffer, length)))
            return 1
        spi.transfer = transfer
        spi.pulse()
        self.assertEqual(events, [("stream", 0x81), ("transfer", 0x80, b"\x9f" * 256), ("stream", 0x80)])

    def test_spi_failure_still_restores_stream(self):
        spi = capture.BareSpi.__new__(capture.BareSpi)
        spi.opened = True
        events = []
        spi.stream = lambda index, mode: events.append(mode) or 1
        spi.transfer = lambda *args: 0
        with self.assertRaises(RuntimeError):
            spi.pulse()
        self.assertEqual(events, [0x81, 0x80])

    def test_closed_adapter_cannot_drive(self):
        spi = capture.BareSpi.__new__(capture.BareSpi)
        spi.opened = False
        with self.assertRaises(RuntimeError):
            spi.pulse()

    def test_scope_stops_when_excitation_fails(self):
        scope = capture.Pico2205A.__new__(capture.Pico2205A)
        scope.handle = 1
        def timebase(handle, tb, count, interval, units, oversample, max_samples):
            ctypes.cast(interval, ctypes.POINTER(ctypes.c_int32))[0] = 80
            ctypes.cast(units, ctypes.POINTER(ctypes.c_int16))[0] = 2
            ctypes.cast(max_samples, ctypes.POINTER(ctypes.c_int32))[0] = 32000
            return 1
        scope.timebase = timebase
        scope.trigger = scope.run = lambda *args: 1
        events = []
        scope.stop = lambda handle: events.append("stop") or 1
        def fail():
            raise RuntimeError("excitation failed")
        with self.assertRaisesRegex(RuntimeError, "excitation failed"):
            scope.capture(fail)
        self.assertEqual(events, ["stop"])


if __name__ == "__main__":
    unittest.main()
