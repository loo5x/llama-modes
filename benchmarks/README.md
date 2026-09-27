# Reproducible direct/chat comparison

Python standard library only. Start your llama-modes server first. The harness makes sequential requests and writes each raw pair immediately. It never overwrites an existing output directory.

## Run

From the repository root:

```sh
python benchmarks/compare_modes.py --url http://127.0.0.1:8080 --output benchmarks/results/boolean-run --repetitions 3 --warmup 2 --timeout 120 --hardware-label "your GPU and CPU" --version "your commit SHA"
python benchmarks/compare_modes.py --dataset benchmarks/datasets/choice-smoke.jsonl --output benchmarks/results/choice-run --repetitions 3 --warmup 2
```

The default dataset reuses the preserved 100-question Boolean CSV. `choice-smoke.jsonl` has three example tasks and is not a definitive benchmark. Use `--model MODEL_ID` if needed; otherwise the first `/v1/models` ID is selected and saved. `--max-tokens 1024` controls the chat cap. `--output` is a new directory, not a filename.

Use a new output directory for every model/configuration. Keep the runtime launch command and model/runtime hashes alongside it. Read the [methodology](../docs/benchmark-methodology.md) before interpreting comparisons.

## External JSONL

One task per line; IDs are unique non-empty strings:

```json
{"id":"fact-1","mode":"boolean","question":"Is 2 an even number?","choices":["Yes","No"],"expected":"Yes"}
{"id":"city-1","mode":"choice","question":"Which city is the capital of France?","choices":["Paris","London","New York"],"expected":"Paris"}
{"id":"rating-1","mode":"scale","question":"Rate this fictional outage: one feature fails. 0 no impact, 1 partial outage, 2 total outage.","measurement":"ordinal","scale":[{"value":0,"label":"A"},{"value":1,"label":"B"},{"value":2,"label":"C"}]}
```

`expected` is optional. When present it must exactly match a supplied **label**, including SCALE. Do not invent ground truth for subjective ratings. The harness supplies label lists/mappings in both direct/chat messages; only the task question needs to be authored. Boolean defaults to Yes/No if `choices` is omitted. Choices and scale points must number 2..256, with non-empty distinct labels; scale numeric values must be finite and unique. Labels differing only in surrounding whitespace are rejected because exact-answer parsing trims that whitespace.

CSV input supports the preserved historical schema (`Index`, `Category`, `Question`, `Truth`), not arbitrary CSV schemas. JSONL is the public external dataset interface.

## Result format

Each output directory contains:

- `metadata.json`: run settings captured before measurement.
- `warmup.jsonl`: unmeasured warmup request/response pairs.
- `raw.jsonl`: measured pairs with task ID, mode, expected label, repetition, order, model, direct/chat results, correctness, agreement, latency, errors, requests, raw responses, fingerprints, and actual chat completion usage.
- `summary.json`: `schema_version: 1`, final metadata (including observed fingerprints), `aggregate`, and `by_mode`.

Summary metrics include accuracy, exact-answer rate, invalid-output rate, agreement with its denominator, median/p95 latency with sample counts, and mean chat completion tokens with its sample count. Missing metrics are null. Direct generated tokens are recorded separately as zero by design. Exact ties have no unique categorical result. No API usage field is manufactured.

An interrupted run retains completed raw rows but may have no summary. Re-run into a new directory; do not mistake a partial run for a completed benchmark. Summary values must come from actual runs; none are preloaded in the demo or published in the README.

## Fast self-tests

```sh
python benchmarks/test_compare_modes.py
python -m py_compile benchmarks/compare_modes.py benchmarks/test_compare_modes.py
```

Self-tests cover exact chat parsing, truncation, both direct formats, ties, dataset validation, shared message semantics, metric denominators, nearest-rank p95, missing usage, and a complete CLI run against a controlled local HTTP fixture (including failures and overwrite refusal). They do not require llama-server.
