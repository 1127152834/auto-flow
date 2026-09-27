"""Read-only strict debt gate. Baseline changes require a reviewed file diff."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "strict-type-baseline.json"
ERROR = re.compile(r"^(.+?):(\d+)(?::\d+)?: error: (.+?)  \[([^]]+)\]$")


def diagnostics(output: str, root: Path) -> Counter[str]:
    trees: dict[str, ast.Module] = {}
    found: Counter[str] = Counter()
    for line in output.splitlines():
        if ": error:" not in line:
            continue
        match = ERROR.fullmatch(line)
        if match is None:
            raise ValueError(f"Unrecognized mypy error: {line}")
        path, row, message, code = match.groups()
        path = path.replace("\\", "/")
        if path not in trees:
            trees[path] = ast.parse((root / path).read_text(encoding="utf-8-sig"))
        symbols: list[tuple[int, str]] = []
        for node in ast.walk(trees[path]):
            if (
                isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
                and node.lineno <= int(row) <= (node.end_lineno or node.lineno)
            ):
                symbols.append((node.lineno, node.name))
        symbol = ".".join(name for _, name in sorted(symbols)) or "<module>"
        # Exact message and multiplicity prevent an unrelated error offsetting
        # a fixed one; symbol identity survives whitespace and import changes.
        found[json.dumps([path, symbol, code, message], ensure_ascii=False)] += 1
    return found


def main() -> int:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", "--platform", baseline["platform"],
         "--show-error-codes", "--no-pretty", "--no-error-summary", "src"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode not in {0, 1} or result.stderr:
        print(result.stdout + result.stderr)
        return 1
    current = diagnostics(result.stdout, ROOT)
    if result.returncode == 1 and not current:
        print("mypy failed without recognized diagnostics")
        return 1
    allowed: Counter[str] = Counter(baseline["diagnostics"])
    additions = current - allowed
    for identity, count in sorted(additions.items()):
        print(f"NEW strict error x{count}: {identity}")
    print(f"strict debt: {current.total()}; baseline: {allowed.total()}; new: {additions.total()}")
    resolved = allowed - current
    if resolved:
        print(f"Remove {resolved.total()} resolved errors from the reviewed baseline before merging.")
    return int(bool(additions or resolved))


if __name__ == "__main__":
    raise SystemExit(main())
