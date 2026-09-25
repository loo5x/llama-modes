"""Build descriptive tables from preserved experimental rows, without inference."""

import json
from pathlib import Path
import statistics

import run


ROOT = Path(__file__).resolve().parent


def main():
    lines = ["# SCALE v0.4 representation experiment", "", "These are descriptive results on synthetic tasks, not evidence of calibration.", ""]
    details = {}
    for model in ["gptoss", "qwen"]:
        directory = ROOT / "results" / (model + "-validated-full")
        summary = run.analyze(directory)
        rows = [json.loads(s) for s in (directory / "results.jsonl").read_text().splitlines()]
        good = [r for r in rows if r["status"] == "ok"]
        pairs = json.loads((directory / "comparisons.json").read_text())
        config = json.loads((directory / "config.json").read_text())
        lines += [f"## {config['args']['model_id']}", "", f"Completed {len(rows)} matrix rows; {len(good)} successful; {len(rows)-len(good)} errors.", "",
                  "SUM comparisons use total variation distance (TV), from 0 to 1, after aligning by numeric value. The interval mean shift is reported only for interval cases.", "",
                  "| Comparison | Pairs | Mode changes | Median changes | Mean TV | Max TV | Max absolute interval mean shift |",
                  "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
        for name, item in summary["comparisons"].items():
            if ":sum ->" in name and name.endswith(":sum"):
                shift = item["max_absolute_expected_value_shift"]
                lines.append(f"| {name} | {item['pairs']} | {item['modal_changes']} | {item['median_changes']} | {item['mean_total_variation']:.6f} | {item['max_total_variation']:.6f} | {shift:.6f} |")
        lines += ["", "SUM versus MEAN on the same scored rows:", "",
                  "| Representation | Cases | Mode changes | Median changes | Mean TV | Max TV |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for name, item in summary["comparisons"].items():
            if ":sum ->" in name and name.endswith(":mean"):
                lines.append(f"| {name.split(':')[0]} | {item['pairs']} | {item['modal_changes']} | {item['median_changes']} | {item['mean_total_variation']:.6f} | {item['max_total_variation']:.6f} |")
        tokenizations = {}
        for row in good:
            key = f"{row['scale']}:{row['variant']}"
            tokenizations.setdefault(key, {"values": row["values"], "labels": row["labels"], "token_ids": row["token_ids"],
                                           "token_counts": row["token_counts"], "issues": row["token_issues"]})
        lines += ["", "Tokenization of the five main encodings:", "", "| Scale | Encoding | Token counts in value order | Strict-prefix pairs |", "| --- | --- | --- | --- |"]
        for key, tokenization in tokenizations.items():
            scale, variant = key.split(":")
            if variant in ["numeric", "fixed", "symbol", "anchor", "numeric_ended"]:
                prefixes = [(tokenization["labels"][a], tokenization["labels"][b]) for a, b in tokenization["issues"]["strict_prefixes"]]
                lines.append(f"| {scale} | {variant} | {tokenization['token_counts']} | {json.dumps(prefixes)} |")
        lines += ["", "Synthetic target agreement (unique SUM mode):", "", "| Encoding | Instructed | Arithmetic | Rubric lookup |", "| --- | ---: | ---: | ---: |"]
        for variant in ["numeric", "fixed", "symbol", "anchor", "numeric_ended", "numeric_space", "symbol_rotate", "symbol_list_reverse"]:
            cells = []
            for family in ["instructed", "objective", "rubric"]:
                score = summary["synthetic_mapping_accuracy"][f"{variant}:sum:{family}"]
                cells.append(f"{score['unique_mode_correct']}/{score['n']}")
            lines.append(f"| {variant} | " + " | ".join(cells) + " |")
        associations = {}
        for variant in run.VARIANTS + ["numeric_fine"]:
            variant_rows = [r for r in good if r["variant"] == variant]
            coefficients = [r["scores"]["sum"]["token_count_score_pearson"] for r in variant_rows
                            if r["scores"]["sum"]["token_count_score_pearson"] is not None]
            associations[variant] = {"rows": len(variant_rows), "defined_rows": len(coefficients),
                                     "mean_within_row_pearson": statistics.mean(coefficients) if coefficients else None,
                                     "minimum": min(coefficients) if coefficients else None, "maximum": max(coefficients) if coefficients else None}
        lines += ["", "Token-count associations with SUM scores (within request):", "", "| Encoding | Defined / total rows | Mean Pearson r | Min r | Max r |", "| --- | ---: | ---: | ---: | ---: |"]
        for variant, item in associations.items():
            if item["defined_rows"]:
                lines.append(f"| {variant} | {item['defined_rows']}/{item['rows']} | {item['mean_within_row_pearson']:.4f} | {item['minimum']:.4f} | {item['maximum']:.4f} |")
            else:
                lines.append(f"| {variant} | 0/{item['rows']} | undefined | undefined | undefined |")
        lines += ["", "Equal counts make this correlation undefined. These correlations are descriptive and confounded by intended value and task; they are not causal estimates of length bias. Per-pair token-count delta versus SUM-score delta correlations are retained in comparisons.json.", "",
                  f"Control maximum absolute SUM-score differences: `{json.dumps(summary['controls'])}`.", ""]
        details[model] = {"tokenizations": tokenizations, "token_count_associations": associations,
                          "largest_sum_representation_changes": sorted([p for p in pairs if p["left_rule"] == p["right_rule"] == "sum"], key=lambda p: p["total_variation"], reverse=True)[:20]}
        extra = ROOT / "results" / (model + "-paraphrases")
        if (extra / "summary.json").is_file():
            paraphrases = run.analyze(extra)
            lines += ["", "Paraphrased service reports (separate ordinal suite):", "",
                      "| Encoding | Unique SUM mode matches assigned target | SUM to MEAN mode changes |",
                      "| --- | ---: | ---: |"]
            for variant in run.VARIANTS:
                score = paraphrases["synthetic_mapping_accuracy"][f"{variant}:sum:rubric"]
                changes = paraphrases["comparisons"][f"{variant}:sum -> {variant}:mean"]["modal_changes"]
                lines.append(f"| {variant} | {score['unique_mode_correct']}/{score['n']} | {changes} |")
            lines += ["", "| Paraphrase comparison | Pairs | Mode changes | Median changes | Mean TV | Max TV |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
            for name, item in paraphrases["comparisons"].items():
                if ":sum ->" in name and name.endswith(":sum"):
                    lines.append(f"| {name} | {item['pairs']} | {item['modal_changes']} | {item['median_changes']} | {item['mean_total_variation']:.6f} | {item['max_total_variation']:.6f} |")
            lines += ["", "Paraphrase targets are author-assigned ordinal rubric expectations, not independently adjudicated human ratings. No interval summaries are computed.", ""]
            details[model]["paraphrase_summary"] = paraphrases
    run.write_json(ROOT / "analysis.json", details)
    (ROOT / "TABLES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
