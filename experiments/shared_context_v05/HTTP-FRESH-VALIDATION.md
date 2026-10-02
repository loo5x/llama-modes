# Fresh-only HTTP validation on Windows CUDA

2026-10-02. Build `c67d458780b697856c207a7d0019446c64349e47`, GitHub Actions run `36997055966`. The 12 packaged runtime files and the separate native oracle executable match their SHA-256 entries in the build manifest. The model hash matches the preserved GPT-OSS 20B MXFP4 fixture identity.

The fresh-only `/evaluate` endpoint passes this first local GPU check on GPT-OSS and the RTX 5080. Verbose batch-512 logs confirm CUDA0 and all 25 model layers offloaded to the GPU. This follows the separate CPU report with 10 tests passed and no failures, errors, or skips.

| Batch / microbatch | Questions | Candidate comparisons | Maximum checked difference |
| --- | ---: | ---: | ---: |
| 128 / 128 | 3 | 11 | 5.551115123125783e-17 |
| 512 / 512 | 3 | 11 | 0 |

Each run uses the preserved 24-record context with independent Boolean, Choice, and interval Scale questions. Candidate labels include strict-prefix overlap in Choice and signed numeric Scale labels. The endpoint evaluates 11 candidates per request; three requests are executed per batch: original order, reversed question/candidate order, and an unchanged repeat. Responses match exactly after restoring request order.

The independent `test-save-load-state.exe` oracle was executed once for each question at each batch size, six invocations total. Full prompts were prepared through the two native content-entry probes and tokenized by the same server. Candidate labels were tokenized independently without special tokens. The server was stopped before running the oracle to avoid loading a second model concurrently.

SUM and MEAN scores for sequence responses match exactly. Boolean single-token candidate-relative probabilities match the oracle's softmax of full-vocabulary log probabilities. Scale SUM-relative weights differ only by at most 5.551115123125783e-17 at batch 128. Raw Boolean logits are not compared by this oracle, which emits token log probabilities rather than raw logits. The API does not expose per-token score vectors, so those vectors are preserved from the oracle but cannot be compared directly to HTTP output.

Both runs also reject an oversized final question with HTTP 400 and successfully serve a normal completion afterward. Runtime settings use context 4096, f16 KV, full SWA, Flash Attention on, 99 requested GPU layers, and eight threads. The endpoint reserves three sequences/outputs; the existing oracle runs with one sequence and its default output reservation, as in previous oracle checks. Comparisons are within each batch configuration, not between batch sizes.

The first oracle launch rejected two server-only CLI options (`--kv-unified` and `--no-warmup`). The runner was corrected to omit those for the oracle and use `-np 1`, which enables unified KV in that executable. These argument errors occurred before oracle inference. Batch-128 HTTP evidence was retained and only its oracle stage resumed; batch 512 then completed from start to finish.

## Reproduction and evidence

```powershell
python experiments/shared_context_v05/http_fresh_validation.py --output build/shared-v05/http-fresh-gpu-b128 --batch 128
python experiments/shared_context_v05/http_fresh_validation.py --output build/shared-v05/http-fresh-gpu-b512 --batch 512
```

Use new output directories for reruns. The existing directories contain the exact server/oracle commands, identity checks, input/prepared prompts, HTTP responses, oracle token-score vectors, numerical summaries, and process logs. The batch-128 directory contains the initial runner snapshot; the batch-512 snapshot includes the corrected oracle arguments. `--oracle-only` can resume the comparison stage of an existing run with matching runtime/model identity and batch settings.

This initial run validates one GPT-OSS fixture at two batch sizes. Later cancellation, shutdown, sleep/wake, capacity, and repeated-use checks are indexed in [HTTP-VALIDATION.md](HTTP-VALIDATION.md). Allocation failure and other models remain untested. No shared-prefix path has been enabled. Production source and the installed v0.4 package were not modified during this validation.
