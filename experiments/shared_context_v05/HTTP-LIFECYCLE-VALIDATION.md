# HTTP lifecycle validation and pending-cancellation fix

2026-10-02. Initial Windows CUDA build `c67d458780b697856c207a7d0019446c64349e47` from Actions run `36997055966` reproduced the failure below. The corrected build `ab08e0a3a95a93277917763de4ccee3255949db0` from Actions run `37032809537` passed the full lifecycle rerun. Both used GPT-OSS 20B MXFP4 on RTX 5080, batch/microbatch 128, context 4096, one chat slot, and eight HTTP threads. Runtime and model hashes were verified before execution.

## Corrected build validation

The lifecycle suite also passed unchanged on shutdown-fix build `42b3feba407f0183f588098d349ddb6de86e98bf`, Actions run `37041909852`. Evidence is in `build/shared-v05/http-lifecycle-shutdown-fixed`. Active cancellation recovery took 0.646, 0.649, and 0.679 seconds; pending cancellation, successful overlap, final baseline checks, and byte-identical idle chat state all passed. No cancellation regression was observed in this configuration.

Evidence is in `build/shared-v05/http-lifecycle-fixed`. The runner exited successfully and wrote `summary.json` with `passed: true`. All 12 runtime file hashes matched the build manifest, the manifest commit matched local HEAD, and the separate oracle executable hash matched the manifest.

- Three active-disconnect cycles passed, with queued chat recovery in 0.640, 0.653, and 0.691 seconds.
- A completed evaluation released queued chat, and repeated evaluation results matched exactly.
- Disconnecting a pending evaluation released admission while the other chat was still streaming. A replacement evaluation was admitted and waited for the chat to stop, then completed successfully. This is the scenario that failed on the original build.
- Final chat and evaluation checks passed. Serialized idle chat state retained the same hash as the original run.

These timings are observations, not latency guarantees. The new CPU JUnit report was not available locally for inspection. The test server was stopped by the runner after completion.

## Passed on the existing build

- An active evaluation rejects a second evaluation with HTTP 503.
- Ordinary completion waits while evaluation is active and resumes after cancellation. Three consecutive active-cancellation cycles passed in each of the two completed diagnostic sequences.
- Recovery in the final sequence took 1.037, 2.089, and 1.061 seconds from disconnect through receiving the waiting completion. These are observations, not latency guarantees.
- A completed evaluation releases queued chat normally; its output matches a subsequent standalone evaluation exactly.
- Small evaluation results remain exactly equal after cancellations and queued completions.
- Serialized idle chat state before and after an independent evaluation is byte-identical: SHA-256 `f2ca647a8a0c14f8591d3c7e83049c4b3213d00d50898772f0b119cd74e6544d`.

## Reproduced failure

Start a long streaming completion in the only chat slot. Admit an evaluation, which waits for that slot to drain. Disconnect the evaluation client while the chat continues streaming. After 5.312 seconds, a replacement evaluation still receives HTTP 503, with the chat confirmed active. Stop the streaming chat: the cancelled evaluation then releases admission and a fresh evaluation succeeds.

The affected code is `server_response::recv_with_timeout()` in `tools/server/server-queue.cpp`. It waits on the shared result condition variable with a new `wait_for(timeout)` on every loop iteration. Results for another request wake the wait and restart its full timeout. Continuous streaming results therefore prevent the waiting evaluation's HTTP reader from reaching its disconnect check. This is a shared queue behavior, not an evaluation arithmetic problem.

The local fix calculates one `steady_clock` deadline before the loop and uses `wait_until(deadline)`. Notifications still allow matching results to be consumed, but unrelated results cannot extend the disconnect polling deadline indefinitely. No request format or scoring change is involved.

A regression test was added to the existing `test_chat_completion.py`: keep a chat stream active, disconnect a waiting evaluation, then verify a replacement can be admitted before stopping that stream. The existing Actions test selector includes this test automatically. No new test file was added.

## Test controls and earlier attempts

The first harness attempt allowed a short admission probe to overtake the long request; the server correctly rejected the second arrival. Active tests now wait for the evaluation context allocation in the log before probing.

A second attempt compared an initial chat prefill with a cached repeat and observed different generated tokens. A control with three ordinary cached chat requests, before any evaluation, reproduced that difference. The final harness uses fresh prompt processing for chat output comparisons and separately checks serialized idle chat state. It does not claim cached and fresh generation are numerically equivalent or diagnose the broader cache behavior.

The pending-disconnect problem was observed in run r3 after a two-second wait and confirmed in r4 after a five-second wait, with explicit recovery only after the stream stopped. These runs are not reported as a fully passing lifecycle suite.

## Evidence and remaining work

Runner: `http_lifecycle_validation.py`. Raw logs, requests, state snapshots, timings, and failure evidence are in `build/shared-v05/http-lifecycle-gpu-r4`; prior attempts are retained in the neighboring directories. Reproduce with a new output directory:

```powershell
python experiments/shared_context_v05/http_lifecycle_validation.py --output build/shared-v05/http-lifecycle-next
```

The corrected C++ was committed with the human-supplied message `fix wait time`, built through GitHub Actions, and verified with the new binary as described above. Pending cancellation passed in this tested configuration. Sleep/wake, shutdown, allocation failure, other models, and shared-prefix execution remain outside this stage.
