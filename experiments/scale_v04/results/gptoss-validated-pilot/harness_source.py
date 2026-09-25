"""Representation experiments against the unchanged v0.3 /decision endpoint."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import time
import urllib.error
import urllib.request


SCALES = {"0_10": list(range(11)), "1_5": list(range(1, 6)), "minus2_2": list(range(-2, 3))}
ANCHORS = {
    11: ["failed", "dire", "poor", "weak", "limited", "mixed", "fair", "good", "strong", "excellent", "perfect"],
    5: ["failed", "poor", "mixed", "good", "perfect"],
}
DESCRIPTIONS = [
    "The service did nothing useful and left the entire problem unresolved.",
    "The service acknowledged the problem but made almost no useful progress.",
    "The service made very little progress and left major problems unresolved.",
    "The service addressed a small part of the problem but left most of it unresolved.",
    "The service made some useful progress but left more problems than it solved.",
    "The service solved about half of the problem and left about half unresolved.",
    "The service solved more of the problem than it left unresolved.",
    "The service solved most of the problem but left several noticeable gaps.",
    "The service solved the main problem with only small gaps remaining.",
    "The service solved almost everything with one negligible gap remaining.",
    "The service completely solved the problem with no gaps remaining.",
]
VARIANTS = ["numeric", "fixed", "symbol", "anchor", "numeric_ended", "numeric_space",
            "numeric_api_reverse", "symbol_rotate", "symbol_list_reverse", "numeric_raw"]
BASELINES = {"symbol_rotate": "symbol", "symbol_list_reverse": "symbol"}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def weights(scores):
    if not scores or not all(math.isfinite(s) for s in scores):
        raise ValueError("Expected finite scores")
    largest = max(scores)
    unscaled = [math.exp(s - largest) for s in scores]
    total = math.fsum(unscaled)
    return [w / total for w in unscaled]


def token_issues(sequences):
    duplicates, prefixes = [], []
    for i, left in enumerate(sequences):
        for j, right in enumerate(sequences):
            if i < j and left == right:
                duplicates.append([i, j])
            if len(left) < len(right) and left == right[:len(left)]:
                prefixes.append([i, j])
    return {"duplicates": duplicates, "strict_prefixes": prefixes}


def correlation(left, right):
    a, b = statistics.mean(left), statistics.mean(right)
    dx, dy = [x - a for x in left], [y - b for y in right]
    denominator = math.sqrt(math.fsum(x*x for x in dx) * math.fsum(y*y for y in dy))
    return math.fsum(x*y for x, y in zip(dx, dy)) / denominator if denominator else None


def summarize(values, probs, measurement):
    cumulative = [math.fsum(probs[:i+1]) for i in range(len(probs))]
    cumulative[-1] = 1.0
    quantiles = {str(q): next(v for v, c in zip(values, cumulative) if c >= q)
                 for q in [0.1, 0.25, 0.5, 0.75, 0.9]}
    result = {"ordinal": {"modes": [v for v, w in zip(values, probs) if w == max(probs)],
                          "median": quantiles["0.5"], "quantiles": quantiles,
                          "cumulative_weights": cumulative}}
    if measurement == "interval":
        mean = math.fsum(v*w for v, w in zip(values, probs))
        variance = math.fsum(w*(v-mean)**2 for v, w in zip(values, probs))
        result["interval"] = {"expected_value": mean, "standard_deviation": math.sqrt(variance)}
    return result


def distances(a_values, a_weights, b_values, b_weights):
    support = sorted(set(a_values + b_values))
    a, b = dict(zip(a_values, a_weights)), dict(zip(b_values, b_weights))
    delta = [a.get(v, 0.0) - b.get(v, 0.0) for v in support]
    tv = 0.5 * math.fsum(abs(d) for d in delta)
    wasserstein = math.fsum(abs(math.fsum(delta[:i+1])) * (support[i+1]-support[i])
                           for i in range(len(support)-1))
    return {"total_variation": tv, "wasserstein_1_numeric": wasserstein}


def build_plan(smoke=False):
    plan = []
    for scale, values in SCALES.items():
        indices = sorted({0, len(values)//2, len(values)-1})
        tasks = []
        for i in indices:
            value = values[i]
            tasks.append({"case": f"target_{i}", "family": "instructed", "measurement": "interval",
                          "expected": value, "task": f"The requested scale value is exactly {value}. Return its mapped response label."})
            passed = int(10 * i / (len(values)-1))
            tasks.append({"case": f"objective_{i}", "family": "objective", "measurement": "interval",
                          "expected": value, "task": f"A device passed {passed} of 10 independent checks. Compute the rating as {values[0]} + ({values[-1]} - ({values[0]})) * passed / 10. Return the label for that rating."})
        for i in (indices if smoke else range(len(values))):
            description = DESCRIPTIONS[round(10*i/(len(values)-1))]
            tasks.append({"case": f"rubric_{i}", "family": "rubric", "measurement": "ordinal",
                          "expected": values[i], "task": f"Rate this service report using the rubric: {description}"})
        for task in tasks:
            for variant in VARIANTS:
                plan.append({**task, "scale": scale, "values": values, "variant": variant})
            if task["family"] == "objective":
                fine = [values[0] + i/2 for i in range(2*(values[-1]-values[0])+1)]
                plan.append({**task, "scale": scale, "values": fine, "variant": "numeric_fine"})
    return plan


def labels_for(spec):
    values, variant = spec["values"], spec["variant"]
    numeric = [format(v, "g") for v in values]
    if variant == "fixed":
        return [f"{v:+03d}" if min(values) < 0 else f"{v:02d}" for v in values]
    if variant.startswith("symbol"):
        shift = 1 if variant == "symbol_rotate" else 0
        return [chr(65 + (i + shift) % len(values)) for i in range(len(values))]
    if variant == "anchor":
        return ANCHORS[len(values)]
    if variant == "numeric_ended":
        return [s + "\n" for s in numeric]
    if variant == "numeric_space":
        return [" " + s for s in numeric]
    return numeric


def messages_for(spec, labels):
    values = spec["values"]
    mapping_labels = labels
    if spec["variant"] in ("numeric_ended", "numeric_space"):
        mapping_labels = [format(v, "g") for v in values]
    mapping = [f"{json.dumps(label)} = {format(v, 'g')}" for v, label in zip(values, mapping_labels)]
    if spec["variant"] == "symbol_list_reverse":
        mapping.reverse()
    rubric = ""
    if spec["family"] == "rubric":
        rubric = "\nRubric (ordered categories; numeric distances are not assumed):\n" + "\n".join(
            f"{v}: {DESCRIPTIONS[round(10*i/(len(values)-1))]}" for i, v in enumerate(values))
    content = (f"Use the scale from {values[0]} to {values[-1]}.\nResponse label mapping (quotes are delimiters, not part of the label):\n"
               + "\n".join(mapping) + rubric + "\nTask: " + spec["task"]
               + "\nReturn only the mapped response label, without quotes or explanation.")
    return [{"role": "user", "content": content}]


class Client:
    def __init__(self, url, output):
        self.url = url.rstrip("/")
        self.output = output
        self.cache = {}
        self.calls = 0

    def request(self, endpoint, body=None):
        self.calls += 1
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + endpoint, data=data, headers={"Content-Type": "application/json"})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                status, raw = response.status, response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read().decode("utf-8")
        except Exception as error:
            status, raw = 0, repr(error)
        entry = {"id": self.calls, "endpoint": endpoint, "request": body, "status": status,
                 "response_text": raw, "seconds": time.monotonic() - started}
        with (self.output / "http.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=True) + "\n")
        if status != 200:
            raise RuntimeError(f"HTTP {status} on {endpoint}: {raw[:300]}")
        return json.loads(raw)

    def tokenize(self, text, prompt=False):
        key = (text, prompt)
        if key not in self.cache:
            self.cache[key] = self.request("/tokenize", {"content": text, "add_special": prompt, "parse_special": prompt})["tokens"]
        return self.cache[key]

    def render(self, messages):
        key = json.dumps(messages)
        if key not in self.cache:
            rendered = self.request("/apply-template", {"messages": messages})["prompt"]
            if rendered.endswith("<|start|>assistant"):
                rendered += "<|channel|>final<|message|>"
            elif rendered.endswith("<|im_start|>assistant\n<think>\n"):
                rendered += "\n</think>\n\n"
            elif rendered.endswith("<|im_start|>assistant\n"):
                rendered += "<think>\n\n</think>\n\n"
            elif not rendered.endswith("</think>\n\n"):
                raise ValueError("Unsupported native content boundary; add and validate an explicit rendering profile")
            self.cache[key] = rendered
        return self.cache[key]


def evaluate(client, spec):
    labels = labels_for(spec)
    sequences = [client.tokenize(label) for label in labels]
    issues = token_issues(sequences)
    messages = messages_for(spec, labels)
    prompt = client.render(messages)
    result = {**spec, "labels": labels, "token_ids": sequences, "token_counts": list(map(len, sequences)),
              "token_issues": issues, "messages": messages, "prepared_prompt": prompt,
              "prompt_tokens": client.tokenize(prompt, True), "first_http_id": client.calls + 1}
    choices = labels[::-1] if spec["variant"] == "numeric_api_reverse" else labels[:]
    source = {"prompt": prompt} if spec["variant"] == "numeric_raw" else {"messages": messages}
    try:
        original = client.request("/decision", {**source, "choices": choices})
        result["original_response"] = original
        scored = original
        if all(len(ids) == 1 for ids in sequences):
            sentinel = "Diagnostic candidate excluded from the scale statistics."
            sentinel_tokens = client.tokenize(sentinel)
            if len(sentinel_tokens) < 2 or sentinel_tokens in sequences:
                raise ValueError("Invalid diagnostic candidate")
            scored = client.request("/decision", {**source, "choices": choices + [sentinel]})
            result["diagnostic_candidate"] = {"label": sentinel, "token_ids": sentinel_tokens}
            result["augmented_response"] = scored
        by_label = {row["text"]: row for row in scored["choices"]}
        if any(by_label[label]["token_ids"] != ids for label, ids in zip(labels, sequences)):
            raise ValueError("Decision and tokenize token IDs differ")
        sums = [by_label[label]["sum_log_probability"] for label in labels]
        means = [by_label[label]["mean_log_probability"] for label in labels]
        if any(abs(s / len(ids) - m) > 1e-10 for s, m, ids in zip(sums, means, sequences)):
            raise ValueError("Inconsistent mean score")
        result.update(sum_log_probability=sums, mean_log_probability=means)
        result["scores"] = {}
        for rule, scores in [("sum", sums), ("mean", means)]:
            probs = weights(scores)
            result["scores"][rule] = {"relative_weights": probs, **summarize(spec["values"], probs, spec["measurement"]),
                                      "token_count_score_pearson": correlation(result["token_counts"], scores),
                                      "token_count_weight_pearson": correlation(result["token_counts"], probs)}
        if "diagnostic_candidate" in result:
            original_weights = {row["text"]: row["probability"] for row in original["choices"]}
            delta = max(abs(original_weights[label] - w) for label, w in zip(labels, result["scores"]["sum"]["relative_weights"]))
            result["single_token_weight_max_delta"] = delta
            if delta > 2e-5:
                raise ValueError(f"Diagnostic candidate changed relative weights: {delta}")
        result["status"] = "ok"
    except Exception as error:
        result.update(status="error", error=str(error))
    result["last_http_id"] = client.calls
    return result


def compare(left, right, rule="sum", right_rule=None):
    right_rule = right_rule or rule
    a, b = left["scores"][rule], right["scores"][right_rule]
    metric = distances(left["values"], a["relative_weights"], right["values"], b["relative_weights"])
    if left["measurement"] != "interval":
        metric.pop("wasserstein_1_numeric")
    result = {"scale": left["scale"], "case": left["case"], "family": left["family"],
              "measurement": left["measurement"], "left": left["variant"], "right": right["variant"],
              "left_rule": rule, "right_rule": right_rule, "modes_changed": a["ordinal"]["modes"] != b["ordinal"]["modes"],
              "median_changed": a["ordinal"]["median"] != b["ordinal"]["median"],
              "left_median": a["ordinal"]["median"], "right_median": b["ordinal"]["median"],
              "left_prefix_overlap": bool(left["token_issues"]["strict_prefixes"]),
              "right_prefix_overlap": bool(right["token_issues"]["strict_prefixes"]), **metric}
    if left["measurement"] == "interval":
        result["expected_value_shift"] = b["interval"]["expected_value"] - a["interval"]["expected_value"]
    if left["values"] == right["values"]:
        result["token_count_delta_score_delta_pearson"] = correlation(
            [b-a for a, b in zip(left["token_counts"], right["token_counts"])],
            [b-a for a, b in zip(left["sum_log_probability"], right["sum_log_probability"])])
    return result


def analyze(output):
    rows = [json.loads(line) for line in (output / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    good = [r for r in rows if r["status"] == "ok"]
    index = {(r["scale"], r["case"], r["variant"]): r for r in good}
    comparisons = []
    for row in good:
        comparisons.append(compare(row, row, "sum", "mean"))
        baseline = BASELINES.get(row["variant"], "numeric")
        reference = index.get((row["scale"], row["case"], baseline))
        if reference and row["variant"] != baseline:
            for rule in ["sum", "mean"]:
                comparisons.append(compare(reference, row, rule))
    write_json(output / "comparisons.json", comparisons)
    groups = {}
    for pair in comparisons:
        key = f"{pair['left']}:{pair['left_rule']} -> {pair['right']}:{pair['right_rule']}"
        groups.setdefault(key, []).append(pair)
    aggregates = {}
    for key, pairs in groups.items():
        shifts = [abs(p["expected_value_shift"]) for p in pairs if "expected_value_shift" in p]
        aggregates[key] = {"pairs": len(pairs), "modal_changes": sum(p["modes_changed"] for p in pairs),
                           "median_changes": sum(p["median_changed"] for p in pairs),
                           "mean_total_variation": statistics.mean(p["total_variation"] for p in pairs),
                           "max_total_variation": max(p["total_variation"] for p in pairs),
                           "max_absolute_expected_value_shift": max(shifts) if shifts else None}
    accuracy = {}
    for row in good:
        for rule in ["sum", "mean"]:
            key = f"{row['variant']}:{rule}:{row['family']}"
            entry = accuracy.setdefault(key, {"n": 0, "unique_mode_correct": 0, "median_correct": 0})
            entry["n"] += 1
            entry["unique_mode_correct"] += row["scores"][rule]["ordinal"]["modes"] == [row["expected"]]
            entry["median_correct"] += row["scores"][rule]["ordinal"]["median"] == row["expected"]
    controls = {}
    for variant, baseline in [("numeric_api_reverse", "numeric"), ("numeric_raw", "numeric")]:
        deltas = []
        for row in good:
            if row["variant"] == variant:
                base = index.get((row["scale"], row["case"], baseline))
                if base:
                    deltas.append(max(abs(a-b) for a, b in zip(row["sum_log_probability"], base["sum_log_probability"])))
        controls[variant] = {"pairs": len(deltas), "max_absolute_sum_score_delta": max(deltas) if deltas else None}
    summary = {"completed": len(rows), "successful": len(good), "errors": [r for r in rows if r["status"] != "ok"],
               "prefix_overlap_rows": sum(bool(r.get("token_issues", {}).get("strict_prefixes")) for r in rows),
               "duplicate_rows": sum(bool(r.get("token_issues", {}).get("duplicates")) for r in rows),
               "controls": controls, "comparisons": aggregates, "synthetic_mapping_accuracy": accuracy}
    write_json(output / "summary.json", summary)
    return summary


def file_identity(path):
    path = Path(path)
    if not path.is_file():
        return {"path": str(path), "available": False}
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8*1024*1024), b""):
            digest.update(chunk)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8094")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-id", default="unspecified")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--analyze", action="store_true")
    args = parser.parse_args()
    if args.analyze:
        summary = analyze(args.output)
        print(json.dumps({k: summary[k] for k in ["completed", "successful", "prefix_overlap_rows", "controls"]}, indent=2))
        return
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "harness_source.py").write_bytes(Path(__file__).read_bytes())
    client = Client(args.url, args.output)
    props = client.request("/props")
    models = client.request("/v1/models")
    plan = build_plan(args.smoke)
    if args.limit:
        plan = plan[:args.limit]
    config = {"args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "python": platform.python_version(),
              "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "harness": file_identity(__file__), "props": props, "models": models,
              "model_file": file_identity(props.get("model_path", "")),
              "runtime_files": [file_identity(p) for p in args.runtime.glob("*") if p.suffix in (".dll", ".exe")] if args.runtime else [],
              "primary_rule": "sum_log_probability", "experimental_rule": "mean_log_probability",
              "weights_are": "representation-dependent relative scale weights, not calibrated confidence",
              "plan": plan}
    write_json(args.output / "config.json", config)
    preflight_spec = plan[0]
    preflight = [evaluate(client, {**preflight_spec, "variant": variant}) for variant in ["numeric", "numeric_raw", "numeric_api_reverse"]]
    write_json(args.output / "preflight.json", preflight)
    if any(row["status"] != "ok" for row in preflight):
        raise RuntimeError("Preflight scoring failed; see preflight.json")
    if any(max(abs(a-b) for a, b in zip(preflight[0]["sum_log_probability"], row["sum_log_probability"])) > 2e-4 for row in preflight[1:]):
        raise RuntimeError("Raw/messages or candidate-order equivalence failed; see preflight.json")
    for i, spec in enumerate(plan):
        try:
            result = evaluate(client, spec)
        except Exception as error:
            result = {**spec, "status": "error", "error": str(error)}
        with (args.output / "results.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=True, allow_nan=False) + "\n")
        print(f"{i+1}/{len(plan)} {spec['scale']} {spec['case']} {spec['variant']}: {result['status']}", flush=True)
    summary = analyze(args.output)
    print(f"Successful: {summary['successful']}/{summary['completed']}", flush=True)
    if summary["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
