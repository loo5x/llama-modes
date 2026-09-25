# Stage 2 findings

The experiment ran on native Windows + CUDA using the preserved v0.3 runtime and both requested model files. No production code, endpoint, or inference behavior was changed. There is no `/scale` implementation. No commit, push, or tag was made.

## Coverage and evidence

- Two full matrices: 399 rows per model, 798 total, all successful.
- Two separate paraphrased-report suites: 210 rows per model, 420 total, all successful.
- Total retained final experimental rows: 1218, with no scoring request errors or duplicate candidate token sequences.
- Corrected 10-row pilots on each model and raw/messages/order preflights on every corrected run.
- Seven offline harness tests passed. Artifact verification passed for all 1218 rows, including stored source hashes, exact planned coverage, score normalization, and ordinal/interval separation.
- Repeated 24 live control requests per model, plus six targeted GPT-OSS paraphrase controls.
- Raw/messages scores matched exactly in all 120 numeric task comparisons across the main and paraphrase suites.
- Captured generated-token counters remained zero. GPT-OSS's first full run lacks a before snapshot, but the subsequent counter was zero for that server's entire lifetime.

The independent oracle was NOT run: `C:\AI\llama-modes-v03\test-save-load-state.exe` was absent. `Test-Path`, `Get-Item`, and the native oracle runner confirmed this. No alternate runtime was used. See `oracle-status.json`. Oracle agreement from v0.3 is not being claimed as fresh validation of these new cases.

The initial invalid renderer pilot and interrupted preliminary matrix are preserved with `EXCLUDED.md` markers and excluded from every result below.

See `README.md` for design and reproduction, `TABLES.md` for all aggregate comparisons, `analysis.json` for tokenizations and notable cases, and each result directory for raw HTTP requests/responses, exact prompts, token streams, model/runtime hashes, and per-case statistics.

## Natural numeric labels are model-dependent

GPT-OSS tokenizes all integer labels 0..10 as distinct single tokens. Qwen tokenizes `1` as `[16]` and `10` as `[16, 15]`. Thus the event scored for `10` is contained in the event scored for `1`.

For Qwen's explicit target-10 request:

| Value | Token IDs | SUM log probability | Relative SUM weight |
| --- | --- | ---: | ---: |
| 1 | [16] | -0.1441490827 | 0.5171339930 |
| 10 | [16, 15] | -0.2132276298 | 0.4826170432 |

This is a representation defect for selecting the requested scale point, not evidence that the model considers 1 a better semantic rating. A token sequence cannot have greater continuation likelihood than its own strict prefix. Bare numeric SUM scoring selected 1 rather than 10 in Qwen's instructed, arithmetic, and exact-rubric target-10 cases.

Unique SUM-mode agreement with the synthetic targets:

| Encoding | GPT-OSS original 39 tasks | Qwen original 39 tasks | GPT-OSS 21 paraphrases | Qwen 21 paraphrases |
| --- | ---: | ---: | ---: | ---: |
| Natural numeric | 39/39 | 35/39 | 16/21 | 19/21 |
| Fixed-width numeric | 37/39 | 39/39 | 14/21 | 19/21 |
| Symbols | 36/39 | 36/39 | 15/21 | 16/21 |
| Textual anchors | 36/39 | 39/39 | 14/21 | 18/21 |
| Numeric plus newline | 33/39 | 18/39 | 13/21 | 8/21 |

Original rubric tasks are exact-description lookup controls. Paraphrase targets are author-assigned expectations under the supplied rubric, not human-adjudicated ground truth. These ratios do not measure calibration or establish production accuracy.

Natural numbers are a reasonable model-specific candidate for the tested GPT-OSS integer grids. They are not an acceptable unconditional cross-model default, especially for Qwen's 0..10 grid.

## Representation sensitivity is substantial

Across the original 39 paired tasks, switching from natural numeric to symbols changed modes in 3 GPT-OSS cases and 5 Qwen cases. Maximum total variation distances were 0.9355 and 0.9494. TV compares distributions aligned by numeric value and ranges from 0 to 1.

Rotating the symbolic assignment changed modes in 8/39 GPT-OSS and 3/39 Qwen cases. Reversing the prompt's mapping listing changed modes in 6/39 and 4/39. All these symbolic encodings used equal-length, single-token, prefix-free labels. They remain sensitive to the symbol and prompt mapping.

The same-prompt newline diagnostic changed modes in 6/39 GPT-OSS and 18/39 Qwen cases. Maximum interval expected-value shifts were 4.4880 and 4.0131 scale units; mean TV was 0.1263 and 0.5580. Ending probability is part of the new event, so a newline is not a neutral prefix-overlap fix. This experiment did not test a prompt explicitly requiring a newline or a true model end-of-turn token.

Leading spaces changed no GPT-OSS modes and 2 Qwen modes in the original matrix; they still changed medians or weights. Fine-grid changes affected medians in 4/9 GPT-OSS and 1/9 Qwen arithmetic pairs. Fine-grid comparisons change support and prompt listings; these are not estimates of a continuous distribution.

## Prefix freedom helps interpretation, not universal stability

There were strict-prefix overlaps in 9 GPT-OSS original rows (finer grids) and 77 Qwen original rows (0..10 natural variants and finer grids). Qwen's paraphrase suite added 44 overlapping rows. GPT-OSS paraphrases had none. No problematic encoding was dropped.

Padding removed Qwen's 1/10 overlap and performed well in the original synthetic tasks. Its paraphrase agreement was the same as natural numbers, and it performed worse than natural numbers on GPT-OSS. Newline endings also removed the overlap but frequently degraded results. Prefix freedom is a defensible structural requirement for disjoint continuation events; it is not a demonstrated guarantee of accuracy or invariance.

## SUM versus MEAN changes some conclusions

For bare numeric labels in the original matrix, MEAN changed Qwen's mode in 2/39 cases (the instructed and exact-rubric target-10 cases), but not the arithmetic target-10 case. It changed no GPT-OSS bare-numeric modes. Bare-numeric weights still changed: maximum TV was 0.1976 for GPT-OSS and 0.1771 for Qwen. Maximum interval mean shifts were 0.3843 and 0.3578.

The effects were larger for some other encodings. On GPT-OSS, SUM-to-MEAN changed six newline-ended modes and three finer-grid modes. Equal multi-token lengths preserve score ranking but flatten weights under MEAN; unequal lengths can change ranking too. Token-count associations and every per-encoding comparison are retained in `TABLES.md` and the raw comparisons.

MEAN occasionally improves a synthetic target match, but it is a different heuristic. It does not restore disjointness or produce sequence-event probabilities. Retain SUM as the primary rule and MEAN as an experimental diagnostic.

## Runtime control finding requiring follow-up

Qwen's candidate-order comparisons were exactly equal in all 60 numeric tasks. GPT-OSS had two reproducible differences, both on the -2..2 scale:

- Original arithmetic midpoint: maximum absolute SUM-score difference 0.0167963 nats; TV 0.00124409; interval mean shift 0.00195079.
- Paraphrased midpoint report: maximum absolute SUM-score difference 0.0295739 nats; TV 0.000382901.

Each was reproduced three times in both candidate orders, including a stored-raw-prompt replay for the paraphrase case. Neither changed mode or median. Other selected repeat controls matched exactly. Their cause is unresolved; these results must not be presented as exact order invariance. The engine was not modified. Native independent-oracle checks are the next step before attributing the differences to numerical effects or state handling.

## Recommended production encoding contract

1. Keep explicit `{value,label}` points as the authoritative representation; retain exact whitespace, token IDs/counts, and model/template identity.
2. Use SUM scores and call normalized outputs relative scale weights. Keep ordinal and interval summaries distinct.
3. Reject duplicate token sequences and strict token-prefix overlaps for a contract claiming disjoint candidate continuation events. Continue retaining and reporting overlaps in experiments.
4. Allow natural numeric convenience labels only after actual tokenizer validation. A character-level check is insufficient. Do not silently pad numbers, append endings, or switch to MEAN when validation fails.
5. Support explicit alternative encodings, with the mapping and rubric in the prompt. Fixed-width labels are a promising tested option for Qwen's integer grids, not a universally preferred encoding.
6. Expose the expanded points and scored representation. Do not infer confidence, continuous density, or calibrated intervals from these weights.

Do not freeze a universal default encoding from this experiment. Resolve the native oracle availability and GPT-OSS order-control discrepancies, then test more prompts, symbolic rotations, explicit ending instructions, decimal/signed formats, intermediate finer-grid targets, and independently rated examples. No result here justifies replacing the validated v0.3 scoring engine or implementing a separate inference engine.
