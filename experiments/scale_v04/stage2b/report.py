"""Report Stage 2b without changing the preserved Stage 2 artifacts."""

import hashlib
import json
import math
from pathlib import Path

import investigate
import run


ROOT = Path(__file__).resolve().parent


def main():
    cases = investigate.cases()
    lines = ["# Stage 2b: GPT-OSS candidate-order investigation", "",
             "The completed 1218-row Stage 2 experiment was not rerun or modified. This investigation uses its two exact anomalous prompts and targeted controls. Production C++, CI, and the runtime ZIP are unchanged. No commit, push, or tag was made.", "",
             "## Exact original cases", "",
             "Both cases use natural numeric labels on -2..2: original API order `[-2,-1,0,1,2]`, reversed order `[2,1,0,-1,-2]`. These are string labels, not numeric JSON choices. Token IDs are `[[12,17],[12,16],[15],[16],[17]]`, with counts `[2,2,1,1,1]`. There are no duplicate or strict-prefix candidate sequences; the two negative labels share the first token.", "",
             "The prepared prompt bytes, prompt token IDs, and messages are identical between the two orders in each archived pair. The request changes only the choices array order. Exact request/response evidence remains in Stage 2's http.jsonl and results.jsonl; cases.json in the Stage 2b runs also contains the extracted rows.", ""]
    evidence = {}
    for case in cases:
        row = case["original"]
        oracle_file = ROOT / "oracle-default-with-control" / (case["name"] + "-original-scores.json")
        tokens = json.loads(oracle_file.read_text())
        oracle = [math.fsum(s) for s in tokens]
        prompt = row["prepared_prompt"]
        (ROOT / (case["name"] + "-prompt.txt")).write_bytes(prompt.encode("utf-8"))
        for name, labels in [("original", ["-2", "-1"]), ("reversed", ["-1", "-2"])]:
            run.write_json(ROOT / (case["name"] + "-minimal-" + name + ".json"), {"prompt": prompt, "choices": labels})
        lines += [f"### {case['name']}", "", f"Source: `{case['source_directory']}`. Prepared prompt length: {len(row['prompt_tokens'])} tokens. UTF-8 SHA-256: `{hashlib.sha256(prompt.encode()).hexdigest()}`.", "", "```text", prompt, "```", "",
                  "Deltas are reversed minus original, in natural-log units. All float values below use Python's round-trip representation of the preserved JSON doubles.", "",
                  "| Value / label | Token IDs | Count | Original SUM | Reversed SUM | Delta | Fresh oracle SUM |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: |"]
        for value, label, ids, a, b, c in zip(row["values"], row["labels"], row["token_ids"], row["sum_log_probability"], case["reversed"]["sum_log_probability"], oracle):
            lines.append(f"| {value} / `{label}` | {ids} | {len(ids)} | {a!r} | {b!r} | {b-a!r} | {c!r} |")
        evidence[case["name"]] = {"oracle_token_scores": tokens, "original_minus_oracle": [a-b for a, b in zip(row["sum_log_probability"], oracle)],
                                  "reversed_minus_oracle": [a-b for a, b in zip(case["reversed"]["sum_log_probability"], oracle)]}
    lines += ["", "## Runtime and minimal reproduction", "",
              "The model is the original GPT-OSS 20B MXFP4 GGUF, SHA-256 and DLL/EXE identities retained in Stage 2 config.json and identity.json here. Native Windows, RTX 5080, one server process and one slot, sequential HTTP calls, 4096 context, 512 batch and microbatch, 99 GPU layers (all model layers offloaded), native Jinja template, default f16 KV, Flash Attention auto, no warmup, no sampling or speculative model. Thread count reported by startup was 8. Raw prompts avoid current-date/template changes.", "",
              "Start the unchanged executable with the model path from identity.json:", "", "```powershell",
              "& C:\\AI\\llama-modes-v03\\llama-server.exe -m MODEL_PATH --host 127.0.0.1 --port 8094 -c 4096 -np 1 -ngl 99 -b 512 -ub 512 --jinja --metrics --no-warmup",
              "python experiments/scale_v04/stage2b/investigate.py live --minimal --repetitions 3 --output NEW_OUTPUT_DIRECTORY", "```", "",
              "For each prompt, the two saved *-minimal-original.json and *-minimal-reversed.json files are the smallest candidate-set reproducer. POST them unchanged to /decision. A one-candidate request has no order permutation and supplies the fresh-candidate control. A clean restart and repeated requests reproduce the same scores exactly.", "",
              "## Targeted results", "",
              "| Profile | Requests | Arithmetic -2 order delta | Arithmetic -1 order delta | Rubric -2 order delta | Rubric -1 order delta |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    profiles = {}
    for directory in sorted(ROOT.glob("live-*")):
        path = directory / "results.jsonl"
        if not path.exists():
            continue
        rows = [json.loads(s) for s in path.read_text().splitlines()]
        values = []
        max_repeat = 0.0
        by_key = {}
        for row in rows:
            key = (row["case"], tuple(row["choices"]))
            scores = {r["text"]: r.get("sum_log_probability", r.get("logit")) for r in row["response"]["choices"]}
            if key in by_key:
                max_repeat = max(max_repeat, max(abs(scores[label]-by_key[key][label]) for label in scores))
            by_key[key] = scores
        for case in cases:
            a, b = by_key[(case["name"], ("-2", "-1"))], by_key[(case["name"], ("-1", "-2"))]
            values.extend([b[label]-a[label] for label in ["-2", "-1"]])
        lines.append(f"| {directory.name} | {len(rows)} | " + " | ".join(repr(v) for v in values) + " |")
        profiles[directory.name] = {"requests": len(rows), "two_candidate_deltas": values, "maximum_repeat_delta": max_repeat}
    lines += ["", "All repeated identical requests were bit-identical within each tested profile. CPU and batch-64 profiles have one request per order rather than repeated trials. Changing batch size or backend changes absolute scores; those absolute changes are not scored as order anomalies.", "",
              "The baseline candidate reduction includes singleton controls, both negative labels, single-token distractors in multiple positions, signed and unsigned multi-token distractors, and the city labels. The effect follows a signed candidate evaluated after another multi-token candidate and the restore it triggers. A preceding single-token label has no effect. An intervening single-token label does not remove it. `New York` or `+2` before `-2` reproduces it, so a shared prefix and the predecessor's minus sign are not required. The tested unsigned city labels and positive `+2` do not show the same effect; this does not establish that only signed labels can be affected.", "",
              "The attempted batch/microbatch 1 profile could not start: the existing runtime asserted `n_tokens_all <= cparams.n_batch` during initialization. Its log and failed connection are retained. It provides no scoring evidence. Batch/microbatch 64 was used instead.", "",
              "## Known-good city control", "",
              "The exact prompt tokens come from the existing Windows validation input C:\\AI\\decision-oracle-gptoss.json; city-control.json preserves them and their decoded prompt. Candidates are New `[3443]`, New York `[3443,6175]`, New Jersey `[3443,23096]`, London `[51162]`. This repeats the requested shared-prefix labels using the archived validation prompt; the original historical request specifically containing all four labels was not present in that file.", "",
              "| Label | Default CUDA fresh oracle SUM |", "| --- | ---: |"]
    city = json.loads((ROOT / "city-control.json").read_text())
    city_oracle = json.loads((ROOT / "oracle-default-with-control/city_control-original-scores.json").read_text())
    for label, scores in zip(city["labels"], city_oracle):
        lines.append(f"| {label} | {math.fsum(scores)!r} |")
    lines += ["", "The default CUDA server control matches all four oracle sums exactly in both orders. Its order delta is zero. The CPU server control also matches the CPU oracle exactly. The FA-off fresh-context city oracle is invariant; FA-off server city-label controls on the two anomalous prompts were invariant, but the archived city prompt was not separately sent to the FA-off server. The corrected oracle creates a fresh context per candidate and completes prompt decoding before forcing candidate-prefix tokens (tests/test-save-load-state.cpp:678, 704-716, 735-746). Both oracle candidate orders produce exactly the same aligned token scores.", "",
              "## Narrowed cause and implications", "",
              "The demonstrated mechanism is a restoration-triggered, backend-dependent score change: the first multi-token candidate matches its fresh-context oracle, while a later signed candidate uses a restored state and can differ. Neither original nor reversed five-choice response matches the oracle for every candidate. Each negative label matches the oracle when evaluated alone or as the first multi-token candidate. First-token scores are unchanged; the difference is in scoring the second token after forcing `-`.", "",
              "Debug logs establish that the full-attention cache restores all 181 or 252 prompt cells, but the SWA cache restores 128 cells. For the 181-token case, SWA positions 53..180 are repacked into cells 0..127; for the 252-token case, positions 124..251 are retained. Source code filters already SWA-masked cells on sequence-state serialization and allocates new slots on restore. Consequently, the first forced prefix and subsequent restored prefixes have different physical SWA layouts. The model's SWA window is 128. See layout.stderr.log and src/llama-kv-cache.cpp:2055, 2084, 2337, 2397.", "",
              "CPU matches the CPU oracle exactly for the anomalous candidates and is order invariant. Disabling CUDA graphs does not change the default CUDA anomaly. FA-off still has an arithmetic-case anomaly (up to 0.0553196215 nats), while that rubric case becomes invariant. Batch 64 removes the arithmetic anomaly but leaves a smaller rubric anomaly. No concurrency is needed: every request runs alone in one slot. Raw token identity and restart/repeat controls exclude prompt preparation and cross-request accumulation as explanations for these reproductions.", "",
              "The length probe is consistent with SWA compaction being relevant: both sets of 64/96/127/128-token tails are invariant; one 129-token rubric tail has a 0.0368597095-nat difference. Not every longer prompt has an anomaly. These tails alter prompt content, so this is supporting evidence, not a controlled proof of a particular kernel's numerical error.", "",
              "The evidence does not yet distinguish a CUDA reduction/layout numerical effect from a CUDA state-handling defect. No tensor-by-tensor fresh/restored comparison was performed, and no exact CUDA operation has been identified. It would be unjustified to call this proven KV corruption, proven candidate-bookkeeping error, or harmless rounding. The production v0.3 CUDA scoring invariant is implicated, but a source-level logic bug is not demonstrated.", "",
              "Do not freeze production SCALE scoring or widen tolerance to 0.03/0.06 nats on this evidence. Keep 2e-4 nats as the existing diagnostic oracle-comparison threshold for matched runtime settings; it is a test criterion, not a universal backend accuracy guarantee. Report absolute per-candidate score errors and aligned distribution changes, preserve backend/batch/KV settings, and keep the affected cases explicitly failing that criterion. Unchanged mode and median do not establish score correctness. API/mathematical design work can continue, but production rollout should wait for resolution or an explicitly reviewed numerical policy.", "",
              "## Proposed next action; no fix implemented", "",
              "Review a focused fresh-versus-restored tensor/layout diagnostic at the first forced `-` step, starting at server-context.cpp:3863 (save), 3889 (restore), and 3165 (forced input), then the SWA serialization and restoration sites above. Compare KV values, positions, masks, attention outputs and logits to locate the first divergence. If layout alone causes the change, evaluate layout-preserving sequence snapshots. A correctness-first fallback is fresh prompt evaluation for each candidate, but that loses shared-prefill performance and must itself pass the oracle. Neither is a proven minimal fix yet. Restoring before every candidate could equalize order while still missing the fresh oracle, so it is not sufficient evidence of correctness.", "",
              "Proposed regression: extend the existing server test file, not a new production test target, with these two preserved prompts, `[-2,-1]` and reversed order, singleton scores, and a fresh-context oracle. Require <=2e-4 nats under matched settings, include the four-city zero-delta control, and repeat after restart. Keep CPU/default CUDA coverage distinct. No C++ or test-suite change has been made.", "",
              "## Oracle availability and optional packaging proposal", "",
              "The restored native Windows executable was used directly. Its --version identifies commit 65f4875, matching v0.3.0, and its hash is preserved. Nothing was copied into or removed from the user runtime directory, and no runtime ZIP was modified. The existing workflow already builds test-save-load-state but uploads only the server ZIP. No CI change is needed for this investigation. For future availability, propose a separate llama-modes-oracle-win-cuda artifact containing the existing executable and its runtime DLLs; leave llama-modes-win-cuda.zip server-only. An earlier local CI draft was reverted; this remains a proposal only.", ""]
    run.write_json(ROOT / "comparison.json", {"cases": evidence, "profiles": profiles})
    (ROOT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
