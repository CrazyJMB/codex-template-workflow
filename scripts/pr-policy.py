#!/usr/bin/env python3
"""Validate PR metadata and optionally synchronize labels using trusted policy."""

import argparse
import json
import os
import re
from pathlib import Path
from typing import NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


TASK_PREFIXES = {
    "feature": "feat",
    "fix": "fix",
    "hotfix": "fix",
    "refactor": "refactor",
    "docs": "docs",
    "chore": "chore",
    "test": "test",
    "ci": "ci",
    "perf": "perf",
}
VERSION = r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"


class Policy(NamedTuple):
    category: str
    breaking: bool


def metadata_policy(pr: dict) -> Policy:
    """Validate branch/title policy independently of labels."""
    base = pr["base"]["ref"]
    head = pr["head"]["ref"]
    title = pr["title"]
    if base not in {"develop", "main"}:
        raise ValueError(f"Unexpected target branch: {base}")

    if head in {"develop", "main"}:
        head_repo = (pr["head"].get("repo") or {}).get("full_name")
        base_repo = (pr["base"].get("repo") or {}).get("full_name")
        if not head_repo or head_repo != base_repo:
            raise ValueError("Release and sync PRs must use permanent branches in this repository")
        if (head, base) == ("develop", "main"):
            category, prefix = "release", "release"
        elif (head, base) == ("main", "develop"):
            category, prefix = "sync", "sync"
        else:
            raise ValueError("A permanent branch cannot target itself")
    else:
        category, separator, suffix = head.partition("/")
        if not separator or category not in TASK_PREFIXES:
            raise ValueError(f"Invalid task branch: {head}")
        release_preparation = category == "chore" and re.fullmatch(rf"release-v{VERSION}", suffix)
        if not release_preparation and not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", suffix):
            raise ValueError("Task branch descriptions must use lowercase kebab-case")
        if base == "main" and category != "hotfix":
            raise ValueError("Only develop releases or urgent hotfixes may target main")
        if base == "develop" and category == "hotfix":
            raise ValueError("Hotfixes must target main first")
        prefix = TASK_PREFIXES[category]

    if category == "release":
        if not re.fullmatch(rf"release: v{VERSION}", title):
            raise ValueError("Expected title: release: vX.Y.Z")
        breaking = False
    else:
        match = re.fullmatch(rf"{prefix}(?:\([a-zA-Z0-9._/-]+\))?(?P<breaking>!)?: \S[^\r\n]*", title)
        if match is None:
            raise ValueError(f"Expected Conventional Commit-style title starting with {prefix}:")
        breaking = bool(match.group("breaking"))
    return Policy(category, breaking)


def validate_labels(pr: dict, policy: Policy) -> None:
    labels = {label["name"] for label in pr.get("labels", [])}
    expected = f"type:{policy.category}"
    if {label for label in labels if label.startswith("type:")} != {expected}:
        raise ValueError(f"PR must have exactly one type label: {expected}")
    if policy.breaking and "breaking" not in labels:
        raise ValueError("A title marked with ! requires the breaking label")


class GitHubAPI:
    def __init__(self) -> None:
        self.token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GH_TOKEN or GITHUB_TOKEN is required to apply labels")
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
            raise ValueError("GITHUB_REPOSITORY must identify the target owner/repository")
        self.root = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
        self.repository_path = f"repos/{repository}"

    def request(self, method: str, path: str, data: dict | None = None):
        payload = json.dumps(data).encode("utf-8") if data is not None else None
        request = Request(
            f"{self.root}/{self.repository_path}/{path}",
            data=payload,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "template-pr-policy",
            },
        )
        with urlopen(request, timeout=30) as response:
            body = response.read()
        return json.loads(body) if body else None


def ensure_label(api: GitHubAPI, name: str) -> None:
    path = f"labels/{quote(name, safe='')}"
    try:
        api.request("GET", path)
    except HTTPError as error:
        if error.code != 404:
            raise
        error.close()
        try:
            api.request("POST", "labels", {"name": name, "color": "336699"})
        except HTTPError as create_error:
            if create_error.code != 422:
                raise
            create_error.close()
            # Another PR may have created this repository label concurrently.
            api.request("GET", path)


def synchronize_policy(api: GitHubAPI, number: int) -> Policy:
    """Label and check fresh API metadata in the same job; ignore event label snapshots."""
    pr = api.request("GET", f"pulls/{number}")
    policy = metadata_policy(pr)
    expected = f"type:{policy.category}"
    labels = {label["name"] for label in pr.get("labels", [])}
    required = {expected} | ({"breaking"} if policy.breaking else set())
    for label in sorted(labels):
        if label.startswith("type:") and label != expected:
            api.request("DELETE", f"issues/{number}/labels/{quote(label, safe='')}")
    for label in sorted(required - labels):
        ensure_label(api, label)
    if required - labels:
        api.request("POST", f"issues/{number}/labels", {"labels": sorted(required)})

    current = api.request("GET", f"pulls/{number}")
    current_policy = metadata_policy(current)
    if current_policy != policy:
        raise ValueError("PR metadata changed during labeling; rerun policy for its current state")
    validate_labels(current, current_policy)
    return current_policy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", type=Path, help="GitHub pull request event JSON")
    parser.add_argument("--apply-labels", action="store_true", help="Read current PR metadata and update labels")
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    if args.apply_labels:
        number = event["pull_request"]["number"]
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0:
            raise ValueError("Invalid pull request number")
        policy = synchronize_policy(GitHubAPI(), number)
    else:
        pr = event["pull_request"]
        policy = metadata_policy(pr)
        validate_labels(pr, policy)
    print(f"PR policy passed ({policy.category})")


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        error.close()
        raise SystemExit(f"GitHub API request failed (HTTP {error.code})") from error
    except URLError as error:
        raise SystemExit("GitHub API could not be reached") from error
    except (ValueError, KeyError, OSError) as error:
        raise SystemExit(str(error)) from error
