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

## Final 0.5.0 ZIP validation

2026-10-03. Runtime commit `a02fe9f1ed3214ddaceac3630431fd592371abd3`, Actions run `37126739509`. Both the CPU test job and Windows CUDA package job succeeded. CPU checks: 22 tests passed, followed by ten successful repetitions of six shutdown cases (SIGINT/SIGTERM with idle, streaming, and pending-evaluation workloads).

The original `llama-modes-v0.5.0-win-cuda.zip` was checked against its SHA-256 sidecar: `18f9fe09eceb93d64212d89c6ecd7d0ce782223662b97f010c2a2f20b8b5342f`. Extraction into a new directory with spaces produced exactly the 27 manifest-listed files plus the manifest. All sizes and hashes matched, including the installed copies in `C:\AI\llama-modes-v05`. The matching oracle hash was verified separately.

The extracted server reports `0.5.0`. With the same minimal Windows environment described above, both evaluation routes exactly matched a new native-oracle-checked reference. All eleven native candidate comparisons had maximum checked difference zero; question/candidate order, repeated calls, overflow rejection, and subsequent completion passed. Batch/microbatch 128 reused 768 prefix tokens. Ordinary chat matched its retained reference. Packaged modules loaded from the extraction directory. Ctrl+C exited with code zero without force in 1.167 seconds; the port closed.

Six further Windows shutdown scenarios passed: idle, chat only, active evaluation only, active evaluation plus waiting chat, evaluation pending behind chat, and restart. All exited with code zero without force, in 1.160 to 2.259 seconds, with ports closed. No test-owned server remained running.

The first shutdown replay stopped at a comparison with an older numerical baseline, before the shutdown scenarios were exercised; its cleanup still exited normally. The rerun explicitly used the new reference validated against the matching native oracle. Historical expected scores were not overwritten. The shutdown runner now accepts `--reference` and verifies matching build/model identities, batch settings, and execution strategy.

Evidence: `build/shared-v05/http-release-reference`, `http-release-clean-zip`, and `http-release-shutdown-r2`. Selected JSON evidence and its source hashes are preserved in `HTTP-RELEASE-BASELINE.json`. The initial replay remains in `http-release-shutdown`. This validation still uses the existing Windows installation and RTX 5080, not a fresh OS or all model/GPU configurations. The ZIP contains the preparation notes as of its source commit; this later report records the completed checks without altering the tested ZIP. No tag or public release was created.
