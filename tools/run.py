#!/usr/bin/env python3
"""Compile and run the reset-recovery evidence matrix with only stdlib Python."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PASS_MARKER = "TEST_PASS: reset recovery verified"
MUTANT_MARKER = "RESET_FLUSH_CHECK_FAILED:"
FAIL_MARKER = "TEST_FAIL:"
CONFIGS = [
    {"name": "short_narrow", "data_width": 8, "stages": 2, "bias": 3},
    {"name": "default", "data_width": 8, "stages": 3, "bias": 7},
    {"name": "deep_wide", "data_width": 16, "stages": 5, "bias": 257},
]


def command_version(command):
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=5, check=False)
    return result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unknown"


def missing_tools(which=shutil.which):
    return [tool for tool in ("iverilog", "vvp") if which(tool) is None]


def classify_simulation(mutant, returncode, timed_out, output):
    if timed_out:
        return False
    if mutant:
        return (returncode != 0 and MUTANT_MARKER in output and FAIL_MARKER in output
                and PASS_MARKER not in output)
    return returncode == 0 and PASS_MARKER in output and MUTANT_MARKER not in output


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def execute(command, log_path, timeout):
    started = time.monotonic()
    try:
        process = subprocess.Popen(command, cwd=str(ROOT), text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=(os.name == "posix"))
        try:
            output, _ = process.communicate(timeout=timeout)
            returncode, timed_out = process.returncode, False
        except subprocess.TimeoutExpired as exc:
            if os.name == "posix":
                os.killpg(process.pid, 9)
            else:
                process.kill()
            remainder, _ = process.communicate()
            partial = exc.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            output = partial
            if remainder and remainder not in output:
                output += remainder
            output += "\nRUNNER_TIMEOUT\n"
            returncode, timed_out = 124, True
    except OSError as exc:
        output = "RUNNER_EXEC_ERROR: " + str(exc) + "\n"
        returncode, timed_out = 127, False
    log_path.write_text(output, encoding="utf-8")
    return {"command": command, "returncode": returncode, "timed_out": timed_out,
            "duration_seconds": round(time.monotonic() - started, 6), "output": output}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", default="1,17,2026", help="comma-separated integer seeds")
    parser.add_argument("--timeout", type=float, default=10.0, help="seconds per compile or simulation")
    parser.add_argument("--skip-mutant", action="store_true", help="run only the correct implementation")
    args = parser.parse_args()
    seeds = [int(item.strip(), 0) for item in args.seeds.split(",") if item.strip()]
    if not seeds:
        parser.error("at least one seed is required")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be a positive finite number")
    unavailable = missing_tools()
    if unavailable:
        print("ERROR: required tool(s) missing from PATH: " + ", ".join(unavailable), file=sys.stderr)
        return 2

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = ROOT / "runs" / (stamp + "-" + uuid.uuid4().hex[:8])
    run_dir.mkdir(parents=True)
    results = []
    overall = True

    for config in CONFIGS:
        for mutant in ([False] if args.skip_mutant else [False, True]):
            variant = "mutant" if mutant else "correct"
            image = run_dir / (config["name"] + "-" + variant + ".vvp")
            compile_log = run_dir / (config["name"] + "-" + variant + "-compile.log")
            compile_cmd = ["iverilog", "-g2012", "-s", "tb_reset_recovery",
                           "-D", "DATA_WIDTH=" + str(config["data_width"]),
                           "-D", "STAGES=" + str(config["stages"]),
                           "-D", "BIAS=" + str(config["bias"]),
                           "-D", "MUTANT=" + ("1" if mutant else "0"),
                           "-o", str(image), str(ROOT / "rtl/response_pipeline.sv"),
                           str(ROOT / "tb/tb_reset_recovery.sv")]
            compiled = execute(compile_cmd, compile_log, args.timeout)
            compile_ok = compiled["returncode"] == 0 and not compiled["timed_out"]
            for seed in seeds:
                simulation = {"returncode": None, "timed_out": False,
                              "duration_seconds": 0.0, "output": "compile failed"}
                sim_log = run_dir / (config["name"] + "-" + variant + "-seed" + str(seed) + ".log")
                if compile_ok:
                    simulation = execute(["vvp", str(image), "+SEED=" + str(seed)], sim_log, args.timeout)
                else:
                    sim_log.write_text("simulation skipped: compile failed\n", encoding="utf-8")
                expected = classify_simulation(mutant, simulation["returncode"],
                                               simulation["timed_out"], simulation["output"])
                passed = compile_ok and expected
                overall = overall and passed
                results.append({"config": config, "variant": variant, "seed": seed,
                                "compile_command": compiled["command"],
                                "compile_returncode": compiled["returncode"],
                                "compile_seconds": compiled["duration_seconds"],
                                "simulation_returncode": simulation["returncode"],
                                "simulation_command": simulation.get("command"),
                                "simulation_seconds": simulation["duration_seconds"],
                                "timed_out": simulation["timed_out"],
                                "expected_marker": MUTANT_MARKER if mutant else PASS_MARKER,
                                "expected_outcome_observed": passed,
                                "log": sim_log.name})
                print(("PASS" if passed else "FAIL") + ": " + config["name"] +
                      " " + variant + " seed=" + str(seed))

    summary = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "started_utc": stamp,
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "repository": str(ROOT),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "iverilog_version": command_version(["iverilog", "-V"]),
        "vvp_version": command_version(["vvp", "-V"]),
        "timeout_seconds": args.timeout,
        "seeds": seeds,
        "configs": CONFIGS,
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path)
            for path in (ROOT / "rtl/response_pipeline.sv",
                         ROOT / "tb/tb_reset_recovery.sv", ROOT / "tools/run.py")
        },
        "pass_marker": PASS_MARKER,
        "mutant_failure_marker": MUTANT_MARKER,
        "test_failure_marker": FAIL_MARKER,
        "overall_pass": overall,
        "results": results,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    latest = ROOT / "runs" / "LATEST"
    latest.write_text(run_dir.name + "\n", encoding="utf-8")
    print("SUMMARY: " + ("PASS" if overall else "FAIL"))
    print("EVIDENCE: " + str(run_dir / "summary.json"))
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
