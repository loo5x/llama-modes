# Fresh-only HTTP validation baseline

The current validated runtime baseline is `42b3feba407f0183f588098d349ddb6de86e98bf`, Actions run `37041909852`, on Windows CUDA with GPT-OSS 20B MXFP4 and RTX 5080. `/evaluate` still uses a fresh context per candidate. This checkpoint records observed behavior before shared-prefix integration; it is not a general production certification.

## Evidence

| Check | Report | Tested build |
| --- | --- | --- |
| Native oracle, Boolean/Choice/Scale, ordering and repeat | [Fresh scores](HTTP-FRESH-VALIDATION.md) | `c67d458` |
| Admission, queued chat, active and pending cancellation | [Lifecycle](HTTP-LIFECYCLE-VALIDATION.md) | `ab08e0a`, repeated on `42b3feb` |
| Ctrl+C, connected clients, restart | [Shutdown](HTTP-SHUTDOWN-VALIDATION.md) | `42b3feb` |
| Sleep/wake, nine limit cases, 100 evaluation/chat pairs | [Stability](HTTP-STABILITY-VALIDATION.md) | `42b3feb` |

Fresh numerical comparison covered 22 candidates across batches 128 and 512, compared within each configuration. The later lifecycle runs used batch/microbatch 128. The two server fixes affect request waiting and shutdown; the independent numerical oracle run was on the earlier build, not repeated on the final build. Final-build evaluation and fresh chat results matched the retained reference responses.

The original CPU JUnit report showed 10 passes. The workflow now also selects cancellation and shutdown regressions, but subsequent CPU JUnit reports were not available locally for direct inspection. Do not infer inspected test counts from the existence of a downloaded Windows artifact.

## Saved data and local prerequisites

[HTTP-VALIDATION-BASELINE.json](HTTP-VALIDATION-BASELINE.json) preserves selected JSON data from eight runs, including pre-fix failures, plus their original file manifests. Each selected record includes its source SHA-256 and parsed JSON data. All selected source hashes were verified when creating the archive. Full logs, runner snapshots, and serialized slot files remain in local `build/shared-v05` directories; their hashes are retained in the manifests, but their bytes are not included in this compact archive. Re-serializing a `data` object does not reproduce the original byte hash.

The committed `results/expanded/gptoss-records/cases.json` and `identity.json` are the original input fixture and model identity used by the HTTP runners. The runtime fields in that fixture identity describe the older prototype runtime; each HTTP run has its own build manifest. Do not substitute the fixture runtime hashes for the HTTP build manifest.

The four `http_*_validation.py` scripts are the tested local Windows runners. They use local model/runtime paths and require the installed build manifest to match checkout HEAD. A later documentation-only commit does not require a rebuild, but these historical scripts still require running from the matching source checkout. Preserve the validated runtime and use a separate checkout when replaying an older build.

The shutdown runner reads `baseline.json` and `requests.json` from `build/shared-v05/http-lifecycle-fixed`. The stability runner reads those files plus `identity.json` and `server-command.json` from `build/shared-v05/http-lifecycle-shutdown-fixed`. The compact archive contains these records under the corresponding run names. On a fresh checkout, reconstruct these JSON files from their `data` objects at the stated paths, or run the corresponding lifecycle check first. Runtime and model paths must match the test machine. Always use a new output directory to preserve earlier evidence.

## Remaining scope

No allocation/decode failure injection, GPU-specific memory accounting, long-duration soak, other model/backend validation, or shared-prefix integration is claimed. The ordinary cached-chat control produced different tokens before any evaluation; lifecycle comparisons deliberately use fresh chat processing and separately compare saved idle state. The repeated-use test observed a host-memory plateau over 100 pairs, not proof of leak freedom.

The next implementation step is batch-aligned shared-prefix reuse, guided by the earlier prototype and integration design. Compare it against fresh evaluation at identical settings, repeat lifecycle checks, and measure latency before making an efficiency claim.
