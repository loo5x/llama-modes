# Windows HTTP shutdown validation

2026-10-02. Build `ab08e0a3a95a93277917763de4ccee3255949db0`, Actions run `37032809537`, GPT-OSS 20B MXFP4, RTX 5080, batch/microbatch 128, context 4096, one chat slot, eight HTTP threads. Runtime and model hashes matched before execution.

## Method

`http_shutdown_validation.py` creates a separate hidden Windows console for each owned server process. A helper sends `CTRL_C_EVENT` to that console only. The helper ignores the event after starting the server; the server uses its normal Windows handler. The test keeps client connections open while waiting for shutdown. A 30-second deadline triggers forced termination of the owned process, recorded as a failure rather than a successful shutdown.

Each scenario starts on the same localhost port and first checks a small evaluation and a fresh completion against the preceding lifecycle baseline. The active-evaluation cases wait for context allocation and confirm a second evaluation receives HTTP 503. The queued-chat case verifies that chat has not returned before shutdown. The pending-evaluation case confirms the chat slot is busy. The final restart scenario verifies evaluation and completion results again.

## Findings

The initial run in `build/shared-v05/http-shutdown-gpu` passed idle shutdown but required forced termination with an active evaluation and queued chat. The complete diagnostic run in `build/shared-v05/http-shutdown-gpu-r2` wrote `summary.json` with `passed: false` and these results:

| Scenario | Result |
| --- | --- |
| Idle after baseline requests | Clean exit, code 0, 1.184 seconds |
| Ordinary streaming chat only | Forced termination after the 30-second deadline |
| Active evaluation only | Forced termination after the 30-second deadline |
| Active evaluation with queued chat | Forced termination after the 30-second deadline |
| Evaluation pending behind streaming chat | Forced termination after the 30-second deadline |
| Final restart and baseline requests | Results matched; clean idle exit, code 0, 1.088 seconds |

The ordinary-chat control confirms that the failure is not specific to `/evaluate`. Every restart reused the same port successfully, and baseline evaluation and chat outputs matched in all six scenarios. No test server was left running. Timing includes process exit and is an observation, not a guarantee.

Source inspection explains the observed wait: the signal stops the inference queue, then cleanup stops the HTTP listeners and joins HTTP workers. `httplib::Server::stop()` closes the listening socket. Existing requests use `req.is_connection_closed` as their stop condition, which tests the individual client socket. A connected client can therefore leave a reader waiting for results after inference has stopped, preventing HTTP worker shutdown. The ordinary-chat control tests whether this behavior is specific to evaluation.

The previously validated disconnect timeout fix remains separate: it allows disconnect checks to run, but a still-connected client does not satisfy that check during server shutdown.

## Source fix

The HTTP context now records shutdown in an atomic flag before stopping its listeners. The GET, POST, and DELETE request stop callbacks check that flag as well as client disconnection. Requests own their callback by value so the composed callback remains valid for streaming responses. The existing polling path can then finish waiting readers and allow the HTTP worker pool to join. The flag resets when the HTTP context starts.

The existing `test_chat_completion.py` now contains a two-case regression test: keep an ordinary chat stream connected, optionally admit an evaluation behind it, send SIGINT, and require a zero process exit within ten seconds before closing the client sockets. These cases run in the Linux CPU Actions job through the existing `evaluate` selector. Windows skips this Python test because the standard test fixture creates detached processes; the separate hidden-console runner above covers Windows Ctrl+C.

The fix was committed as `42b3feba407f0183f588098d349ddb6de86e98bf` with the human-supplied message `fix forced stop` and built by Actions run `37041909852`. All runtime hashes, the matching oracle hash, and the model hash were verified. The local CPU JUnit report was not available for inspection.

## Corrected Windows build

The unchanged runner completed successfully in `build/shared-v05/http-shutdown-fixed`, with `passed: true`. All six scenarios exited with code 0 and `forced: false`:

| Scenario | Exit time, seconds |
| --- | --- |
| Idle | 1.089 |
| Ordinary streaming chat | 2.221 |
| Active evaluation | 2.119 |
| Active evaluation with queued chat | 1.952 |
| Evaluation pending behind streaming chat | 2.224 |
| Final restart | 1.091 |

Baseline evaluation and fresh chat results matched before every shutdown. Each restart reused the same port. The four formerly failing scenarios now exit while the client connections remain open. These are measured results for the configuration above, not universal shutdown latency guarantees.

The existing lifecycle suite also passed unchanged on this build in `build/shared-v05/http-lifecycle-shutdown-fixed`, covering three active cancellations, one pending cancellation during streaming chat, successful evaluation with queued chat, and final recovery. Idle chat state remained byte-identical. All owned test servers were stopped.

## Scope

This tests one Ctrl+C event and direct-server shutdown on Windows CUDA. It does not test a second interrupt, router shutdown, service-manager shutdown, sleep/wake, or other models and backends. Forced process exits are explicitly recorded and are not evidence of clean resource cleanup.
