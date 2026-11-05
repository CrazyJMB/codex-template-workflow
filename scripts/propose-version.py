#!/usr/bin/env python3
"""Suggest a SemVer release from merged develop PR labels (read-only)."""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone


def gh(*args: str) -> object:
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def version_parts(tag: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag)
    if not match:
        raise ValueError(f"Not a SemVer release: {tag}")
    return tuple(map(int, match.groups()))


def next_version(previous: tuple[int, int, int], categories: set[str]) -> str:
    major, minor, patch = previous
    if "breaking" in categories:
        return f"v{major + 1}.0.0"
    if "type:feature" in categories:
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> None:
    try:
        latest = gh("release", "view", "--json", "tagName,publishedAt")
        assert isinstance(latest, dict)
        previous_tag = latest["tagName"]
        since = parse_date(latest["publishedAt"])
        previous = version_parts(previous_tag)
    except (subprocess.CalledProcessError, KeyError, ValueError):
        print("No published release detected; assuming initial version 0.0.0.", file=sys.stderr)
        previous_tag = "none"
        since = datetime.min.replace(tzinfo=timezone.utc)
        previous = (0, 0, 0)

    pull_requests = gh(
        "pr", "list", "--state", "merged", "--base", "develop", "--limit", "500",
        "--json", "number,title,labels,mergedAt",
    )
    assert isinstance(pull_requests, list)
    selected = sorted(
        (pr for pr in pull_requests if pr.get("mergedAt") and parse_date(pr["mergedAt"]) > since),
        key=lambda pr: pr["mergedAt"],
    )
    categories = {
        label["name"]
        for pr in selected
        for label in pr.get("labels", [])
        if isinstance(label, dict) and "name" in label
    }
    categories.discard("type:release")
    categories.discard("type:sync")
    if not selected or not categories:
        print(f"No classified changes found after {previous_tag}. No version proposed.")
        return

    print(f"Latest release: {previous_tag}")
    print(f"Suggested release: {next_version(previous, categories)} (owner approval required)")
    print("Merged develop PRs since last release:")
    for pr in selected:
        labels = ", ".join(label["name"] for label in pr.get("labels", [])) or "unlabeled"
        print(f"  #{pr['number']} {pr['title']} [{labels}]")
    print("Review classification, breaking changes, version metadata, and upgrade steps manually.")
    if len(pull_requests) == 500:
        print("WARNING: Query reached the 500 PR limit; older PRs may be missing.", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        raise SystemExit("GitHub CLI (gh) is required for this read-only suggestion.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"GitHub CLI failed: {exc.stderr or exc}") from exc
