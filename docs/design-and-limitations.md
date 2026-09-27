# Design and limitations

llama-modes exposes structured evaluation at a prepared model state. It does not claim equivalence to free-form reasoning.

## What computation is performed?

Normal chat can generate reasoning tokens before its eventual answer. Direct evaluation reads preferences at the prepared assistant content state; multi-token candidates are evaluated by forcing their prefixes. There is no free answer generation. These are different computational procedures and can legitimately give different answers.

Zero generated tokens does not mean zero model work. Prompt prefill, forced candidate-prefix evaluations, and correctness-first re-prefills still cost compute and memory. Multi-token scoring can be expensive with long prompts or many labels. No universal speedup is promised.

## Scores depend on representation

- Label wording and whitespace affect likelihoods. Tokenization of independently supplied labels can differ from concatenated text tokenization.
- Sequence length affects SUM likelihood. Longer continuations multiply more conditional probabilities.
- MEAN log probability is a heuristic for average token predictability, not a corrected sequence probability.
- SCALE weights are conditional on supplied representations. A..K can avoid specific numeric prefix collisions but does not eliminate representation sensitivity.
- Adding or removing points changes normalization and potentially all derived summaries.
- Dense grids do not automatically form continuous probability densities.
- Numeric category labels alone do not establish meaningful numeric distances.
- Prompt wording, model weights/quantization, native template, and tokenizer matter. A template can even inject a date.
- Candidate-relative weights are not calibrated confidence, probabilities of factual correctness, or validated measures of uncertainty about the real world.

For sensitive applications, use task-specific evaluation, human review, and a rubric appropriate to the decision. A visual distribution does not establish measurement validity.

## The v0.3.1 correctness lesson

During SCALE experiments, GPT-OSS CUDA/SWA multi-token scores changed with candidate order when prompt-state snapshot restoration changed physical KV layout. Diagnostic work compared logical attention inputs, physical layouts, candidate order, and fresh-context oracle scores.

The exact backend arithmetic cause was not isolated. This is not a confirmed upstream llama.cpp backend defect. llama-modes adopted the experimentally validated correctness-first strategy: clear the candidate state and freshly re-prefill the original prompt before later multi-token candidates. This restored agreement in the tested diagnostic cases, at increased prompt-processing cost.

The initial prompt still supplies all first-token scores. The first multi-token candidate uses that fresh state; later multi-token candidates get fresh prompt re-prefill. No change to normal chat semantics is implied. Detailed evidence is preserved in the [Stage 2c report](../experiments/scale_v04/stage2c/REPORT.md) and [server runtime history](../tools/server/README.md#post-decision-and-v1decision-score-text-choices).

## Scope of evidence

Preserved validation covers GPT-OSS 20B and Qwen3.8 Ridge configurations, including Windows CUDA work. It does not establish universal model/template/backend compatibility or identical floating-point behavior across hardware. The existing [100-question Boolean experiment](decision-mode-v0.md) is useful historical evidence, with incomplete historical runtime settings. The [SCALE experiments](../experiments/scale_v04/README.md) include synthetic tasks and explicitly excluded early runs; do not pool them indiscriminately.

Use the [benchmark harness](../benchmarks/README.md) for new measurements. Report model, build, dataset, runtime settings, hardware, errors, and raw results alongside any comparison.
