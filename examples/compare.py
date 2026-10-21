"""Offline quality comparison of two synthetic support assistant versions.

Python 3.12+; standard library only. Results are NOT measurements of live LLMs.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CONFIG_KEYS = (
    "dataset_version", "evaluator_version", "prompt_version",
    "tools_version", "documents_version", "generation",
)


def load(name: str) -> dict[str, Any]:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def validate_inputs(dataset: dict[str, Any], baseline: dict[str, Any],
                    candidate: dict[str, Any]) -> None:
    cases = dataset["cases"]
    if not cases:
        raise ValueError("Golden dataset has no cases")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case ID")
    for key in CONFIG_KEYS:
        if baseline.get(key) != candidate.get(key):
            raise ValueError(f"Configuration drift: {key}")
    for run in (baseline, candidate):
        if run.get("dataset_version") != dataset["dataset_version"]:
            raise ValueError("Dataset version mismatch")
        if run.get("evaluator_version") != dataset["evaluator_version"]:
            raise ValueError("Evaluator version mismatch")
        unknown = set(run["answers"]) - set(ids)
        if unknown:
            raise ValueError(f"Unknown case IDs: {sorted(unknown)}")


def evaluate(case: dict[str, Any], response: Any) -> tuple[str, str]:
    if response is None:
        return "UNDETERMINED", "observation missing"
    if (not isinstance(response, dict)
            or response.get("http_status") != 200
            or not isinstance(response.get("answer"), str)
            or not isinstance(response.get("answer_type"), str)
            or not isinstance(response.get("executed_tools"), list)):
        return "FAIL", "HTTP or response contract"
    check = case["check"]
    if check["kind"] == "terms":
        text = response["answer"].casefold()
        ok = all(term.casefold() in text for term in check["required"])
        return ("PASS", "required terms present") if ok else ("FAIL", "required terms missing")
    if check["kind"] == "answer_type":
        ok = response["answer_type"] == check["expected"] and not response["executed_tools"]
        return ("PASS", "expected response type") if ok else ("FAIL", "unexpected answer or tool")
    if check["kind"] == "payload":
        payload = response.get("payload")
        ok = (isinstance(payload, dict)
              and all(payload.get(k) == v for k, v in check["expected"].items()))
        return ("PASS", "required JSON fields") if ok else ("FAIL", "invalid JSON fields")
    if check["kind"] == "no_tool":
        ok = not response["executed_tools"] and response["answer_type"] == check["expected_type"]
        return ("PASS", "authorization respected") if ok else ("FAIL", "forbidden tool or missing refusal")
    return "UNDETERMINED", "unsupported evaluator"


def compare(dataset: dict[str, Any], baseline: dict[str, Any],
            candidate: dict[str, Any]) -> list[dict[str, str]]:
    validate_inputs(dataset, baseline, candidate)
    results = []
    for case in dataset["cases"]:
        case_id = case["id"]
        before, _ = evaluate(case, baseline["answers"].get(case_id))
        after, reason = evaluate(case, candidate["answers"].get(case_id))
        if "UNDETERMINED" in (before, after):
            change = "undetermined"
        elif before == "FAIL" and after == "PASS":
            change = "improved"
        elif before == "PASS" and after == "FAIL":
            change = "regressed"
        else:
            change = "unchanged"
        results.append({"id": case_id, "category": case["category"],
                        "severity": case["severity"], "baseline": before,
                        "candidate": after, "change": change, "reason": reason})
    return results


def release_gate(results: list[dict[str, str]]) -> tuple[str, str]:
    # An already failing critical requirement must not become RELEASE just
    # because both baseline and candidate fail it.
    critical = [r for r in results
                if r["severity"] == "critical" and r["candidate"] == "FAIL"]
    if critical:
        regressions = [r["id"] for r in critical if r["change"] == "regressed"]
        if regressions:
            return "BLOCK", f"critical regression: {', '.join(regressions)}"
        return "BLOCK", "critical candidate failure: " + ", ".join(r["id"] for r in critical)
    if any(r["change"] == "undetermined" for r in results):
        return "REVIEW", "some cases have no reliable evaluation"
    if any(r["candidate"] == "FAIL" for r in results):
        return "REVIEW", "candidate has noncritical failures to investigate"
    return "RELEASE", "all evaluated candidate cases passed (dataset coverage limited)"


def report(results: list[dict[str, str]]) -> str:
    lines = ["Synthetic fixtures; NOT real model measurements"]
    for r in results:
        lines.append(f"{r['id']}: {r['baseline']} -> {r['candidate']} ({r['change']})")
    for version in ("baseline", "candidate"):
        counts = Counter(r[version] for r in results)
        lines.append(f"{version}: PASS={counts['PASS']} FAIL={counts['FAIL']} UNDETERMINED={counts['UNDETERMINED']}")
    changes = Counter(r["change"] for r in results)
    lines.append("changes: " + " ".join(
        f"{key}={changes[key]}" for key in ("improved", "regressed", "unchanged", "undetermined")
    ))
    gate, reason = release_gate(results)
    lines.append(f"gate: {gate} ({reason})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ci", action="store_true",
                        help="Return 1 for BLOCK and 2 for REVIEW")
    args = parser.parse_args()
    results = compare(load("golden.json"), load("baseline.json"), load("candidate.json"))
    print(report(results))
    decision = release_gate(results)[0]
    return {"RELEASE": 0, "BLOCK": 1, "REVIEW": 2}[decision] if args.ci else 0


if __name__ == "__main__":
    raise SystemExit(main())
