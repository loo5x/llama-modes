"""Check preserved coverage, source hashes, scores, and measurement separation."""

import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    checked = []
    for model in ["gptoss", "qwen"]:
        for suffix, expected_count in [("validated-full", 399), ("paraphrases", 210)]:
            directory = ROOT / "results" / f"{model}-{suffix}"
            config = json.loads((directory / "config.json").read_text())
            source_hash = hashlib.sha256((directory / "harness_source.py").read_bytes()).hexdigest()
            assert source_hash == config["harness"]["sha256"]
            rows = [json.loads(s) for s in (directory / "results.jsonl").read_text().splitlines()]
            assert len(rows) == len(config["plan"]) == expected_count
            assert len({(r["scale"], r["case"], r["variant"]) for r in rows}) == expected_count
            for row, spec in zip(rows, config["plan"]):
                assert row["status"] == "ok"
                assert all(row[key] == value for key, value in spec.items())
                n = len(row["values"])
                assert n == len(row["labels"]) == len(row["token_ids"]) == len(row["sum_log_probability"])
                assert row["token_counts"] == list(map(len, row["token_ids"]))
                assert row["values"] == sorted(set(row["values"]))
                assert all(math.isclose(s/len(ids), m, abs_tol=1e-12) for s, m, ids in zip(row["sum_log_probability"], row["mean_log_probability"], row["token_ids"]))
                for rule in ["sum", "mean"]:
                    stats = row["scores"][rule]
                    weights = stats["relative_weights"]
                    scores = row[f"{rule}_log_probability"]
                    assert len(weights) == n and all(0 <= w <= 1 for w in weights)
                    assert math.isclose(sum(weights), 1, abs_tol=1e-12)
                    denominator = sum(math.exp(s-max(scores)) for s in scores)
                    assert all(math.isclose(w, math.exp(s-max(scores))/denominator, abs_tol=1e-12) for w, s in zip(weights, scores))
                    assert ("interval" in stats) == (row["measurement"] == "interval")
                    cdf = stats["ordinal"]["cumulative_weights"]
                    assert len(cdf) == n and cdf[-1] == 1
                    assert all(b >= a - 1e-15 for a, b in zip(cdf, cdf[1:]))
                    assert all(q in row["values"] for q in stats["ordinal"]["quantiles"].values())
            checked.append({"run": directory.name, "rows": len(rows), "source_hash_verified": True})
    result = {"checked": checked, "total_rows": sum(r["rows"] for r in checked), "status": "passed"}
    (ROOT / "artifact-verification.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
