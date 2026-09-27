# Decision: Boolean and categorical choices

`POST /decision` (alias `/v1/decision`) scores supplied text alternatives at a prepared model evaluation state. Boolean is the two-label case; choice supports arbitrary labels, including multiple tokens. No answer is sampled or autoregressively generated. Generated tokens are zero by design, even when scoring requires additional model evaluations.

## Request

```json
{
  "messages": [{"role": "user", "content": "Which city is the capital of France? Select Paris, London, or New York. Return only the label."}],
  "choices": ["Paris", "London", "New York"]
}
```

Supply exactly one of `messages` or `prompt`. The optional `model` field selects a model through a router. No temperature, sampling, scoring-method, or request-level template options are accepted by this endpoint.

In messages mode, the server uses the model's native chat template and enters a new assistant content response. The conversation must be non-empty and end in a user message. Each message contains only `role` and string `content`; supported roles are `system`, `developer`, `user`, and `assistant`. Tools, multimodal inputs, reasoning fields, and assistant continuation are unsupported. An ambiguous assistant content boundary is rejected, rather than guessed.

In raw mode, a non-empty `prompt` string is tokenized with model special-token parsing and normal prompt special tokens enabled. No chat template is applied:

```json
{"prompt":"Answer yes or no: Is Paris the capital of France?\nAnswer:","choices":[" yes"," no"]}
```

Raw prompts must end at the response position you intend to evaluate. For GPT-OSS, an assistant role boundary alone is not a final-content boundary. Prefer messages unless you understand your model's template; see the [historical boundary experiment](decision-mode-v0.md).

## Single-token fast path

If every choice independently tokenizes to one token, the response retains the legacy format:

```json
{"choices":[{"text":"Yes","token_id":123,"logit":2.0986122887,"probability":0.75},{"text":"No","token_id":456,"logit":1.0,"probability":0.25}]}
```

These are illustrative values and token IDs, not inference results. `probability` is softmax over the supplied candidate logits only. It is neither a full-vocabulary probability nor calibrated confidence. Response choices remain in request order. Read their scores; do not assume the first item won.

## Multi-token teacher-forced scoring

If any choice has more than one token, **every choice** uses the sequence-score format:

```json
{"choices":[{"text":"Paris","token_ids":[123],"token_count":1,"sum_log_probability":-1.2,"mean_log_probability":-1.2},{"text":"New York","token_ids":[456,789],"token_count":2,"sum_log_probability":-4.0,"mean_log_probability":-2.0}]}
```

This is an illustrative response excerpt. Actual responses contain every requested choice. Each next candidate token is scored against logits normalized over the **full vocabulary**, while the preceding candidate tokens are forced into the model. The final token is scored without decoding it. An M-token label needs M-1 forced token evaluations.

- `sum_log_probability` is the sum of natural-log token probabilities. Higher (less negative) is more likely.
- `mean_log_probability` is SUM divided by token count. It measures average token predictability; it is a length-normalization heuristic, **not sequence probability** or a corrected probability.
- `token_ids` and `token_count` expose the actual representation being scored.

No EOS/EOT or closing template tokens are appended. SUM measures a token continuation event, not the probability of a complete answer stopping at that label. Prefix-sharing labels are allowed for `/decision`; a strict prefix can overlap another candidate's continuation event.

There is no multi-token `probability` field. The demo computes softmax of SUM scores for display and labels it as a UI-derived relative weight. That calculation does not remove length bias, make overlapping continuations disjoint, or produce calibrated confidence. The benchmark selects the largest SUM without adding a probability field to the API response.

## State isolation and candidate order

Candidate scores should be independent of API candidate order for an unchanged prepared prompt. In v0.3.1, production scoring adopted a correctness-first strategy: store first-token scores after the initial prompt prefill, then clear the slot sequence and re-prefill the original prompt before each later multi-token candidate. Single-token candidates use stored first-token scores. This costs extra prompt processing but avoids the observed snapshot-restoration order dependence. See [design and limitations](design-and-limitations.md).

This invariant concerns API candidate order. Reordering the label list inside the prompt changes the prompt and may change preferences. Ties should remain ties; clients should not silently interpret array order as evidence.

## Validation and limits

The endpoint accepts 1..256 choices, at most 1 MiB of total choice text and 32768 choice tokens. The public demo/harness require at least two alternatives. Choices tokenize independently with `add_special=false`, `parse_special=false`; this may differ from tokenizing concatenated prompt and label text. Whitespace and tokenizer normalization matter. Empty or duplicate complete token sequences are rejected.

The prompt and largest forced candidate prefix must fit the slot context. Requests are not shifted or truncated. Invalid input and context overflow return HTTP 400; evaluation failures return HTTP 500. Embedding-only models are unsupported.

The contract is implemented in [server-context.cpp](../tools/server/server-context.cpp) and [server-task.cpp](../tools/server/server-task.cpp); the [server reference](../tools/server/README.md#post-decision-and-v1decision-score-text-choices) retains detailed runtime history.
