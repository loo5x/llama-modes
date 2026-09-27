# llama-modes

**Structured LLM inference modes for llama.cpp.**

LLM applications often need a judgment rather than generated prose. llama-modes scores supplied alternatives at a prepared model evaluation state and returns a structured result.

**[Quick start](docs/quickstart.md) | [Demo](demo/README.md) | [Cookbook](docs/cookbook.md) | [API: Decision](docs/decision.md) / [SCALE](docs/scale.md) | [Benchmark methodology](docs/benchmark-methodology.md) | [Releases](https://github.com/loo5x/llama-modes/releases)**

## Three modes

| Mode | Give it | Get back |
| --- | --- | --- |
| **BOOLEAN** | A question and Yes / No | Relative scores for both alternatives |
| **CHOICE** | Arbitrary labels, including multi-token labels | Candidate scores and token details |
| **SCALE** | Ordered points and label representations | A discrete distribution, mode, median, and quantiles; mean and spread for interval scales |

```text
CHAT         prompt -> autoregressive generation -> text answer
llama-modes  prompt -> prepared evaluation state -> score supplied alternatives -> structured result
```

| Capability | Behavior |
| --- | --- |
| Direct evaluation | Zero generated answer tokens; prompt and candidate-prefix evaluation still cost compute |
| Native messages | Uses the model's chat template at a supported assistant content boundary |
| Raw prompts | Caller controls the evaluation boundary |
| Local runtime | Your GGUF, llama-server, existing llama.cpp backends |
| Compatibility | Normal llama-server chat/completion behavior remains available |

## A 60-second example

With a llama-modes runtime and your GGUF already downloaded, start the server in PowerShell:

```powershell
.\llama-server.exe -m "C:\models\your-model.gguf" --host 127.0.0.1 --port 8080 -ngl 99 --jinja
```

In another terminal:

```powershell
$body = @{ messages = @(@{ role = 'user'; content = 'Is Paris the capital of France? Return only Yes or No.' }); choices = @('Yes', 'No') } | ConvertTo-Json -Depth 10
Invoke-RestMethod http://127.0.0.1:8080/decision -Method Post -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 20
```

For single-token labels, inspect each choice's `probability`. If a label has multiple tokens, the response uses `sum_log_probability` and `mean_log_probability` instead. [Understand the two formats](docs/decision.md).

## More than a single rating

For comment favorability from 0 to 10, an **illustrative, unmeasured** distribution might be:

```text
value      0  1  2  3  4  5  6  7    8    9    10
weight     0  0  0  0  0  0  0  10%  20%  60%  10%

mode: [9]     median: 9     expected_value: 8.7
```

`expected_value` is derived from the full discrete distribution; the model does not generate it directly. It appears only for interval scales, where the caller asserts that numeric distances have meaning. [Complete SCALE request and interpretation](docs/scale.md).

## Run the local demo

From this repository, with Node.js 22.12+:

```sh
cd demo
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. Explore Boolean, Choice, SCALE, and sequential **Interactive comparison** with chat. Presentation mode enlarges results and charts. A loopback-only proxy connects to your server at `127.0.0.1:8080`; no cloud services, telemetry, or accounts are used. [Demo setup and settings](demo/README.md).

![Actual rendered demo with explicitly labeled fixture data; no live inference or measured latency](demo/screenshot-fixture.png)

Screenshot: illustrative fixture data, not a model result or benchmark.

## Download and install

Use the [GitHub Releases page](https://github.com/loo5x/llama-modes/releases) for public runtime downloads. The intended v0.4.0 package is a **Windows CUDA runtime ZIP**; supply your own GGUF model. No release asset is asserted to exist until published. Check its GPU/driver requirements and checksum. GitHub Actions artifacts are not the long-term public download interface.

If no release package is available, see the [source build guide](docs/build.md) for this fork. Windows CUDA validation is documented; validated binaries for other platforms are not promised. The [Windows quick start](docs/quickstart.md) covers extraction, model discovery, all three modes, and the demo.

## Interpret results carefully

**Relative candidate/scale weights are not calibrated confidence.** Direct evaluation is not equivalent to autoregressive reasoning. Labels, tokenization, prompt wording, and templates affect scores. SCALE is discrete, representation-sensitive, and can reject strict token-prefix collisions such as `1` versus `10` for some tokenizers. There is no claim of universally better accuracy or speed than chat.

- [Cookbook: 15 practical recipes](docs/cookbook.md)
- [Design, correctness history, and limitations](docs/design-and-limitations.md)
- [Runnable Python, PowerShell, and curl examples](examples/README-modes.md)
- [Reproducible benchmark harness](benchmarks/README.md) and [methodology](docs/benchmark-methodology.md)
- [v0.4.0 release notes](RELEASE_NOTES_v0.4.0.md)

The benchmark preserves raw results and accepts external datasets. This landing page publishes no performance numbers from an unrun benchmark.

## Roadmap

**v0.5 — Shared-context multi-question evaluation**

Ask multiple structured questions about the same context with shared prompt evaluation.

[Roadmap →](docs/roadmap.md)

## Based on llama.cpp

llama-modes is a fork/extension of **[ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp)**. It retains its model, runtime, and backend capabilities while adding structured evaluation modes. The upstream source, [MIT license](LICENSE), [third-party notices](licenses/), and source history are preserved. See [upstream attribution and release preparation](docs/upstream.md) and [contributor guidelines](CONTRIBUTING.md).

Upstream acknowledgements are retained: [cpp-httplib](https://github.com/yhirose/cpp-httplib) (MIT), [stb](https://github.com/nothings/stb) (public domain), [nlohmann/json](https://github.com/nlohmann/json) (MIT), [miniaudio](https://github.com/mackron/miniaudio) (public domain), and [subprocess.h](https://github.com/sheredom/subprocess.h) (public domain).
