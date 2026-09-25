"""Read-only inference experiments for the GPT-OSS candidate-order anomalies."""

import argparse
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run

ROOT = Path(__file__).resolve().parent


def cases():
    result = []
    for directory, name in [("gptoss-validated-full", "objective_2"), ("gptoss-paraphrases", "paraphrase_2")]:
        source = ROOT.parent / "results" / directory
        rows = [json.loads(s) for s in (source / "results.jsonl").read_text().splitlines()]
        original = next(r for r in rows if r["scale"] == "minus2_2" and r["case"] == name and r["variant"] == "numeric")
        reversed_row = next(r for r in rows if r["scale"] == "minus2_2" and r["case"] == name and r["variant"] == "numeric_api_reverse")
        assert original["messages"] == reversed_row["messages"]
        assert original["prompt_tokens"] == reversed_row["prompt_tokens"]
        result.append({"name": name, "source_directory": str(source), "original": original, "reversed": reversed_row,
                       "deltas_reverse_minus_original": [b-a for a, b in zip(original["sum_log_probability"], reversed_row["sum_log_probability"])]})
    return result


def matrix():
    rows = []
    for choices in [["-2"], ["-1"], ["-2", "-1"], ["-2", "0"], ["-1", "0"],
                    ["-2", "1", "0"], ["-2", "-1", "0"], ["-2", "-1", "0", "1", "2"],
                    ["-2", "New York"], ["-2", "+2"], ["New York", "London"],
                    ["+2", "0"], ["00", "-2"], ["-2", "0", "New York"],
                    ["New", "New York", "New Jersey", "London"]]:
        orders = list(itertools.permutations(choices)) if len(choices) <= 3 else [tuple(choices), tuple(reversed(choices))]
        rows.extend([list(order) for order in orders])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["extract", "live", "oracle"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--url", default="http://127.0.0.1:8094")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--oracle", type=Path, default=Path(r"C:\AI\llama-modes-v03\test-save-load-state.exe"))
    parser.add_argument("--gpu-layers", default="99")
    parser.add_argument("--flash-attn", default="auto")
    parser.add_argument("--batch", default="512")
    parser.add_argument("--minimal", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "source.py").write_bytes(Path(__file__).read_bytes())
    extracted = cases()
    if (ROOT / "city-control.json").exists():
        extracted.append({"name": "city_control", "original": json.loads((ROOT / "city-control.json").read_text())})
    run.write_json(args.output / "cases.json", extracted)
    if args.mode == "extract":
        return
    if args.mode == "live":
        client = run.Client(args.url, args.output)
        run.write_json(args.output / "props.json", client.request("/props"))
        for case in extracted:
            original = case["original"]
            assert client.tokenize(original["prepared_prompt"], True) == original["prompt_tokens"]
            orders = matrix()
            if args.minimal:
                orders = [["-2"], ["-1"], ["-2", "-1"], ["-1", "-2"], ["New York", "-2"]]
            if case["name"] == "city_control":
                orders = [original["labels"], original["labels"][::-1]]
            for choices in orders:
                tokens = [client.tokenize(c) for c in choices]
                for repetition in range(args.repetitions):
                    response = client.request("/decision", {"prompt": original["prepared_prompt"], "choices": choices})
                    entry = {"case": case["name"], "choices": choices, "tokens": tokens, "repetition": repetition, "response": response}
                    with (args.output / "results.jsonl").open("a") as stream:
                        stream.write(json.dumps(entry) + "\n")
            print(case["name"], "completed", flush=True)
    else:
        if not args.oracle.is_file() or sys.platform != "win32":
            raise ValueError("Native Windows oracle required")
        config = json.loads((Path(extracted[0]["source_directory"]) / "config.json").read_text())
        run.write_json(args.output / "oracle_identity.json", run.file_identity(args.oracle))
        for case in extracted:
            row = case["original"]
            for reverse in [False, True]:
                name = case["name"] + ("-reverse" if reverse else "-original")
                tokens = row["token_ids"][::-1] if reverse else row["token_ids"]
                output = args.output / (name + "-scores.json")
                request = args.output / (name + "-request.json")
                run.write_json(request, {"prompt_tokens": row["prompt_tokens"], "choices": tokens, "output": str(output.resolve())})
                command = [str(args.oracle), "-m", config["model_file"]["path"], "-c", "4096", "-b", args.batch, "-ub", args.batch,
                           "-ngl", args.gpu_layers, "-fa", args.flash_attn, "--decision-oracle", str(request.resolve())]
                run.write_json(args.output / (name + "-command.json"), command)
                with (args.output / (name + ".log")).open("w") as log:
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=600, check=True)
                scores = json.loads(output.read_text())
                if reverse:
                    scores.reverse()
                sums = [math.fsum(s) for s in scores]
                print(name, sums, flush=True)


if __name__ == "__main__":
    main()
