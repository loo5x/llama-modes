# Based on llama.cpp

llama-modes is a fork/extension of [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp). It retains the model loading, GGUF support, runtime, backends, normal chat/completion endpoints, and source history of its upstream base, while adding structured evaluation modes.

This does not imply that llama-modes continuously tracks the latest upstream commit, or that every upstream model/backend combination has been validated with its added modes. The historical baseline for the first decision milestone was `444826532091bba42771d749b9dc7e71ddc76efd`.

The [MIT license](../LICENSE), attribution, third-party notices under [licenses/](../licenses/), and upstream source are retained. The root landing page presents llama-modes; upstream implementation and contributor documentation remain available in the repository.

- [Source build instructions](build.md)
- [Server usage and API reference](../tools/server/README.md)
- [Server development guide](../tools/server/README-dev.md)
- [Contributing guidelines](../CONTRIBUTING.md)
- [Upstream project](https://github.com/ggml-org/llama.cpp)

## Published release provenance

[llama-modes v0.5.0](https://github.com/loo5x/llama-modes/releases/tag/v0.5.0) is a normal release with experimental shared-context evaluation. Tag `v0.5.0` points to the tested runtime commit `a02fe9f1ed3214ddaceac3630431fd592371abd3`, built in Actions run `37126739509`. The public Windows CUDA ZIP and checksum are attached to that release; users supply their own GGUF.

Later documentation and validation records do not change the tagged binaries. See the [v0.5.0 notes](../RELEASE_NOTES_v0.5.0.md), [package validation](../experiments/shared_context_v05/HTTP-CLEAN-INSTALL-VALIDATION.md#final-050-zip-validation), and [historical v0.4.0 notes](../RELEASE_NOTES_v0.4.0.md). The package preserves the license and third-party notices. Its validated configuration does not establish support for every upstream model, backend, or GPU.

GitHub displays the README from the repository's default branch. Documentation changes on another branch reach that landing page only after the owner incorporates them into the default branch. Updating these files does not change repository settings, branches, tags, or release assets.
