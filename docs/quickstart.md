# Quick start: Windows + NVIDIA + your GGUF

You need a GGUF model supported by your runtime, an NVIDIA GPU/driver compatible with the chosen CUDA build, and enough memory for that model and context. No model is bundled.

## 1. Get the runtime

Open [llama-modes Releases](https://github.com/loo5x/llama-modes/releases). When v0.4.0 is published, select its **Windows CUDA runtime ZIP**, verify its published checksum, and extract it with its DLLs intact. The intended package name is `llama-modes-win-cuda.zip`; this documentation does not assert that a public asset has already been uploaded. If no release asset is available, build this fork from source using [docs/build.md](build.md), or wait for the release. An ordinary upstream llama.cpp binary does not provide the added endpoints.

The preserved Windows validation used RTX 5080 hardware; it does not establish compatibility with every NVIDIA GPU. Read the release's architecture/driver requirements before downloading. No validated Linux/macOS binary is promised here.

## 2. Start the server

In PowerShell, from the extracted runtime folder:

```powershell
.\llama-server.exe -m "C:\models\your-model.gguf" --host 127.0.0.1 --port 8080 -ngl 99 -c 4096 -np 1 --jinja
```

Replace the example path with your GGUF. Keep the server running in that terminal. Adjust GPU layers/context to fit memory. The model's native template must support an unambiguous assistant content boundary for messages mode.

## 3. Verify the model

Open another PowerShell terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/v1/models | ConvertTo-Json -Depth 10
```

## 4. Boolean

```powershell
$body = @{ messages = @(@{ role = 'user'; content = 'Is Paris the capital of France? Return only Yes or No.' }); choices = @('Yes', 'No') } | ConvertTo-Json -Depth 10
Invoke-RestMethod http://127.0.0.1:8080/decision -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 20
```

Read the larger relative probability. Depending on tokenization, choices can use the sequence-score format instead. Neither is calibrated confidence.

## 5. Choice

```powershell
$body = @{ messages = @(@{ role = 'user'; content = 'Which city is the capital of France? Return only Paris, London, or New York.' }); choices = @('Paris', 'London', 'New York') } | ConvertTo-Json -Depth 10
Invoke-RestMethod http://127.0.0.1:8080/decision -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 20
```

For sequence scoring, rank by `sum_log_probability` (largest wins). See [decision details](decision.md).

## 6. SCALE

```powershell
$points = @(0..10 | ForEach-Object { @{ value = $_; label = [string][char](65 + $_) } })
$mapping = ($points | ForEach-Object { "$($_.label)=$($_.value)" }) -join ', '
$body = @{ messages = @(@{ role = 'user'; content = "How favorable is this comment, 0 very unfavorable to 10 very favorable? Comment: I loved it and would recommend it. Return one label. Mapping: $mapping" }); measurement = 'interval'; scale = $points } | ConvertTo-Json -Depth 10
Invoke-RestMethod http://127.0.0.1:8080/scale -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 20
```

The expected value comes from the full discrete distribution. Interval treatment asserts meaningful numeric distances. Use `ordinal` for order alone. Symbolic labels avoid the observed `1`/`10` token-prefix issue in the tested Qwen configuration; other models still need validation.

## 7. Start the demo

Download/clone this fork's source and use Node.js 22.12+ (Node 24 was used for local frontend checks). From the repository root:

```powershell
cd demo
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. For a built local demo, use `npm run demo` and open `http://127.0.0.1:4173`. The loopback proxy avoids browser CORS configuration. See [demo instructions](../demo/README.md).

## Troubleshooting

- Disconnected: verify the server terminal, port, and `/v1/models`; use Reconnect in demo settings.
- HTTP 404: ensure you are running llama-modes with the required endpoint version.
- HTTP 400 token-prefix overlap: change labels and explicitly update their mapping; see [SCALE](scale.md).
- Ambiguous template boundary: the messages path intentionally rejects unsupported boundaries. See [raw mode](decision.md) before trying a model-specific prompt.
- Context overflow: shorten the task or labels, or start the server with a suitable context. Direct requests are not silently truncated.
- Chat returns no exact answer: inspect its final content, finish reason, and reasoning in Advanced. The demo uses a 1024-token chat limit; the benchmark exposes `--max-tokens` for longer runs.

## Linux/macOS source builds

Follow the retained [llama.cpp build guide](build.md) for your backend, building this fork's checkout. Use `llama-server` instead of `llama-server.exe`. Those source instructions are build pointers, not a claim that new release binaries or the added modes have been validated on every platform.
