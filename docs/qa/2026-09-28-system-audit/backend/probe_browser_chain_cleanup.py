"""Diagnostic variant only; leave the original QA script and business code unchanged."""

from pathlib import Path

source = Path(__file__).resolve().parents[4] / "scripts/qa-pm5-browser-chain.py"
original = source.read_text()
before = "    finally:\n        site.close()\n"
after = (
    "    finally:\n"
    "        if client is not None:\n"
    "            client.__exit__(None, None, None)\n"
    "        site.close()\n"
)
assert original.count(before) == 1
exec(compile(original.replace(before, after), str(source), "exec"),
     {"__file__": str(source), "__name__": "__main__"})
