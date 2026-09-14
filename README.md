# Reset Recovery Verification

This is a small, runnable RTL verification example for a failure that is easy to miss: a synchronous reset clears data registers but leaves pipeline validity state alive. Old work can then emerge after reset as a ghost response.

## Contract

`response_pipeline` accepts a request when `req_valid && req_ready` is sampled on a rising edge. A response appears in request order after `STAGES` clocks and carries `(req_data + BIAS) mod 2**DATA_WIDTH`.

When `rst` is sampled high on a rising edge:

- `req_ready` is low;
- every in-flight request is cancelled;
- no response belonging to cancelled work may appear after reset;
- new requests may be accepted on the first cycle after reset is low.

The implementation is synthesizable and parameterized by width, pipeline depth, and transform bias.

## Failure, cause, and correction

The deliberate mutant sets `MUTANT_KEEP_VALID_ON_RESET=1`. Its reset branch clears the data registers but retains `valid_pipe`. Once reset is released, those valid bits continue through the pipeline and produce responses for requests the contract cancelled. The testbench reports these with the exact marker `RESET_FLUSH_CHECK_FAILED`.

The correction is the normal implementation: synchronously clear all validity bits in the reset branch. Clearing data alone is insufficient because validity is what authorizes an output transaction.

## Run from any directory

Only Python's standard library, Icarus Verilog (`iverilog`), and `vvp` are required. The runner resolves every path relative to its own file, so the current directory does not matter.

```sh
python3 /absolute/path/to/reset-recovery-verification/tools/run.py
```

For this checkout:

```sh
python3 /Users/avishas/developer/rivoryxa-examples/reset-recovery-verification/tools/run.py
```

The default matrix runs three real parameter configurations, three seeds, and both the correct and mutant variants. A successful runner invocation means all correct simulations emitted `TEST_PASS: reset recovery verified` with exit status zero, while every mutant emitted `RESET_FLUSH_CHECK_FAILED:` with a nonzero status. A crash or arbitrary nonzero mutant exit does not count as expected failure. Runner regressions cover missing tools, simulation timeout, and unexpected failure markers:

```sh
python3 /absolute/path/to/reset-recovery-verification/tools/test_runner.py
```

Useful options:

```sh
python3 tools/run.py --seeds 5,9 --timeout 15
python3 tools/run.py --skip-mutant
```

## Evidence

Each invocation creates a unique UTC timestamp and random-suffix directory under `runs/`. Previous run directories are never deleted or overwritten. It contains compile logs, simulation logs, compiled images, and `summary.json`. The summary records seeds, configurations, source SHA-256 hashes, tool versions, platform, timeout, timings, exact markers, return codes, and the verdict for every case. `runs/LATEST` names the newest directory. Generated evidence is ignored by Git; CI uploads it as an artifact even when verification fails.

The testbench covers reset with multiple requests pending, ghost-response rejection, immediate post-reset recovery, exact pipeline latency, response order and data, repeated resets, and seeded mixed traffic. The deterministic pending-reset sequence guarantees that the mutant is exercised independently of random traffic.

## Limits

This is simulation evidence for one synchronous, single-clock, always-ready pipeline. It does not prove asynchronous reset release, clock-domain crossing behavior, output backpressure, formal completeness, or silicon timing. The teaching mutant is a parameter in the same module so the correct and defective variants share the exact test and build path; production code should keep it at its default value of zero or remove the parameter.

## Layout

- `rtl/response_pipeline.sv` — synthesizable DUT and explicit reset behavior
- `tb/tb_reset_recovery.sv` — self-checking testbench
- `tools/run.py` — portable matrix runner and evidence writer
- `.github/workflows/verify.yml` — CI run and artifact upload

Contributions are welcome under [CONTRIBUTING.md](CONTRIBUTING.md). The project is licensed under the MIT License.

## Recorded result

[Review log and measured results](recorded/2026-09-15/README.md): 9 correct configurations pass and 9 seeded failures are detected. Raw logs, source hashes, timings, and the default RTL synthesis check are included. These are finite educational examples, not client results.
