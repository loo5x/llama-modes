# Release status

## Current release - v0.5.0

Evaluate multiple Boolean, Choice, and Scale questions against the same input with optional reuse of common prompt processing.

Released capabilities:

- one shared context, many structured questions
- mixed Boolean, Choice, and Scale questions in one request
- optionally reuse eligible batch-aligned common prompt prefixes
- structured combined response
- preserve the semantics and diagnostics of the existing modes

The direct-server `/evaluate` API and batch-aligned sharing path are implemented. Sharing requires `--evaluate-shared-prefix` in addition to `--evaluate`; fresh scoring remains the default. Windows CUDA validation on GPT-OSS 20B covers same-configuration score equivalence, cancellation, shutdown/restart, sleep/wake, selected limits, and 100 repeated evaluation/chat pairs.

The Windows 0.5.0 package has passed checksum, extraction, numerical, chat, and clean shutdown checks on the tested RTX 5080 configuration. The [normal v0.5.0 release](https://github.com/loo5x/llama-modes/releases/tag/v0.5.0) is public, and final validation evidence is saved. Other models/backends, allocation/decode failure injection, and broader performance measurements remain separate work. See [v0.5.0 release notes](../RELEASE_NOTES_v0.5.0.md) and [validation results](../experiments/shared_context_v05/HTTP-SHARED-VALIDATION.md).
