"""Native Windows state diagnostics; no server or production changes."""
import argparse
import ctypes as C
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import sys
import time

import numpy as np
from native import Native, LOG, EVAL, P, TensorHeader

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "stage2b"))
from investigate import cases


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def logp(row, token):
    maximum = float(max(row))
    denominator = 0.0
    for value in row:
        denominator += math.exp(float(value) - maximum)
    return float(row[token]) - maximum - math.log(denominator)


def difference(a, b):
    d = b.astype(np.float64) - a.astype(np.float64)
    indices = np.argsort(np.abs(d))[-10:][::-1]
    return {"max_abs": float(np.max(np.abs(d))), "rms": float(np.sqrt(np.mean(d*d))),
            "changed": int(np.count_nonzero(d)), "top": [{"index": int(i), "a": float(a[i]), "b": float(b[i]), "delta": float(d[i])} for i in indices]}


def state_metadata(raw, full=False):
    offset = 4 + struct.unpack_from("<I", raw)[0] if full else 8
    caches = []
    for name in ["full_attention", "swa"]:
        streams, = struct.unpack_from("<I", raw, offset)
        offset += 4
        assert streams == 1
        cells, = struct.unpack_from("<I", raw, offset)
        offset += 4
        positions = []
        for _ in range(cells):
            pos, seqs = struct.unpack_from("<iI", raw, offset)
            offset += 8 + 4*seqs
            positions.append(pos)
        entry = {"name": name, "cells": cells, "positions": positions, "layers": []}
        if cells:
            trans, layers = struct.unpack_from("<II", raw, offset)
            offset += 8
            assert trans == 0
            for kind in ["K", "V"]:
                for layer in range(layers):
                    dtype, row = struct.unpack_from("<iQ", raw, offset)
                    offset += 12
                    payload = raw[offset:offset+row*cells]
                    offset += row*cells
                    entry["layers"].append({"kind": kind, "cache_layer": layer, "type": dtype, "row_bytes": row,
                                             "sha256": hashlib.sha256(payload).hexdigest()})
        caches.append(entry)
    assert offset == len(raw), (offset, len(raw))
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "caches": caches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--copy", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--attention-inputs", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    for name in ["native.py", "diagnose.py"]:
        (args.output / name).write_bytes((ROOT / name).read_bytes())
    identity = json.loads((ROOT.parent / "stage2b/identity.json").read_text())
    write(args.output / "identity.json", identity)
    runtime = Path(r"C:\AI\llama-modes-v03")
    n = Native(runtime)
    logstream = (args.output / "native.log").open("w", encoding="utf-8")
    @LOG
    def logger(level, message, data):
        logstream.write(message.decode("utf-8", errors="replace"))
        logstream.flush()
    n.llama_log_set(logger, None)
    trace = {"active": False, "path": None, "nodes": []}
    @EVAL
    def callback(tensor, ask, data):
        name = n.ggml_get_name(tensor).decode()
        selected = trace["active"] and name.startswith(("attn_norm-", "Qcur-", "Kcur-", "Vcur-", "attn_out-", "ffn_inp-", "l_out-", "kqv_out-", "result_output"))
        if ask:
            return selected
        if selected:
            header = C.cast(tensor, C.POINTER(TensorHeader)).contents
            size = n.ggml_nbytes(tensor)
            buffer = C.create_string_buffer(size)
            n.ggml_backend_tensor_get(tensor, buffer, 0, size)
            filename = f"{len(trace['nodes']):03d}-{name}.bin"
            (trace["path"] / filename).write_bytes(buffer.raw)
            trace["nodes"].append({"name": name, "type": header.type, "shape": list(header.ne), "strides": list(header.nb), "file": filename})
            if args.attention_inputs and name == "kqv_out-0":
                nodes = []
                def capture(ptr, depth, label):
                    if not ptr or depth > 3:
                        return
                    h = C.cast(ptr, C.POINTER(TensorHeader)).contents
                    size = n.ggml_nbytes(ptr)
                    filename = "input-" + label + ".bin"
                    buf = C.create_string_buffer(size)
                    n.ggml_backend_tensor_get(ptr, buf, 0, size)
                    (trace["path"] / filename).write_bytes(buf.raw)
                    nodes.append({"path": label, "name": n.ggml_get_name(ptr).decode(), "type": h.type, "shape": list(h.ne), "strides": list(h.nb),
                                  "op": h.op, "op_params": list(h.op_params), "file": filename})
                    for i, source in enumerate(h.src):
                        capture(source, depth+1, label+"-"+str(i))
                capture(tensor, 0, "root")
                write(trace["path"] / "attention-inputs.json", nodes)
        return True
    mp = n.llama_model_default_params()
    mp.n_gpu_layers = 99
    model = n.llama_model_load_from_file(identity["model"]["path"].encode(), mp)
    if not model:
        raise RuntimeError("Model load failed")
    vocab = n.llama_vocab_n_tokens(n.llama_model_get_vocab(model))
    cp = n.llama_context_default_params()
    cp.n_ctx, cp.n_batch, cp.n_ubatch = 4096, 512, 512
    cp.n_threads = cp.n_threads_batch = 8
    cp.n_seq_max = 2 if args.copy else 1
    cp.n_outputs_max = 1
    cp.swa_full = False
    cp.kv_unified = args.copy
    if args.trace:
        cp.cb_eval = C.cast(callback, P)
    write(args.output / "config.json", {"runtime": str(runtime), "version": n.llama_version().decode(), "n_vocab": vocab,
          "context": {k: getattr(cp, k) for k, _ in cp._fields_ if k not in ["cb_eval", "cb_eval_user_data", "samplers", "ctx_other", "abort_callback", "abort_callback_data"]},
          "trace": args.trace, "copy": args.copy, "benchmark": args.benchmark})
    selected = cases()
    selected.append({"name": "city_control", "original": json.loads((ROOT.parent / "stage2b/city-control.json").read_text())})
    write(args.output / "cases.json", selected)
    def logits(ctx):
        return np.ctypeslib.as_array(n.llama_get_logits_ith(ctx, -1), shape=(vocab,)).copy()
    def checkpoint(ctx, directory, name, seq=0):
        row = logits(ctx)
        row.tofile(directory / (name + ".f32"))
        mem = n.llama_get_memory(ctx)
        meta = {"seq": seq, "position_min": n.llama_memory_seq_pos_min(mem, seq), "position_max": n.llama_memory_seq_pos_max(mem, seq),
                "sequence_state": state_metadata(n.snapshot(ctx, sequence=seq).raw),
                "full_state": state_metadata(n.snapshot(ctx, full=True).raw, True)}
        write(directory / (name + "-state.json"), meta)
        return row
    results = []
    for case in selected:
        prompt = case["original"]["prompt_tokens"]
        prefix = 3443 if case["name"] == "city_control" else 12
        targets = [6175, 23096] if prefix == 3443 else [17, 16]
        if args.benchmark:
            orders = [[0, 1, 2, 3], [3, 2, 1, 0]] if prefix == 3443 else [[0, 1], [1, 0]]
            choices = case["original"]["token_ids"][:4 if prefix == 3443 else 2]
            for strategy in ["snapshot", "reprefill"]:
                ctx = n.llama_init_from_model(model, cp)
                assert ctx
                for order in orders:
                    for repeat in range(6):
                        n.llama_memory_clear(n.llama_get_memory(ctx), True)
                        start = time.perf_counter()
                        n.decode(ctx, prompt)
                        base = logits(ctx)
                        snap = n.snapshot(ctx) if strategy == "snapshot" else None
                        rows = []
                        for position, index in enumerate(order):
                            if position:
                                if strategy == "snapshot":
                                    n.restore(ctx, snap)
                                else:
                                    n.llama_memory_clear(n.llama_get_memory(ctx), True)
                                    n.decode(ctx, prompt)
                                    base = logits(ctx)
                            choice = choices[index]
                            token_rows = [base.copy()]
                            for j, token in enumerate(choice[:-1]):
                                n.decode(ctx, [token], len(prompt)+j)
                                token_rows.append(logits(ctx))
                            rows.append((index, choice, token_rows))
                        elapsed = time.perf_counter() - start
                        scores = {str(index): [logp(row, token) for row, token in zip(token_rows, choice)] for index, choice, token_rows in rows}
                        results.append({"case": case["name"], "strategy": strategy, "order": order, "repeat": repeat, "seconds": elapsed, "scores": scores})
                        write(args.output / "results.json", results)
                n.llama_free(ctx)
            print(case["name"], "benchmark done", flush=True)
            continue
        baseline = None
        for mode in (["A", "COPY"] if args.copy else ["A", "B", "C", "D", "FULL_B", "FULL_C"]):
            directory = args.output / (case["name"] + "-" + mode)
            directory.mkdir()
            ctx = n.llama_init_from_model(model, cp)
            assert ctx
            n.decode(ctx, prompt)
            pre = checkpoint(ctx, directory, "prompt")
            snap = n.snapshot(ctx, full=mode.startswith("FULL"))
            seq = 0
            if mode in ["C", "D", "FULL_C", "COPY"]:
                if mode == "COPY":
                    n.llama_memory_seq_cp(n.llama_get_memory(ctx), 0, 1, -1, -1)
                n.decode(ctx, [prefix], len(prompt))
                checkpoint(ctx, directory, "candidate1")
            if mode in ["B", "C", "FULL_B", "FULL_C"]:
                n.restore(ctx, snap, full=mode.startswith("FULL"))
            elif mode == "D":
                assert n.llama_memory_seq_rm(n.llama_get_memory(ctx), 0, -1, -1)
                n.decode(ctx, prompt)
            elif mode == "COPY":
                seq = 1
            before = checkpoint(ctx, directory, "before_force", seq)
            trace.update(active=args.trace, path=directory, nodes=[])
            n.decode(ctx, [prefix], len(prompt), seq)
            trace["active"] = False
            after = checkpoint(ctx, directory, "after_force", seq)
            if args.trace:
                write(directory / "tensors.json", trace["nodes"])
            if baseline is None:
                baseline = after
            oracle = json.loads((ROOT.parent / f"stage2b/oracle-default-with-control/{case['name']}-original-scores.json").read_text())
            target_oracle = [oracle[1][1], oracle[2][1]] if prefix == 3443 else [oracle[0][1], oracle[1][1]]
            entry = {"case": case["name"], "mode": mode, "prompt_tokens": len(prompt), "prefix": prefix,
                     "targets": targets, "logp": [logp(after, t) for t in targets], "oracle_logp": target_oracle,
                     "vs_A": difference(baseline, after), "buffer_before_force_vs_prompt": difference(pre, before)}
            results.append(entry)
            write(args.output / "results.json", results)
            print(case["name"], mode, entry["logp"], entry["vs_A"]["max_abs"], flush=True)
            n.llama_free(ctx)
    n.llama_model_free(model)
    logstream.close()


if __name__ == "__main__":
    main()
