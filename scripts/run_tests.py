"""
Test runner script for Medical Invoice Parser.

Usage:
    # Run all tests (except API tests which require server)
    uv run python scripts/run_tests.py

    # Run all tests including API tests (requires server running)
    uv run python scripts/run_tests.py --all

    # Run specific test categories
    uv run python scripts/run_tests.py --parser
    uv run python scripts/run_tests.py --inference
    uv run python scripts/run_tests.py --stress

    # Run with verbose output
    uv run python scripts/run_tests.py -v

    # Run with pytest directly
    uv run pytest tests/ -v
"""

import subprocess
import sys
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run Medical Invoice Parser tests")
    parser.add_argument("--all", action="store_true", help="Run all tests including API tests")
    parser.add_argument("--parser", action="store_true", help="Run parser tests only")
    parser.add_argument("--inference", action="store_true", help="Run inference tests only")
    parser.add_argument("--stress", action="store_true", help="Run stress tests only")
    parser.add_argument("--api", action="store_true", help="Run API tests only (requires server)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-x", "--exitfirst", action="store_true", help="Exit on first failure")

    args = parser.parse_args()

    # Build pytest command
    cmd = ["uv", "run", "pytest"]

    # Determine which tests to run
    test_files = []
    if args.parser:
        test_files.append("tests/test_parser.py")
    elif args.inference:
        test_files.append("tests/test_inference.py")
    elif args.stress:
        test_files.append("tests/test_stress.py")
    elif args.api:
        test_files.append("tests/test_api.py")
    elif args.all:
        test_files.append("tests/")
    else:
        # Default: run all except API tests
        test_files.extend([
            "tests/test_parser.py",
            "tests/test_inference.py",
            "tests/test_stress.py"
        ])

    cmd.extend(test_files)

    # Add options
    if args.verbose:
        cmd.append("-v")
    if args.exitfirst:
        cmd.append("-x")

    # Add nice output
    cmd.extend(["--tb=short", "-q"])

    # Show what we're running
    print("=" * 60)
    print("Medical Invoice Parser - Test Suite")
    print("=" * 60)
    print(f"\nRunning: {' '.join(cmd)}\n")

    # Run tests
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
