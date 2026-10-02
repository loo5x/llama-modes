# Shared-prefix HTTP validation

2026-10-02. Build `427d6bdfdd0f0568c4d1bf76fd58a9589cec208d`, Actions run `37066508221`, GPT-OSS 20B MXFP4 on RTX 5080. The installed runtime and oracle hashes matched the manifest; model identity was verified before the tests. The local CPU JUnit report was not available for direct inspection.

## Scores and preliminary timings

The mixed fixture contains three independent Boolean, Choice, and interval Scale questions, with eleven total candidates. Both fresh and shared HTTP modes were tested on the same build at batch/microbatch 128 and 512. Complete prepared token inputs and response results match exactly between modes within each configuration. Original, reversed, and repeated requests pass. Oversized final questions return HTTP 400, followed by successful ordinary completion.

| Batch/microbatch | Shared tokens | Shared versus fresh result difference | Maximum oracle difference |
| --- | ---: | ---: | ---: |
| 128/128 | 768 | 0 | 5.551115123125783e-17 |
| 512/512 | 512 | 0 | 0 |

The independent native oracle ran for each question in each mode/configuration: twelve invocations and 44 candidate comparisons. Sequence SUM and MEAN scores match exactly; the small oracle difference at batch 128 is in derived candidate-relative weights. Raw Boolean logits are compared between HTTP modes, not against the oracle's token-log-probability output. HTTP still does not expose per-token vectors. These checks do not establish equality across different batch sizes.

The runner records the original and repeated `/evaluate` call durations, excluding startup, prompt preparation, and oracle work. Reversed requests use `/v1/evaluate` and are checked for correctness but are not in these timing samples.

| Batch | Fresh first/repeat, seconds | Shared first/repeat, seconds | Repeat fresh/shared ratio |
| --- | --- | --- | ---: |
| 128 | 2.225 / 2.167 | 0.401 / 0.312 | 6.94 |
| 512 | 1.190 / 1.134 | 0.327 / 0.230 | 4.94 |

These are preliminary observations from two timed calls per mode/configuration, not a general benchmark or latency guarantee. Runs were sequential, not randomized. Reused prompt work and fewer context allocations both contribute; this does not isolate their individual costs.

Evidence directories under `build/shared-v05`: `http-shared-b128`, `http-current-fresh-b128`, `http-shared-b512`, `http-current-fresh-b512`. The direct comparison is saved as `http-shared-comparison.json`.

## Lifecycle

`http-lifecycle-shared` passed three active-cancellation cycles, admission rejection, queued-chat recovery, successful overlap, pending cancellation while another chat streams, and final recovery. Active recovery took 0.650, 0.652, and 0.651 seconds. The runner uses two questions for small/medium checks and asserts `shared_aligned` execution. Saved idle chat state retained SHA-256 `f2ca647a8a0c14f8591d3c7e83049c4b3213d00d50898772f0b119cd74e6544d`.

`http-shutdown-shared` passed all six shutdown/restart scenarios with code zero and no forced termination. Baseline shared results match the preserved fresh results. Shutdown times ranged from 1.137 to 2.471 seconds. The test keeps client sockets open until server exit.

## Sleep, limits, and repeated use

`http-stability-shared` used the request/response reference from `http-lifecycle-shared`, including the shared-mode server option. All three sleep/wake cycles and nine limit cases passed, followed by 100 exact-baseline evaluation/completion pairs. The repeated evaluation contains two questions and its execution metadata must match the shared baseline. The context-capacity case with identical 4096-token prompts can intentionally use the empty-suffix fresh fallback.

The process private-byte range was only 4096 bytes across the final 60 cycles; working-set measurements were also retained. Pair latency had a median of 0.295 seconds and a maximum of 0.321 seconds. These are finite host-memory observations, not GPU-specific accounting or proof of leak freedom. Both phase servers exited cleanly with no forced termination. All test-owned servers were stopped after completion.

## Archive and replay

[HTTP-SHARED-BASELINE.json](HTTP-SHARED-BASELINE.json) contains selected JSON records from the seven successful runs, their original file manifests, and the direct fresh/shared comparison. Selected source hashes were verified when archiving. Full logs and binary slot snapshots remain local; their hashes are retained. Parsed data reserialization does not reproduce the original byte hashes.

The numerical runner accepts `--shared-prefix`; omit it for fresh mode. Lifecycle and shutdown runners now accept the same switch and use two-question baseline requests to exercise actual sharing. Stability accepts `--reference build/shared-v05/http-lifecycle-shared` and uses that reference's requests, results, and server command. Without the new options, the historical runner defaults remain available. Use new output directories and the matching runtime/source commit, as described in [the baseline replay notes](HTTP-VALIDATION.md#saved-data-and-local-prerequisites).

## Scope

No production source change was required during these runs. Test runners gained optional shared-mode inputs; existing historical evidence remains unchanged. Allocation/decode failure injection, additional deployed models/backends, GPU-specific memory measurements, and a broader performance benchmark remain outside this validation.
