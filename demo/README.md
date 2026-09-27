# llama-modes local demo

A local React + TypeScript workbench for BOOLEAN, CHOICE, SCALE, and **Interactive comparison**. All live inference comes from llama-server. The demo does not contain an inference engine.

## Launch

Start your llama-modes server with a GGUF on `http://127.0.0.1:8080`. Use Node.js 22.12+ (local checks used Node 24), then:

```sh
cd demo
npm install
npm run dev
```

Open `http://127.0.0.1:5173`. For the built local demo:

```sh
npm run demo
```

Open `http://127.0.0.1:4173`. This builds then runs Vite's local preview server. The dev and preview servers both bind to loopback and use the same restricted proxy. They are local demonstration tools, not public hosting services. `npm ci` reproduces the committed lockfile after the first checkout.

## Connection settings

The header detects a model through `/v1/models`. Reconnect is available in settings. To change the server port, create `demo/.env.local`:

```text
LLAMA_SERVER_URL=http://127.0.0.1:8090
```

Restart the demo after editing it. Only HTTP `127.0.0.1`, `localhost` (normalized to 127.0.0.1), and `[::1]` targets are accepted. Credentials, URL paths, query strings, fragments, and non-loopback hosts are rejected. The target cannot be changed by a browser request.

## Features

- Boolean Yes/No scoring and latency, with zero generated tokens by design.
- Editable categorical labels, including multi-token labels; ranked candidate bars.
- Ordered SCALE point editor with an explicit label/value mapping shown to the user and included in the model prompt.
- Ordinal/interval selection, mode, median, q25/q75, all weights, histogram, and interval mean/spread.
- Editable fact, sentiment, favorability, topic, Likert, and severity presets.
- Direct, Chat, and sequential Run Both controls for every mode. Chat exact labels are compared with the unique direct winner; ties/missing answers give no agreement value.
- Advanced request/response JSON, copy JSON/curl, token IDs/counts, SUM/MEAN log scores, and chat usage/fingerprint when returned. The copied curl command targets llama-server directly and uses POSIX shell quoting.
- Presentation mode enlarges scores/charts, retains model and latency context, and hides Advanced.
- Helpful errors for offline servers, unsupported endpoints, invalid requests, prefix overlap, malformed responses, and timeouts. Inputs are locked during a run; editing inputs clears previous results.

For sequence choices the UI computes stable softmax over SUM scores and explicitly labels that display transformation. It does not add a probability field to the API. Mean log probability is shown only in Advanced and is not used as sequence probability.

Chat requires an exact supplied label in final content after outer whitespace trimming, and a `stop` finish reason. Reasoning, prose, changed case, and truncated output are not converted into a label. The default chat cap is 1024 tokens. Inspect raw responses and use the [benchmark CLI](../benchmarks/README.md) for configurable generation caps and repeatable measurements.

## Fixture preview

![Rendered SCALE demo using labeled fixture data](screenshot-fixture.png)

Open `http://127.0.0.1:5173/?fixture=1` and click **Show fixture** in SCALE. A persistent banner identifies illustrative data. No model requests are made, token IDs are illustrative, and latency is marked unmeasured. The preview supports SCALE only; remove the query parameter for live inference. This mode is for visual development and screenshots, never performance evidence.

## Checks

```sh
npm run build
npm run typecheck
npm run lint
npm test
```

Pure unit tests need no model server. Browser/manual checks should cover editing during runs, mode changes, reconnect, proxy failure, fixture labeling, and presentation readability. No fake benchmark values are shipped. Benchmark visualization is intentionally deferred; use the separately saved raw/summary JSON.

## Architecture and privacy

- `src/App.tsx`: view state, editable inputs, sequential runs, results, and Advanced.
- `src/api.ts`: request construction, strict response parsing, and interpretation helpers.
- `src/presets.ts` / `src/fixtures.ts`: editable tasks and explicitly labeled development data.
- `proxy.ts`: loopback-only target, exact endpoint/method allowlist, same-origin checks, request size limit, redirect refusal, timeout, and disconnect cancellation.
- `vite.config.ts`: identical proxy behavior for development and built preview.

The proxy accepts only `/v1/models`, `/decision`, `/scale`, and `/v1/chat/completions`, plus its own read-only config endpoint. It forwards no browser credentials. No authentication system, filesystem API, database, analytics, telemetry, remote model service, or external font is added. Runtime requests stay on the machine; dependency installation separately downloads packages from npm. Raw content is shown as React text, never rendered as HTML.

The stack follows the [Vite guide](https://vite.dev/guide/), [Tailwind Vite integration](https://tailwindcss.com/docs/installation/using-vite), and [Recharts responsive container API](https://recharts.github.io/api/ResponsiveContainer/). Its dependencies are isolated from the existing upstream server UI.
