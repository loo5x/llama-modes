"""Validate sleep, request limits, and repeated use on the Windows build."""
import argparse
import copy
import ctypes
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

from http_fresh_validation import digest, write


def memory(pid):
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        value = Counters()
        value.cb = ctypes.sizeof(value)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(value), value.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"private_bytes": value.PrivateUsage, "working_set_bytes": value.WorkingSetSize}
    finally:
        kernel.CloseHandle(handle)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, output / Path(__file__).name)
    runtime = Path(r"C:\AI\llama-modes-v05")
    manifest = json.loads((runtime / "build-manifest.json").read_text(encoding="utf-8-sig"))
    assert manifest["commit"] == subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for item in manifest["files"]:
        assert digest(runtime / item["name"]) == item["sha256"]
    prior = root / "build/shared-v05/http-lifecycle-shutdown-fixed"
    identity = json.loads((prior / "identity.json").read_text())
    assert digest(Path(identity["model"]["path"])) == identity["model"]["sha256"]
    write(output / "identity.json", identity)
    requests = json.loads((prior / "requests.json").read_text())
    baseline = json.loads((prior / "baseline.json").read_text())
    events = []

    def event(name, **details):
        row = {"event": name, **details}
        events.append(row)
        write(output / "events.json", events)
        print(json.dumps(row), flush=True)

    for phase in ("sleep_limits", "repeat"):
        directory = output / phase
        directory.mkdir()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        command = json.loads((prior / "server-command.json").read_text())
        command[command.index("--port") + 1] = str(port)
        slot_index = command.index("--slot-save-path")
        del command[slot_index:slot_index + 2]
        command += ["--sleep-idle-seconds", "3" if phase == "sleep_limits" else "-1"]
        write(directory / "command.json", command)
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0

        def request(route, body=None):
            req = urllib.request.Request(f"http://127.0.0.1:{port}" + route, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=120) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        def ok(route, body=None):
            status, value = request(route, body)
            assert status == 200, (route, status, value)
            return value

        def check_chat():
            chat = ok("/completion", requests["chat"])
            assert chat["tokens"] == baseline["chat"]["tokens"] and chat["content"] == baseline["chat"]["content"]

        def check_eval():
            assert ok("/evaluate", requests["small"]) == baseline["evaluation"]

        with (directory / "host.log").open("w") as log:
            process = subprocess.Popen([sys.executable, str(root / "experiments/shared_context_v05/http_shutdown_validation.py"), "--host", str(directory)],
                creationflags=subprocess.CREATE_NEW_CONSOLE, startupinfo=startup, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 240
                while True:
                    assert process.poll() is None
                    try:
                        if request("/health")[0] == 200:
                            break
                    except OSError:
                        pass
                    assert time.monotonic() < deadline
                    time.sleep(0.5)
                check_eval()
                check_chat()
                if phase == "sleep_limits":
                    for cycle in range(3):
                        deadline = time.monotonic() + 30
                        while not ok("/props")["is_sleeping"]:
                            assert time.monotonic() < deadline, "Did not enter sleep"
                            time.sleep(0.2)
                        assert ok("/health")["status"] == "ok"
                        assert ok("/models")["data"]
                        assert ok("/props")["is_sleeping"]
                        started = time.monotonic()
                        if cycle == 1:
                            check_chat()
                            check_eval()
                        else:
                            check_eval()
                            check_chat()
                        assert not ok("/props")["is_sleeping"]
                        event("sleep_wake_passed", cycle=cycle, wake_and_checks_seconds=time.monotonic() - started)

                    def limit_case(name, payload, status):
                        actual, body = request("/evaluate", payload)
                        write(directory / (name + ".json"), {"request": payload, "status": actual, "response": body})
                        assert actual == status, (name, actual, body)
                        if status != 200:
                            assert "results" not in body
                        check_eval()
                        check_chat()
                        event("limit_passed", case=name, status=actual)

                    payload = copy.deepcopy(requests["small"])
                    payload["questions"] = [{**payload["questions"][0], "id": str(i)} for i in range(32)]
                    limit_case("questions_32", payload, 200)
                    payload["questions"].append({**payload["questions"][0], "id": "32"})
                    limit_case("questions_33", payload, 400)
                    payload = copy.deepcopy(requests["small"])
                    payload["questions"][0]["id"] = "a" * 128
                    limit_case("id_128_bytes", payload, 200)
                    payload["questions"][0]["id"] += "a"
                    limit_case("id_129_bytes", payload, 400)
                    payload = copy.deepcopy(requests["small"])
                    payload["context"] = "x" * (1024 * 1024 + 1)
                    limit_case("text_over_1mib", payload, 400)
                    payload = copy.deepcopy(requests["small"])
                    payload["questions"][0].update(type="choice", choices=[f"Option {i:03d}" for i in range(256)])
                    limit_case("choices_256", payload, 200)
                    payload["questions"][0]["choices"].append("Option 256")
                    limit_case("choices_257", payload, 400)
                    payload = copy.deepcopy(requests["small"])

                    def prompt_size(words):
                        payload["context"] = " word" * words
                        question = payload["questions"][0]["question"]
                        probe = "DecisionContentProbe_A7f3"
                        prompt = ok("/apply-template", {"messages": [
                            {"role": "user", "content": payload["context"] + "\n\n" + question},
                            {"role": "assistant", "content": probe}], "add_generation_prompt": False})["prompt"]
                        assert prompt.count(probe) == 1
                        return len(ok("/tokenize", {"content": prompt[:prompt.index(probe)], "add_special": True, "parse_special": True})["tokens"])

                    low, high = 1, 4096
                    while low < high:
                        mid = (low + high + 1) // 2
                        if prompt_size(mid) <= 4096:
                            low = mid
                        else:
                            high = mid - 1
                    assert prompt_size(low) == 4096
                    for label in payload["questions"][0]["choices"]:
                        assert len(ok("/tokenize", {"content": label, "add_special": False, "parse_special": False})["tokens"]) == 1
                    limit_case("prompt_4096_tokens", payload, 200)
                    assert prompt_size(low + 1) == 4097
                    limit_case("prompt_4097_tokens", payload, 400)
                else:
                    pid = json.loads((directory / "pid.json").read_text())["pid"]
                    samples = []
                    for cycle in range(100):
                        started = time.monotonic()
                        check_eval()
                        check_chat()
                        samples.append({"cycle": cycle + 1, "seconds": time.monotonic() - started, **memory(pid)})
                        write(directory / "memory.json", samples)
                        if (cycle + 1) % 10 == 0:
                            event("repeat_progress", **samples[-1])
                    write(directory / "summary.json", {"passed": True, "cycles": 100,
                        "private_bytes_first_20_range": [min(s["private_bytes"] for s in samples[:20]), max(s["private_bytes"] for s in samples[:20])],
                        "private_bytes_last_20_range": [min(s["private_bytes"] for s in samples[-20:]), max(s["private_bytes"] for s in samples[-20:])]})
            finally:
                if process.poll() is None:
                    (directory / "stop").touch()
                    process.wait(timeout=45)
            result = json.loads((directory / "exit.json").read_text())
            assert result["code"] == 0 and not result["forced"], result
            event("phase_finished", phase=phase, shutdown=result)
    write(output / "summary.json", {"passed": True, "commit": manifest["commit"], "sleep_cycles": 3, "limit_cases": 9, "repeat_cycles": 100})


if __name__ == "__main__":
    main()
