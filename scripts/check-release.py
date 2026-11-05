#!/usr/bin/env python3
"""Validate release metadata and notes without building, tagging, or publishing."""

import argparse
import re
import runpy
from pathlib import Path


def release_tag(changelog: str) -> str:
    match = re.search(r"(?m)^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}\s*$", changelog)
    if match is None:
        raise ValueError("Missing dated release section in CHANGELOG.md")
    return f"v{match.group(1)}"


def check(tag: str | None = None) -> str:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    tag = tag or release_tag(changelog)
    scripts = Path(__file__).resolve().parent
    runpy.run_path(str(scripts / "verify-version.py"))["main"](tag)
    runpy.run_path(str(scripts / "extract-release-notes.py"))["extract"](changelog, tag)
    print(f"Release preflight passed for {tag}; nothing was published.")
    return tag


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("tag", nargs="?", help="Release tag vX.Y.Z")
    choice.add_argument("--from-changelog", action="store_true", help="Use the first dated release section")
    args = parser.parse_args()
    try:
        check(args.tag)
    except (ValueError, FileNotFoundError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
