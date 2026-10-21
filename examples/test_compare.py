"""Independent negative controls for the article's offline evaluator."""
import copy
import runpy
import unittest
from pathlib import Path

api = runpy.run_path(str(Path(__file__).with_name("compare.py")))
load, compare, gate = api["load"], api["compare"], api["release_gate"]


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.dataset = load("golden.json")
        self.baseline = load("baseline.json")
        self.candidate = load("candidate.json")

    def test_same_pass_rate_still_blocks(self):
        rows = compare(self.dataset, self.baseline, self.candidate)
        self.assertEqual(sum(r["baseline"] == "PASS" for r in rows), 5)
        self.assertEqual(sum(r["candidate"] == "PASS" for r in rows), 5)
        self.assertEqual(gate(rows)[0], "BLOCK")
        critical = next(r for r in rows if r["id"] == "cross_tenant_access")
        self.assertEqual(critical["change"], "regressed")

    def test_missing_observation_requires_review(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["model"] = "missing-candidate"
        del candidate["answers"]["cross_tenant_access"]
        rows = compare(self.dataset, self.baseline, candidate)
        self.assertEqual(next(r["change"] for r in rows if r["id"] == "cross_tenant_access"),
                         "undetermined")
        self.assertEqual(gate(rows)[0], "REVIEW")

    def test_tool_policy_negative_control(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["model"] = "malicious-candidate"
        candidate["answers"]["cross_tenant_access"]["executed_tools"] = [
            {"name": "get_ticket", "arguments": {"tenant_id": "beta"}}
        ]
        rows = compare(self.dataset, self.baseline, candidate)
        self.assertEqual(gate(rows)[0], "BLOCK")

    def test_existing_critical_failure_still_blocks(self):
        baseline = copy.deepcopy(self.candidate)
        rows = compare(self.dataset, baseline, self.candidate)
        self.assertEqual(
            next(r["change"] for r in rows if r["id"] == "cross_tenant_access"),
            "unchanged",
        )
        self.assertEqual(gate(rows)[0], "BLOCK")

    def test_existing_noncritical_failure_requires_review(self):
        candidate = copy.deepcopy(self.baseline)
        rows = compare(self.dataset, self.baseline, candidate)
        self.assertEqual(gate(rows)[0], "REVIEW")

    def test_clean_candidate_releases(self):
        candidate = copy.deepcopy(self.baseline)
        candidate["answers"]["renewal_ambiguity"] = copy.deepcopy(
            self.candidate["answers"]["renewal_ambiguity"]
        )
        rows = compare(self.dataset, self.baseline, candidate)
        self.assertEqual(gate(rows)[0], "RELEASE")

    def test_configuration_drift_rejected(self):
        candidate = copy.deepcopy(self.candidate)
        candidate["prompt_version"] = "changed"
        with self.assertRaisesRegex(ValueError, "Configuration drift"):
            compare(self.dataset, self.baseline, candidate)

    def test_empty_dataset_rejected(self):
        dataset = copy.deepcopy(self.dataset)
        dataset["cases"] = []
        with self.assertRaisesRegex(ValueError, "Golden dataset has no cases"):
            compare(dataset, self.baseline, self.candidate)


if __name__ == "__main__":
    unittest.main()
