#!/usr/bin/env python3
"""Sequential direct/chat comparison. Standard library only; see README.md."""

import argparse
import csv
import hashlib
import json
import math
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def request(url, endpoint, body=None, timeout=120):
    data = None if body is None else json.dumps(body, allow_nan=False).encode()
    req = urllib.request.Request(url.rstrip("/") + endpoint, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def load_dataset(path):
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as source:
            tasks = [{"id": row["Index"], "mode": "boolean", "question": row["Question"],
                      "choices": ["Yes", "No"], "expected": row["Truth"].capitalize(),
                      "category": row["Category"]} for row in csv.DictReader(source)]
    else:
        tasks = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not tasks:
        raise ValueError("Dataset is empty")
    ids = set()
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not task["id"] or task["id"] in ids:
            raise ValueError("Every task needs a unique, non-empty string id")
        ids.add(task["id"])
        if task.get("mode") not in ("boolean", "choice", "scale"):
            raise ValueError(f"{task['id']}: unsupported mode")
        if not isinstance(task.get("question"), str) or not task["question"].strip():
            raise ValueError(f"{task['id']}: question must be non-empty text")
        if task["mode"] == "scale":
            points = task.get("scale", [])
            if task.get("measurement") not in ("ordinal", "interval") or not isinstance(points, list) or not 2 <= len(points) <= 256:
                raise ValueError(f"{task['id']}: scale needs measurement and 2..256 points")
            values = [p.get("value") for p in points if isinstance(p, dict)]
            if len(values) != len(points) or any(type(v) not in (int, float) or not math.isfinite(v) for v in values) or len(set(values)) != len(values):
                raise ValueError(f"{task['id']}: scale values must be unique finite numbers")
            labels = [p.get("label") for p in points]
        else:
            labels = task.get("choices", ["Yes", "No"] if task["mode"] == "boolean" else [])
            task["choices"] = labels
        if not isinstance(labels, list) or not 2 <= len(labels) <= 256 or any(not isinstance(x, str) or not x.strip() for x in labels):
            raise ValueError(f"{task['id']}: provide 2..256 non-empty labels")
        if len(set(labels)) != len(labels) or len({x.strip() for x in labels}) != len(labels):
            raise ValueError(f"{task['id']}: labels must remain distinct after outer whitespace trimming")
        if task.get("expected") is not None and task["expected"] not in labels:
            raise ValueError(f"{task['id']}: expected must be a supplied label, including for SCALE")
    return tasks


def payloads(task, model=None, max_tokens=1024):
    is_scale = task["mode"] == "scale"
    labels = [p["label"] for p in task["scale"]] if is_scale else task["choices"]
    instruction = "Select exactly one supplied label. Return only that label. Labels: " + json.dumps(labels, ensure_ascii=False)
    if is_scale:
        instruction += ". Ordered label/value mapping: " + json.dumps(sorted(task["scale"], key=lambda p: p["value"]))
    messages = [{"role": "user", "content": task["question"] + "\n" + instruction}]
    direct = {"messages": messages}
    direct.update({"measurement": task["measurement"], "scale": task["scale"]} if is_scale else {"choices": labels})
    chat = {"messages": messages, "temperature": 0, "max_tokens": max_tokens, "stream": False}
    if model:
        direct["model"] = chat["model"] = model
    return "/scale" if is_scale else "/decision", direct, chat, labels


def direct_answer(body, labels, mode):
    rows = body.get("points" if mode == "scale" else "choices") if isinstance(body, dict) else None
    if not isinstance(rows, list) or len(rows) != len(labels) or not all(isinstance(r, dict) for r in rows):
        raise ValueError("Malformed direct response")
    label_key = "label" if mode == "scale" else "text"
    if {r.get(label_key) for r in rows} != set(labels):
        raise ValueError("Direct response labels do not match request")
    score_key = "relative_weight" if mode == "scale" else ("probability" if "probability" in rows[0] else "sum_log_probability")
    scores = [r.get(score_key) for r in rows]
    if any(type(s) not in (int, float) or not math.isfinite(s) for s in scores):
        raise ValueError("Direct response has missing/non-finite scores")
    if score_key != "sum_log_probability" and (any(s < 0 or s > 1 for s in scores) or not math.isclose(sum(scores), 1, abs_tol=1e-5)):
        raise ValueError("Direct response weights are not normalized")
    winners = [r[label_key] for r, s in zip(rows, scores) if s == max(scores)]
    return winners[0] if len(winners) == 1 else None


def chat_answer(body, labels):
    choices = body.get("choices") if isinstance(body, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("Malformed chat response")
    choice = choices[0]
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("Malformed chat message")
    content = message.get("content")
    if choice.get("finish_reason") != "stop" or not isinstance(content, str):
        return None
    matches = [label for label in labels if content.strip() == label.strip()]
    return matches[0] if len(matches) == 1 else None


def run_one(url, endpoint, payload, labels, mode, timeout):
    started = time.perf_counter()
    result = {"request": payload, "response": None, "result": None, "error": None,
              "http_ok": False, "latency_ms": None, "completion_tokens": None}
    try:
        body = request(url, endpoint, payload, timeout)
        result["latency_ms"] = (time.perf_counter() - started) * 1000
        result["http_ok"] = True
        result["response"] = body
        result["result"] = chat_answer(body, labels) if mode == "chat" else direct_answer(body, labels, mode)
        if mode == "chat":
            usage = body.get("usage")
            tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            result["completion_tokens"] = tokens if type(tokens) is int and tokens >= 0 else None
        if result["result"] is None:
            result["error"] = "No exact final label (or tied direct scores)"
    except urllib.error.HTTPError as exc:
        with exc:
            result["error"] = f"HTTP {exc.code}: {exc.read().decode(errors='replace')}"
    except (OSError, ValueError, TypeError, KeyError) as exc:
        result["error"] = str(exc)
    result["elapsed_ms"] = (time.perf_counter() - started) * 1000
    if mode != "chat":
        result["generated_tokens_by_design"] = 0
    return result


def percentile95(values):
    return sorted(values)[math.ceil(0.95 * len(values)) - 1] if values else None


def aggregate(rows):
    count = len(rows)
    summary = {"requests": count, "labeled_requests": sum(r["expected"] is not None for r in rows)}
    for side in ("direct", "chat"):
        latencies = [r[side]["latency_ms"] for r in rows if r[side]["http_ok"]]
        labeled = [r for r in rows if r["expected"] is not None]
        valid = sum(r[side]["result"] is not None for r in rows)
        tokens = [r[side]["completion_tokens"] for r in rows if r[side]["completion_tokens"] is not None]
        summary[side] = {
            "accuracy": sum(r[side + "_correct"] is True for r in labeled) / len(labeled) if labeled else None,
            "exact_answer_rate": valid / count if count else None,
            "invalid_output_rate": (count - valid) / count if count else None,
            "median_latency_ms": statistics.median(latencies) if latencies else None,
            "p95_latency_ms": percentile95(latencies), "latency_samples": len(latencies),
            "mean_completion_tokens": statistics.mean(tokens) if tokens else None,
            "completion_token_samples": len(tokens),
        }
    summary["direct"]["generated_tokens_by_design"] = 0
    pairs = [r for r in rows if r["agreement"] is not None]
    summary["agreement_pairs"] = len(pairs)
    summary["agreement"] = sum(r["agreement"] for r in pairs) / len(pairs) if pairs else None
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--model")
    parser.add_argument("--dataset", type=Path, default=Path(__file__).resolve().parents[1] / "experiments/results/decision_v01_final_channel_100.csv")
    parser.add_argument("--output", type=Path, required=True, help="New output directory; never overwritten")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=2, help="Unmeasured pairs, cycling through dataset")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--hardware-label")
    parser.add_argument("--version", help="User-supplied llama-modes version/commit")
    args = parser.parse_args()
    if args.repetitions < 1 or args.warmup < 0 or args.timeout <= 0 or not math.isfinite(args.timeout) or args.max_tokens < 1:
        parser.error("Invalid repetitions, warmup, timeout, or max-tokens")
    tasks = load_dataset(args.dataset)
    models = request(args.url, "/v1/models", timeout=args.timeout)
    model = args.model or models["data"][0]["id"]
    args.output.mkdir(parents=True, exist_ok=False)
    metadata = {"timestamp": datetime.now(timezone.utc).isoformat(), "model": model,
                "server_url": args.url, "models_response": models, "version": args.version,
                "dataset": str(args.dataset), "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
                "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "repetitions": args.repetitions, "warmup": args.warmup, "timeout_seconds": args.timeout,
                "max_tokens": args.max_tokens, "hardware_label": args.hardware_label,
                "order": "alternating direct-first/chat-first pairs; sequential", "system_fingerprints": []}
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with (args.output / "warmup.jsonl").open("x", encoding="utf-8") as warmup:
        for i in range(args.warmup):
            task = tasks[i % len(tasks)]
            endpoint, direct, chat, labels = payloads(task, model, args.max_tokens)
            pair = {"id": task["id"], "direct": run_one(args.url, endpoint, direct, labels, task["mode"], args.timeout),
                    "chat": run_one(args.url, "/v1/chat/completions", chat, labels, "chat", args.timeout)}
            warmup.write(json.dumps(pair, allow_nan=False) + "\n")
            warmup.flush()
            if not pair["direct"]["http_ok"] or not pair["chat"]["http_ok"]:
                raise RuntimeError("Warmup failed; inspect warmup.jsonl. No measured results were produced.")
    rows = []
    with (args.output / "raw.jsonl").open("x", encoding="utf-8") as output:
        for repetition in range(args.repetitions):
            for task_index, task in enumerate(tasks):
                endpoint, direct, chat, labels = payloads(task, model, args.max_tokens)
                order = ["direct", "chat"] if (repetition * len(tasks) + task_index) % 2 == 0 else ["chat", "direct"]
                row = {"task_id": task["id"], "mode": task["mode"], "expected": task.get("expected"),
                       "repetition": repetition, "model": model, "order": order}
                for side in order:
                    row[side] = run_one(args.url, endpoint if side == "direct" else "/v1/chat/completions",
                                        direct if side == "direct" else chat, labels,
                                        task["mode"] if side == "direct" else "chat", args.timeout)
                    row[side + "_correct"] = row[side]["result"] == row["expected"] if row["expected"] is not None else None
                    body = row[side]["response"]
                    fingerprint = body.get("system_fingerprint") if isinstance(body, dict) else None
                    row[side]["system_fingerprint"] = fingerprint
                    if fingerprint is not None and fingerprint not in metadata["system_fingerprints"]:
                        metadata["system_fingerprints"].append(fingerprint)
                row["agreement"] = row["direct"]["result"] == row["chat"]["result"] if all(row[s]["result"] is not None for s in order) else None
                output.write(json.dumps(row, allow_nan=False) + "\n")
                output.flush()
                rows.append(row)
                print(f"{repetition + 1}/{args.repetitions} {task['id']}: direct={row['direct']['result']} chat={row['chat']['result']}")
    summary = {"schema_version": 1, "metadata": metadata, "aggregate": aggregate(rows),
               "by_mode": {mode: aggregate([r for r in rows if r["mode"] == mode]) for mode in sorted({r["mode"] for r in rows})}}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Saved {len(rows)} pairs to {args.output}")


if __name__ == "__main__":
    main()
