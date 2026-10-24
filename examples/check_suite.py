"""Run the offline comparison controls through pytest."""

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest


def main() -> None:
    output = io.StringIO()
    with redirect_stdout(output), redirect_stderr(output):
        result = pytest.main(["-q", str(Path(__file__).with_name("test_compare.py"))])
    if result != pytest.ExitCode.OK or "8 passed" not in output.getvalue():
        raise SystemExit(output.getvalue() or "comparison suite failed")
    sys.stdout.write("8 tests passed\n")


if __name__ == "__main__":
    main()
