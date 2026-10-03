# llama-modes v0.5.0 - preparation notes

Multiple independent evaluations over a shared context.

These notes describe the validated experimental feature. A clean-folder runtime check passed; extraction of the final versioned ZIP, tagging, and public release remain pending. The tested runtime commit is `427d6bdfdd0f0568c4d1bf76fd58a9589cec208d`, built in Actions run `37066508221`.

## Windows package preparation

The Windows workflow accepts `release=true` to build version `0.5.0`; ordinary builds use `0.5.0-dev`. This does not tag or publish a release. The package includes runtime instructions, licenses/notices, and a manifest recording the source commit, Actions run, and file hashes. A separate SHA-256 file accompanies the versioned ZIP. The final archive still requires checksum, extraction, version, and runtime validation after the build.

The [clean-folder check](experiments/shared_context_v05/HTTP-CLEAN-INSTALL-VALIDATION.md) used the earlier binaries on the existing Windows installation, with a minimal environment and a path containing spaces. It confirmed independent loading of packaged DLLs, evaluation/chat results, and clean shutdown. It did not test the final ZIP or a fresh Windows installation.

## Added behavior

`POST /evaluate` and `/v1/evaluate` accept one text and 1..32 independent Boolean, Choice, or Scale questions, returning one structured response. Enable the endpoint with `--evaluate`. Add `--evaluate-shared-prefix` to reuse complete batches from the common tokenized prompt prefix. Sharing remains optional; fresh scoring is the default and the fallback for ineligible requests. Existing decision/scale score semantics and normal chat remain available.

The response reports the execution strategy, reused token count, batch settings, and any fallback reason. Questions and candidate branches are isolated. No answer text is generated, and weights remain representation-sensitive rather than calibrated confidence. See the [API](docs/evaluate.md) and [Windows example](docs/quickstart.md#8-v05-multiple-questions-optional).

## Validated configuration

GPT-OSS 20B MXFP4, Windows CUDA, RTX 5080, context 4096, with batch/microbatch 128 and 512 for numerical comparisons. Shared and fresh response results matched exactly within each configuration. The independent native oracle comparisons passed. Lifecycle checks at batch 128 covered cancellation, admission, queued chat, shutdown/restart, sleep/wake, selected request limits, and 100 evaluation/chat pairs.

Preliminary repeated-request timings on the three-question fixture were 2.167 versus 0.312 seconds at batch 128, and 1.134 versus 0.230 seconds at batch 512, fresh versus shared. Only two calls per mode/configuration were timed; this is not a general performance benchmark or a guarantee. [Full evidence and limitations](experiments/shared_context_v05/HTTP-SHARED-VALIDATION.md).

## Boundaries

Direct-server only. Unsupported configurations include recurrent/hybrid models, multimodal input, adapters, control vectors, and speculative decoding. One evaluation is admitted at a time and can delay queued chat. The main context remains resident while evaluation allocates temporary memory. Inputs are neither truncated nor shifted, and execution failures do not silently change batch size or return partial success.

Other deployed model/backend configurations, injected allocation/decode failures, GPU-specific memory accounting, and long-duration workloads remain outside this validation. No public artifact or final release version is asserted by these preparation notes.
