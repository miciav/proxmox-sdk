from __future__ import annotations

import ast
import argparse
from dataclasses import dataclass
from pathlib import Path

ROOT_PACKAGE = "proxmox_sdk"


@dataclass
class Smell:
    category: str
    severity: str
    file: str
    line: int
    message: str


def _check_ast() -> list[Smell]:
    smells: list[Smell] = []
    root = Path(f"src/{ROOT_PACKAGE}")

    for py_file in sorted(root.rglob("*.py")):
        if "devtools" in str(py_file) and py_file.name != "__init__.py":
            continue
        source = py_file.read_text()
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if handler.type is None:
                        smells.append(Smell(
                            "bug", "high", str(py_file), handler.lineno,
                            "Bare except: — catches KeyboardInterrupt and SystemExit",
                        ))

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type and ast.unparse(node.type) in ("Exception", "BaseException"):
                    smells.append(Smell(
                        "bug", "medium", str(py_file), node.lineno,
                        f"Broad except clause catches {ast.unparse(node.type)}",
                    ))

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults + node.args.kw_defaults:
                    if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        smells.append(Smell(
                            "bug", "high", str(py_file), default.lineno,
                            f"Mutable default argument in `{node.name}()`",
                        ))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end = node.end_lineno or node.lineno
                loc = end - node.lineno + 1
                if loc > 30:
                    smells.append(Smell(
                        "simplification", "medium", str(py_file), node.lineno,
                        f"Function `{node.name}()` is {loc} lines (max: 30)",
                    ))

    return smells


def format_report(smells: list[Smell]) -> str:
    if not smells:
        return "No issues found."

    by_category: dict[str, list[Smell]] = {}
    for s in smells:
        by_category.setdefault(s.category, []).append(s)

    category_names = {
        "bug": "1. Possible Bugs",
        "simplification": "2. Simplification Opportunities",
    }

    lines: list[str] = []
    for cat_key in ("bug", "simplification"):
        items = by_category.get(cat_key, [])
        lines.append(category_names[cat_key])
        lines.append("-" * len(category_names[cat_key]))
        if not items:
            lines.append("  (none)\n")
            continue
        for item in sorted(
            items, key=lambda s: {"high": 0, "medium": 1, "low": 2}[s.severity]
        ):
            lines.append(
                f"  [{item.severity.upper()}] {item.file}:{item.line} — {item.message}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate code quality: bugs, simplifications, smells."
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    all_smells = _check_ast()

    if args.json:
        import json
        items = [
            {"category": s.category, "severity": s.severity,
             "file": s.file, "line": s.line, "message": s.message}
            for s in all_smells
        ]
        print(json.dumps(items, indent=2))
    else:
        print(format_report(all_smells))


if __name__ == "__main__":
    main()
