from __future__ import annotations

import subprocess
import sys

CHECKS = (
    ("ruff", ["uv", "run", "ruff", "check", "src/", "tests/"]),
    ("mypy", ["uv", "run", "mypy", "src/"]),
)


def main() -> None:
    failures: list[str] = []
    for name, command in CHECKS:
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            failures.append(name)

    if failures:
        joined = ", ".join(failures)
        raise SystemExit(f"Quality checks failed: {joined}")

    sys.stdout.write("Quality checks passed\n")
