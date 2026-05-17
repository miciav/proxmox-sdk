# proxmox-sdk Quality Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all code quality issues, add CI/CD, enforce type safety and coverage without breaking the public API.

**Architecture:** All changes are isolated to specific files — no architectural restructuring. Each task targets one area: dependencies, linting, code quality, CI, PEP 561 marker.

**Tech Stack:** Python 3.11+, uv, pytest, ruff, mypy, GitHub Actions

---

### Task 1: Fix pyproject.toml — Dependencies & Coverage

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add paramiko dependency and coverage config**

```toml
[project]
name = "proxmox-sdk"
version = "0.1.0"
description = "Pythonic SDK for Proxmox VE VM management"
readme = "README.md"
authors = [
    { name = "miciav", email = "5889596+miciav@users.noreply.github.com" }
]
requires-python = ">=3.11"
dependencies = [
    "paramiko>=3.0",
    "proxmoxer>=2.0.1",
    "requests>=2.31",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-cov",
    "mypy",
    "ruff",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/proxmox_sdk"]

[tool.ruff]
line-length = 88

[tool.mypy]
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.coverage.report]
fail_under = 80

[dependency-groups]
dev = [
    "pytest>=9.0.2",
    "pytest-cov>=7.1.0",
    "ruff>=0.15.9",
]
```

- [ ] **Step 2: Install dependencies and verify**

```bash
uv sync
```

Expected: `paramiko` installed, no errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add paramiko dependency and coverage threshold"
```

---

### Task 2: Fix ruff warnings

**Files:**
- Modify: `src/proxmox_sdk/routing.py:33`
- Modify: `tests/test_routing.py:154`

- [ ] **Step 1: Remove unused `field` import in routing.py**

Change line 33:
```python
# Before
from dataclasses import dataclass, field

# After
from dataclasses import dataclass
```

- [ ] **Step 2: Rename unused variable in test_routing.py**

Change line 154:
```python
# Before
first = mgr.add_rules(list(SAMPLE_MAPPINGS))

# After
_first = mgr.add_rules(list(SAMPLE_MAPPINGS))
```

- [ ] **Step 3: Verify ruff passes**

```bash
uv run ruff check src/ tests/
```
Expected: "All checks passed!"

- [ ] **Step 4: Commit**

```bash
git add src/proxmox_sdk/routing.py tests/test_routing.py
git commit -m "style: fix ruff warnings (unused import, unused variable)"
```

---

### Task 3: Use urlparse in _utils.py

**Files:**
- Modify: `src/proxmox_sdk/_utils.py`

- [ ] **Step 1: Replace string manipulation with urlparse**

```python
from __future__ import annotations

from urllib.parse import urlparse


def parse_proxmox_url(api_url: str) -> tuple[str, int]:
    """
    Extract host and port from a Proxmox API URL.

    Handles forms like:
      https://192.168.1.100:8006/api2/json
      http://proxmox-host:8006
      proxmox-host

    Returns (host, port).
    """
    if "://" not in api_url:
        api_url = f"https://{api_url}"
    parsed = urlparse(api_url)
    return parsed.hostname or "localhost", parsed.port or 8006
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
uv run pytest tests/test_client.py::test_from_url_parses_host_and_port -v
```
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/proxmox_sdk/_utils.py
git commit -m "refactor: use urlparse in parse_proxmox_url"
```

---

### Task 4: Improve ProxmoxVM.exec() with configurable timeout and backoff

**Files:**
- Modify: `src/proxmox_sdk/vm.py:180-201`

- [ ] **Step 1: Replace exec() method**

```python
    def exec(self, command: list[str], *, timeout: float = 30.0) -> CommandResult:
        """Run a command inside the VM via QEMU guest agent."""
        from proxmox_sdk.exceptions import ProxmoxAPIError

        result = self._backend.post(
            f"nodes/{self.node}/qemu/{self.vm_id}/agent/exec",
            command=command,
        )
        pid = result.get("pid", 0)
        deadline = time.monotonic() + timeout
        interval = 0.5
        while time.monotonic() < deadline:
            status = self._backend.get(
                f"nodes/{self.node}/qemu/{self.vm_id}/agent/exec-status",
                pid=pid,
            )
            if status.get("exited"):
                return CommandResult(
                    exit_code=int(status.get("exitcode", 1)),
                    stdout=status.get("out-data", ""),
                    stderr=status.get("err-data", ""),
                )
            if "error" in status:
                raise ProxmoxAPIError(
                    status_code=500,
                    message=str(status.get("error", "guest agent error")),
                    path=f"nodes/{self.node}/qemu/{self.vm_id}/agent/exec-status",
                )
            time.sleep(interval)
            interval = min(interval * 1.5, 2.0)
        raise ProxmoxTimeoutError(self.vm_id, "exec", timeout)
```

- [ ] **Step 2: Verify existing tests pass**

```bash
uv run pytest tests/ -v
```
Expected: all 83 tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/proxmox_sdk/vm.py
git commit -m "fix: add configurable timeout and error handling to VM exec()"
```

---

### Task 5: Fix ParamikoSshBackend ImportError message

**Files:**
- Modify: `src/proxmox_sdk/backends/ssh.py:46-49`

- [ ] **Step 1: Update ImportError message**

```python
        except ImportError as exc:
            raise ImportError(
                "paramiko is required for SSH operations. "
                "Install it with: pip install paramiko"
            ) from exc
```

- [ ] **Step 2: Commit**

```bash
git add src/proxmox_sdk/backends/ssh.py
git commit -m "fix: update paramiko ImportError message"
```

---

### Task 6: Add PEP 561 py.typed marker

**Files:**
- Create: `src/proxmox_sdk/py.typed`

- [ ] **Step 1: Create empty py.typed file**

```bash
touch src/proxmox_sdk/py.typed
```

- [ ] **Step 2: Commit**

```bash
git add src/proxmox_sdk/py.typed
git commit -m "feat: add PEP 561 py.typed marker"
```

---

### Task 7: Add GitHub Actions CI pipeline

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create CI workflow**

```yaml
name: CI

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run ruff check src/ tests/
      - run: uv run mypy src/

  test:
    needs: lint
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: uv sync
      - run: uv run pytest --cov=src --cov-report=term --cov-fail-under=80
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions workflow (ruff, mypy, pytest matrix)"
```

---

### Task 8: Add CI badge to README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add badge at top of README**

Insert after the `# proxmox-sdk` title line:

```markdown
[![CI](https://github.com/miciav/proxmox-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/miciav/proxmox-sdk/actions/workflows/ci.yml)
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add CI badge to README"
```

---

### Task 9: Install mypy and fix any type errors

**Files:**
- Potentially any source file with type errors

- [ ] **Step 1: Install mypy**

```bash
uv sync --group dev
```

- [ ] **Step 2: Run mypy strict check**

```bash
uv run mypy src/
```

Expected: no errors. If errors found, fix them in the affected files.

- [ ] **Step 3: Commit if fixes were needed**

```bash
git add <fixed files>
git commit -m "fix: resolve mypy strict mode type errors"
```
