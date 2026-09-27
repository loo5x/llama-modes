# Based on llama.cpp

llama-modes is a fork/extension of [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp). It retains the model loading, GGUF support, runtime, backends, normal chat/completion endpoints, and source history of its upstream base, while adding structured evaluation modes.

This does not imply that llama-modes continuously tracks the latest upstream commit, or that every upstream model/backend combination has been validated with its added modes. The historical baseline for the first decision milestone was `444826532091bba42771d749b9dc7e71ddc76efd`.

The [MIT license](../LICENSE), attribution, third-party notices under [licenses/](../licenses/), and upstream source are retained. The root landing page presents llama-modes; upstream implementation and contributor documentation remain available in the repository.

- [Source build instructions](build.md)
- [Server usage and API reference](../tools/server/README.md)
- [Server development guide](../tools/server/README-dev.md)
- [Contributing guidelines](../CONTRIBUTING.md)
- [Upstream project](https://github.com/ggml-org/llama.cpp)

## Public landing page and release migration (manual)

Recommended description: **Structured LLM inference modes for llama.cpp.**

Suggested topics: `llama-cpp`, `llm`, `local-llm`, `structured-inference`, `gguf`, `inference`, `classification`, `cuda`.

1. Review and validate the public-release branch. The owner handles any commit/push after review; this milestone does neither.
2. Create a public `main` branch from the reviewed release state. Keep `master` and upstream history if useful for tracking the base.
3. In GitHub repository settings, change the default branch to `main`. Review branch protections and Actions branch filters; do not rename or delete history merely to change the landing page.
4. Build and test the intended Windows CUDA runtime package from the exact release commit. Record the commit, CUDA/GPU compatibility, runtime dependencies, ZIP contents, and SHA-256 checksum. Include license and third-party notices with redistributed binaries.
5. Create the `v0.4.0` tag and GitHub Release manually when ready. Use the prepared [release notes](../RELEASE_NOTES_v0.4.0.md), after confirming every validation claim.
6. Attach the actual Windows CUDA runtime ZIP and checksum to the Release. Users supply their own GGUF. Actions artifacts are build outputs, not the durable public download interface.
7. Check the release page and download from a signed-out browser, then set the description/topics above. Add exact asset links only after the assets exist.

No repository settings, releases, tags, or remote branches are changed by this preparation.
