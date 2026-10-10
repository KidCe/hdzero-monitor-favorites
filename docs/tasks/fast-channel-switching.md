# FUT-001: Faster channel switching on the Monitor

Status: Deferred. Priority: After the Favorites feature is implemented and tested on the real Monitor.
Requested by the user on 2026-10-09. AI assistance: OpenAI Codex helped record the investigation scope.

## Goal

Investigate whether channel changes can preserve the receiver/video setup and reduce blank-screen time, following the lightweight retune approach in the custom HDZero Goggle firmware. Retain a reliable fallback when the receiver needs full reacquisition. Do not promise universally instant switching.

## Entry condition

Start only after P1–P8 works on the physical Monitor, including L6/L7 transitions, labels, both directions, saved-state retention and a demonstrated recovery route. This task does not change the current Favorites implementation or its acceptance criteria.

## Feasibility assessment

A focused investigation is realistic because the Monitor's selection, save, receiver refresh and tuning paths have been located in recovered assembly: `0674/06D6`, `9F29`, `61D2`, `67E7`, `0C74` and `5D19`. This is a feasibility inference, not proof that the Goggle optimization transfers directly to the Monitor or that RF lock time can be eliminated.

The [Ripples 1.1.2 author notes](https://github.com/LVTY-AI/hdzero-goggle/releases/tag/ripples-v1.1.2) restrict reported instant changes to matching bandwidth, camera, resolution and frame rate; other combinations require reacquisition. The [same-protocol selection path](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/input_device.c#L150-L193) and [lightweight retune routine](https://github.com/LVTY-AI/hdzero-goggle/blob/6528ad1f22fa629c2149bd058102de55c247637f/src/core/app_state.c#L274-L287) are useful references. See the existing [source findings](../research/ripples-favorites-monitor-findings.md).

## Work

1. Measure the current Favorites build: input-to-tune time and tune-to-stable-video time separately. Use supported video modes and repeatable live RF sources.
2. Trace avoidable settings-write delays, source reinitialization, display retiming and validity resets. Keep required RF profile/calibration changes, particularly transitions across Lowband.
3. Determine when the current bandwidth/video state can be retained, and how incompatible or unknown state selects the safe reacquisition path.
4. Implement an isolated source change only after the relevant preconditions are understood. Compare it with the working Favorites baseline in bounded emulator checks and real-device measurements.
5. Check image correctness, loss-of-signal recovery, recording and persistent selection alongside switching latency. Document the measured benefit and limitations before adoption.

## Initial timing findings (2026-10-10, static analysis, Claude)

Entry condition is now met (v5/v6 accepted on the device, restore demonstrated). User observation after a scan lock: black screen, a pause, then picture, about 2 s.

- `3D7C` is a busy-wait `delay(n)`: n outer passes of a fixed 2,746-iteration inner loop. With a ~1T 8051 core this is plausibly milliseconds; the clock is not established. All 20 literal call sites: `delay(20)` ×9 in the settings save (`9F2F..A0DD`), `delay(250)` per scan entry (`702F`), `delay(1000)` once in the startup sequence (`5E31`, next to the version display), `delay(20/10/50)` elsewhere.
- **Channel step** (`06D6`) calls the settings save `9F29` **before** the receiver refresh `61D2`. The save writes nine fields to device `50`, each preceded by `delay(20)`: about 180 delay units before tuning starts on every button press. Candidates: save only the selection, save after the refresh, or shorten the delays (EEPROM write-cycle requirements must be respected).
- **Scan**: 12 entries × (full `0C74` tune + `delay(250)`) ≈ 3 s per pass before a result.
- Status module `6426`: elapsed-tick comparisons against 250 (`64D0`), 100 (`69DC`) and 500 (`6A50`) ticks are candidates for signal-detection/mode-decision timers; `6849` (500 ticks) only toggles a port bit (likely an LED). Not yet traced.
- Video lock in the FPGA and MStar format switching (black screen) are outside the receiver code and cannot be shortened here.

## Acceptance

- Demonstrated latency reduction on the Monitor for defined compatible cases.
- Correct tuning across all eight Favorites, including Lowband transitions.
- Reliable fallback for incompatible formats and signal loss.
- No regression in Favorites navigation, saved settings, display or recording.
- Reproducible source build, experimental package and verified rollback to the tested Favorites baseline.
