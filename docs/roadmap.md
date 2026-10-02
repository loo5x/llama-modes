# Roadmap

## v0.5 - Shared-context multi-question evaluation

Evaluate multiple Boolean, Choice, and Scale questions against the same input with optional reuse of common prompt processing.

Goals:

- one shared context, many structured questions
- mixed Boolean, Choice, and Scale questions in one request
- avoid repeated prompt processing
- structured combined response
- preserve the semantics and diagnostics of the existing modes

The direct-server `/evaluate` API and batch-aligned sharing path are implemented. Sharing requires `--evaluate-shared-prefix` in addition to `--evaluate`; fresh scoring remains the default. Windows CUDA validation on GPT-OSS 20B covers same-configuration score equivalence, cancellation, shutdown/restart, sleep/wake, selected limits, and 100 repeated evaluation/chat pairs.

Next: preserve validation evidence, finish the user documentation, and verify a clean runtime package before release. Other models/backends, allocation/decode failure injection, and broader performance measurements remain separate work. See [v0.5 preparation notes](../RELEASE_NOTES_v0.5.0.md) and [validation results](../experiments/shared_context_v05/HTTP-SHARED-VALIDATION.md).
