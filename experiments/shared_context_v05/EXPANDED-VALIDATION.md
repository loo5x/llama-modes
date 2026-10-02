# Expanded aligned-prefix validation

The batch-aligned shared-prefix strategy passes the expanded CUDA correctness matrix on GPT-OSS 20B MXFP4 and the local Qwen3.8 27B Ridge model, at batch/microbatch 32, 128, and 512. All 648 complete shared question score vectors match their same-configuration fresh oracle exactly. All 192 isolated split comparisons also match, including full-vocabulary logits. The independent C++ fresh-context oracle passes all 54 new checks, with maximum token/SUM difference `4.902744876744691e-13`. The diagnostic threshold remains `2e-4`.

## Fixtures and coverage

| Model / fixture | Complete prompt lengths | Common prefix | Reused prefix at batch 32 / 128 / 512 | Shared vectors | Failed vectors |
|---|---|---:|---|---:|---:|
| GPT-OSS / records | 807, 811, 821 | 787 | 768 / 768 / 512 | 216 | 0 |
| GPT-OSS / history | 1749, 1761, 1765 | 1731 | 1728 / 1664 / 1536 | 216 | 0 |
| Qwen / records | 857, 861, 872 | 834 | 832 / 768 / 512 | 216 | 0 |

The records fixture contains 24 numbered service records with varying check counts and a named city. Its independent questions use Boolean `true/false`, Choice `New/New York/New York City/London`, and Scale signed integer labels. The history fixture contains 52 inspection entries. Its questions use Boolean `yes/no`, Choice labels with leading spaces, and Scale decimal labels `-2.0/-1.0/0.0/1.0/2.0`. Candidates include one through four tokens on GPT-OSS, including strict-prefix overlap in Choice. Scale representations have no strict token-prefix overlap.

These are synthetic scorer-correctness fixtures, not answer-quality or calibration measurements. Every question receives exactly `context + "\n\n" + question`, as a user message. The native template is rendered using the two content-entry probes with assistant continuation disabled. For all nine prepared prompts, `/decision` with original messages produces exactly the same choice results as `/decision` with the prepared prompt. Native templates, prepared text, tokens, candidate representations, and actual injected dates are preserved.

The longest common prefix is identified after complete prompt tokenization. The reused portion ends at a complete logical batch boundary; the remaining common tokens are evaluated with the question suffix. This preserves every prompt token and the whole-prompt decode schedule. Batch/microbatch are equal in all tests.

## Execution and checks

Each fixture/batch configuration has its own shared context. Sequence 0 prefills its protected prefix once. Sequence 1 prepares the question, and sequence 2 evaluates candidate prefixes. Candidate scratch is removed before question cleanup and preparation. All six question orders, both candidate orders, and two repetitions execute on that context. Serialized prefix and question states stay unchanged after every candidate. No snapshot restoration, sampling, generated reasoning, or answer insertion is used.

The 648 shared vectors contain 2,304 candidate evaluations. Their complete per-token vectors, SUM scores, candidate-relative SUM weights, and oracle references are saved. There are also 192 aligned-split candidate comparisons using fresh contexts exclusively on sequence 0. All numerical differences and vocabulary-logit differences are zero; all order/repeat score spans are zero. Full logits are compared in memory, with their maximum differences saved. Score lengths, finite values, SUM reconstruction, normalization, complete matrices, decode positions/chunk sizes, and protected-state flags passed verification.

The independent C++ oracle was actually rerun for each new fixture, batch, question, and candidate direction: 18 invocations per fixture, 54 total. The existing unchanged executable and its previously copied v0.4 DLL dependencies were reused after hash and C++ source/header checks. Each candidate gets a fresh context. Python reserves three sequences/outputs; C++ uses one sequence and default output reservation. Their per-token and SUM scores match within the diagnostic threshold. Commands and full C++ token-score vectors are preserved in each fixture's `cpp-checks.json`.

Runtime settings remain Windows x64, RTX 5080, exact v0.4 DLLs, context 4096, unified KV, full SWA allocation, f16 K/V, Flash Attention on, 99 requested GPU layers, and eight decode/prefill threads. Inference processes ran sequentially. This is not a timing or throughput benchmark.

Model hashes:

- GPT-OSS: `27cd6c432c7672cb812a92f611cf3ba7bbc35928262bb1e1253ff4ee6ae35901`.
- Qwen: `95580dbdaad579582ee898257116abc18d7f3625a00c16a15735d41444a09f5e`.

The guarded ctypes ABI is unchanged. DLL identities, parameter layouts, actual context parameters, model paths, and original C++ binary identity are included with the evidence.

## Limits and next step

Agreement is with a fresh oracle at the same batch settings. Scores are not invariant across different batch sizes: maximum cross-batch SUM spans in these fixtures are 4.731906508054323, 5.363217456729833, and 1.7957415442902427 respectively. The shared path reproduces the corresponding fresh behavior; alignment does not eliminate this pre-existing batch dependence.

Validation now covers two native templates, common prefixes up to 1,731 tokens, longer forced candidate prefixes, and batch 512 with a non-empty reusable prefix. It still does not cover arbitrary models, unequal batch/microbatch sizes, contexts near capacity, cache exhaustion, automatic context shifting, simultaneous requests, tools, or multimodal prompts. Full SWA allocation and sequential scoring remain part of the tested configuration.

The next step is a reviewable integration design that preserves this decode schedule, scoring isolation, context capacity checks, and a fresh-evaluation fallback when a usable aligned prefix does not exist. `/evaluate` was not implemented or enabled in this stage. Existing v0.4 production behavior remains unchanged.

## Reproduction

The executed preparation commands used the preserved GPT-OSS path and the local Qwen GGUF:

```powershell
python experiments/shared_context_v05/expanded_cases.py --output build/shared-v05/expanded-gptoss-cases --model C:/Users/lucia/.cache/huggingface/hub/models--ggml-org--gpt-oss-20b-GGUF/snapshots/ef9b12f2ff56c69cf32153a02784e7a3c88bf524/gpt-oss-20b-MXFP4.gguf
python experiments/shared_context_v05/expanded_cases.py --output build/shared-v05/expanded-qwen-cases --model C:/AI/qwen38-ridge/Qwen3.8-27B-Ridge-3.7bpw.gguf --fixtures records
python experiments/shared_context_v05/expanded_aligned.py --source build/shared-v05/expanded-gptoss-cases/records --output build/shared-v05/expanded-gptoss-records
python experiments/shared_context_v05/expanded_aligned.py --source build/shared-v05/expanded-gptoss-cases/history --output build/shared-v05/expanded-gptoss-history
python experiments/shared_context_v05/expanded_aligned.py --source build/shared-v05/expanded-qwen-cases/records --output build/shared-v05/expanded-qwen-records
python experiments/shared_context_v05/expanded_oracle.py --run build/shared-v05/expanded-gptoss-records
python experiments/shared_context_v05/expanded_oracle.py --run build/shared-v05/expanded-gptoss-history
python experiments/shared_context_v05/expanded_oracle.py --run build/shared-v05/expanded-qwen-records
python experiments/shared_context_v05/verify_expanded.py build/shared-v05/expanded-gptoss-records
python experiments/shared_context_v05/verify_expanded.py build/shared-v05/expanded-gptoss-history
python experiments/shared_context_v05/verify_expanded.py build/shared-v05/expanded-qwen-records
python -m py_compile experiments/shared_context_v05/expanded_cases.py experiments/shared_context_v05/expanded_aligned.py experiments/shared_context_v05/expanded_oracle.py experiments/shared_context_v05/verify_expanded.py
git diff --check
git status --short --branch
git rev-parse HEAD main v0.4.0
```

Use new output directories for reruns and run inference commands sequentially. `expanded_oracle.py` requires the verified executable/dependencies at `build/shared-v05/run6/cpp-oracle-correct`, created in the prior stage. Both inference scripts return status 1 for failed numerical checks; all completed runs returned status 0. Structural verification reports numerical failures separately from matrix integrity.

The final runner can also read a preserved fixture directory under `results/expanded` to avoid rerendering a template with a new date. Its prefix is now calculated directly from complete prompt token arrays rather than reading the preparer's prefix metadata. This small final change was checked to produce exactly the same lengths, 787/1731/834, as those used during inference. No numerical scoring, scheduling, or tolerance logic changed. Original source snapshots remain with the local runs.

## Changed files and git

New source files: `expanded_cases.py`, `expanded_aligned.py`, `expanded_oracle.py`, and `verify_expanded.py`. New report: this file. Exact evidence paths and hashes are in [results/expanded/FILES.json](results/expanded/FILES.json). The evidence includes all new prepared cases, native template properties/commands, context and ABI parameters, isolated/shared vectors, summaries, C++ vectors/commands/identity, and verification outcomes. Local native logs and executed source snapshots remain under ignored `build/shared-v05`.

All earlier source/evidence manifests remain hash-identical. Syntax checks, ASCII/trailing-whitespace checks, complete matrix verification, and final manifest checks passed. No existing tracked file changed.

Final branch remains `feature/shared-context-v05`; HEAD and main remain `6e0c988e784000916e00c87915d47dc3bee6da32`, and v0.4.0 remains `fc2db284ec4717f5799e31c81deef1021321c8ec`. Git status contains only `?? experiments/shared_context_v05/`. There was no commit, push, endpoint integration, or external submission. Work stops after expanded validation and this report.
