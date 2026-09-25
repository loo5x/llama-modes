# SCALE v0.4 Stage 2 experiment

This directory contains an experiment against the unchanged v0.3 `/decision` API. It does not implement `/scale` or change inference. The authoritative runtime is native Windows + CUDA. No WSL build is used.

Read `FINDINGS.md` for conclusions, `TABLES.md` for numerical comparisons, and `oracle-status.json` for the uncompleted native oracle checks. The requested oracle executable was absent during this run.

## Design

The full matrix has 399 rows per model: 39 tasks x 10 variants, plus 9 finer-grid arithmetic cases. The scales are 0..10, 1..5, and -2..2, all with step 1. The finer grids use step 0.5 over the same endpoints. `--smoke` uses 279 rows; `--limit 10` selects the first complete set of 10 variants. The stored config contains every task and variant actually selected.

There are 9 instructed-target cases and 9 objectively checkable arithmetic cases, covering the endpoints and midpoint of each scale. These use interval semantics. There are 21 ordinal rubric cases, covering every point of each scale. These deliberately reuse a rubric description as the service report and test rubric lookup and label mapping, not generalization to unseen service reports. All targets are synthetic and author-defined. This is not a calibration dataset.

A separate `--rubric-paraphrases` suite uses 21 concrete service reports with wording different from the rubric, again across all points and ten variants (210 rows per model). These receive ordinal summaries only. They test transfer beyond exact-description lookup, with author-assigned expected categories rather than independently adjudicated human ratings. Results are kept in `*-paraphrases` and are not pooled into the original matrix.

Variants:

- Natural numeric labels, including a minus sign only for negative values.
- Fixed-width labels: two digits on positive scales; an explicit sign and two digits on the signed scale (`-02`, `-01`, `+00`, `+01`, `+02`). This changes sign formatting as well as width.
- Symbolic labels A..K or A..E with the value mapping explicitly stated in the prompt.
- Short textual anchors with rubric meanings given separately in ordinal prompts. For numeric tasks, anchors are arbitrary explicitly mapped response labels.
- Numeric labels followed by a newline. The newline is scored and changes the event likelihood. The prompt is identical to the bare numeric prompt; this is a boundary diagnostic, not a newly instructed output format.
- Leading-space numeric labels, also with the bare numeric prompt, to diagnose tokenization and response-boundary effects.
- Reversed API candidate order with identical prompt and labels.
- A one-position cyclic rotation of symbolic label/value assignments.
- Reversed listing of symbol mappings in the prompt, without changing their assignments.
- Raw prompt versus native messages at equivalent assistant content boundaries.

Meaning, task, scale values, and rubric are held fixed within representation pairs. The mapping necessarily changes when the representation changes. Space/newline and API-order controls preserve the prompt byte for byte. Fine-grid comparisons necessarily change the candidate support and its prompt listing; they are sensitivity checks, not pure tokenization interventions.

## Scores and statistics

The primary weights are stable softmax over `sum_log_probability`. A separate experimental distribution uses softmax over `mean_log_probability`. Both are representation-dependent relative scale weights, never calibrated confidence.

For each row the harness saves exact labels, token IDs/counts, duplicate token sequences, strict token-prefix overlaps, raw scores, both sets of weights, exact modal ties, discrete median, 0.1/0.25/0.5/0.75/0.9 quantiles, and cumulative weights. The discrete quantile is the first sorted scale value whose cumulative weight is at least the quantile. Modes use exact equality; no arbitrary near-tie tolerance is imposed. Only interval cases receive expected value and population standard deviation.

Paired comparisons align by numeric value and use total variation distance, `0.5 * sum(abs(p - q))`, on the union of supports. This is defined for ordinal distributions. Interval cases additionally record one-dimensional Wasserstein distance in scale units, and signed expected-value shift. TV on fine/coarse grids reflects new support as well as changed scores. No interpolation or bin aggregation is implied.

Within-row Pearson correlations associate token count with scores and weights. Paired correlations associate token-count changes with SUM-score changes where support matches. Equal counts produce `null`, not a fabricated zero. These are descriptive associations, confounded by task and value, not causal length-bias estimates.

Problematic encodings are retained. Duplicate candidates will produce a saved HTTP error; prefix overlaps remain scored by v0.3 and are flagged, never silently removed. Overlapping scores can be normalized as index weights but cannot be interpreted as probabilities of disjoint model continuation events.

## Single-token scores

The v0.3 single-token fast path does not return absolute full-vocabulary log probabilities. The harness first records the original request/response, then adds one explicitly recorded multi-token diagnostic candidate to trigger v0.3's existing sequence scorer. The diagnostic label is never inserted into the prompt and never included in SCALE statistics. All scale candidates are scored unchanged; weights normalized over just those candidates must match the original fast-path weights within 2e-5. A mismatch marks the row as an error.

This is an experimental adapter to the existing API, not a change to the inference engine or production contract.

## Native messages and raw prompts

For GPT-OSS, the normal native generation prompt ending in `<|start|>assistant` is extended with `<|channel|>final<|message|>`. For Qwen, the assistant content boundary includes the empty closed thinking block. These conventions follow the existing server tests. Unknown boundaries fail explicitly. Before a matrix runs, raw/messages and candidate-order preflight scores must agree within 2e-4 nats. All 39 task pairs are also measured and reported afterward; passing a preflight is not a claim that every case passes.

The initial development pilot and interrupted preliminary matrix used an incorrect assistant-probe renderer. Their directories contain `EXCLUDED.md`; they are preserved for audit and excluded from findings. Use only `*-validated-full` for the main tables. The corrected 10-row pilots are additional validation, not pooled into the matrix.

## Reproduction

Start the preserved Windows runtime with one model at a time:

```powershell
& C:\AI\llama-modes-v03\llama-server.exe -m MODEL_PATH --host 127.0.0.1 --port 8094 -c 4096 -np 1 -ngl 99 -b 512 -ub 512 --jinja --metrics --no-warmup
```

Models used:

- `C:\Users\lucia\.cache\huggingface\hub\models--ggml-org--gpt-oss-20b-GGUF\snapshots\ef9b12f2ff56c69cf32153a02784e7a3c88bf524\gpt-oss-20b-MXFP4.gguf`
- `C:\AI\qwen38-ridge\Qwen3.8-27B-Ridge-3.7bpw.gguf`

The GPU is an NVIDIA GeForce RTX 5080 with 16303 MiB reported memory. Server command arguments are identical except for model path. Server stdout/stderr are retained beside this README. Model file SHA-256, runtime EXE/DLL hashes, full `/props`, `/v1/models`, template, Python version, Git commit, and harness hash are saved in each run config. The two full-matrix harness source snapshots are retained; later recorder changes do not change their scoring design. The GPT-OSS full run predates before/after metrics capture; its supplementary repeat controls record a zero lifetime generated-token counter instead.

From the repository root, use a new output directory for each run:

```powershell
python experiments/scale_v04/test_harness.py
python experiments/scale_v04/verify_artifacts.py
python experiments/scale_v04/run.py --output experiments/scale_v04/results/NEW-PILOT --model-id MODEL_NAME --runtime C:\AI\llama-modes-v03 --smoke --limit 10
python experiments/scale_v04/run.py --output experiments/scale_v04/results/NEW-FULL --model-id MODEL_NAME --runtime C:\AI\llama-modes-v03
python experiments/scale_v04/run.py --output experiments/scale_v04/results/NEW-PARAPHRASES --model-id MODEL_NAME --runtime C:\AI\llama-modes-v03 --rubric-paraphrases
python experiments/scale_v04/run.py --output experiments/scale_v04/results/NEW-FULL --analyze
python experiments/scale_v04/validate_runtime.py --results experiments/scale_v04/results/NEW-FULL --output experiments/scale_v04/results/NEW-REPEATS
```

The native oracle spot-check command is below. Stop the server first to free GPU memory. It uses the stored exact prompt tokens and candidate token IDs, independent fresh contexts, the same model file, and the matrix context/batch/GPU settings. Four cases cover the numeric target 10 (including Qwen's overlap), signed numeric, ended numeric, and a finer grid. It records every oracle command, input, token score, output, process log, and difference. It never downloads, searches for, or builds another runtime.

```powershell
python experiments/scale_v04/validate_runtime.py --results experiments/scale_v04/results/NEW-FULL --output experiments/scale_v04/results/NEW-ORACLE --oracle C:\AI\llama-modes-v03\test-save-load-state.exe
```

`report.py` regenerates `TABLES.md` and `analysis.json` from the two named full runs. Each run retains `http.jsonl` (exact HTTP bodies and responses), `config.json`, `preflight.json`, `results.jsonl`, `comparisons.json`, and `summary.json`. Source snapshots are included in corrected runs. Existing result directories are never overwritten by inference runs. Derived analysis files can be regenerated.

`verify_artifacts.py` requires the four final run directories and checks all 1218 preserved rows. `validate_runtime.py --case scale:case:variant` selects an individual recorded control instead of the four defaults.

Native templates can inject the current date. For later exact-context repeat checks, add `--replay-raw` to `validate_runtime.py` to use the stored prepared prompt rather than rerendering messages. The oracle always uses stored tokens. Changing model/runtime, hardware, or evaluation settings may still change floating-point results.

## Limits

These are small synthetic task families, one prompt wording, one symbol rotation, one listing reversal, and one ending. Signed padding confounds sign formatting with width. The separate paraphrase suite remains synthetic and small. Fine-grid arithmetic targets are shared with the coarse grid, not intermediate targets. The suite does not estimate calibration, human agreement, test-retest reliability across hardware, or a continuous density. Prefix freedom establishes disjointness of token-prefix events; it does not guarantee accuracy or representation invariance.
