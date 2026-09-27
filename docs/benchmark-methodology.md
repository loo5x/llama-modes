# Benchmark methodology

Use [benchmarks/compare_modes.py](../benchmarks/compare_modes.py) for recorded experiments. The demo's live timings are an **Interactive comparison**, not a benchmark.

## What is being compared?

Direct and chat are different computational procedures. Chat may perform autoregressive reasoning before answering. Direct evaluation exposes preference at the prepared assistant content state, and forces supplied prefixes when scoring multi-token choices. Accuracy differences are meaningful observations, not implementation failures by definition.

The harness supplies identical user messages to both endpoints, including the same label list and, for SCALE, the same value mapping. It uses the same selected model and server. Direct uses native content-entry template semantics; normal chat can enter reasoning first. Identical message text does not imply identical internal token trajectories. No grammar forces chat's output, and no reasoning text is silently parsed as a final answer.

## Experimental controls

- Run one model/server build at a time with no other GPU workloads. Record its launch command, context, batch settings, offload settings, quantization, template, model file hash, and runtime hash with your results.
- Do not run direct and chat concurrently. Requests are sequential; measured pairs alternate direct-first and chat-first order to reduce a fixed order bias. Odd-sized runs are not perfectly balanced.
- Warm up both paths before measurement. `--warmup N` makes N unmeasured pairs, cycling through dataset tasks. A transport failure stops warmup and preserves its log. Warmup does not require an exact final answer.
- Keep repetitions and input order explicit. The harness repeats the dataset in file order. It does not randomize, clear chat caches, or reset the server between requests. Cache behavior is part of the measured runtime and can affect comparisons.
- Keep the chat generation cap explicit (`--max-tokens`, default 1024). Reasoning can consume the cap. A different cap can change accuracy, invalid-output rate, latency, and tokens.
- Preserve raw requests/responses and errors. Repeated tasks are repeated observations, not independent new ground-truth items.

## Parsing and metrics

Chat parsing accepts only one exact supplied label in final `message.content`, after trimming outer whitespace, with `finish_reason: "stop"`. Case, punctuation, explanations, markdown, reasoning-only output, and truncation are not silently corrected. Labels must remain unique after trimming. This conservative **exact-answer rate** measures format compliance, not semantic correctness of arbitrary prose.

Direct selects the largest single-token `probability`, multi-token `sum_log_probability`, or SCALE `relative_weight`. Exact ties have no single answer and count as invalid for this categorical comparison; raw scores preserve the tie. SCALE comparisons use the modal label, never its expected value as a generated answer. Unlabeled subjective scales receive no accuracy score.

| Metric | Definition and denominator |
| --- | --- |
| Accuracy | Correct exact labels / all labeled requests, including failures and invalid answers |
| Exact-answer rate | Valid unique exact answers / all requests |
| Invalid-output rate | 1 - exact-answer rate; includes transport failures, malformed responses, ties, and unparseable answers |
| Direct/chat agreement | Equal answers / pairs where both have a valid unique answer; `agreement_pairs` reports this denominator |
| Median latency | Median client wall time for successfully decoded HTTP JSON responses, including responses with invalid answers |
| p95 latency | Nearest-rank percentile: sorted sample at `ceil(0.95 * N) - 1` (zero-based); no interpolation |
| Mean chat completion tokens | Mean of non-negative integer `usage.completion_tokens` values actually returned; missing values are excluded and sample count reported |

Latency uses `time.perf_counter()` around JSON encoding, HTTP request/response, and JSON decoding. It includes local transport and possible queueing; it is not GPU kernel time. HTTP/transport failures have `elapsed_ms` in raw rows but are excluded from latency aggregates. All raw attempts retain elapsed time. The two procedures can have different successful sample sets; always read sample counts and failures alongside latency.

Direct rows record `generated_tokens_by_design: 0` as a harness annotation. No direct API `usage` or completion-token field is invented. Forced candidate-prefix evaluations and repeated prompt prefills remain real work. Missing latency/accuracy/token metrics are JSON `null`, never fabricated zeroes. Aggregates are reported overall and by mode to avoid hiding mode differences.

## Data and metadata

The default dataset reuses the 100 preserved Boolean questions/labels in `experiments/results/decision_v01_final_channel_100.csv`. Only task ID, category, question, and truth are imported, never historical answers, timing, or the legacy `Confidence` column. The new harness uses native messages and strict exact-label parsing, unlike the historical template pipeline and parser. This is not an exact reproduction of historical performance figures.

`choice-smoke.jsonl` contains only three straightforward categorical examples. It is explicitly a smoke dataset, not a definitive benchmark. External JSONL supports Boolean, Choice, and SCALE tasks. See [dataset schema](../benchmarks/README.md#external-jsonl).

Each run saves model discovery, selected model, URL, UTC timestamp, dataset SHA-256, harness SHA-256, repetition/warmup counts, timeout, generation cap, user-supplied hardware and version/commit labels, and system fingerprints when actually returned. Exact direct/chat requests, raw responses, correctness, agreement, token usage, order, latency, and errors are in `raw.jsonl`. Fingerprints may be absent. No unreliable automatic hardware detection is attempted.

The user-supplied hardware label is a label, not verified hardware evidence. Hashes and metadata make the experiment auditable but cannot by themselves guarantee identical results across hardware or floating-point implementations.

## Claims deliberately not made

No calibrated confidence, chain-of-thought equivalence, universal latency advantage, universal accuracy advantage, continuous regression, representation-independent scales, or model-independent encoding is claimed. The repository ships no fabricated performance results. Report new numerical claims only with the associated raw run, settings, dataset, and limitations.
