# Clean-folder runtime validation

2026-10-03. Tested runtime commit `427d6bdfdd0f0568c4d1bf76fd58a9589cec208d`, Actions run `37066508221`, on the existing Windows/RTX 5080 machine with GPT-OSS 20B MXFP4.

## Result

The test passed in `build/shared-v05/http-clean-install-r2`. It copied only the twelve runtime files named in the build manifest plus the manifest itself into a new directory containing spaces. Source and destination hashes matched. The oracle executable was excluded. The server started from an initially empty working directory, with PATH restricted to Windows and System32 and no inherited model, CUDA-toolkit, or llama-specific environment settings.

Both `/evaluate` and `/v1/evaluate` returned exactly the current-day shared reference response for the three-question fixture. Ordinary fresh chat tokens/content matched the earlier chat reference. Loaded module inspection confirmed that loaded packaged libraries came from the new runtime directory, including `ggml-cuda.dll`, with none loaded from `C:\AI\llama-modes-v05`. Windows/driver libraries remain system dependencies. Ctrl+C produced a zero exit without forced termination, and the listening port closed.

## Reference date control

The initial attempt in `http-clean-install` compared against the previous day's scores and stopped on that assertion. The process then exited cleanly. Native GPT-OSS prompts include a current-date field. The new prepared prompts differ from the old ones only by `2026-10-02` becoming `2026-10-03`; the initial clean-folder response exactly matches the new reference.

The original installed runtime was rerun on the current date in `http-reference-oct03-r2`. All eleven candidate comparisons with the matching native oracle passed with maximum checked difference zero; order, repeat, overflow rejection, and subsequent completion also passed. The clean-folder rerun used that same-day reference. Do not compare scoring baselines across changed template inputs.

The numerical runner now offers `--allow-documentation-only` for this replay: the manifest commit must be an ancestor of HEAD, and committed differences must be limited to documentation, experiment files, README, or release notes. Runtime/model hashes are still checked. The first reference launch used the original strict HEAD check and stopped before inference; this was a runner guard, not a runtime failure.

## Packaging limits and remaining work

The original v0.5 ZIP was not present in Downloads, so this is a manifest-file reconstruction check, not verification of archive extraction. It is not a fresh Windows installation: installed system runtimes and the NVIDIA driver were available. Binaries report `0.4.1-dev`, despite containing the experimental v0.5 feature. Public packaging must set the intended version, include license/notices, and record the final binary/source identities before publication. No tag, release, upload, or production code change was made during this test.

Runner: `http_clean_install_validation.py`. Evidence includes the minimal environment, copied manifest, exact command, module paths, version output, responses, shutdown result, logs, and runner snapshot. The copied binaries remain local in the test directory; evidence manifests record their hashes.
