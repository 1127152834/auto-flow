"""Run the backend suite one test file at a time with a hard per-file budget.

Why this exists: a single `pytest` invocation that hangs on one runner shows no
result for hours, and CI log storage is not always reachable by the people
triaging it. Per-file processes turn "the job never ended" into a list of
files that failed, timed out or were slow, written to annotations and the job
summary. It is a diagnostic runner; it does not replace the normal command.

Usage: python scripts/ci_pytest_by_file.py [--timeout SECONDS] [--root TESTS_DIR]
                                           [--pytest-arg ARG ...]
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# pytest exit code 5 means "no tests collected" (e.g. everything deselected by
# the default marker expression); that is not a failure of the file.
OK_CODES = {0, 5}
PER_FILE_LIMIT = 3_000  # GitHub shows about 4 KB of an annotation message


@dataclass(frozen=True)
class FileResult:
    path: str
    status: str  # passed | failed | timeout
    seconds: float
    code: int | None
    detail: str = ""


def _escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def discover(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(
        path for path in root.rglob("test_*.py") if "__pycache__" not in path.parts
    )


def collect_ids(path: Path, command: list[str]) -> list[str]:
    """Test ids in a file, so a hang can be pinned to one test instead of a file."""
    probe = subprocess.run(
        [*command, "--collect-only", "-q", str(path)],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    ids = [line.strip() for line in probe.stdout.splitlines() if "::" in line]
    return ids or [str(path)]


def kill_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            capture_output=True,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()


def _detail(output: str, status: str) -> str:
    """Short, annotation-safe evidence: failed test ids, or the test that hung."""
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if status == "timeout":
        # With -v the last line names the test that never reported a result.
        return (lines[-1] if lines else "")[:400]
    failed = [line for line in lines if line.startswith(("FAILED ", "ERROR "))]
    return " | ".join(failed[:5] or lines[-2:])[:600]


def run_file(
    path: Path | str, timeout: float, command: list[str], clock=time.monotonic
) -> FileResult:
    started = clock()
    kwargs: dict = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True
    with tempfile.TemporaryFile() as capture:
        process = subprocess.Popen(
            [*command, str(path)], stdout=capture, stderr=subprocess.STDOUT, **kwargs
        )
        try:
            code = process.wait(timeout=timeout)
            status = "passed" if code in OK_CODES else "failed"
        except subprocess.TimeoutExpired:
            kill_tree(process)
            code, status = None, "timeout"
        capture.seek(0)
        output = capture.read().decode("utf-8", errors="replace")
    if status != "passed":
        print(output[-6000:], flush=True)
    return FileResult(
        str(path),
        status,
        clock() - started,
        code,
        _detail(output, status) if status != "passed" else "",
    )


def build_report(
    results: list[FileResult], *, slowest: int = 15
) -> tuple[str, list[str]]:
    problems = [r for r in results if r.status != "passed"]
    total = len(results)
    counts = {
        status: sum(r.status == status for r in results)
        for status in ("passed", "failed", "timeout")
    }
    headline = (
        f"## Per-file backend run: {total} files, {counts['passed']} passed, "
        f"{counts['failed']} failed, {counts['timeout']} timed out"
    )
    lines = [headline, ""]
    if problems:
        lines.append("### Failed or timed out")
        lines += [
            f"- `{r.path}` {r.status}"
            + (f" (exit {r.code})" if r.code is not None else "")
            + f" after {r.seconds:.0f}s"
            + (f": {r.detail}" if r.detail else "")
            for r in problems
        ]
        lines.append("")
    lines.append(f"### Slowest {slowest} files")
    for r in sorted(results, key=lambda item: item.seconds, reverse=True)[:slowest]:
        lines.append(f"- `{r.path}` {r.seconds:.0f}s ({r.status})")
    annotations = []
    for r in problems[:10]:
        text = f"{r.status}{'' if r.code is None else f' (exit {r.code})'} after {r.seconds:.0f}s"
        text += f": {r.detail}" if r.detail else ""
        annotations.append(
            f"::error title={r.status} {r.path}::" + _escape(text[:PER_FILE_LIMIT])
        )
    if len(problems) > 10:
        listed = "; ".join(r.path for r in problems[10:])
        annotations.append(
            f"::error title={len(problems) - 10} more problem files::"
            + _escape(listed[:PER_FILE_LIMIT])
        )
    slow = "; ".join(
        f"{r.path}:{r.seconds:.0f}s"
        for r in sorted(results, key=lambda item: item.seconds, reverse=True)[:slowest]
    )
    annotations.append(f"::notice title=slowest backend files::{slow[:PER_FILE_LIMIT]}")
    return "\n".join(lines), annotations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--root", type=Path, default=Path("tests"))
    parser.add_argument("--pytest-arg", action="append", default=[])
    parser.add_argument(
        "--per-test",
        action="store_true",
        help="run every collected test id in its own process (slower, pins a hang to one test)",
    )
    args = parser.parse_args(argv)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-v",
        "-rfE",
        "-p",
        "no:cacheprovider",
        *args.pytest_arg,
    ]
    files: list = discover(args.root)
    if args.per_test:
        files = [item for path in files for item in collect_ids(path, command)]
    results: list[FileResult] = []
    for path in files:
        result = run_file(path, args.timeout, command)
        results.append(result)
        print(
            f"[{len(results)}/{len(files)}] {result.status:7} {result.seconds:7.1f}s {result.path}",
            flush=True,
        )
    text, annotations = build_report(results)
    print(text)
    for annotation in annotations:
        print(annotation)
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        with open(destination, "a", encoding="utf-8") as output:
            output.write(text + "\n")
    return 1 if any(r.status != "passed" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
