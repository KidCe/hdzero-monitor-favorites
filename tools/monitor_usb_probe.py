"""Identify an HDZero Monitor's CH341 bridge and read flash metadata/samples.

No erase, program, write-enable, configuration-write or arbitrary SPI operation
is implemented. Flash-target selection actively changes the board's routing.
"""

import argparse
import ctypes
import hashlib
import json
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SOURCE = "https://github.com/hd-zero/hdzero-programmer/blob/85a497e5b258e1bd1137e39668e078c02f895668/ch341.py"
EXPECTED_DLL_SHA256 = "7d7dd5405b88b2b0140fbc07251ced4f9774b81d0fcf45d59fa92222f4420971"
RELEASES = {
    "6b7f7cd53be329eaa4059b7b40c2e3e8f2fad1d8ecd94bfe0cb7a228131f7041": "1.1.1",
    "3db0a81fe43869085b5455031c34bc69f19c998606c2fedf4085eb150fac8725": "1.2.0",
}
TARGETS = {"fpga": 0x8300, "5680": 0x4300, "8339": 0xC800}
RELEASE_OUTPUT = 0xC200
MAX_READ_BYTES = 1024


def verify_usb_environment():
    command = r"""
$ErrorActionPreference = 'Stop'
$devices = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '^USB\\VID_1A86&PID_5512' })
$programmers = @(Get-Process -Name HDZeroProgrammer -ErrorAction SilentlyContinue)
@{ device_count=$devices.Count; programmer_count=$programmers.Count } | ConvertTo-Json -Compress
"""
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, timeout=20, check=True,
    )
    status = json.loads(result.stdout)
    if status["device_count"] != 1:
        raise RuntimeError("Exactly one connected CH341 1A86:5512 device is required")
    if status["programmer_count"] != 0:
        raise RuntimeError("Close HDZeroProgrammer before using this tool")
    return status


def bind(dll, name, result, *arguments):
    function = getattr(dll, name)
    function.restype = result
    function.argtypes = list(arguments)
    return function


def require_success(result, operation):
    if not result:
        raise RuntimeError(f"{operation} failed")


def reference_payloads(path):
    if path is None:
        return None, {}
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest not in RELEASES:
        raise ValueError("Baseline does not match either pinned official release")
    sizes = struct.unpack_from("<3I", data, 2)
    if sum(sizes) + 14 != len(data):
        raise ValueError("Baseline component lengths do not match the container")
    offset = 14
    payloads = {}
    for name, size in zip(("5680", "fpga", "8339"), sizes):
        payloads[name] = data[offset : offset + size]
        offset += size
    return RELEASES[digest], payloads


class Bridge:
    def __init__(self, path):
        if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 8:
            raise RuntimeError("This probe requires 64-bit Windows Python")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != EXPECTED_DLL_SHA256:
            raise ValueError("DLL differs from the audited official/installed x64 DLL")
        self.dll = ctypes.WinDLL(str(path.resolve()))
        u32 = ctypes.c_uint32
        pointer = ctypes.c_void_p
        boolean = ctypes.c_int32
        self.open_device = bind(self.dll, "CH341OpenDevice", pointer, u32)
        self.close_device = bind(self.dll, "CH341CloseDevice", None, u32)
        self.get_descriptor = bind(self.dll, "CH341GetDeviceDescr", boolean, u32, pointer, ctypes.POINTER(u32))
        self.set_timeout = bind(self.dll, "CH341SetTimeout", boolean, u32, u32, u32)
        self.set_stream = bind(self.dll, "CH341SetStream", boolean, u32, u32)
        self.set_output = bind(self.dll, "CH341SetOutput", boolean, u32, u32, u32, u32)
        self.transfer = bind(self.dll, "CH341StreamSPI4", boolean, u32, u32, u32, pointer)
        self.opened = False
        self.routed = False

    def open(self):
        verify_usb_environment()
        handle = self.open_device(0)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise RuntimeError("Cannot open CH341 index 0; check connection and other applications")
        self.opened = True
        require_success(self.set_timeout(0, 3000, 3000), "Set USB timeouts")
        buffer = ctypes.create_string_buffer(256)
        length = ctypes.c_uint32(len(buffer))
        require_success(self.get_descriptor(0, buffer, ctypes.byref(length)), "Read USB device descriptor")
        if length.value < 18 or length.value > len(buffer):
            raise RuntimeError("Invalid USB descriptor length")
        raw = buffer.raw[: length.value]
        if raw[0] != 18 or raw[1] != 1:
            raise RuntimeError("Unexpected USB device descriptor")
        vid, pid = struct.unpack_from("<HH", raw, 8)
        if (vid, pid) != (0x1A86, 0x5512):
            raise RuntimeError(f"Unexpected USB device {vid:04x}:{pid:04x}; no routing attempted")
        return {"vid": f"0x{vid:04X}", "pid": f"0x{pid:04X}", "descriptor_hex": raw.hex()}

    def select(self, name):
        self.routed = True  # Also clean up if the transport partially applies a failed request.
        require_success(self.set_output(0, 0x03, 0x0000FF00, TARGETS[name]), f"Select {name} flash")

    def _read_transaction(self, command):
        if not command or command[0] not in (0x9F, 0x03):
            raise ValueError("Only JEDEC ID and flash READ are allowed")
        if command[0] == 0x9F and command != bytes([0x9F]) * 6:
            raise ValueError("Unexpected JEDEC transaction")
        if command[0] == 0x03 and (len(command) < 5 or any(command[4:])):
            raise ValueError("Flash reads require an address and zero dummy bytes")
        if not self.opened or not self.routed or len(command) > MAX_READ_BYTES + 4:
            raise ValueError("Probe transaction outside the reviewed scope")
        buffer = ctypes.create_string_buffer(command, len(command))
        require_success(self.set_stream(0, 0x81), "Set SPI stream mode")
        try:
            require_success(self.transfer(0, 0x80, len(command), buffer), "SPI read transaction")
            return buffer.raw
        finally:
            require_success(self.set_stream(0, 0x80), "Restore stream mode")

    def jedec_id(self):
        result = self._read_transaction(bytes([0x9F]) * 6)
        identifier = result[1:4]
        if identifier in (bytes(3), bytes([0xFF]) * 3):
            raise RuntimeError(f"No valid JEDEC ID: {identifier.hex()}")
        return identifier.hex().upper()

    def read_prefix(self):
        return self.read(0, 64)

    def read(self, address, length):
        if not isinstance(address, int) or not isinstance(length, int):
            raise ValueError("Read address and length must be integers")
        if address < 0 or length < 1 or length > MAX_READ_BYTES or address + length > 1 << 24:
            raise ValueError("Read exceeds the reviewed 24-bit address/length limits")
        command = b"\x03" + address.to_bytes(3, "big") + bytes(length)
        return self._read_transaction(command)[4:]

    def close(self):
        cleanup_errors = []
        if self.opened:
            try:
                if self.routed:
                    if not self.set_output(0, 0x03, 0x0000FF00, RELEASE_OUTPUT):
                        cleanup_errors.append("Stock bus release failed")
            finally:
                self.close_device(0)
                self.opened = False
        if cleanup_errors:
            raise RuntimeError("; ".join(cleanup_errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--identify-only", action="store_true")
    args = parser.parse_args()
    version, reference = reference_payloads(args.baseline)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "dll_sha256": EXPECTED_DLL_SHA256,
        "mode": "usb_descriptor_only" if args.identify_only else "flash_ids_and_64_byte_prefixes",
        "baseline_version": version,
        "flash_mutation_commands_implemented": False,
        "targets": {},
    }
    bridge = None
    success = False
    try:
        bridge = Bridge(args.dll)
        report["usb"] = bridge.open()
        print("Opened verified USB device 1A86:5512", flush=True)
        if not args.identify_only:
            for name in ("fpga", "5680", "8339"):
                bridge.select(name)
                first = bridge.jedec_id()
                second = bridge.jedec_id()
                if first != second:
                    raise RuntimeError(f"Unstable JEDEC ID for {name}")
                if name == "fpga" and first != "EF4018":
                    raise RuntimeError("FPGA flash ID differs from the official Monitor connection check")
                report["targets"][name] = {"jedec_id": first}
                prefix = bridge.read_prefix()
                repeated_prefix = bridge.read_prefix()
                if prefix != repeated_prefix:
                    raise RuntimeError(f"Unstable flash prefix for {name}")
                target = report["targets"][name]
                target["prefix_hex"] = prefix.hex()
                target["prefix_repeat_equal"] = True
                if name in reference:
                    target["prefix_matches_baseline"] = prefix == reference[name][:64]
                print(f"{name}: JEDEC={first}, repeated prefix equal, baseline match={target.get('prefix_matches_baseline')}", flush=True)
        success = True
    except Exception as error:
        report["error"] = str(error)
        print(f"ERROR: {error}", file=sys.stderr, flush=True)
    finally:
        if bridge is not None:
            try:
                bridge.close()
                report["cleanup_success"] = True
            except Exception as error:
                report["cleanup_error"] = str(error)
                success = False
                print(f"CLEANUP ERROR: {error}", file=sys.stderr, flush=True)
        report["success"] = success
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
