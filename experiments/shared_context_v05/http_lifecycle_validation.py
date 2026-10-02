"""Exercise admission, queued chat, and disconnect cancellation on the built server."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import json
from pathlib import Path
import select
import shutil
import socket
import struct
import subprocess
import time
import urllib.error
import urllib.request

from http_fresh_validation import digest, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--shared-prefix", action="store_true")
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\AI\llama-modes-v05"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, output / Path(__file__).name)
    (output / "slots").mkdir()
    manifest = json.loads((args.runtime / "build-manifest.json").read_text(encoding="utf-8-sig"))
    assert manifest["commit"] == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for item in manifest["files"]:
        assert digest(args.runtime / item["name"]) == item["sha256"]
    fixture = root / "experiments/shared_context_v05/results/expanded/gptoss-records"
    identity = json.loads((fixture / "identity.json").read_text())
    model = Path(identity["model"]["path"])
    assert digest(model) == identity["model"]["sha256"]
    write(output / "identity.json", {"manifest": manifest, "model": identity["model"]})
    context = json.loads((fixture / "cases.json").read_text())["context"]
    small = {"context": context, "questions": [{"id": "fact", "type": "boolean",
             "question": "Is every repair complete? Answer true or false.", "choices": ["true", "false"]}]}
    heavy = {"context": context, "questions": [{"id": str(i), "type": "choice",
             "question": "Select a numbered option.", "choices": [f"Option {j:03d}" for j in range(64)]} for i in range(8)]}
    medium = copy.deepcopy(heavy)
    medium["questions"] = medium["questions"][:1]
    medium["questions"][0]["choices"] = medium["questions"][0]["choices"][:24]
    if args.shared_prefix:
        small["questions"].append({**small["questions"][0], "id": "fact2"})
        medium["questions"].append({**medium["questions"][0], "id": "1"})
    chat = {"prompt": "The capital of France is", "n_predict": 8, "temperature": 0, "seed": 42,
            "cache_prompt": False, "return_tokens": True, "id_slot": 0}
    write(output / "requests.json", {"small": small, "heavy": heavy, "medium": medium, "chat": chat})
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    events = []
    started = time.monotonic()

    def event(name, **details):
        row = {"event": name, "seconds": time.monotonic() - started, **details}
        events.append(row)
        write(output / "events.json", events)
        print(json.dumps(row), flush=True)

    def request(route, body=None):
        req = urllib.request.Request(url + route, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def ok(route, body=None):
        status, value = request(route, body)
        assert status == 200, (route, status, value)
        return value

    sockets = []

    def raw(route, body):
        data = json.dumps(body).encode()
        sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        sockets.append(sock)
        sock.sendall((f"POST {route} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n").encode() + data)
        return sock

    def disconnect(sock):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("HH", 1, 0))
        sock.close()
        sockets.remove(sock)

    def admitted():
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status, body = request("/evaluate", small)
            if status == 503:
                assert "already admitted" in body["error"]["message"], body
                return
            assert status == 200, (status, body)
            time.sleep(0.05)
        raise AssertionError("Could not observe evaluation admission")

    def await_allocation(offset):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with (output / "server.log").open("rb") as stream:
                stream.seek(offset)
                if b"n_seq_max             = 3" in stream.read():
                    return
            time.sleep(0.02)
        raise AssertionError("Evaluation context was not allocated")

    def same_chat(actual, expected):
        assert actual["content"] == expected["content"]
        assert actual["tokens"] == expected["tokens"]

    command = [str(args.runtime / "llama-server.exe"), "-m", str(model), "-ngl", "99", "-c", "4096", "-np", "1",
               "-b", "128", "-ub", "128", "-t", "8", "-tb", "8", "--kv-unified", "--swa-full", "-fa", "on",
               "--no-warmup", "--no-prefill-assistant", "--host", "127.0.0.1", "--port", str(port),
               "--threads-http", "8", "--slots", "--slot-save-path", str(output / "slots") + "/", "--evaluate", "--evaluate-context", "4096", "-lv", "4"]
    if args.shared_prefix:
        command.append("--evaluate-shared-prefix")
    write(output / "server-command.json", command)
    process = None
    pool = ThreadPoolExecutor(max_workers=3)
    try:
        with (output / "server.log").open("w") as log:
            process = subprocess.Popen(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            deadline = time.monotonic() + 240
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Server exited")
                try:
                    if request("/health")[0] == 200:
                        break
                except (OSError, ValueError):
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError("Server startup")
                time.sleep(1)
            cached_chat = {**chat, "cache_prompt": True}
            cached_control = [ok("/completion", cached_chat) for _ in range(3)]
            write(output / "cached-chat-control.json", cached_control)
            event("ordinary_cached_chat_control", tokens_identical=all(r["tokens"] == cached_control[0]["tokens"] for r in cached_control))
            baseline = ok("/evaluate", small)
            if args.shared_prefix:
                assert baseline["execution"]["strategy"] == "shared_aligned"
            baseline_chat = ok("/completion", chat)
            fresh_control = ok("/completion", chat)
            write(output / "fresh-chat-control.json", fresh_control)
            same_chat(fresh_control, baseline_chat)
            ok("/slots/0?action=save", {"filename": "before.bin"})
            assert ok("/evaluate", small) == baseline
            ok("/slots/0?action=save", {"filename": "after.bin"})
            assert digest(output / "slots/before.bin") == digest(output / "slots/after.bin"), "Evaluation modified idle chat state"
            event("idle_chat_state_unchanged", sha256=digest(output / "slots/before.bin"))
            write(output / "baseline.json", {"evaluation": baseline, "chat": baseline_chat})
            event("baseline_passed")

            for iteration in range(3):
                offset = (output / "server.log").stat().st_size
                sock = raw("/evaluate", heavy)
                await_allocation(offset)
                admitted()
                event("second_evaluation_rejected", iteration=iteration, status=503)
                waiting_chat = pool.submit(ok, "/completion", chat)
                time.sleep(0.3)
                assert not waiting_chat.done(), "Chat ran while evaluation was active"
                admitted()
                assert not select.select([sock], [], [], 0)[0], "Heavy evaluation completed before cancellation"
                assert ok("/health")["status"] == "ok"
                t = time.monotonic()
                disconnect(sock)
                result = waiting_chat.result(timeout=10)
                write(output / f"recovered-chat-{iteration}.json", result)
                same_chat(result, baseline_chat)
                latency = time.monotonic() - t
                assert ok("/evaluate", small) == baseline
                event("active_disconnect_recovered", iteration=iteration, chat_recovery_seconds=latency)

            offset = (output / "server.log").stat().st_size
            evaluation = pool.submit(ok, "/evaluate", medium)
            await_allocation(offset)
            admitted()
            waiting_chat = pool.submit(ok, "/completion", chat)
            time.sleep(0.3)
            assert not waiting_chat.done(), "Chat was not deferred"
            admitted()
            result = evaluation.result(timeout=60)
            if args.shared_prefix:
                assert result["execution"]["strategy"] == "shared_aligned"
            same_chat(waiting_chat.result(timeout=10), baseline_chat)
            assert result == ok("/evaluate", medium)
            write(output / "completed-evaluation.json", result)
            event("successful_evaluation_releases_chat")

            streaming = raw("/completion", {"prompt": "List the numbers from one to a thousand:", "n_predict": 4096,
                            "temperature": 0, "ignore_eos": True, "stream": True, "cache_prompt": False, "id_slot": 0})
            deadline = time.monotonic() + 10
            while not any(slot["is_processing"] for slot in ok("/slots")):
                if time.monotonic() > deadline:
                    raise TimeoutError("Streaming chat did not become active")
                time.sleep(0.05)
            pending = raw("/evaluate", heavy)
            time.sleep(0.5)
            admitted()
            assert any(slot["is_processing"] for slot in ok("/slots"))
            disconnect(pending)
            cancelled_at = time.monotonic()
            time.sleep(5)
            replacement = pool.submit(request, "/evaluate", small)
            time.sleep(0.3)
            if replacement.done():
                status, body = replacement.result()
                write(output / "pending-replacement.json", {"status": status, "body": body})
                busy = any(slot["is_processing"] for slot in ok("/slots"))
                event("pending_cancellation_not_released", status=status, chat_still_active=busy,
                      seconds_since_disconnect=time.monotonic() - cancelled_at)
                disconnect(streaming)
                deadline = time.monotonic() + 10
                while True:
                    recovery_status, recovery_body = request("/evaluate", small)
                    if recovery_status == 200:
                        assert recovery_body == baseline
                        event("pending_recovers_after_stream_stops")
                        break
                    assert recovery_status == 503
                    if time.monotonic() > deadline:
                        raise TimeoutError("Pending cancellation did not recover after stream stopped")
                    time.sleep(1.2)
                raise AssertionError("Pending disconnect was not processed while streaming results continued")
            assert any(slot["is_processing"] for slot in ok("/slots")), "Streaming chat ended too soon"
            t = time.monotonic()
            disconnect(streaming)
            assert replacement.result(timeout=10) == (200, baseline)
            event("pending_disconnect_recovered", replacement_recovery_seconds=time.monotonic() - t)
            same_chat(ok("/completion", chat), baseline_chat)
            assert ok("/evaluate", small) == baseline
            event("final_recovery_passed")
            write(output / "summary.json", {"passed": True, "build_commit": manifest["commit"], "active_cancellation_cycles": 3,
                  "pending_cancellation_cycles": 1, "successful_overlap_cycles": 1, "batch": 128,
                  "max_active_chat_recovery_seconds": max(e["chat_recovery_seconds"] for e in events if "chat_recovery_seconds" in e)})
    except Exception as error:
        write(output / "failure.json", {"type": type(error).__name__, "message": str(error)})
        raise
    finally:
        for sock in list(sockets):
            disconnect(sock)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        pool.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    main()
