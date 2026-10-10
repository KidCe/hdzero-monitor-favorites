"""Run bounded original ARM settings functions, without hardware or RF models."""

import argparse
import itertools
import json
import struct
import sys
from pathlib import Path

from offline_firmware import APPLICATION_BASE, load_application


STACK_BASE, STACK_SIZE = 0x30000000, 0x10000
RETURN_ADDRESS = 0x40000000
SETTINGS_ADDRESS = 0x20431DD4
HD_VALUE, SWITCH_VALUE = 0x20350604, 0x20350584
PROFILE_FUNCTION, PROPERTY_FUNCTION = 0x20075928, 0x2023EDC0
INSTRUCTION_LIMIT, TIMEOUT_US = 100000, 1000000


def configure_unicorn(directory):
    sys.path.insert(0, str(directory / "python-libs"))
    import unicorn
    if unicorn.__version__ != "2.1.4":
        raise ValueError("This harness requires the pinned Unicorn 2.1.4 runtime")
    return unicorn


def contains(region, address, size):
    return size > 0 and region[0] <= address and address + size <= region[0] + region[1]


def run_function(unicorn, application, entry, registers=None, image_inputs=(), ram_inputs=(), stack_inputs=(), observe=()):
    """Execute original code. Unknown access stops execution; no API calls are stubbed."""
    from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_R0

    if not contains((APPLICATION_BASE, len(application)), entry, 4) or entry % 4:
        raise ValueError("Entry must be aligned inside the validated ARM application")
    mu = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM | unicorn.UC_MODE_LITTLE_ENDIAN)
    image_region = (APPLICATION_BASE, len(application))
    stack_region = (STACK_BASE, STACK_SIZE)
    mu.mem_map(APPLICATION_BASE, (len(application) + 0xFFF) & ~0xFFF,
               unicorn.UC_PROT_READ | unicorn.UC_PROT_EXEC)
    mu.mem_write(APPLICATION_BASE, application)
    mu.mem_map(STACK_BASE, STACK_SIZE, unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
    mu.mem_map(RETURN_ADDRESS, 0x1000, unicorn.UC_PROT_EXEC)
    modeled_ram, pages = [], set()
    for address, value in ram_inputs:
        if not value or contains(image_region, address, len(value)) or contains(stack_region, address, len(value)):
            raise ValueError("Explicit RAM inputs must be nonempty and outside image/stack")
        for page in range(address & ~0xFFF, (address + len(value) + 0xFFF) & ~0xFFF, 0x1000):
            if page not in pages:
                mu.mem_map(page, 0x1000, unicorn.UC_PROT_READ | unicorn.UC_PROT_WRITE)
                pages.add(page)
        mu.mem_write(address, value)
        modeled_ram.append((address, len(value)))
    for address, value in image_inputs:
        if not contains(image_region, address, len(value)):
            raise ValueError("Input field falls outside the validated application")
        # Host fixture initialization is allowed; ARM writes to image remain prohibited.
        mu.mem_write(address, value)
    for address, value in stack_inputs:
        if not contains(stack_region, address, len(value)):
            raise ValueError("Input falls outside stack")
        mu.mem_write(address, value)
    mu.reg_write(UC_ARM_REG_SP, STACK_BASE + STACK_SIZE - 0x10)
    mu.reg_write(UC_ARM_REG_LR, RETURN_ADDRESS)
    for register, value in (registers or {}).items():
        mu.reg_write(register, value)
    state = {"instructions": 0, "blocked_access": None}
    code_pages = set()

    def block(kind, address, size):
        if state["blocked_access"] is None:
            state["blocked_access"] = {"kind": kind, "address": hex(address), "bytes": size,
                                       "pc": hex(mu.reg_read(UC_ARM_REG_PC))}
        mu.emu_stop()

    def instruction_hook(engine, address, size, user_data):
        state["instructions"] += 1
        code_pages.add(address & ~0xFFF)
        if not contains(image_region, address, size):
            block("execution_outside_original_image", address, size)

    def memory_hook(engine, access, address, size, value, user_data):
        write = access == unicorn.UC_MEM_WRITE
        allowed = [stack_region, *modeled_ram]
        if not write:
            allowed.append(image_region)
        if not any(contains(region, address, size) for region in allowed):
            block("unmodeled_write" if write else "unmodeled_read", address, size)

    def invalid_hook(engine, access, address, size, value, user_data):
        block("unmapped_or_protected_access", address, size)
        return False

    mu.hook_add(unicorn.UC_HOOK_CODE, instruction_hook)
    mu.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE, memory_hook)
    mu.hook_add(unicorn.UC_HOOK_MEM_INVALID, invalid_hook)
    error = None
    try:
        mu.emu_start(entry, RETURN_ADDRESS, timeout=TIMEOUT_US, count=INSTRUCTION_LIMIT)
    except unicorn.UcError as exc:
        error = str(exc)
    pc = mu.reg_read(UC_ARM_REG_PC)
    returned = pc == RETURN_ADDRESS and state["blocked_access"] is None and error is None
    observed = {}
    for address, size in observe:
        if not any(contains(region, address, size) for region in [image_region, stack_region, *modeled_ram]):
            raise ValueError("Observation falls outside the explicit model")
        observed[hex(address)] = bytes(mu.mem_read(address, size)).hex()
    return {"entry": hex(entry), "r0": mu.reg_read(UC_ARM_REG_R0), "final_pc": hex(pc),
            "returned": returned, "instructions": state["instructions"],
            "blocked_access": state["blocked_access"], "emulator_error": error,
            "executed_image_pages": [hex(page) for page in sorted(code_pages)],
            "limit_or_timeout_reached": not returned and error is None and state["blocked_access"] is None,
            "modeled_ram": [{"address": hex(a), "bytes": n} for a, n in modeled_ram],
            "observed_memory": observed}


def run_suite(unicorn, application):
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1

    # Verify field names behind the fixture offsets before changing host input values.
    for field, name in ((HD_VALUE, b"Display_hd_sd\0"), (SWITCH_VALUE, b"Channel_Switch\0")):
        pointer = struct.unpack_from("<I", application, field - 4 - APPLICATION_BASE)[0]
        offset = pointer - APPLICATION_BASE
        if offset < 0 or application[offset:offset + len(name)] != name:
            raise ValueError("Settings record identity mismatch")
    cases = []
    for hd, switch in itertools.product((0, 1), repeat=2):
        fields = [(HD_VALUE, struct.pack("<I", hd)), (SWITCH_VALUE, struct.pack("<I", switch))]
        for entry, property_id in ((PROFILE_FUNCTION, None), (PROPERTY_FUNCTION, 0xD1)):
            pointer = STACK_BASE + 0x100
            result = run_function(unicorn, application, entry,
                                  registers={} if property_id is None else {UC_ARM_REG_R0: pointer},
                                  image_inputs=fields,
                                  stack_inputs=[] if property_id is None else [(pointer, struct.pack("<I", property_id))])
            expected = switch * 2 + hd
            cases.append({"test": "packed_display_switch" if property_id is None else "property_d1",
                          "inputs": {"display_hd_sd": hd, "channel_switch": switch},
                          "expected_r0": expected, "passed": result["returned"] and result["r0"] == expected,
                          **result})
    for byte0, byte1 in ((0, 0), (6, 7), (255, 254)):
        for property_id, expected in ((0x7C, byte0), (0x7D, byte1)):
            pointer = STACK_BASE + 0x100
            result = run_function(unicorn, application, PROPERTY_FUNCTION,
                                  registers={UC_ARM_REG_R0: pointer},
                                  ram_inputs=[(SETTINGS_ADDRESS, bytes((byte0, byte1)))],
                                  stack_inputs=[(pointer, struct.pack("<I", property_id))])
            cases.append({"test": f"property_{property_id:02x}",
                          "inputs": {"settings_byte_0": byte0, "settings_byte_1": byte1},
                          "expected_r0": expected, "passed": result["returned"] and result["r0"] == expected,
                          **result})
    # The same original property getter must fail when its RAM has not been modeled.
    pointer = STACK_BASE + 0x100
    result = run_function(unicorn, application, PROPERTY_FUNCTION, registers={UC_ARM_REG_R0: pointer},
                          stack_inputs=[(pointer, struct.pack("<I", 0x7C))])
    cases.append({"test": "unknown_ram_is_blocked", "inputs": {"property_id": "0x7c"},
                  "passed": not result["returned"] and result["blocked_access"] is not None
                  and result["blocked_access"]["address"] == hex(SETTINGS_ADDRESS), **result})
    for packet, count, expected in ((b"\x3e\x01\x01", 0, 0),
                                    (b"\x3e\x01\x01", 2, 0),
                                    (b"\x3e\x02\x03\x55", 3, 0x54),
                                    (b"\x3e\x02\xff\x01", 3, 0xFC)):
        pointer = STACK_BASE + 0x100
        result = run_function(unicorn, application, 0x2007FC2C,
                              registers={UC_ARM_REG_R0: pointer, UC_ARM_REG_R1: count},
                              stack_inputs=[(pointer, packet)])
        cases.append({"test": "uart_xor_checksum", "inputs": {"bytes": packet.hex(), "count": count},
                      "expected_r0": expected, "passed": result["returned"] and result["r0"] == expected,
                      **result})
    for packet in (b"", b"\x11\x22\x33", b"\x3c\x01\x02\x07\x00"):
        descriptor, buffer, state = 0x2064F5C4, 0x2064F5D0, 0x20434DE8
        storage = bytearray(4096)
        storage[1:1 + len(packet)] = packet
        result = run_function(unicorn, application, 0x2007F954,
                              ram_inputs=[(descriptor, struct.pack("<III", buffer, 0, len(packet))),
                                          (buffer, bytes(storage)), (state, bytes(6))],
                              observe=[(state, 6), (descriptor, 12)])
        observed_state = bytes.fromhex(result["observed_memory"][hex(state)])
        cases.append({"test": "uart_reject_or_empty", "inputs": {"bytes": packet.hex()},
                      "expected_r0": 0,
                      "passed": result["returned"] and result["r0"] == 0
                      and observed_state[4] == 0 and observed_state[5] == 0, **result})
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--tools-directory", type=Path, default=Path.home() / ".cache/hdzero-monitor-tools")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() == args.input.resolve() or args.report.exists():
        raise ValueError("Report must be a new file distinct from the input")
    application, metadata = load_application(args.input)
    unicorn = configure_unicorn(args.tools_directory)
    cases = run_suite(unicorn, application)
    report = {"schema": "hdzero-monitor.original-function-tests.v1", "input": metadata,
              "unicorn_version": unicorn.__version__, "instruction_limit_per_call": INSTRUCTION_LIMIT,
              "timeout_microseconds_per_call": TIMEOUT_US, "hardware_access": False,
              "rf_or_fpga_simulated": False, "hardware_api_stubs": [], "favorites_patch_tested": False,
              "scope": "original settings/property and UART checksum/rejection functions; not a full Monitor emulator",
              "success": all(case["passed"] for case in cases), "cases": cases}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"success": report["success"], "passed": sum(c["passed"] for c in cases),
                      "total": len(cases), "report": str(args.report.resolve())}, indent=2))
    if not report["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
