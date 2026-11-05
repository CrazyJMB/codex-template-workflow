#!/usr/bin/env python3
"""Verify common project-version metadata against the requested release tag."""

import json
import re
import sys
import tomllib
from pathlib import Path


def main(tag: str) -> None:
    if not re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError("Expected release tag vX.Y.Z")
    version = tag[1:]
    versions: dict[str, str] = {}
    if Path("package.json").is_file():
        data = json.loads(Path("package.json").read_text(encoding="utf-8"))
        if data.get("version"):
            versions["package.json"] = str(data["version"])
    if Path("composer.json").is_file():
        data = json.loads(Path("composer.json").read_text(encoding="utf-8"))
        if data.get("version"):
            versions["composer.json"] = str(data["version"])
    if Path("pyproject.toml").is_file():
        data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        declared = data.get("project", {}).get("version") or data.get("tool", {}).get("poetry", {}).get("version")
        if declared:
            versions["pyproject.toml"] = str(declared)
    if Path("VERSION").is_file():
        versions["VERSION"] = Path("VERSION").read_text(encoding="utf-8").strip().removeprefix("v")

    mismatches = [f"{name}: {found}" for name, found in versions.items() if found != version]
    if mismatches:
        raise ValueError(f"Version must be {version}; mismatches: {', '.join(mismatches)}")
    print(f"Verified release version {version} across {len(versions)} version metadata files.")


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) == 2 else "")
    except (ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as error:
        raise SystemExit(str(error)) from error
