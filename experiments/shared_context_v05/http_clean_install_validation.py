"""Check the manifest runtime in a fresh directory with a minimal environment."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

from http_fresh_validation import digest, write


def modules(pid):
    if sys.platform != "win32":
        raise RuntimeError("Module inspection requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    psapi.EnumProcessModulesEx.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong]
    psapi.GetModuleFileNameExW.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entries = (ctypes.c_void_p * 2048)()
        needed = ctypes.c_ulong()
        if not psapi.EnumProcessModulesEx(handle, entries, ctypes.sizeof(entries), ctypes.byref(needed), 3):
            raise ctypes.WinError(ctypes.get_last_error())
        assert needed.value <= ctypes.sizeof(entries)
        paths = []
        for module in entries[:needed.value // ctypes.sizeof(ctypes.c_void_p)]:
            buffer = ctypes.create_unicode_buffer(32768)
            if not psapi.GetModuleFileNameExW(handle, module, buffer, len(buffer)):
                raise ctypes.WinError(ctypes.get_last_error())
            paths.append(buffer.value)
        return paths
    finally:
        kernel.CloseHandle(handle)


def main():
    if sys.platform != "win32":
        raise RuntimeError("Clean-folder runtime validation requires Windows")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, output / Path(__file__).name)
    source = Path(r"C:\AI\llama-modes-v05")
    manifest = json.loads((source / "build-manifest.json").read_text(encoding="utf-8-sig"))
    subprocess.run(["git", "diff", "--exit-code", manifest["commit"], "HEAD", "--", "common", "src", "ggml", "include", "tools/server", "vendor", "cmake", "CMakeLists.txt"], cwd=root, check=True, stdout=subprocess.PIPE)
    runtime = output / "clean runtime"
    runtime.mkdir()
    for item in manifest["files"]:
        assert Path(item["name"]).name == item["name"]
        assert digest(source / item["name"]) == item["sha256"]
        shutil.copy2(source / item["name"], runtime / item["name"])
        assert digest(runtime / item["name"]) == item["sha256"]
    shutil.copy2(source / "build-manifest.json", runtime / "build-manifest.json")
    assert len(list(runtime.iterdir())) == len(manifest["files"]) + 1
    assert not (runtime / "test-save-load-state.exe").exists()
    work = output / "empty working directory"
    work.mkdir()
    env = {name: os.environ[name] for name in ("SystemRoot", "WINDIR", "TEMP", "TMP", "COMSPEC", "PATHEXT") if name in os.environ}
    windows = Path(os.environ["SystemRoot"])
    env["PATH"] = str(windows / "System32") + ";" + str(windows)
    write(output / "environment.json", env)
    version = subprocess.run([str(runtime / "llama-server.exe"), "--version"], cwd=work, env=env, capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    assert version.returncode == 0
    (output / "version.txt").write_bytes(version.stdout + version.stderr)
    prior = args.reference.resolve()
    identity = json.loads((prior / "identity.json").read_text())
    assert manifest == identity["manifest"]
    assert digest(Path(identity["model"]["path"])) == identity["model"]["sha256"]
    write(output / "identity.json", identity)
    command = json.loads((prior / "server-command.json").read_text())
    command[0] = str(runtime / "llama-server.exe")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    command[command.index("--port") + 1] = str(port)
    write(output / "command.json", command)
    payload = json.loads((prior / "request.json").read_text())
    expected = json.loads((prior / "response.json").read_text())
    baseline = json.loads((root / "build/shared-v05/http-lifecycle-shared/baseline.json").read_text())
    chat = json.loads((root / "build/shared-v05/http-lifecycle-shared/requests.json").read_text())["chat"]

    def request(route, body=None):
        req = urllib.request.Request(f"http://127.0.0.1:{port}" + route, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)

    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    with (output / "host.log").open("w") as log:
        process = subprocess.Popen([sys.executable, str(root / "experiments/shared_context_v05/http_shutdown_validation.py"), "--host", str(output)],
            cwd=work, env=env, startupinfo=startup, creationflags=subprocess.CREATE_NEW_CONSOLE, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 240
            while True:
                assert process.poll() is None, "Host exited"
                try:
                    if request("/health")["status"] == "ok":
                        break
                except OSError:
                    pass
                assert time.monotonic() < deadline
                time.sleep(0.5)
            actual = request("/evaluate", payload)
            write(output / "response.json", actual)
            assert actual == expected
            assert request("/v1/evaluate", payload) == expected
            completion = request("/completion", chat)
            write(output / "completion.json", completion)
            assert completion["tokens"] == baseline["chat"]["tokens"] and completion["content"] == baseline["chat"]["content"]
            pid = json.loads((output / "pid.json").read_text())["pid"]
            loaded = modules(pid)
            write(output / "loaded-modules.json", loaded)
            packaged = {item["name"].lower() for item in manifest["files"]}
            for path in loaded:
                if Path(path).name.lower() in packaged:
                    assert Path(path).parent == runtime, path
                assert str(source).lower() not in path.lower(), path
            assert any(Path(p).name.lower() == "ggml-cuda.dll" for p in loaded)
            print("Clean runtime, shared scores, alias, chat and loaded module checks passed", flush=True)
        finally:
            if process.poll() is None:
                (output / "stop").touch()
                process.wait(timeout=45)
    stopped = json.loads((output / "exit.json").read_text())
    assert stopped["code"] == 0 and not stopped["forced"]
    with socket.socket() as probe:
        probe.settimeout(1)
        assert probe.connect_ex(("127.0.0.1", port)) != 0
    write(output / "summary.json", {"passed": True, "runtime_commit": manifest["commit"], "runtime_files": len(manifest["files"]), "shutdown": stopped,
        "scope": "Manifest files copied to a fresh folder on the existing Windows machine; original v0.5 ZIP not available"})


if __name__ == "__main__":
    main()
