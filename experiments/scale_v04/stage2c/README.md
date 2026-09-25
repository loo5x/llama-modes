# Stage 2c native diagnostics

Experimental Windows x64 Python/NumPy tooling for the exact validated DLL ABI. It uses C:\AI\llama-modes-v03 without changing that package. No WSL, native compilation, server changes, sampling, or full SCALE rerun.

Run from the repository root, with no competing model process using the GPU. Output directories must be new. Execute the inference commands sequentially.

```powershell
python experiments/scale_v04/stage2c/diagnose.py --output experiments/scale_v04/stage2c/new-run/baseline
python experiments/scale_v04/stage2c/diagnose.py --output experiments/scale_v04/stage2c/new-run/traced --trace
python experiments/scale_v04/stage2c/diagnose.py --output experiments/scale_v04/stage2c/new-run/attention-inputs --trace --attention-inputs
python experiments/scale_v04/stage2c/diagnose.py --output experiments/scale_v04/stage2c/new-run/copy-validated --copy
python experiments/scale_v04/stage2c/diagnose.py --output experiments/scale_v04/stage2c/new-run/benchmark-verified --benchmark
python experiments/scale_v04/stage2c/analyze.py --root experiments/scale_v04/stage2c/new-run
```

The existing independent executable was invoked using the preserved Stage 2b harness:

```powershell
python experiments/scale_v04/stage2b/investigate.py oracle --output experiments/scale_v04/stage2c/new-oracle-confirmation
```

To verify the completed primary run without new inference:

```powershell
python experiments/scale_v04/stage2c/analyze.py --root experiments/scale_v04/stage2c/matched
python experiments/scale_v04/stage2c/verify.py
```

Python 3.14.7 and NumPy 2.5.2 were used. `verify.py` hashes the model/runtime and all experimental artifacts; it can take longer than the analysis. The manifest excludes itself and Python bytecode caches. Float arrays are little-endian float32. Tensor dumps include shapes and byte strides, which must be used for non-contiguous views. Serialized KV metadata parsing is specific to GPT-OSS, non-transposed f16 values, and this exact DLL build; it asserts complete byte consumption.

Primary results are under `matched/`; earlier root-level runs are preserved pilots. Read [REPORT.md](REPORT.md) for distinctions, measurements, and limitations.
