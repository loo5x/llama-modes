# Proposed /evaluate integration

Status: design for review, 2026-10-02. No endpoint implementation or production configuration change. Source baseline: `6e0c988e784000916e00c87915d47dc3bee6da32` on `feature/shared-context-v05`.

## Decision

Add an experimental, opt-in `/evaluate` endpoint that scores independent Boolean, Choice, and Scale questions against one text context. Use a request-owned inference context with the already loaded model. Keep its decode batches separate from ordinary server slots. Reuse only a batch-aligned prefix of the fully prepared question prompts. Fall back to a fresh context per candidate when sharing is ineligible.

This is a proposal, not a claim that server integration is validated. The scoring algorithm passed [expanded validation](EXPANDED-VALIDATION.md): 648 shared vectors, 192 isolated split comparisons, and 54 independent C++ checks. Concurrent server scheduling, context allocation alongside the main context, cancellation, and memory pressure remain untested.

## Proposed request contract

`POST /evaluate`, alias `/v1/evaluate`. Non-streaming, one combined response. The initial implementation is direct-server only; router proxy support is a later explicit step.

```json
{
  "context": "Record: Paris is in France. Quality rating: high.",
  "questions": [
    {"id": "in-france", "type": "boolean", "question": "Is Paris in France? Answer true or false.", "choices": ["true", "false"]},
    {"id": "city", "type": "choice", "question": "Which city is named? Answer Paris or London.", "choices": ["Paris", "London"]},
    {"id": "quality", "type": "scale", "question": "Rate quality: L=low, M=medium, H=high. Answer one label.", "measurement": "ordinal", "scale": [{"value": 0, "label": "L"}, {"value": 1, "label": "M"}, {"value": 2, "label": "H"}]}
  ]
}
```

Top-level fields are `context`, `questions`, and optional `model` using existing direct-server model handling. Reject unknown fields. Require a non-empty context string and 1..32 questions. Each question has a unique non-empty string `id` (at most 128 UTF-8 bytes), a non-empty `question`, and a lowercase `type`. Reject fields belonging to another type.

- Boolean: exactly two explicit `choices`. This is the existing two-label decision mode; labels do not acquire an implicit true/false mapping. Preserve their order and diagnostics.
- Choice: 1..256 explicit `choices`, with existing decision validation. Strict token-prefix overlap remains allowed.
- Scale: `measurement` and `scale` follow the existing scale contract, including numeric sorting, 2..256 points, unique values/labels, and strict token-prefix rejection.

No raw prompt, messages history, template override, sampling parameters, streaming, tools, media, or request-level batch controls in this initial contract. A label mapping must appear in the question when needed; the server does not inject one. Candidate strings are not inserted into prompts automatically.

For every question, create exactly one user message with content `context + "\n\n" + question`. Apply the existing native content-entry template path, with assistant continuation disabled. Prepare all questions against one template configuration and one captured set of dynamic template inputs, including date. Fail on an ambiguous content boundary. Tokenize the complete prepared prompts first; only then compute the common prefix. Independently tokenize candidates with `add_special=false`, `parse_special=false`.

Proposed aggregate limits are 1 MiB for context plus all question text, 1 MiB for candidate text, 32768 candidate tokens, and 131072 prepared prompt tokens across the request. Retain per-question limits from `/decision` and `/scale`. Count UTF-8 bytes and use checked arithmetic. Enforce the server HTTP body limit before parsing and aggregate limits before queue admission; stop prompt preparation when its running token limit is exceeded. These new limits are conservative policy choices, not measured performance thresholds.

## Response and scoring compatibility

Return an object containing `results` in request order and an `execution` object. Each result has exactly `id`, `type`, and `result`. The nested `result` is the existing decision or scale JSON representation. Do not introduce a selected answer or break ties by array position.

| Type | Nested result |
| --- | --- |
| Boolean / Choice, all labels one token | Existing `choices` with text, token_id, logit, and candidate-relative probability |
| Boolean / Choice, any label multi-token | Existing `choices` with text, token_ids, token_count, sum_log_probability, and mean_log_probability |
| Scale | Existing scale formatter, including points, SUM-relative weights, mode, median, quantiles, and interval-only summaries |

Use the current `server_task_result_decision` formatters. Preserve raw first-token logits for the single-token representation and full-vocabulary log probabilities for sequence scoring. Teacher-force the preceding candidate tokens; score the final token without decoding it. Append no terminator. SUM and MEAN retain their current meanings. Do not add a multi-token probability field or normalize Scale using MEAN.

`execution` reports `strategy` (`shared_aligned` or `fresh`), `shared_prefix_tokens`, actual `n_batch` and `n_ubatch`, and `fallback_reason` (null or a stable reason such as `no_aligned_prefix` or `sharing_ineligible`). These fields make the numerical configuration visible; they are not timing claims. If fresh is used, shared_prefix_tokens is zero. Detailed memory/decode counters stay in server logs initially.

Matching v0.4 means preserving its request validation and score/response semantics. It does not promise numerical equality to arbitrary v0.4 server batching. The numerical reference is a fresh candidate evaluation with the same effective model, template, context settings, and decode schedule. Scores demonstrably change across batch sizes.

## Context ownership and scheduling

The HTTP worker validates JSON, applies templates, tokenizes, and retains response-only metadata. It posts one native evaluation task through the existing response reader and task queue. The inference task owns token arrays and typed candidate metadata, not raw JSON. Results cross back as native score arrays; formatting stays in the HTTP worker.

Create a temporary `llama_context` on the existing inference thread using the loaded model. Do not reload weights or start a second inference worker. Reserve three sequence IDs and at least three outputs. Initially use unified KV, full SWA allocation, f16 K/V, and equal logical/microbatch sizes for the sharing path. The effective batch size is operator-configured and fixed for the request. Verify effective parameters after creation. Keep other numerical settings identical between shared and fresh paths.

Proposed first admission policy: allow one admitted evaluation, reject another with HTTP 503, and start only when ordinary active inference slots have drained. Once admitted, defer new inference starts until evaluation finishes; continue read-only administration and cancellation handling. Existing idle chat KV stays in the main context. This deliberately trades chat latency for a simple initial isolation boundary. Bound total evaluation work with the request limits above. Measure this latency before enabling mixed workloads.

Advance a small evaluation state machine from `update_slots()`, at most one prompt chunk or forced-token decode per iteration. While it is active, skip normal slot batching. Return to task processing between steps. The existing `yield_to_queue` permits only metrics and slot inspection during a decode: do not mutate/free the evaluation context from that worker. Cancellation takes effect after the current decode returns. Include allocation, failure, shutdown, and cleanup in the same ownership discipline.

Admission must mark the server busy while waiting for slots to drain and throughout evaluation. Extend idle/sleep accounting, explicit unload handling, cancellation routing, and deferred-task wakeup; evaluation is not an ordinary occupied slot. Freeze model/adapter state through completion. Initially reject evaluation when LoRA/adapters, speculative decoding, or unsupported memory architectures are configured; do not silently drop their settings. Defer model-changing control operations until cleanup. Do not change live model state underneath prepared prompts.

Temporary context memory is additional to the resident main context, although model weights are shared. Keep the feature disabled by default and use an explicit operator context cap. Allocation failure returns an error; never evict chat KV to make it succeed. Request limits do not prove GPU memory availability.

## Shared execution state machine

Let `B = n_batch = n_ubatch`, `L` be the common token-prefix length, and `P = floor(L / B) * B`. Initially share only if at least two questions exist, `P > 0`, and every question has at least one prompt token after P. A prompt ending exactly at P uses fresh evaluation for the whole request in this first version, avoiding an unvalidated empty-suffix output case.

1. Allocate the request context. Prefill positions `[0, P)` in B-token chunks on protected sequence 0.
2. Before each question, remove candidate sequence 2, then question sequence 1. Copy sequence 0 to sequence 1 and decode the remaining full prompt in the original B-token schedule. Save the final prompt logits before any further decode can invalidate them.
3. Before each candidate, remove sequence 2 and copy sequence 1 to sequence 2. Score its first token from saved prompt logits. Decode each preceding candidate token individually on sequence 2 to score the next token.
4. Store complete candidate scores. Leave protected prefix and prepared question state unchanged. Repeat candidates, then questions, in request order.
5. Destroy the temporary context, return the complete result, release admission, and resume deferred inference.

The candidate-before-question removal order is mandatory: reversing it caused order dependence in earlier experiments. No snapshot restoration, prompt-cache reuse, mixed-question decode, context shift, truncation, or adaptive batch reduction belongs in this path. Production need not serialize states after every candidate; that remains a validation assertion.

## Capacity and fresh fallback

Before admission require, for every candidate, `prepared_prompt_tokens + candidate_tokens - 1 <= evaluation_context_cap`. Use overflow-safe arithmetic and verify actual context capacity after allocation. This is a necessary logical check, not a sufficient guarantee of backend allocation or sequence-copy support. Sequence and output reservations, unified memory behavior, and SWA settings must also satisfy the eligibility checks.

Use fresh mode for the entire request when P is zero, only one question exists, a suffix is empty, or the otherwise supported runtime cannot use the validated sharing configuration. Fresh mode means a newly created context for each candidate, complete prompt prefill from position zero in the fixed batch schedule, then single-token teacher forcing. Destroy one candidate context before creating the next. Reuse saved first-token scores only if future tests justify that optimization.

Fresh fallback is not a universal model-compatibility claim. Reject configurations that cannot perform ordinary text candidate scoring. Models outside the two tested fixtures need their own oracle validation before sharing is enabled in a deployment; do not embed model-name heuristics into the public API.

Do not retry decode failures with a smaller batch or silently continue from partially modified memory. Initial version returns an error on runtime copy/remove/decode failure, non-finite scores, or allocation failure. A later automatic fresh retry would have to discard all partial results and restart the whole request with unchanged numerical settings; it is outside this proposal.

## Errors and lifecycle

Validate every question before inference. Return one HTTP 400 for invalid fields, template/tokenization failures, unsupported input, or logical context overflow, identifying the question index/id when applicable. Return 503 for evaluation admission exhaustion or unavailable temporary-context capacity and 500 for unexpected evaluation failure, using the existing server error envelope. Final status mapping must use the existing error helpers rather than introducing a second envelope.

Return no partial success response. If the client disconnects, the existing response reader posts cancellation; extend cancellation to pending and active evaluation ownership in addition to slots. Destroy temporary state after the in-flight decode finishes, suppress results for the cancelled reader, and release admission on every path. Shutdown follows the same cleanup order before freeing model weights. No evaluation state persists between requests.

## Source touch points and bounded implementation order

| Existing source | Intended change |
| --- | --- |
| `tools/server/server.cpp` | Register the two direct-server routes behind explicit enablement |
| `tools/server/server-context.h` | Declare the route and minimal owned evaluation state interface |
| `tools/server/server-context.cpp` | HTTP preparation, task admission, isolated step execution, cancellation, sleep/unload accounting |
| `tools/server/server-task.h` | Native evaluation task/result payloads |
| `tools/server/server-task.cpp` | Combined response wrapper reusing existing decision/scale formatters |
| Existing server parameter definitions | Opt-in flag and bounded evaluation context setting; finalize spelling during implementation review |
| Existing server test/oracle infrastructure | Extend coverage without adding a new file under `tests/` |

Follow the server architecture in [README-dev](../../tools/server/README-dev.md). Extract only the existing validation/scoring helpers needed to avoid divergent copies. Keep `/decision` and `/scale` behavior covered during any extraction. No generic evaluation framework, snapshot manager, or new scheduler subsystem is needed.

Implement in reviewable increments: (1) preparation and response contract with fresh-only execution; (2) bounded scheduling and lifecycle verification; (3) aligned sharing behind eligibility checks; (4) oracle comparison and memory/latency measurements. Keep the endpoint opt-in until all acceptance checks pass. Router support and broader configuration support are separate work.

## Acceptance gates before activation

- Reproduce the expanded same-configuration oracle matrix through HTTP, including order permutations, multi-token labels, Choice overlap, and Scale rejection. Compare prepared tokens and per-token scores, not only selected labels. Use the established 2e-4 diagnostic tolerance; record actual maxima.
- Validate all response shapes against existing formatters, all-invalid/mixed-invalid requests, duplicate IDs, aggregate limits, dynamic template input consistency, and exact prompt composition.
- Exercise fresh fallback at P=0, one question, empty suffix, and an eligible fresh-only configuration. Verify unchanged batch size and no partial results.
- Test context capacity at the boundary and one token beyond, allocation/decode failures, non-finite scores, and cleanup after failure.
- Exercise disconnect while pending and during scoring, shutdown, sleep/wake, model-changing controls, a second evaluation, and ordinary chat before/during/after evaluation. Verify no stale admission or modified chat KV.
- Measure peak memory and chat delay with the main context resident. Compare prompt decode counts and end-to-end latency to fresh-only mode before claiming a speedup.
- Build the modified native server and run relevant existing tests. The current environment previously lacked a native compiler; prototype DLL checks cannot substitute for compiling and testing new C++.

The next implementation decision is approval of this request contract and temporary-context ownership policy. They are new design choices; the completed experiments validate the arithmetic strategy only. This document does not authorize a commit, push, or upstream submission.
