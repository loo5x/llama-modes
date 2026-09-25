"""Verify and summarize the preserved Stage 2c native diagnostics."""
import hashlib
import json
from pathlib import Path
import statistics
import argparse

import numpy as np
from diagnose import difference, write

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def attention(directory):
    nodes = {x["path"]: x for x in read(directory / "attention-inputs.json")}
    def tensor(key):
        node = nodes[key]
        raw = (directory / node["file"]).read_bytes()
        return np.ndarray(node["shape"], dtype={0: "<f4", 1: "<f2"}[node["type"]], buffer=raw, strides=node["strides"])
    mask = tensor("root-0-3").reshape(-1)
    physical = np.flatnonzero(np.isfinite(mask))
    positions = read(directory / "after_force-state.json")["full_state"]["caches"][1]["positions"]
    logical = np.array(positions)[physical]
    order = np.argsort(logical)
    physical = physical[order]
    return {"physical": physical, "logical": logical[order], "q": tensor("root-0-0").copy(),
            "k": tensor("root-0-1")[:, physical, :, :].copy(), "v": tensor("root-0-2")[:, physical, :, :].copy(),
            "sinks": tensor("root-0-4").copy(), "mask": mask[physical], "op_params": nodes["root-0"]["op_params"]}


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    ROOT = args.root
    rows = read(ROOT / "baseline/results.json")
    checks = []
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})
    for row in rows:
        case, mode = row["case"], row["mode"]
        folder = case + "-" + mode
        base = np.fromfile(ROOT / "baseline" / folder / "after_force.f32", dtype="<f4")
        for trial in ["traced", "attention-inputs"]:
            other = np.fromfile(ROOT / trial / folder / "after_force.f32", dtype="<f4")
            check(folder + " " + trial + " instrumentation agreement", np.array_equal(base, other))
        if mode in ["A", "D"]:
            check(folder + " exact oracle target logp", row["logp"] == row["oracle_logp"])
        if mode == "D":
            check(folder + " prompt re-prefill logits", row["buffer_before_force_vs_prompt"]["max_abs"] == 0)
        if mode in ["B", "C"]:
            state = read(ROOT / "baseline" / folder / "before_force-state.json")
            prompt = read(ROOT / "baseline" / folder / "prompt-state.json")
            check(folder + " serialized sequence bytes unchanged", state["sequence_state"]["sha256"] == prompt["sequence_state"]["sha256"])
        if mode in ["FULL_B", "FULL_C"]:
            state = read(ROOT / "baseline" / folder / "before_force-state.json")
            prompt = read(ROOT / "baseline" / folder / "prompt-state.json")
            check(folder + " serialized full-context bytes unchanged", state["full_state"]["sha256"] == prompt["full_state"]["sha256"])
        if mode == "C":
            b = ROOT / "baseline" / (case + "-B/after_force.f32")
            c = ROOT / "baseline" / folder / "after_force.f32"
            check(folder + " immediate equals post-candidate restore", b.read_bytes() == c.read_bytes())
    traces = []
    input_comparisons = []
    for case in ["objective_2", "paraphrase_2", "city_control"]:
        adir = ROOT / "attention-inputs" / (case + "-A")
        atensors = read(adir / "tensors.json")
        aa = attention(adir)
        for mode in ["B", "C", "D", "FULL_B", "FULL_C"]:
            bdir = ROOT / "attention-inputs" / (case + "-" + mode)
            differences = []
            for item, other in zip(atensors, read(bdir / "tensors.json")):
                assert item == other
                assert item["type"] == 0
                a = np.fromfile(adir / item["file"], dtype="<f4")
                b = np.fromfile(bdir / item["file"], dtype="<f4")
                if not np.array_equal(a, b):
                    differences.append({"name": item["name"], "file": item["file"], **difference(a, b)})
            traces.append({"case": case, "mode": mode, "changed_tensors": differences})
            bb = attention(bdir)
            equality = {key: bool(np.array_equal(aa[key], bb[key])) for key in ["logical", "q", "k", "v", "sinks", "mask", "op_params"]}
            check(case + " " + mode + " layer 0 logical attention inputs", all(equality.values()))
            input_comparisons.append({"case": case, "mode": mode, "equal": equality, "logical_positions": bb["logical"].tolist(),
                                      "A_physical": aa["physical"].tolist(), "other_physical": bb["physical"].tolist()})
    copy_directory = ROOT / ("copy-validated" if (ROOT / "copy-validated").exists() else "copy")
    copy = read(copy_directory / "results.json")
    for row in copy:
        check(row["case"] + " " + row["mode"] + " sequence-copy oracle agreement", row["logp"] == row["oracle_logp"] and row["vs_A"]["max_abs"] == 0)
        normal = ROOT / "baseline" / (row["case"] + "-A/after_force.f32")
        actual = copy_directory / (row["case"] + "-" + row["mode"] + "/after_force.f32")
        check(row["case"] + " " + row["mode"] + " two-sequence config equals baseline", normal.read_bytes() == actual.read_bytes())
    bench = read(ROOT / "benchmark-verified/results.json")
    timings = []
    for case in ["objective_2", "paraphrase_2", "city_control"]:
        oracle = read(Path(__file__).resolve().parents[1] / f"stage2b/oracle-default-with-control/{case}-original-scores.json")
        subset = [r for r in bench if r["case"] == case]
        fresh = [r for r in subset if r["strategy"] == "reprefill"]
        check(case + " all re-prefill orders/repeats equal oracle per token", all(score == oracle[int(i)] for r in fresh for i, score in r["scores"].items()))
        entry = {"case": case}
        for strategy in ["snapshot", "reprefill"]:
            values = [r["seconds"] for r in subset if r["strategy"] == strategy and r["repeat"] > 0]
            entry[strategy] = {"median_seconds": statistics.median(values), "min": min(values), "max": max(values), "n": len(values)}
        entry["ratio"] = entry["reprefill"]["median_seconds"] / entry["snapshot"]["median_seconds"]
        timings.append(entry)
    write(ROOT / "tensor-comparison.json", traces)
    write(ROOT / "attention-input-comparison.json", input_comparisons)
    write(ROOT / "analysis.json", {"logits": rows, "timings": timings, "checks": checks})
    failures = [c for c in checks if not c["passed"]]
    print("Checks", len(checks), "failures", failures)
    print("Timings", timings)
    for row in rows:
        print(row["case"], row["mode"], row["vs_A"]["max_abs"], row["vs_A"]["rms"], row["vs_A"]["changed"])
    assert not failures


if __name__ == "__main__":
    main()
