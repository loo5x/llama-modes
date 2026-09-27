# llama-modes v0.4.0

Structured LLM inference modes for llama.cpp.

Release text prepared for owner review. Publishing, tagging, uploading binaries, and changing repository settings are separate manual steps.

## Progression

| Milestone | Added behavior |
| --- | --- |
| v0.1 | Direct single-token decision scoring with candidate-relative probabilities |
| v0.2 | Native messages and template-aware direct evaluation at the assistant content boundary |
| v0.3 | Arbitrary multi-token choices with teacher-forced SUM and MEAN log scores |
| v0.3.1 | Correctness-first fresh prompt re-prefill between later multi-token candidates |
| v0.4 | Discrete ordinal and interval SCALE distributions and derived summaries |

`/decision` and `/scale` generate zero answer tokens by design. Multi-token scoring still evaluates forced prefixes and may repeat prompt processing. Normal llama-server chat/completion behavior remains available.

## Public project surface

A llama-modes landing page, Windows quick start, 15-recipe cookbook, detailed API and limitations documents, runnable Python/PowerShell/curl examples, a local React demo, and a reproducible sequential direct/chat harness accompany this release preparation. The demo includes editable symbolic scale mappings, distributions, presentation mode, raw JSON, and honest handling of unparseable chat answers.

## Validation scope

Preserved runtime history reports GPT-OSS 20B MXFP4 and Qwen3.8 Ridge validation, including a Windows CUDA build and RTX 5080 runtime checks. These are tested configurations, not evidence of universal model/backend/template compatibility. See [decision runtime history](tools/server/README.md#post-decision-and-v1decision-score-text-choices), [SCALE experiment scope](experiments/scale_v04/README.md), and the [correctness diagnostic report](experiments/scale_v04/stage2c/REPORT.md). Experimental v0.3 measurements must not be relabeled as v0.4 endpoint validation. The production SCALE contract and its regression cases are visible in [server tests](tools/server/tests/unit/test_completion.py).

This public-polish change does not rerun the historical GPU validation or build C++ binaries. Confirm the final v0.4.0 runtime artifact and its model smoke checks before publishing it. No new performance result is claimed by these notes.

## Interpretation

Candidate/scale weights are not calibrated confidence. Direct evaluation is not equivalent to autoregressive reasoning and is not promised to improve accuracy or latency universally. SCALE is discrete; interval summaries depend on a caller assertion about meaningful distances. Strict token-prefix collisions are rejected. Labels and mappings remain representation-sensitive.

## Downloads

The intended public package is a Windows CUDA runtime ZIP containing `llama-server.exe` and required runtime DLLs, together with appropriate license notices. Users provide their own GGUF model. Publish its GPU/driver requirements, checksum, and exact source commit alongside the actual asset. GitHub Actions artifacts are not the long-term user download mechanism.

[Release index](https://github.com/loo5x/llama-modes/releases) | [Quick start](docs/quickstart.md) | [Migration checklist](docs/upstream.md#public-landing-page-and-release-migration-manual)

No asset URL is asserted here before publication. Validated binaries for other platforms are not promised.

## Based on llama.cpp

llama-modes is a fork/extension of [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp), retaining its runtime/model/backend foundation, license, attribution, and source history. See [LICENSE](LICENSE) and [upstream notes](docs/upstream.md).
