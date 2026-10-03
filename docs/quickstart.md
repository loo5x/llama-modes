# Quick start: Windows + NVIDIA + your GGUF

You need a GGUF model supported by your runtime, an NVIDIA GPU/driver compatible with the chosen CUDA build, and enough memory for that model and context. No model is bundled.

## 1. Get the runtime

Download [llama-modes v0.5.0](https://github.com/loo5x/llama-modes/releases/tag/v0.5.0): `llama-modes-v0.5.0-win-cuda.zip` and its `.sha256` file. Verify the checksum and extract the ZIP with its DLLs intact. The package targets Windows x64 and CUDA architecture 120; see its README for driver and Microsoft Visual C++ runtime requirements. For source builds, use [docs/build.md](build.md). An ordinary upstream llama.cpp binary does not provide the added endpoints.

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

## 8. v0.5 multiple questions (optional)

The v0.5.0 runtime includes the experimental `/evaluate` feature. Restart the server with the endpoint and optional sharing enabled:

```powershell
.\llama-server.exe -m "C:\models\your-model.gguf" --host 127.0.0.1 --port 8080 -ngl 99 -c 4096 -np 1 -b 128 -ub 128 --jinja --no-prefill-assistant --evaluate --evaluate-context 4096 --evaluate-shared-prefix
```

In another terminal, submit two independent questions about one text:

```powershell
$text = ('Paris is in France. The service was good. ' * 20)
$body = @{
    context = $text
    questions = @(
        @{ id = 'location'; type = 'boolean'; question = 'Is Paris in France? Answer yes or no.'; choices = @('yes', 'no') }
        @{ id = 'service'; type = 'choice'; question = 'Describe the service. Answer good or bad.'; choices = @('good', 'bad') }
    )
} | ConvertTo-Json -Depth 10
$result = Invoke-RestMethod http://127.0.0.1:8080/evaluate -Method Post -ContentType 'application/json' -Body $body
$result | ConvertTo-Json -Depth 20
```

The repeated text makes a longer shared context for this small example. Check `execution.strategy` and `execution.shared_prefix_tokens`. An eligible request reports `shared_aligned`; a short prefix or other ineligible case reports `fresh` with a reason. Remove `--evaluate-shared-prefix` to use fresh scoring for comparison. Removing `--evaluate` disables both endpoint routes.

The validated shared configuration used GPT-OSS 20B MXFP4 on Windows CUDA with RTX 5080. Other models need their own checks, and evaluation requires memory in addition to the resident chat context. Read the [API and limits](evaluate.md), [v0.5.0 release notes](../RELEASE_NOTES_v0.5.0.md), and [final ZIP validation](../experiments/shared_context_v05/HTTP-CLEAN-INSTALL-VALIDATION.md#final-050-zip-validation). Reuse lasts for this request only, and each question remains independent. The demo does not expose this endpoint.

## Troubleshooting

- Disconnected: verify the server terminal, port, and `/v1/models`; use Reconnect in demo settings.
- HTTP 404: ensure you are running llama-modes with the required endpoint version.
- HTTP 400 token-prefix overlap: change labels and explicitly update their mapping; see [SCALE](scale.md).
- Ambiguous template boundary: the messages path intentionally rejects unsupported boundaries. See [raw mode](decision.md) before trying a model-specific prompt.
- Context overflow: shorten the task or labels, or start the server with a suitable context. Direct requests are not silently truncated.
- Chat returns no exact answer: inspect its final content, finish reason, and reasoning in Advanced. The demo uses a 1024-token chat limit; the benchmark exposes `--max-tokens` for longer runs.

## Linux/macOS source builds

Follow the retained [llama.cpp build guide](build.md) for your backend, building this fork's checkout. Use `llama-server` instead of `llama-server.exe`. Those source instructions are build pointers, not a claim that new release binaries or the added modes have been validated on every platform.
