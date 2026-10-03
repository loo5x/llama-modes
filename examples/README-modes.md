# Runnable llama-modes examples

Start a llama-modes server with your GGUF first. All examples default to `http://127.0.0.1:8080`, print actual response JSON, and include no model output fixtures. Requests live in [requests/](requests/) so you can edit the question, labels, and scale mapping directly.

These scripts exercise the three individual scoring primitives and chat comparison. For v0.5.0 shared-context multi-question evaluation, use the complete [PowerShell quickstart](../docs/quickstart.md#8-v05-multiple-questions-optional) and [`/evaluate` contract](../docs/evaluate.md). `/evaluate` requires `--evaluate` on a direct server; it is not a router endpoint.

From the repository root:

```sh
python examples/python/boolean.py
python examples/python/choice.py
python examples/python/scale.py
python examples/python/compare_direct_chat.py --url http://127.0.0.1:8080
```

Python needs only its standard library. Optional `--model MODEL_ID` selects a router model; `--timeout` is in seconds.

```powershell
.\examples\powershell\boolean.ps1
.\examples\powershell\choice.ps1
.\examples\powershell\scale.ps1
.\examples\powershell\compare_direct_chat.ps1 -Url http://127.0.0.1:8080
```

PowerShell accepts `-Model MODEL_ID` and `-Timeout 120`. Your local PowerShell execution policy must allow scripts you have reviewed.

The curl scripts use a POSIX shell (Linux/macOS/Git Bash). In Windows PowerShell use the `.ps1` examples, or `curl.exe` with the JSON files:

```sh
sh examples/curl/boolean.sh
sh examples/curl/choice.sh
sh examples/curl/scale.sh
sh examples/curl/compare_direct_chat.sh http://127.0.0.1:8080
```

```powershell
curl.exe --fail-with-body http://127.0.0.1:8080/scale -H "Content-Type: application/json" --data-binary "@examples/requests/scale.json"
```

For a router, add `"model":"MODEL_ID"` to each curl request JSON. `compare_direct_chat` runs Boolean direct then chat sequentially; it is an interactive example, not a benchmark. No parser invents a result: inspect the final content, finish reason, and reported completion tokens. See the [benchmark harness](../benchmarks/README.md) for exact-answer parsing and repeated measurements.

Direct generated tokens are zero by design; this is not a fabricated API usage field. Multi-token decisions return log scores, not the legacy single-token probability field. SCALE weights and decision-relative probabilities are not calibrated confidence. [API details](../docs/decision.md) | [SCALE interpretation](../docs/scale.md).
