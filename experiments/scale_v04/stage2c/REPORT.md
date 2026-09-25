# Stage 2c: GPT-OSS state restoration divergence

The first numerical divergence is at layer 0's CUDA SWA attention operation, after decoding the forced prefix token. An immediate sequence snapshot/restore is sufficient. The logical attention inputs are identical; their physical KV placement is different. Tiny attention-output differences subsequently grow into the previously observed candidate-score differences. Fresh prompt recomputation restores exact agreement in the tested cases.

This narrows the mechanism to layout-sensitive attention arithmetic and downstream amplification. It does not identify a defective CUDA instruction or prove a particular reduction implementation is wrong. The v0.3 candidate-order correctness problem remains real, even though no loss of required logical KV values was found.

## Scope and identity

Only the existing objective_2 and paraphrase_2 signed cases, plus the existing New/New York/New Jersey/London control, were used. The 1,218-row SCALE experiment was not rerun. Stage 2 and Stage 2b files were not edited. Production C++, CI, public API, and runtime packaging were not changed.

The primary evidence is under `matched/`. Native Windows, RTX 5080, GPT-OSS 20B MXFP4, the existing v0.3 DLLs, context 4096, batch/microbatch 512/512, 8 threads, all model layers offloaded, f16 KV, Flash Attention auto, one sequence, one output, `swa_full=false`, `kv_unified=false`. The SWA window is 128, allocated SWA capacity 768 cells, full-attention capacity 4096 cells. Exact parameters and identities are in each run's config.json and identity.json. Model SHA256: `27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901`.

The raw API reports version `0.4.1-dev`; it is the same DLL build identified and validated against tag commit 65f4875 in Stage 2b. The binding checks the exact llama.dll hash, not that version string. `verification.json` verifies runtime and model hashes independently.

The exact prepared prompts and token arrays are preserved in `matched/baseline/cases.json`, with the original prompt text also in [objective_2-prompt.txt](../stage2b/objective_2-prompt.txt) and [paraphrase_2-prompt.txt](../stage2b/paraphrase_2-prompt.txt). The signed candidates are -2 `[12,17]` and -1 `[12,16]`. The forced prefix is token 12. Objective prompt length is 181; rubric prompt length is 252. No generation or sampling was used.

## Paths and checkpoints

- A: new context, decode prompt, decode prefix 12, capture logits.
- B: new context, decode prompt, save and immediately restore the sequence, decode prefix 12.
- C: new context, decode prompt, save sequence, decode prefix 12 for candidate 1, restore, decode prefix 12 again. The final target token is scored, not decoded, matching /decision and the oracle boundary.
- D: after candidate 1, remove sequence 0, re-decode the exact prompt token array, decode prefix 12.
- FULL_B/FULL_C: replace sequence state operations with full-context state operations.
- COPY: preserve the prompt using sequence copy 0 -> 1, evaluate candidate 1 on sequence 0, then evaluate the same prefix on sequence 1.

COPY necessarily uses two sequences, two reserved outputs, and a unified KV cache. Its separately measured fresh baseline matches the one-sequence baseline bit for bit. This is a copy diagnostic, not a validated multi-candidate implementation.

Each path saves full-vocabulary float32 logits at prompt completion, before the measured forced decode, and after it; C/D also save the candidate-1 checkpoint. State metadata includes logical positions, occupied serialized cells for both caches, per-layer K/V hashes, and complete serialized-state hashes. Allocation capacities are in native.log. The serializer's occupied-cell count must not be confused with allocated capacity or logical prompt length.

Restoration does not restore the output logits buffer in this build. B still has the original prompt logits. C has stale candidate-1 logits before the next decode. This is expected buffer behavior, not evidence of a new scoring error: v0.3 retains first-token scores separately. D recomputes the prompt logits exactly.

## Full-vocabulary results

All differences below compare the output after the forced prefix to A over all 201,088 vocabulary entries. B and C are bit-identical to each other. Capturing tensors with the evaluation callback does not change the output logits; two independently instrumented passes match the uninstrumented pass exactly.

| Prompt | Path | Maximum absolute logit difference | RMS logit difference | Changed entries |
|---|---|---:|---:|---:|
| objective_2 | B or C | 0.11325931549072266 | 0.02090169488717491 | 201088 |
| objective_2 | D | 0 | 0 | 0 |
| objective_2 | FULL_B or FULL_C | 0.13756752014160156 | 0.023650006765619132 | 201088 |
| paraphrase_2 | B or C | 0.11482834815979004 | 0.022821069240417793 | 201086 |
| paraphrase_2 | D | 0 | 0 | 0 |
| paraphrase_2 | FULL_B or FULL_C | 0 | 0 | 0 |
| city control | B/C/D/FULL_B/FULL_C | 0 | 0 | 0 |
| all three | COPY versus its fresh baseline | 0 | 0 | 0 |

The largest changed token IDs, original/recomputed logits, and exact deltas are in `matched/baseline/results.json`. Raw arrays are the corresponding `after_force.f32` files, indexed by vocabulary ID.

The following are conditional target-token log probabilities after the prefix, not complete candidate SUM scores. Adding the unchanged first-token score reproduces the Stage 2b SUM anomaly exactly.

| Prompt | Target | A / independent oracle / D | B / C | Full-context restore |
|---|---|---:|---:|---:|
| objective_2 | 17 (2) | -3.9317038064842635 | -3.914907477776758 | -3.9832486098456408 |
| objective_2 | 16 (1) | -0.39507889803699786 | -0.40728952733730495 | -0.4173802321600938 |
| paraphrase_2 | 17 (2) | -3.3101619903179595 | -3.3397358778896327 | -3.3101619903179595 |
| paraphrase_2 | 16 (1) | -0.03837434688534249 | -0.03719223775291374 | -0.03837434688534249 |

The existing native `test-save-load-state.exe` was rerun in both candidate orders for all three prompts. All per-token scores match the preserved independent oracle exactly. These six executable runs are in `oracle-confirmation/`. That executable exposes token log probabilities, not full logits. Therefore full-vocabulary differences use the diagnostic fresh-context A arrays; their scored target values are independently cross-checked against the executable. No claim is made that the executable itself dumped full-vocabulary arrays.

## First divergence and state evidence

At prompt snapshot restoration, physical layout already changes. No new model output is computed until the forced decode. During that decode, all captured layer-0 normalization and Q/K/V tensors match exactly. The first changed captured result is `FLASH_ATTN_EXT` (operation 74), exposed by its reshape `kqv_out-0`.

| Comparison | First attention-output maximum difference | First changed projected attention output | First changed layer output |
|---|---:|---|---|
| objective_2 A vs B | 9.5367431640625e-7 | layer 18, 0.0147857666015625 | layer 18, 0.9170684814453125 |
| paraphrase_2 A vs B | 4.76837158203125e-7 | layer 14, 0.00074005126953125 | layer 14, 0.1793212890625 |
| objective_2 A vs FULL_B | 7.152557373046875e-7 | layer 4, 0.00013256072998046875 | layer 4, 0.1010894775390625 |

Several early SWA attention results differ at approximately float32 rounding scale while the following projected/layer outputs remain bit-identical. Later the difference propagates and grows. The traces measure that amplification; they do not identify a particular quantization threshold or MoE routing decision as its cause.

The first-layer attention inputs were also dumped, including tensor strides, operation parameters, Q, cached K/V, mask, and attention sinks. Aligning visible KV rows by logical token position gives exact equality of every one of those inputs between A and B/C/D/FULL_B/FULL_C. There are the same 128 visible positions. The captured difference is therefore not explained by a missing visible token, changed RoPE position, changed sink value, or changed first-layer KV payload.

For objective_2:

- Fresh prompt: full/SWA occupied cells 181/181. The next forced token occupies physical cell 181; visible SWA cells are 54..181, representing logical positions 54..181.
- Sequence restore: full/SWA occupied cells 181/128. SWA retained positions 53..180 occupy cells 0..127. The forced token occupies cell 128; visible cells 1..128 still represent exactly logical positions 54..181.
- Full-context restore: retains all 181 prompt cells but resets the cache search head to 0. The next forced token replaces an already masked SWA cell at physical cell 0. Visible logical positions are unchanged, but their physical ordering changes. This also diverges.

For paraphrase_2, sequence restore compacts 252 SWA prompt cells to the 128 cells for positions 124..251. The next forced token is at logical position 252. `matched/attention-input-comparison.json` records exact physical and logical lists for each path.

Sequence snapshot hashes are identical before and after B/C restoration, across both cache types and all K/V layers. Full-context snapshot hashes are likewise identical before and after FULL_B/FULL_C restoration. The next allocation still differs because that serialized representation does not preserve the original search head. Thus matching serialized bytes does not imply matching physical execution history.

There is no evidence of full-attention KV corruption at restoration. Full-attention layers later receive changed activations after SWA differences propagate, so the eventual discrepancy is not confined to SWA outputs. The logical serialized state needed by the first divergent attention operation is preserved; the execution layout is not. Physical arrangement is sufficient to distinguish the measured attention executions with otherwise identical logical inputs. Compaction alone is too narrow an explanation because full-context restoration also changes subsequent placement without dropping the old prompt cells.

This does not prove which CUDA reduction/tiling step causes the rounding difference. Stage 2b already showed divergence with Flash Attention disabled; the current default-path trace should not be interpreted as a Flash-Attention-only bug.

## Correctness fallback and cost

Fresh re-prefill matches A over the entire vocabulary for all three prompts. A separate repeated scoring diagnostic tests the two signed candidates and all four city labels in forward and reversed order. For each strategy and order it runs six times, discarding the first timing as warm-up. Every re-prefill per-token score in all 36 requests matches the independent oracle exactly. There are 72 total benchmark requests including the snapshot strategy.

| Task | Snapshot median | Re-prefill median | Ratio |
|---|---:|---:|---:|
| objective_2, two candidates | 48.63 ms | 78.31 ms | 1.61x |
| paraphrase_2, two candidates | 50.87 ms | 82.44 ms | 1.62x |
| city control, four candidates | 44.26 ms | 116.15 ms | 2.62x |

These are synchronized diagnostic inference-loop timings on this GPU. They include prompt decoding, candidate-prefix decoding, snapshot/restore when applicable, and copying output arrays; they exclude model/context initialization, HTTP overhead, instrumentation dumps, and Python log-softmax calculations. Each median uses ten timed requests across the two orders. The simple fallback re-prefills even for single-token choices. No optimization was attempted. These are not server throughput benchmarks or general bounds for longer prompts/more candidates.

Re-prefill is a reliable correctness fallback for these tested prompts/configuration. It is not yet a production fix or a proof across other models, simultaneous slots, longer prompts, and batching schedules.

## Source areas and ranked proposals

1. Smallest scorer-level correctness fallback: replace between-candidate sequence restoration with clearing the relevant sequence and re-decoding the exact prepared prompt, preserving the prompt/forced-prefix decode boundary. Relevant integration points are `tools/server/server-context.cpp` score_decision around lines 3825-3894 and forced-prefix scheduling around line 3165. No public API change is needed. This is the recommended first patch to review; slot scheduling and counters still need a focused regression test.
2. Protected prompt sequence plus candidate scratch sequence: the measured single-copy diagnostic preserves correctness. Repeated scratch cleanup, SWA retention, shared-cell allocation, context limits, and concurrent slots remain unvalidated. This is more invasive than re-prefill and must not be substituted on the strength of one copy alone.
3. Layout-preserving snapshots: investigate `src/llama-kv-cache.cpp` state_write around 2055, state_read_meta around 2337, full-restore `head = 0` around 2502, and find_slot around 898; `src/llama-kv-cache-iswa.cpp` around 259 composes the two caches. Preserving physical cell placement and allocation state could retain the fresh arithmetic path, but is a broader memory/state-format change. Merely retaining all SWA cells or using the current full-context API is demonstrably insufficient.
4. Backend/layout-independent attention arithmetic: investigate `src/llama-graph.cpp` build_attn_mha around 2623-2650 and CUDA attention dispatch/reduction code in `ggml/src/ggml-cuda/fattn.cu` and `fattn-common.cuh`. Canonical logical ordering or more stable arithmetic may help, but the precise kernel-level change and cost are not established. Flash-Attention-off behavior must also be addressed.

The regression proposal is the preserved two-candidate signed reproducer in both orders, repeated, checking per-token/SUM scores against fresh-context evaluation, plus the city control. Cover immediate round-trip and re-prefill, the tested CUDA/SWA configuration, and existing CPU invariance. Do not silently increase the score tolerance to accept the current discrepancy.

Recommendation: patch and validate v0.3 scoring correctness before implementing or freezing production SCALE behavior. Mathematical/API design discussion can continue while the backend investigation stays open. Representation choices do not repair this execution-order dependency.

## Reproducibility and preserved limitations

See [README.md](README.md) for commands. `native.py` is a hash-guarded ctypes adapter for the existing DLLs, `diagnose.py` runs the native experiment, `analyze.py` checks and compares the evidence, and `verify.py` verifies identity and artifacts. No native binary was rebuilt. Each run includes its exact source snapshot.

The authoritative analysis is `matched/analysis.json`: 90 automated checks passed, including oracle values, full-vocabulary instrumentation agreement, state hashes, immediate/post-candidate equality, aligned attention inputs, sequence-copy controls, and repeated fallback scores.

Earlier root-level baseline/traced/attention-inputs/copy/benchmark directories are retained as pilot evidence: the initial raw context defaults used a full-size SWA allocation and different output/unified-cache defaults. Their measured logits agree with the corrected matched runs, but their timings are not the reported primary timings. The first pilot benchmark also reused the original first-token logits during re-prefill; `benchmark-verified` recomputes them. The primary benchmark uses the corrected implementation.

`matched/copy/` preserves a failed context initialization: two sequences with only one reserved output triggered the existing n_outputs_max assertion before scoring. `matched/copy-validated/` reserves two outputs and is the measured copy experiment. This failure is not counted as inference evidence.

The remaining open question is the exact CUDA arithmetic implementation responsible for the layout-dependent first attention result, and whether a practical backend change can bound downstream amplification without forcing identical physical layout. No source-level backend fix has been demonstrated or applied.
