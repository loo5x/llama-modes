"""Validate the fresh-only HTTP endpoint against the matching native oracle."""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\AI\llama-modes-v05"))
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--oracle-only", action="store_true")
    parser.add_argument("--shared-prefix", action="store_true")
    parser.add_argument("--allow-documentation-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    fixture = root / "experiments/shared_context_v05/results/expanded/gptoss-records"
    identity = json.loads((fixture / "identity.json").read_text())
    model = Path(identity["model"]["path"])
    output = args.output.resolve()
    manifest = json.loads((args.runtime / "build-manifest.json").read_text(encoding="utf-8-sig"))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if manifest["commit"] != head:
        assert args.allow_documentation_only, "Runtime commit differs from HEAD"
        subprocess.run(["git", "merge-base", "--is-ancestor", manifest["commit"], head], cwd=root, check=True)
        changed = subprocess.check_output(["git", "diff", "--name-only", manifest["commit"], head], cwd=root, text=True).splitlines()
        assert all(p.startswith(("docs/", "experiments/", "RELEASE_NOTES_")) or p == "README.md" for p in changed), changed
    for item in manifest["files"]:
        assert (args.runtime / item["name"]).stat().st_size == item["bytes"]
        assert digest(args.runtime / item["name"]) == item["sha256"]
    oracle = args.runtime / "test-save-load-state.exe"
    assert digest(oracle) == manifest["oracle_sha256"]
    assert digest(model) == identity["model"]["sha256"]
    common = ["-m", str(model), "-ngl", "99", "-c", "4096", "-b", str(args.batch), "-ub", str(args.batch),
              "-t", "8", "-tb", "8", "--kv-unified", "--swa-full", "-fa", "on", "--no-warmup", "-lv", "4"]
    if args.oracle_only:
        saved = json.loads((output / "identity.json").read_text())
        assert saved["manifest"] == manifest and saved["model"] == identity["model"]
        prepared = json.loads((output / "prepared.json").read_text())
        response = json.loads((output / "response.json").read_text())
        assert response["execution"]["n_batch"] == response["execution"]["n_ubatch"] == args.batch
        check_oracle(args, output, model, common, prepared, response, manifest)
        return
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, output / Path(__file__).name)
    write(output / "identity.json", {"manifest": manifest, "model": identity["model"]})
    original = json.loads((fixture / "cases.json").read_text())
    questions = []
    for i, q in enumerate(original["questions"]):
        question = {"id": str(i), "type": q["mode"], "question": q["question"]}
        if q["mode"] == "scale":
            question.update(measurement="interval", scale=[{"value": int(label), "label": label} for label in q["labels"]])
        else:
            question["choices"] = q["labels"]
        questions.append(question)
    payload = {"context": original["context"], "questions": questions}
    write(output / "request.json", payload)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    timings = []

    def request(route, body=None):
        started = time.monotonic()
        req = urllib.request.Request(url + route, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as response:
            value = json.load(response)
        if route == "/evaluate":
            timings.append(time.monotonic() - started)
            write(output / "http-timings.json", timings)
        return value

    command = [str(args.runtime / "llama-server.exe"), *common, "-np", "1", "--no-prefill-assistant",
               "--host", "127.0.0.1", "--port", str(port), "--evaluate", "--evaluate-context", "4096"]
    write(output / "server-command.json", command)
    if args.shared_prefix:
        command.append("--evaluate-shared-prefix")
        write(output / "server-command.json", command)
    prepared = []
    with (output / "server.log").open("w") as log:
        process = subprocess.Popen(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic() + 240
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Server exited; inspect server.log")
                try:
                    request("/health")
                    break
                except (OSError, ValueError):
                    if time.monotonic() > deadline:
                        raise TimeoutError("Server startup timed out")
                    time.sleep(1)
            write(output / "props.json", request("/props"))
            for q, old in zip(questions, original["questions"]):
                messages = [{"role": "user", "content": payload["context"] + "\n\n" + q["question"]}]
                prefixes = []
                for probe in ["DecisionContentProbe_A7f3", "OtherContentProbe_B9e2"]:
                    rendered = request("/apply-template", {"messages": messages + [{"role": "assistant", "content": probe}], "add_generation_prompt": False})["prompt"]
                    assert rendered.count(probe) == 1
                    prefixes.append(rendered[:rendered.index(probe)])
                assert prefixes[0] == prefixes[1]
                prompt = request("/tokenize", {"content": prefixes[0], "add_special": True, "parse_special": True})["tokens"]
                tokens = [request("/tokenize", {"content": label, "add_special": False, "parse_special": False})["tokens"] for label in old["labels"]]
                prepared.append({"prompt_tokens": prompt, "choices": tokens, "prepared_prompt": prefixes[0]})
            write(output / "prepared.json", prepared)
            response = request("/evaluate", payload)
            if args.shared_prefix:
                assert response["execution"]["strategy"] == "shared_aligned"
                assert response["execution"]["shared_prefix_tokens"] > 0
                assert response["execution"]["shared_prefix_tokens"] % args.batch == 0
            else:
                assert response["execution"]["strategy"] == "fresh"
            write(output / "response.json", response)
            print("HTTP mixed request passed", flush=True)
            reverse = copy.deepcopy(payload)
            reverse["questions"].reverse()
            for q in reverse["questions"]:
                q["scale" if q["type"] == "scale" else "choices"].reverse()
            reversed_response = request("/v1/evaluate", reverse)
            write(output / "reversed.json", reversed_response)
            for actual, expected in zip(reversed(reversed_response["results"]), response["results"]):
                if "choices" in actual["result"]:
                    actual["result"]["choices"].reverse()
                assert actual == expected, "Order dependence"
            repeated = request("/evaluate", payload)
            write(output / "repeated.json", repeated)
            assert response == repeated, "Repeat dependence"
            invalid = copy.deepcopy(payload)
            invalid["questions"][-1]["question"] = " word" * 5000
            try:
                request("/evaluate", invalid)
                raise AssertionError("Oversized request accepted")
            except urllib.error.HTTPError as error:
                assert error.code == 400
                write(output / "overflow.json", json.load(error))
            write(output / "completion.json", request("/completion", {"prompt": "Hello", "n_predict": 2}))
            print("Order, repeat, overflow and subsequent completion passed", flush=True)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)

    check_oracle(args, output, model, common, prepared, response, manifest)


def check_oracle(args, output, model, common, prepared, response, manifest):
    oracle = args.runtime / "test-save-load-state.exe"
    checks = []
    for i, item in enumerate(prepared):
        scores_path = output / f"oracle-{i}-scores.json"
        request_path = output / f"oracle-{i}-request.json"
        write(request_path, {"prompt_tokens": item["prompt_tokens"], "choices": item["choices"], "output": str(scores_path)})
        command = [str(oracle), *(v for v in common if v not in {"--kv-unified", "--no-warmup"}), "-np", "1", "--decision-oracle", str(request_path)]
        write(output / f"oracle-{i}-command.json", command)
        with (output / f"oracle-{i}.log").open("w") as log:
            subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, timeout=600, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        token_scores = json.loads(scores_path.read_text())
        assert list(map(len, token_scores)) == list(map(len, item["choices"]))
        sums = [math.fsum(row) for row in token_scores]
        assert all(math.isfinite(s) for s in sums)
        weights = [math.exp(s - max(sums)) for s in sums]
        weights = [w / math.fsum(weights) for w in weights]
        value = response["results"][i]["result"]
        rows = value.get("choices", value.get("points"))
        deltas = []
        for c, row in enumerate(rows):
            if "sum_log_probability" in row:
                assert row["token_ids"] == item["choices"][c]
                deltas.extend([abs(row["sum_log_probability"] - sums[c]), abs(row["mean_log_probability"] - sums[c] / len(item["choices"][c]))])
            else:
                assert row["token_id"] == item["choices"][c][0]
                deltas.append(abs(row["probability"] - weights[c]))
            if "relative_weight" in row:
                deltas.append(abs(row["relative_weight"] - weights[c]))
        checks.append({"question": i, "candidate_count": len(rows), "max_delta": max(deltas), "passed": max(deltas) <= 2e-4})
        write(output / "oracle-checks.json", checks)
        print("Oracle", i, checks[-1], flush=True)
    summary = {"build_commit": manifest["commit"], "batch": args.batch, "questions": len(checks),
               "execution": response["execution"],
               "candidates": sum(c["candidate_count"] for c in checks), "max_delta": max(c["max_delta"] for c in checks),
               "passed": all(c["passed"] for c in checks), "order_repeat_overflow_completion": "passed"}
    write(output / "summary.json", summary)
    print(json.dumps(summary), flush=True)
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
