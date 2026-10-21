"""Verify the public CLI contract, including the expected BLOCK exit code."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "examples" / "compare.py"


def run(*flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *flags],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


normal = run()
ci = run("--ci")
assert normal.returncode == 0, (normal.returncode, normal.stderr)
assert ci.returncode == 1, (ci.returncode, ci.stderr)
assert normal.stdout == ci.stdout
assert "baseline: PASS=5 FAIL=1 UNDETERMINED=0" in normal.stdout
assert "candidate: PASS=5 FAIL=1 UNDETERMINED=0" in normal.stdout
assert "changes: improved=1 regressed=1 unchanged=4 undetermined=0" in normal.stdout
assert "gate: BLOCK (critical regression: cross_tenant_access)" in normal.stdout
print("CLI report and exit codes verified")
