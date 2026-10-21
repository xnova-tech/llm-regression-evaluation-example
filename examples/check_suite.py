"""Run the unittest controls with stable stdout for the publication verifier."""
import runpy
import unittest
from pathlib import Path

test_namespace = runpy.run_path(str(Path(__file__).with_name("test_compare.py")))
suite = unittest.defaultTestLoader.loadTestsFromTestCase(test_namespace["ComparisonTests"])
result = unittest.TestResult()
suite.run(result)
if not result.wasSuccessful() or result.testsRun != 8:
    raise SystemExit(f"failed: {result.failures}, errors: {result.errors}")
print("8 tests passed")
