# Evaluate: independent questions over one text

Experimental fresh-only implementation. Enable with `--evaluate`; routes are absent by default and are not registered in router mode. Set `--evaluate-context N` to bound each prepared prompt plus forced candidate prefix (default 4096 tokens). Native compilation and live integration validation are still required for this initial implementation.

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

An `execution` object reports `strategy: "fresh"`, `shared_prefix_tokens: 0`, actual `n_batch` and `n_ubatch`, and `fallback_reason: "fresh_only"`. This version does not reuse a prefix. Batch-size changes can change scores; compare results only under the same configuration. Relative candidate weights are not calibrated confidence.

Limits:

- Unique, non-empty question IDs of at most 128 UTF-8 bytes; non-empty context and question text.
- Context plus question text: 1 MiB total. Candidate text: 1 MiB total. Candidate tokens: 32768 total. Prepared prompt tokens: 131072 total.
- Per-question Choice/Scale limits remain in force. Every prompt plus the longest candidate's forced prefix must fit `--evaluate-context`. Nothing is shifted or truncated.
- One evaluation admitted at a time; another receives HTTP 503. Existing active chat work drains before evaluation starts; new inference waits until it finishes. This can delay chat requests.

A fresh temporary context is allocated for every candidate using the loaded model weights. The main server context stays resident, so additional memory is required. Evaluation uses unified KV, full SWA, f16 K/V, three sequence/output reservations, and the configured batch/microbatch sizes. Other model context parameters come from the server configuration. Encoder, recurrent/hybrid, multimodal, adapter, control-vector, speculative, and explicitly non-causal configurations are rejected in this first version.

Validation errors return HTTP 400 without partial results. Admission/allocation unavailability returns 503; decode or other execution failures return 500 without changing batch size or retrying. Disconnect cancellation is processed between steps after any current decode completes. Temporary contexts are discarded after each candidate, failure, cancellation, or shutdown.

The initial HTTP checks live in the existing `tools/server/tests/unit/test_chat_completion.py`; they cover mixed scoring, order/repeat invariance, selected validation failures, recovery, and default-disabled routes. Broader cancellation/concurrency/sleep tests, native oracle comparison, and memory/latency measurements remain activation gates in the [integration design](../experiments/shared_context_v05/EVALUATE-INTEGRATION.md).
