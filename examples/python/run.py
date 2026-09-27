"""Small standard-library client shared by the four example entry points."""
import argparse
import json
import time
import urllib.request
from pathlib import Path


def main(mode):
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    name = "boolean" if mode == "compare_direct_chat" else mode
    body = json.loads((Path(__file__).parents[1] / "requests" / (name + ".json")).read_text(encoding="utf-8"))
    if args.model:
        body["model"] = args.model

    def call(endpoint, payload):
        started = time.perf_counter()
        request = urllib.request.Request(args.url.rstrip("/") + endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            result = json.load(response)
        print(json.dumps({"endpoint": endpoint, "latency_ms": (time.perf_counter() - started) * 1000, "response": result}, indent=2))

    call("/scale" if mode == "scale" else "/decision", body)
    if mode == "compare_direct_chat":
        print("Interactive comparison: sequential requests; inspect exact final content, finish_reason, and usage. Direct generated tokens = 0 by design.")
        chat = {"messages": body["messages"], "temperature": 0, "max_tokens": 1024, "stream": False}
        if args.model:
            chat["model"] = args.model
        call("/v1/chat/completions", chat)
