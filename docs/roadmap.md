# Roadmap

## v0.5 — Shared-context multi-question evaluation

Evaluate multiple Boolean, Choice, and Scale questions against the same
input while sharing the common prompt/context evaluation.

Goals:

- one shared context, many structured questions
- mixed Boolean, Choice, and Scale questions in one request
- avoid repeated prompt processing
- structured combined response
- preserve the semantics and diagnostics of the existing modes

The exact API and execution strategy are still under design.
