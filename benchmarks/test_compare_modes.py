import importlib.util
import contextlib
import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("compare_modes", Path(__file__).with_name("compare_modes.py"))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


class HarnessTests(unittest.TestCase):
    def test_exact_chat_and_truncation(self):
        def body(text, finish="stop"):
            return {"choices": [{"message": {"content": text}, "finish_reason": finish}]}
        self.assertEqual(bench.chat_answer(body(" Yes\n"), ["Yes", "No"]), "Yes")
        for text in ["Yes, because", "<think>Yes</think>", "", "yes"]:
            self.assertIsNone(bench.chat_answer(body(text), ["Yes", "No"]))
        self.assertIsNone(bench.chat_answer(body("Yes", "length"), ["Yes", "No"]))

    def test_direct_both_contracts_and_ties(self):
        body = {"choices": [{"text": "A", "probability": .75}, {"text": "B", "probability": .25}]}
        self.assertEqual(bench.direct_answer(body, ["A", "B"], "choice"), "A")
        body = {"choices": [{"text": "A", "sum_log_probability": -1001}, {"text": "B", "sum_log_probability": -1000}]}
        self.assertEqual(bench.direct_answer(body, ["A", "B"], "choice"), "B")
        body["choices"][0]["sum_log_probability"] = -1000
        self.assertIsNone(bench.direct_answer(body, ["A", "B"], "choice"))
        with self.assertRaises(ValueError):
            bench.direct_answer(body, ["A", "C"], "choice")

    def test_statistics_denominators(self):
        def side(result, ms):
            return {"result": result, "http_ok": ms is not None, "latency_ms": ms, "completion_tokens": None}
        rows = [{"expected": "A", "direct": side("A", 10), "chat": side(None, 30), "direct_correct": True, "chat_correct": False, "agreement": None},
                {"expected": "B", "direct": side(None, None), "chat": side("B", 50), "direct_correct": False, "chat_correct": True, "agreement": None}]
        stats = bench.aggregate(rows)
        self.assertEqual(stats["direct"]["accuracy"], .5)
        self.assertEqual(stats["chat"]["invalid_output_rate"], .5)
        self.assertEqual(stats["chat"]["median_latency_ms"], 40)
        self.assertEqual(stats["chat"]["p95_latency_ms"], 50)
        self.assertIsNone(stats["agreement"])
        self.assertEqual(bench.percentile95(list(range(1, 101))), 95)
        self.assertIsNone(bench.percentile95([]))

    def test_dataset_and_shared_messages(self):
        task = {"id": "x", "mode": "scale", "question": "Rate", "measurement": "ordinal", "scale": [{"value": 0, "label": "A"}, {"value": 1, "label": "B"}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "data.jsonl"
            path.write_text(json.dumps(task))
            loaded = bench.load_dataset(path)[0]
            endpoint, direct, chat, labels = bench.payloads(loaded)
            self.assertEqual(endpoint, "/scale")
            self.assertEqual(direct["messages"], chat["messages"])
            self.assertEqual(labels, ["A", "B"])
            task["scale"][1]["value"] = 0
            path.write_text(json.dumps(task))
            with self.assertRaises(ValueError):
                bench.load_dataset(path)

    def test_missing_usage_and_malformed_responses(self):
        response = {"choices": [{"message": {"content": "Yes"}, "finish_reason": "stop"}], "usage": None}
        with patch.object(bench, "request", return_value=response):
            result = bench.run_one("unused", "/v1/chat/completions", {}, ["Yes", "No"], "chat", 1)
        self.assertEqual(result["result"], "Yes")
        self.assertIsNone(result["completion_tokens"])
        for response in [None, [], {}, {"choices": [None]}]:
            with patch.object(bench, "request", return_value=response):
                result = bench.run_one("unused", "/decision", {}, ["Yes", "No"], "boolean", 1)
            self.assertIsNotNone(result["error"])
            self.assertIsNone(result["result"])

    def test_cli_against_controlled_http_fixture(self):
        calls = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def send(self, body, status=200):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def do_GET(self):
                self.send({"data": [{"id": "CONTROLLED-TEST-FIXTURE"}]})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, body))
                valid = body["messages"][0]["content"].startswith("alpha")
                if self.path == "/decision":
                    if not valid:
                        self.send({"error": {"message": "controlled failure"}}, 400)
                    else:
                        self.send({"choices": [{"text": "Yes", "probability": .8}, {"text": "No", "probability": .2}]})
                else:
                    self.send({"choices": [{"message": {"content": "Yes" if valid else "Extra prose"}, "finish_reason": "stop"}],
                               "usage": {"completion_tokens": 7}, "system_fingerprint": "test-fixture"})

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                dataset = Path(folder) / "tasks.jsonl"
                tasks = [{"id": q, "mode": "boolean", "question": q, "expected": "Yes"} for q in ["alpha", "beta"]]
                dataset.write_text("\n".join(json.dumps(t) for t in tasks), encoding="utf-8")
                output = Path(folder) / "run"
                args = ["compare_modes", "--url", f"http://127.0.0.1:{server.server_port}", "--dataset", str(dataset),
                        "--output", str(output), "--warmup", "1", "--repetitions", "2", "--hardware-label", "fixture"]
                with patch("sys.argv", args), contextlib.redirect_stdout(io.StringIO()):
                    bench.main()
                summary = json.loads((output / "summary.json").read_text())
                rows = [json.loads(line) for line in (output / "raw.jsonl").read_text().splitlines()]
                self.assertEqual(len(rows), 4)
                self.assertEqual(summary["aggregate"]["direct"]["accuracy"], .5)
                self.assertEqual(summary["aggregate"]["chat"]["invalid_output_rate"], .5)
                self.assertEqual(summary["aggregate"]["agreement_pairs"], 2)
                self.assertEqual(summary["metadata"]["system_fingerprints"], ["test-fixture"])
                self.assertEqual(rows[0]["order"], ["direct", "chat"])
                self.assertEqual(rows[1]["order"], ["chat", "direct"])
                self.assertEqual(len(calls), 10)
                for i in range(0, len(calls), 2):
                    self.assertEqual(calls[i][1]["messages"], calls[i + 1][1]["messages"])
                with patch("sys.argv", args):
                    with self.assertRaises(FileExistsError):
                        bench.main()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
