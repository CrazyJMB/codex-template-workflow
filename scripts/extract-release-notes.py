#!/usr/bin/env python3
"""Extract one Keep a Changelog release section as GitHub release notes."""

import re
import sys
from datetime import date
from pathlib import Path


def extract(changelog: str, tag: str) -> str:
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("Expected release tag vX.Y.Z")
    version = tag.removeprefix("v")
    pattern = rf"(?m)^## \[{re.escape(version)}\] - (\d{{4}}-\d{{2}}-\d{{2}})\s*$"
    match = re.search(pattern, changelog)
    if match is None:
        raise ValueError(f"Missing CHANGELOG.md section for {version}")
    date.fromisoformat(match.group(1))
    following = re.search(r"(?m)^## \[", changelog[match.end():])
    end = match.end() + following.start() if following else len(changelog)
    body = changelog[match.end():end].strip()
    content = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
    content = re.sub(r"(?m)^\s*(?:#+\s.*|\[[^\]]+\]:.*)$", "", content).strip()
    if not content:
        raise ValueError(f"Empty release notes for {version}")
    return f"# {tag} ({match.group(1)})\n\n{body}\n"


if __name__ == "__main__":
    if len(sys.argv) != 2 or not re.fullmatch(r"v\d+\.\d+\.\d+", sys.argv[1]):
        raise SystemExit("Usage: extract-release-notes.py vX.Y.Z")
    try:
        print(extract(Path("CHANGELOG.md").read_text(encoding="utf-8"), sys.argv[1]), end="")
    except (ValueError, FileNotFoundError) as error:
        raise SystemExit(str(error)) from error
