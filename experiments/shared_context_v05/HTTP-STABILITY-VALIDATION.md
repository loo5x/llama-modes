# Sleep, limits, and repeated-use validation

2026-10-02. Windows CUDA build `42b3feba407f0183f588098d349ddb6de86e98bf`, Actions run `37041909852`, GPT-OSS 20B MXFP4 on RTX 5080. Batch/microbatch 128, context 4096, one chat slot, eight HTTP threads. The runner verifies runtime and model hashes before starting owned servers in hidden consoles.

Runner: `http_stability_validation.py`. Evidence: `build/shared-v05/http-stability-gpu-r2`. The initial attempt in `http-stability-gpu` passed three sleep cycles and the 32-question request, then stopped on a Python event-recording argument collision. That harness error was corrected; it was not a server failure. The initial server exited cleanly through Ctrl+C.

## Method

Three sleep cycles use a three-second idle threshold. Health, model listing, and properties must remain available without waking the model. Evaluation wakes the model in two cycles; ordinary completion wakes it in the other. Evaluation results and fresh completion tokens must exactly match the earlier lifecycle baseline after each wake.

Nine limit cases check 32/33 questions, 128/129-byte IDs, text above 1 MiB, 256/257 choices, and prepared prompts of exactly 4096/4097 tokens with single-token candidates. Prompt size is measured through native template rendering and tokenization. Every case is followed by a baseline evaluation and completion to check recovery; rejected requests must have no partial results.

A separate server with sleep disabled alternates 100 evaluations with 100 fresh completions. Every response is checked against the prior baseline. After each pair, Windows process private bytes and working set are recorded with latency. These are host-process memory measurements, not GPU memory measurements. A finite run cannot prove that no leak exists.

Both servers receive Ctrl+C after their work and must exit with code zero without forced termination. No production code is changed by this validation.

## Results

The complete rerun exited successfully and wrote `summary.json` with `passed: true`. All three sleep/wake cycles and all nine limit cases passed. Wake plus baseline checks took 5.684, 5.704, and 5.675 seconds. The health and model-listing checks did not wake the sleeping server.

All 100 evaluation/completion pairs matched the baseline exactly. Pair latency had a median of 0.469 seconds and a maximum of 0.501 seconds. Private bytes increased by 2.215 MiB from the first to the last sample, mainly during the initial cycles. Across the final 60 cycles the private-byte range was only 4096 bytes, consistent with a plateau over this observation window. This is not a proof of leak freedom, and GPU allocations were not measured separately.

Both phase servers exited normally on Ctrl+C: 1.246 seconds after sleep/limits and 1.197 seconds after repeated use. No server process was left running. No rebuild or production change was needed.

## Scope

This stage covers selected request limits and the stated model/backend configuration. It does not inject allocation/decode failures or exhaust GPU memory. It does not establish numerical equivalence across different batch sizes, cached versus fresh chat processing, other models, or other backends. Shared-prefix execution remains a separate feature.
