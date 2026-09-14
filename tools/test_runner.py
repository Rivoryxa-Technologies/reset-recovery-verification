#!/usr/bin/env python3
"""Regression tests for evidence classification and runner failure handling."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

MODULE_PATH = Path(__file__).with_name("run.py")
SPEC = importlib.util.spec_from_file_location("evidence_runner", str(MODULE_PATH))
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_missing_tool_is_reported(self):
        present = {"iverilog": "/bin/iverilog", "vvp": None}
        self.assertEqual(runner.missing_tools(present.get), ["vvp"])

    def test_timeout_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "timeout.log"
            result = runner.execute(
                [sys.executable, "-c", "import time; print('started', flush=True); time.sleep(1)"],
                log, 0.1)
            self.assertTrue(result["timed_out"])
            self.assertEqual(result["returncode"], 124)
            self.assertIn("started", result["output"])
            self.assertIn("RUNNER_TIMEOUT", result["output"])
            self.assertFalse(runner.classify_simulation(False, result["returncode"],
                                                        result["timed_out"], result["output"]))

    def test_arbitrary_nonzero_is_not_expected_mutant_failure(self):
        self.assertFalse(runner.classify_simulation(True, 1, False, "syntax crash"))
        self.assertFalse(runner.classify_simulation(True, 1, False, runner.PASS_MARKER))
        self.assertFalse(runner.classify_simulation(True, 1, False,
                                                    runner.MUTANT_MARKER + " ghost"))
        self.assertTrue(runner.classify_simulation(
            True, 1, False, runner.MUTANT_MARKER + " ghost\n" + runner.FAIL_MARKER))

    def test_exec_error_is_structured(self):
        with tempfile.TemporaryDirectory() as directory:
            result = runner.execute(["/definitely/missing/program"],
                                    Path(directory) / "error.log", 1)
            self.assertEqual(result["returncode"], 127)
            self.assertIn("RUNNER_EXEC_ERROR", result["output"])


if __name__ == "__main__":
    unittest.main()
