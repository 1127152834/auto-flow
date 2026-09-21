#!/usr/bin/env python3
"""Guarded Android management smoke entry point.

The command intentionally stops before mutation until a real device and provider
adapter are available; it never treats a missing runtime as a passing result.
"""

import argparse
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the guarded Android management smoke test")
    parser.add_argument("--workspace", required=True, type=Path, help="isolated workspace for generated resources")
    parser.add_argument("--allow-device-mutation", action="store_true", help="explicitly authorize device mutation")
    parser.add_argument("--device-id", action="append", default=[], help="device created by this smoke run")
    args = parser.parse_args(argv)
    if not args.allow_device_mutation:
        parser.error("--allow-device-mutation is required before any device mutation")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"blocked: real macOS Android runtime validation is unavailable for {args.workspace}", file=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
