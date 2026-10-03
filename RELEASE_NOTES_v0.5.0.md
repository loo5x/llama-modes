# llama-modes v0.5.0 - release notes

Multiple independent evaluations over a shared context.

These notes describe the validated experimental feature. The Windows 0.5.0 ZIP passed checksum, extraction, file identity, numerical, chat, and clean shutdown checks on the existing RTX 5080 machine. Its runtime commit is `a02fe9f1ed3214ddaceac3630431fd592371abd3`, built in Actions run `37126739509`. [v0.5.0 is published as a normal release](https://github.com/loo5x/llama-modes/releases/tag/v0.5.0); `/evaluate` remains experimental. The broader earlier feature validation used runtime commit `427d6bdfdd0f0568c4d1bf76fd58a9589cec208d`.

## Published Windows package

Download `llama-modes-v0.5.0-win-cuda.zip` and its `.sha256` file from the release page. The package targets Windows x64 and CUDA architecture 120; validation used RTX 5080.

The Windows workflow accepts `release=true` to build version `0.5.0`; ordinary builds use `0.5.0-dev`. This does not tag or publish a release. The package includes runtime instructions, licenses/notices, and a manifest recording the source commit, Actions run, and file hashes. A separate SHA-256 file accompanies the versioned ZIP. The final archive passed those checks on 2026-10-03; see the package validation section in the clean-folder report.

The [clean-folder report](experiments/shared_context_v05/HTTP-CLEAN-INSTALL-VALIDATION.md) records both the earlier reconstruction and the final ZIP extraction. The final check used a minimal environment and a path containing spaces. It confirmed independent loading of packaged DLLs, evaluation/chat results, and clean shutdown. This was not a fresh Windows installation.

## Added behavior

`POST /evaluate` and `/v1/evaluate` accept one text and 1..32 independent Boolean, Choice, or Scale questions, returning one structured response. Enable the endpoint with `--evaluate`. Add `--evaluate-shared-prefix` to reuse complete batches from the common tokenized prompt prefix. Sharing remains optional; fresh scoring is the default and the fallback for ineligible requests. Existing decision/scale score semantics and normal chat remain available.

The response reports the execution strategy, reused token count, batch settings, and any fallback reason. Questions and candidate branches are isolated. No answer text is generated, and weights remain representation-sensitive rather than calibrated confidence. See the [API](docs/evaluate.md) and [Windows example](docs/quickstart.md#8-v05-multiple-questions-optional).

## Validated configuration

The [Correctness & Validation overview](README.md#correctness--validation) separates regression thresholds from observed differences and links the automated tests, local numerical evidence and lifecycle reports.

GPT-OSS 20B MXFP4, Windows CUDA, RTX 5080, context 4096, with batch/microbatch 128 and 512 for numerical comparisons. Shared and fresh response results matched exactly within each configuration. The independent native oracle comparisons passed. Lifecycle checks at batch 128 covered cancellation, admission, queued chat, shutdown/restart, sleep/wake, selected request limits, and 100 evaluation/chat pairs.

Preliminary repeated-request timings on the three-question fixture were 2.167 versus 0.312 seconds at batch 128, and 1.134 versus 0.230 seconds at batch 512, fresh versus shared. Only two calls per mode/configuration were timed; this is not a general performance benchmark or a guarantee. [Full evidence and limitations](experiments/shared_context_v05/HTTP-SHARED-VALIDATION.md).

## Boundaries

Direct-server only. Unsupported configurations include recurrent/hybrid models, multimodal input, adapters, control vectors, and speculative decoding. One evaluation is admitted at a time and can delay queued chat. The main context remains resident while evaluation allocates temporary memory. Inputs are neither truncated nor shifted, and execution failures do not silently change batch size or return partial success.

Other deployed model/backend configurations, injected allocation/decode failures, GPU-specific memory accounting, and long-duration workloads remain outside this validation. The published ZIP retains the documentation from its build commit; these source notes record the subsequent validation and publication status.
