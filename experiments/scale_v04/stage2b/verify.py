"""Verify the specific evidence supporting the Stage 2b report."""

import json
import math

import investigate
import run


def main():
    root = investigate.ROOT
    for case in investigate.cases():
        assert case["original"]["prepared_prompt"].encode() == case["reversed"]["prepared_prompt"].encode()
        assert case["original"]["prompt_tokens"] == case["reversed"]["prompt_tokens"]
    live_requests = 0
    for profile, oracle_profile in [("live-baseline", "oracle-default-with-control"),
                                    ("live-restart", "oracle-default-with-control"),
                                    ("live-graphs-off", "oracle-default-with-control"),
                                    ("live-cpu", "oracle-cpu"), ("live-fa-off", "oracle-fa-off")]:
        rows = [json.loads(s) for s in (root / profile / "results.jsonl").read_text().splitlines()]
        live_requests += len(rows)
        for case in investigate.cases():
            a = json.loads((root / oracle_profile / (case["name"] + "-original-scores.json")).read_text())
            b = json.loads((root / oracle_profile / (case["name"] + "-reverse-scores.json")).read_text())
            assert a == b[::-1]
            reference = dict(zip(case["original"]["labels"], map(math.fsum, a)))
            for row in rows:
                if row["case"] != case["name"]:
                    continue
                for candidate in row["response"]["choices"]:
                    if len(row["choices"]) == 1 or profile == "live-cpu":
                        if candidate["text"] in ("-2", "-1"):
                            assert candidate["sum_log_probability"] == reference[candidate["text"]]
    for profile, oracle_profile in [("live-restart", "oracle-default-with-control"), ("live-cpu", "oracle-cpu")]:
        reference = json.loads((root / oracle_profile / "city_control-original-scores.json").read_text())
        city = json.loads((root / "city-control.json").read_text())
        expected = dict(zip(city["labels"], map(math.fsum, reference)))
        rows = [json.loads(s) for s in (root / profile / "results.jsonl").read_text().splitlines()]
        for row in rows:
            if row["case"] == "city_control":
                assert {c["text"]: c["sum_log_probability"] for c in row["response"]["choices"]} == expected
    identity = json.loads((root / "identity.json").read_text())
    assert identity["runtime_matches_stage2_hashes"]
    assert "65f4875" in identity["oracle_version"]
    result = {"status": "passed", "live_rows_in_checked_profiles": live_requests,
              "checks": ["byte/token-identical archived prompt pairs", "fresh oracle order invariance", "singleton/oracle agreement",
                         "CPU signed-candidate oracle agreement", "default CUDA and CPU city control oracle agreement",
                         "model/runtime hashes unchanged from Stage 2", "oracle version matches v0.3.0 commit"]}
    run.write_json(root / "verification.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
