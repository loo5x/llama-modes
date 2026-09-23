# Decision mode v0: first validated milestone

## Preserved runtime

- Upstream llama.cpp baseline: `444826532091bba42771d749b9dc7e71ddc76efd`.
- First decision implementation: `4ecd03d6e94eeb284716f4a067f3982f8188d001`.
- JSON parser fix and validated runtime: `4a508fcbd5ba0f0f2e54e8f0708620eb95d39851`.

`POST /decision` performs one prompt evaluation (prefill), reads the candidate next-token logits, and stops. It performs no sampling and generates zero autoregressive tokens. Prefill can use multiple batches; this is not an autoregressive decoding loop. Each supplied choice must tokenize independently to exactly one token. Whitespace matters, and accepted choices depend on the tokenizer.

Returned probabilities are a softmax only over the supplied candidates. They are not calibrated confidence, nor probabilities over all possible answers. See the [endpoint documentation](../tools/server/README.md#post-decision-and-v1decision-score-single-token-choices) for the request and response contract.

## GPT-OSS prompt boundary

Raw arbitrary prompts work mechanically, but GPT-OSS performs substantially better with its native Harmony/chat structure. Simply applying the GPT-OSS chat template and reading Yes/No immediately after `<|start|>assistant` is INVALID: that position expects channel structure rather than final answer content.

The validated direct-answer readout point for this experiment is:

```text
native GPT-OSS template
+ "<|channel|>final<|message|>"
-> read Yes/No logits
-> stop
```

For the controlled question "Is it not the case that 1 is prime?", direct final-channel readout preferred No (approximately 59.16%). Normal greedy completion started from exactly the same final-channel state also produced "No". Normal GPT-OSS chat with autoregressive reasoning produced "yes". This confirms that /decision faithfully exposes the next-token state rather than inventing a separate answer. Direct readout does not include the reasoning tokens that normal chat can generate before its final answer.

## Validated 100-question benchmark

The preserved benchmark contains 20 questions in each category: facts, logic, negation, commonsense, and technical.

| Measurement | Direct final-channel readout | Normal GPT-OSS chat |
| --- | --- | --- |
| Accuracy | 93/100 | 100/100 |
| Completion tokens | 0 | 7151 total |
| Median latency | Approximately 30.4 ms, full pipeline | Approximately 317 ms |

The median latency difference was approximately 10.4x in this benchmark. Direct full-pipeline timing includes template application and the decision request. This is a small validation benchmark, not a claim of general task accuracy. Timing depends on the model, hardware, server settings, and request conditions; these figures are historical validation results, not guaranteed reproduction targets.

### Invalid intermediate experiment

The native template without the final-channel marker produced a strong Yes bias and scored 58/100 only because 58 ground-truth answers were Yes. Those results must not be used as evidence for the method.

## Artifacts and reproduction

The [original CSV](../experiments/results/decision_v01_final_channel_100.csv) is preserved byte-for-byte from `C:\Users\lucia\Desktop\decision_v01_final_channel_100.csv`. Its legacy `Confidence` column is a candidate-relative probability, not calibrated confidence. Its numeric fields use decimal commas.

The [PowerShell 5.1 reproduction script](../experiments/decision_v01_final_channel_100.ps1) reads the exact 100 questions and truth labels from that CSV. No original script was found in the repository or working tree; this is a new reproduction harness, not the historical script. Historical generation settings and the full server/model configuration are not recorded in the CSV, so exact numerical reproduction is not assured.

Start the validated server with GPT-OSS and its native chat template, then run:

```powershell
powershell.exe -NoProfile -File .\experiments\decision_v01_final_channel_100.ps1 -BaseUrl http://127.0.0.1:8080
```

The script sends each question as a user message to `/apply-template`, checks the assistant boundary, appends exactly `<|channel|>final<|message|>`, and calls `/decision` with `["Yes", "No"]`. It compares this with normal `/v1/chat/completions` using temperature 0 and a configurable completion limit (4096 by default). Chat answer scoring uses the initial Yes/No word in final content; malformed or truncated answers count as errors. It records errors without dropping questions and fails after saving if any request or answer fails validation.

New results default to a timestamped CSV next to the preserved results. Existing output files are never overwritten. Reports include global and per-category accuracy, latency, disagreements, errors, and completion token totals. Accuracy uses all questions as the denominator, including errors. Latency summaries use successful responses only.
