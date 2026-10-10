"""Run with python -m unittest backend.scripts.test_ai_benchmark_tools -v."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.scripts import ai_synthetic_benchmark as smoke
from backend.scripts.ai_cached_guard_benchmark import compare_existing


class SyntheticBenchmarkTests(unittest.TestCase):
    def test_default_fixture_checks_never_call_ocr_or_network(self):
        original = os.environ.get("APP_LLM_ENABLED")
        with patch("requests.sessions.Session.request", side_effect=AssertionError("network not allowed")), \
                patch("backend.app.ai.preprocessor.run_ocr_on_image", side_effect=AssertionError("OCR not allowed")):
            report = smoke.run_benchmark(repeat=2, warmup=1)
        self.assertEqual(report["summary"], {"case_count": 24, "passed": 24, "failed": 0, "result": "passed"})
        self.assertEqual(report["stages"]["real_llm"]["status"], "not_run")
        self.assertEqual(report["stages"]["real_ocr"]["status"], "not_run")
        self.assertTrue(report["source_unchanged_during_run"])
        self.assertEqual(os.environ.get("APP_LLM_ENABLED"), original)
        self.assertTrue(all(case["seconds"]["sample_count"] == 2 for case in report["cases"]))

    def test_warmup_failure_cannot_be_discarded(self):
        with patch.object(smoke, "perf_counter", return_value=0):
            callback = iter([(0.01, {"passed": False}), (0.01, {"passed": True})])
            report = smoke._measure("fake", "fake", lambda: next(callback), repeat=1, warmup=1)
        self.assertFalse(report["passed"])
        self.assertEqual(report["seconds"]["sample_count"], 1)

    def test_exceptions_are_failures_without_successful_latency_samples(self):
        def fail():
            raise RuntimeError("must not be counted as a pass")
        report = smoke._measure("fake", "fake", fail, repeat=1, warmup=0)
        self.assertFalse(report["passed"])
        self.assertEqual(report["seconds"]["sample_count"], 0)
        self.assertIsNone(report["seconds"]["mean"])

    def test_outputs_are_new_and_cannot_overwrite_frozen_or_customer_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            smoke.write_result(path, {"example": True})
            with self.assertRaises(FileExistsError):
                smoke.write_result(path, {"example": False})
            self.assertEqual(json.loads(path.read_text()), {"example": True})
        for root in ("eval", "docs/eval", "storage"):
            with self.assertRaises(ValueError):
                smoke.write_result(smoke.PROJECT / root / "never-created.json", {})

    def test_invalid_repeat_returns_setup_error(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(smoke.main(["--repeat", "0"]), 2)

    def test_percentile_definition(self):
        self.assertEqual(smoke.timing_summary([1, 2, 3, 4])["p95"], 4)
        self.assertEqual(smoke.timing_summary([1, 2, 3, 4])["p50"], 2.5)


class FrozenMetricComparisonTests(unittest.TestCase):
    def test_new_diagnostics_do_not_change_old_metric_reproduction(self):
        expected = {"rule": {"accuracy": .5, "counts": [1, 2]}}
        actual = {"rule": {"accuracy": .5, "counts": [1, 2], "new_diagnostic": 0}}
        self.assertEqual(compare_existing(expected, actual), [])

    def test_changed_or_missing_metric_is_reported(self):
        self.assertEqual(compare_existing({"rule": {"accuracy": .5}}, {"rule": {"accuracy": 1}}),
                         ["rule.accuracy"])
        self.assertEqual(compare_existing({"rule": {"accuracy": .5}}, {"rule": {}}), ["rule.accuracy"])


if __name__ == "__main__":
    unittest.main()
