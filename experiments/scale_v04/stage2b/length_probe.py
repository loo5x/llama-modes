"""Test the same two-candidate order swap at selected prompt token lengths."""

import json
from pathlib import Path

import investigate
import run


def main():
    output = investigate.ROOT / "length-probe"
    output.mkdir(exist_ok=False)
    client = run.Client("http://127.0.0.1:8094", output)
    rows = []
    for case in investigate.cases():
        original = case["original"]
        for length in sorted({64, 96, 127, 128, 129, 160, len(original["prompt_tokens"])}):
            tokens = original["prompt_tokens"][-length:]
            prompt = client.request("/detokenize", {"tokens": tokens})["content"]
            if client.tokenize(prompt, True) != tokens:
                raise ValueError("Prompt round trip changed token IDs")
            scores = []
            for labels in [["-2", "-1"], ["-1", "-2"]]:
                response = client.request("/decision", {"prompt": prompt, "choices": labels})
                scores.append({r["text"]: r["sum_log_probability"] for r in response["choices"]})
            delta = {label: scores[1][label]-scores[0][label] for label in scores[0]}
            rows.append({"case": case["name"], "prompt_tokens": tokens, "prompt": prompt,
                         "length": len(tokens), "scores": scores, "deltas": delta})
            run.write_json(output / "results.json", rows)
            print(case["name"], length, delta, flush=True)


if __name__ == "__main__":
    main()
