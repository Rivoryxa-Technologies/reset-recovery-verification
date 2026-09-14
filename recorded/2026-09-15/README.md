# Recorded review: 15 September 2026

Source revision: `9fe0cf41067042260df1b53678a49c0c4ce25b47`. Logs were produced from a separate local clone of this revision on macOS arm64 with Python 3.9.6 and Icarus/vvp 13.0. Source SHA-256 values are in [summary.json](summary.json).

- 9 correct configurations passed.
- 9 deliberately broken configurations failed with their required diagnostic.
- 4 Python runner regression tests passed independently.
- Individual simulation process times: 0.0101 to 0.0127 seconds. Compilation is recorded separately in the summary. These timings describe this machine and run, not engineering effort or a client delivery estimate.

Rerun the full matrix from the repository root with `python3 tools/run.py`. See the root README for prerequisites and parameter scope. Generated binaries are omitted from this snapshot; every run compiles its own.

The default correct RTL also passed Yosys synthesis and `check -assert`. [synthesis.log](synthesis.log) records the tool version and command. This is a structural synthesis check, not a formal proof, timing closure, or evidence for every parameter.

```sh
yosys -Q -T -p 'read_verilog -sv rtl/response_pipeline.sv; hierarchy -check -top response_pipeline; synth -top response_pipeline; check -assert'
```
