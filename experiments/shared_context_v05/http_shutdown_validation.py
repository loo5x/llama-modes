"""Test Windows Ctrl+C shutdown in an isolated hidden console."""
import argparse
import ctypes
import json
from pathlib import Path
import select
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from http_fresh_validation import digest, write


def host(directory):
    command = json.loads((directory / "command.json").read_text())
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    with (directory / "server.log").open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            if not kernel.SetConsoleCtrlHandler(None, True):
                raise ctypes.WinError(ctypes.get_last_error())
            write(directory / "pid.json", {"pid": process.pid})
            while not (directory / "stop").exists():
                if process.poll() is not None:
                    raise RuntimeError("Server exited before shutdown request")
                time.sleep(0.05)
            start = time.monotonic()
            if not kernel.GenerateConsoleCtrlEvent(0, 0):
                raise ctypes.WinError(ctypes.get_last_error())
            forced = False
            try:
                code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                forced = True
                process.terminate()
                code = process.wait(timeout=10)
            write(directory / "exit.json", {"code": code, "forced": forced, "seconds": time.monotonic() - start})
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--shared-prefix", action="store_true")
    parser.add_argument("--host", type=Path)
    parser.add_argument("--runtime", type=Path, default=Path(r"C:\AI\llama-modes-v05"))
    args = parser.parse_args()
    if args.host:
        host(args.host)
        return
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, output / Path(__file__).name)
    manifest = json.loads((args.runtime / "build-manifest.json").read_text(encoding="utf-8-sig"))
    assert manifest["commit"] == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for item in manifest["files"]:
        assert digest(args.runtime / item["name"]) == item["sha256"]
    fixture = root / "experiments/shared_context_v05/results/expanded/gptoss-records"
    identity = json.loads((fixture / "identity.json").read_text())
    model = Path(identity["model"]["path"])
    assert digest(model) == identity["model"]["sha256"]
    write(output / "identity.json", {"manifest": manifest, "model": identity["model"]})
    requests = json.loads((root / "build/shared-v05/http-lifecycle-fixed/requests.json").read_text())
    expected = json.loads((root / "build/shared-v05/http-lifecycle-fixed/baseline.json").read_text())
    if args.shared_prefix:
        requests["small"]["questions"].append({**requests["small"]["questions"][0], "id": "fact2"})
        expected["evaluation"]["results"].append({**expected["evaluation"]["results"][0], "id": "fact2"})
    write(output / "requests.json", requests)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    results = []
    for scenario in ["idle", "chat_only", "active_only", "active", "pending", "restart"]:
        directory = output / scenario
        directory.mkdir()
        command = [str(args.runtime / "llama-server.exe"), "-m", str(model), "-ngl", "99", "-c", "4096", "-np", "1",
                   "-b", "128", "-ub", "128", "-t", "8", "-tb", "8", "--kv-unified", "--swa-full", "-fa", "on",
                   "--no-warmup", "--no-prefill-assistant", "--host", "127.0.0.1", "--port", str(port),
                   "--threads-http", "8", "--slots", "--evaluate", "--evaluate-context", "4096", "-lv", "4"]
        if args.shared_prefix:
            command.append("--evaluate-shared-prefix")
        write(directory / "command.json", command)
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        sockets = []

        def request(route, body=None):
            req = urllib.request.Request(f"http://127.0.0.1:{port}" + route, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        def raw(route, body):
            data = json.dumps(body).encode()
            sock = socket.create_connection(("127.0.0.1", port), timeout=10)
            sockets.append(sock)
            sock.sendall((f"POST {route} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Type: application/json\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n").encode() + data)
            return sock

        with (directory / "host.log").open("w") as log:
            process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--host", str(directory)],
                                       creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 240
                while True:
                    assert process.poll() is None, "Console host exited"
                    try:
                        if request("/health")[0] == 200:
                            break
                    except OSError:
                        pass
                    assert time.monotonic() < deadline, "Startup timeout"
                    time.sleep(0.5)
                status, evaluation_result = request("/evaluate", requests["small"])
                assert status == 200 and evaluation_result["results"] == expected["evaluation"]["results"]
                if args.shared_prefix:
                    assert evaluation_result["execution"]["strategy"] == "shared_aligned"
                else:
                    assert evaluation_result == expected["evaluation"]
                status, chat = request("/completion", requests["chat"])
                assert status == 200 and chat["tokens"] == expected["chat"]["tokens"] and chat["content"] == expected["chat"]["content"]
                if scenario in ("pending", "chat_only"):
                    raw("/completion", {**requests["chat"], "n_predict": 4096, "ignore_eos": True, "stream": True})
                    deadline = time.monotonic() + 10
                    while not any(s["is_processing"] for s in request("/slots")[1]):
                        assert time.monotonic() < deadline
                        time.sleep(0.05)
                if scenario in ("active", "active_only", "pending"):
                    offset = (directory / "server.log").stat().st_size
                    evaluation = raw("/evaluate", requests["heavy"])
                    if scenario in ("active", "active_only"):
                        deadline = time.monotonic() + 10
                        while True:
                            with (directory / "server.log").open("rb") as stream:
                                stream.seek(offset)
                                if b"n_seq_max             = 3" in stream.read():
                                    break
                            assert time.monotonic() < deadline, "Evaluation allocation timeout"
                            time.sleep(0.02)
                    else:
                        time.sleep(0.5)
                    status, body = request("/evaluate", requests["small"])
                    assert status == 503 and "already admitted" in body["error"]["message"]
                    assert not select.select([evaluation], [], [], 0)[0], "Evaluation completed too early"
                    if scenario == "active":
                        waiting_chat = raw("/completion", requests["chat"])
                        time.sleep(0.2)
                        assert not select.select([waiting_chat], [], [], 0)[0]
                    elif scenario == "pending":
                        assert any(s["is_processing"] for s in request("/slots")[1])
                (directory / "stop").touch()
                process.wait(timeout=45)
                result = json.loads((directory / "exit.json").read_text())
                results.append({"scenario": scenario, **result})
                write(output / "results.json", results)
                print(json.dumps(results[-1]), flush=True)
                with socket.socket() as probe:
                    probe.settimeout(1)
                    assert probe.connect_ex(("127.0.0.1", port)) != 0, "Port remains open"
            finally:
                for sock in sockets:
                    sock.close()
                if process.poll() is None:
                    (directory / "stop").touch()
                    process.wait(timeout=45)
    passed = all(not r["forced"] and r["code"] == 0 for r in results)
    write(output / "summary.json", {"passed": passed, "commit": manifest["commit"], "results": results})
    assert passed, "One or more shutdown scenarios failed"


if __name__ == "__main__":
    main()
