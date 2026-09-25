"""Repeat live controls or run the existing native Windows independent oracle."""

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8094")
    parser.add_argument("--oracle", type=Path)
    parser.add_argument("--replay-raw", action="store_true", help="Replay the stored prompt, including its original template date")
    parser.add_argument("--case", help="Select one scale:case:variant instead of the four default controls")
    args = parser.parse_args()
    if args.oracle and (sys.platform != "win32" or not args.oracle.is_file()):
        raise SystemExit("The native Windows oracle executable must exist; no alternate runtime is used.")
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "validation_source.py").write_bytes(Path(__file__).read_bytes())
    (args.output / "harness_source.py").write_bytes(Path(run.__file__).read_bytes())
    config = json.loads((args.results / "config.json").read_text())
    rows = [json.loads(line) for line in (args.results / "results.jsonl").read_text().splitlines()]
    selected = [("0_10", "objective_5", "numeric"), ("minus2_2", "objective_2", "numeric"),
                ("0_10", "objective_5", "numeric_ended"), ("0_10", "objective_5", "numeric_fine")]
    if args.oracle:
        selected[0] = ("0_10", "target_10", "numeric")
    if args.case:
        selected = [tuple(args.case.split(":"))]
    rows = [r for r in rows if (r["scale"], r["case"], r["variant"]) in selected]
    if len(rows) != len(selected):
        raise ValueError("Requested control cases were not all found in the stored results")
    summary = []
    if args.oracle:
        run.write_json(args.output / "oracle_identity.json", run.file_identity(args.oracle))
        for row in rows:
            name = f"{row['scale']}-{row['case']}-{row['variant']}"
            request = args.output / (name + "-request.json")
            response = args.output / (name + "-response.json")
            run.write_json(request, {"prompt_tokens": row["prompt_tokens"], "choices": row["token_ids"], "output": str(response.resolve())})
            command = [str(args.oracle.resolve()), "-m", config["model_file"]["path"], "-c", "4096", "-b", "512", "-ub", "512",
                       "-ngl", "99", "-fa", "auto", "--decision-oracle", str(request.resolve())]
            run.write_json(args.output / (name + "-command.json"), command)
            with (args.output / (name + "-process.log")).open("w", encoding="utf-8") as log:
                completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=600)
            if completed.returncode:
                summary.append({"case": name, "error": f"Oracle exit code {completed.returncode}"})
                continue
            scores = json.loads(response.read_text())
            if len(scores) != len(row["token_ids"]) or any(len(a) != len(b) for a, b in zip(scores, row["token_ids"])):
                raise ValueError("Oracle token score dimensions differ")
            deltas = [math.fsum(a)-b for a, b in zip(scores, row["sum_log_probability"])]
            summary.append({"case": name, "sum_score_deltas": deltas, "maximum_absolute_delta": max(map(abs, deltas))})
            run.write_json(args.output / "summary.json", summary)
            print(summary[-1], flush=True)
    else:
        client = run.Client(args.url, args.output)
        live_props = client.request("/props")
        if live_props["model_path"] != config["props"]["model_path"]:
            raise ValueError("Live model differs from stored results")
        (args.output / "metrics-before.txt").write_text(client.request("/metrics"), encoding="utf-8")
        for row in rows:
            responses = []
            for repetition in range(3):
                for reverse in [False, True]:
                    labels = row["labels"][::-1] if reverse else row["labels"]
                    if all(len(ids) == 1 for ids in row["token_ids"]):
                        labels = labels + ["Diagnostic candidate excluded from the scale statistics."]
                    source = {"prompt": row["prepared_prompt"]} if args.replay_raw else {"messages": row["messages"]}
                    raw = client.request("/decision", {**source, "choices": labels})
                    scores = {r["text"]: r["sum_log_probability"] for r in raw["choices"]}
                    ordered = [scores[label] for label in row["labels"]]
                    responses.append({"repetition": repetition, "reverse": reverse, "scores": ordered,
                                      "maximum_absolute_delta_from_matrix": max(abs(a-b) for a, b in zip(ordered, row["sum_log_probability"]))})
            summary.append({"scale": row["scale"], "case": row["case"], "variant": row["variant"], "responses": responses})
        (args.output / "metrics-after.txt").write_text(client.request("/metrics"), encoding="utf-8")
    run.write_json(args.output / "summary.json", summary)


if __name__ == "__main__":
    main()
