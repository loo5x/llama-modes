# Evaluate: independent questions over one text

Experimental implementation, fresh-only by default. Enable with `--evaluate`; routes are absent by default and are not registered in router mode. Set `--evaluate-context N` to bound each prepared prompt plus forced candidate prefix (default 4096 tokens). Windows CUDA validation of the fresh-only path on GPT-OSS 20B is recorded in the [validation baseline](../experiments/shared_context_v05/HTTP-VALIDATION.md). The optional shared-prefix path has also passed [Windows CUDA validation](../experiments/shared_context_v05/HTTP-SHARED-VALIDATION.md) in that configuration.

`POST /evaluate` (alias `/v1/evaluate`) accepts one context and 1..32 independent questions:

```json
{
  "context": "Paris is in France. The service was good.",
  "questions": [
    {"id": "fact", "type": "boolean", "question": "Is Paris in France? Answer yes or no.", "choices": ["yes", "no"]},
    {"id": "city", "type": "choice", "question": "Name the city. Answer Paris or London.", "choices": ["Paris", "London"]},
    {"id": "rating", "type": "scale", "question": "Rate service: L=bad, H=good. Answer one label.", "measurement": "ordinal", "scale": [{"value": 0, "label": "L"}, {"value": 1, "label": "H"}]}
  ]
}
```

The server prepares a separate user message containing exactly `context + "\n\n" + question` for every question. It uses the native assistant content-entry template, with one captured template time for the request. Questions do not see other questions or their answers. No answer is sampled, no labels are inserted into the prompt automatically, and no EOS or other terminator is appended to candidates.

Boolean requires exactly two explicit labels, without an implicit truth mapping. Choice and Scale retain the validation and scoring rules in [decision](decision.md) and [scale](scale.md). Unknown fields are rejected. Optional top-level `model` has the existing direct-server handling. Raw prompts, conversation history, media, tools, streaming, and request-level inference/template settings are unsupported.

The response has `results` in request order. Each entry contains `id`, `type`, and `result`, where `result` is the existing decision or scale response. Boolean/Choice keep the single-token logit/probability format when all choices have one token; otherwise they expose SUM/MEAN sequence scores. Scale always uses full-vocabulary sequence scores and SUM-relative weights.

An `execution` object reports `strategy`, `shared_prefix_tokens`, actual `n_batch` and `n_ubatch`, and `fallback_reason`. Without `--evaluate-shared-prefix`, these remain `fresh`, zero, and `fresh_only`. Batch-size changes can change scores; compare results only under the same configuration. Relative candidate weights are not calibrated confidence.

Add `--evaluate-shared-prefix` alongside `--evaluate` to opt into batch-aligned sharing. The server finds the common prefix of the complete tokenized prompts and reuses only its complete-batch portion. Shared execution uses one temporary context per request, protects the prefix, prepares each question separately, and isolates each candidate. No prompt token is omitted. Successful sharing reports `strategy: "shared_aligned"`, the reused token count, and a null fallback reason.

The whole request uses fresh evaluation when there is one question (`single_question`), effective batch and microbatch sizes differ (`unequal_batches`), no complete common batch exists (`no_aligned_prefix`), any question has an empty suffix after the aligned prefix (`empty_suffix`), or the context lacks the required memory/sequence configuration (`sharing_ineligible`). Unsupported models remain rejected. Runtime failures do not trigger a retry with another batch size or a partial response. The option remains experimental; the linked measurements cover one model/backend configuration and do not guarantee a speedup for every workload.

Limits:

- Unique, non-empty question IDs of at most 128 UTF-8 bytes; non-empty context and question text.
- Context plus question text: 1 MiB total. Candidate text: 1 MiB total. Candidate tokens: 32768 total. Prepared prompt tokens: 131072 total.
- Per-question Choice/Scale limits remain in force. Every prompt plus the longest candidate's forced prefix must fit `--evaluate-context`. Nothing is shifted or truncated.
- One evaluation admitted at a time; another receives HTTP 503. Existing active chat work drains before evaluation starts; new inference waits until it finishes. This can delay chat requests.

Fresh mode allocates a temporary context for every candidate using the loaded model weights; shared mode keeps one temporary context for the request. The main server context stays resident, so additional memory is required. Evaluation uses unified KV, full SWA, f16 K/V, three sequence/output reservations, and the configured batch/microbatch sizes. Other model context parameters come from the server configuration. Encoder, recurrent/hybrid, multimodal, adapter, control-vector, speculative, and explicitly non-causal configurations are rejected in this first version.

Validation errors return HTTP 400 without partial results. Admission/allocation unavailability returns 503; decode or other execution failures return 500 without changing batch size or retrying. Disconnect cancellation is processed between steps after any current decode completes. Fresh contexts are discarded after each candidate; shared contexts are discarded after the request. Both are discarded on failure, cancellation, or shutdown.

The HTTP checks live in the existing `tools/server/tests/unit/test_chat_completion.py`; they cover mixed scoring, order/repeat invariance, selected validation failures, recovery, default-disabled routes, pending cancellation, and shutdown with connected clients. Local Windows runs also cover native oracle comparison, cancellation/concurrency, sleep/wake, shutdown/restart, selected capacity boundaries, and repeated use. See the [validation baseline](../experiments/shared_context_v05/HTTP-VALIDATION.md) for tested builds and limits. Shared execution passed the same local lifecycle checks; see the [shared validation report](../experiments/shared_context_v05/HTTP-SHARED-VALIDATION.md). Allocation/decode failure injection and other deployed model/backend configurations remain unvalidated.
