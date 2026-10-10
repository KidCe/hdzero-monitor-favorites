# PicoScope MCP evaluation

Reviewed on 2026-10-09 for the connected PicoScope 2205A. Recommendation: **do not install this repository unchanged for the current Monitor work.** Its MCP structure is useful scaffolding, but a working 2205A backend and several correctness repairs would be needed first.

## Scope and provenance

Source-only review of `markuskreitzer/picoscope_mcp` at commit [`450249997e8ff80728b98892b4f67072491b51e5`](https://github.com/markuskreitzer/picoscope_mcp/tree/450249997e8ff80728b98892b4f67072491b51e5). The checkout is retained privately under `artifacts/firmware-analysis/20261009-picoscope-mcp-review/source`. No upstream code, tests or dependencies were executed or installed; no hardware access, MCP configuration changes or firmware writes occurred in this evaluation. This note was produced with substantial assistance from OpenAI Codex; see the [project disclosure](../../README.md#ai-assistance-disclosure).

## Compatibility and concrete defects

The manager imports and calls **ps5000a only**, opens at 12-bit resolution and reports four channels. No ps2000 backend exists. `current_device` stays `None` after successful `connect()`, so `is_connected()` remains false. Configuration/capture tools reject the connection; the public disconnect tool also returns before closing the open handle. Failed connection setup discards its handle without guaranteed cleanup. Discovery catches exceptions as an empty list and closes discovered devices without `finally`. [Pinned manager](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/device_manager.py#L7-L169), [public disconnect](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/tools/discovery.py#L122-L159).

Capture polls readiness without a deadline, sleep or status check; no acquisition `finally` guarantees stop. It ignores returned sample count and overflow, hardcodes ADC maximum 32767, truncates interval metadata to integer nanoseconds, and uses timebase zero followed by a search through 100. Analog offset is converted to ADC counts rather than passed as volts. These are source findings, not hardware-tested failures. [Pinned capture/configuration](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/device_manager.py#L225-L485), [Pico's official SetChannel binding](https://github.com/picotech/picosdk-python-wrappers/blob/master/picosdk/ps5000a.py#L293-L303).

Our local capture uses the distinct legacy ps2000 functions. Pico's official bindings show different open, channel, timebase and retrieval signatures; swapping the imported driver is insufficient. [Official ps2000 binding](https://github.com/picotech/picosdk-python-wrappers/blob/master/picosdk/ps2000.py#L87-L216), [local capture](../../tools/picoscope_ch341_capture.py).

## Advertised versus implemented tools

| Area | Actual pinned implementation |
| --- | --- |
| Discovery/connect/channel/edge trigger/block capture | Real driver-call code, subject to the backend and connection-state defects above. |
| Requested timebase | Informational return only; requested interval is not stored/applied. |
| Streaming start/stop/data | MCP tools return `not_implemented`. |
| Frequency/amplitude | Return instructions, not numerical measurements from a retained capture. |
| Rise time, pulse width, FFT, statistics, THD | Return `not_implemented`. |
| Signal generator, math channels, file export, downsampling | Return `not_implemented`. |

Sources: [configuration](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/tools/configuration.py#L115-L162), [acquisition](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/tools/acquisition.py#L127-L173), [analysis](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/tools/analysis.py), [advanced](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/tools/advanced.py).

No probe attenuation field exists in channel/trigger/capture models or tools. A physical 10x probe therefore requires explicit external scaling; an input reading near 0.326 V must become approximately 3.26 V at the probe tip. [Models](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/models.py), [configuration interface](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/tools/configuration.py#L11-L37).

Block capture returns full time and voltage arrays inline for each channel, with no configured sample cap or artifact export. The default is 2000 samples per channel; larger requests enlarge both acquisition allocation and MCP response. There is no bounded summary mode. [Capture tool](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/tools/acquisition.py#L74-L125).

Startup registers tools and starts STDIO; repository code does not open a scope or activate its generator automatically. Generator tools are placeholders. Missing-PicoSDK warnings use ordinary `print()` during import, which can contaminate STDIO MCP protocol output. [Server](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/server.py), [import handling](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/src/picoscope_mcp/device_manager.py#L7-L16).

The two included tests check manager initialization and discovery's list return type. Discovery can access hardware when drivers are present. There are no fake-driver capture, conversion, timeout or cleanup tests. They were not run in this review. [Tests](https://github.com/markuskreitzer/picoscope_mcp/blob/450249997e8ff80728b98892b4f67072491b51e5/tests/test_tools.py).

## Recommendation for this project

Continue current SCK/CS measurements with [our 2205A capture script](../../tools/picoscope_ch341_capture.py): it already applies the user-confirmed 10x factor, uses the ps2000 API, checks DLL/device identity, limits captures, records overflow/counts, imposes a readiness deadline, stops/closes devices, and saves CSV evidence plus compact summaries. This narrow script is not a general scope application and its native open/driver calls are not all cancellable; MCP wrapping alone would not change those limitations.

If reusable MCP operation becomes a separate task, build a small measurement-only interface around the reviewed 2205A backend, with configurable probe factor/range/trigger/timebase, bounded artifact results, explicit device ownership and cleanup, and fake-driver plus physical validation. Keep any CH341 excitation an explicit isolated-adapter operation, separate from general scope acquisition. Installing upstream unchanged offers no immediate benefit for this hardware.
