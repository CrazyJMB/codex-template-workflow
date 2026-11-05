#!/usr/bin/env python3
"""Suggest a SemVer release from unreleased develop PRs (read-only)."""

import json
import re
import subprocess
import sys


def gh_pages(endpoint: str) -> list[dict]:
    result = subprocess.run(
        ["gh", "api", "--paginate", "--slurp", endpoint],
        capture_output=True, text=True, check=True,
    )
    pages = json.loads(result.stdout)
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("Expected paginated GitHub API arrays")
    return [item for page in pages for item in page]


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def branch_ref(branch: str) -> str:
    shallow = git("rev-parse", "--is-shallow-repository")
    if shallow.returncode or shallow.stdout.strip() != "false":
        raise ValueError("Complete Git history is required; fetch/unshallow main, develop and all tags first.")
    for ref in (f"refs/remotes/origin/{branch}", f"refs/heads/{branch}"):
        if git("rev-parse", "--verify", f"{ref}^{{commit}}").returncode == 0:
            return ref
    raise ValueError(f"{branch} is missing; fetch origin main develop and all tags before proposing a release.")


def is_ancestor(older: str, newer: str) -> bool:
    result = git("merge-base", "--is-ancestor", older, newer)
    if result.returncode not in (0, 1):
        raise ValueError(
            f"Cannot compare {older} with {newer}; fetch complete main/develop history and all tags."
        )
    return result.returncode == 0


def version_parts(tag: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag)
    if not match:
        raise ValueError(f"Not a SemVer release: {tag}")
    return tuple(map(int, match.groups()))


def latest_release(releases: list[dict], main_ref: str) -> str | None:
    candidates = [
        release["tag_name"] for release in releases
        if not release.get("draft") and not release.get("prerelease")
        and re.fullmatch(r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", release["tag_name"])
    ]
    for tag in sorted(candidates, key=version_parts, reverse=True):
        if is_ancestor(f"refs/tags/{tag}^{{commit}}", main_ref):
            return tag
    return None


def pr_categories(pr: dict) -> set[str]:
    categories = {label["name"] for label in pr.get("labels", [])}
    if re.match(r"^[a-z]+(?:\([^\r\n)]+\))?!: ", pr["title"]):
        categories.add("breaking")
    return categories & {
        "breaking", "type:feature", "type:fix", "type:hotfix", "type:perf",
        "type:refactor", "type:docs", "type:chore", "type:test", "type:ci",
    }


def select_unreleased(prs: list[dict], develop: str, previous_tag: str | None) -> list[dict]:
    selected = []
    for pr in prs:
        if not pr.get("merged_at"):
            continue
        labels = {label["name"] for label in pr.get("labels", [])}
        if labels & {"type:release", "type:sync"}:
            continue
        if re.fullmatch(r"chore/release-v\d+\.\d+\.\d+", pr.get("head", {}).get("ref", "")):
            continue
        commit = pr.get("merge_commit_sha")
        if not commit:
            raise ValueError(f"Merged PR #{pr['number']} has no merge commit SHA")
        if not is_ancestor(commit, develop):
            continue
        if previous_tag and is_ancestor(commit, f"refs/tags/{previous_tag}^{{commit}}"):
            continue
        selected.append(pr)
    return sorted(selected, key=lambda pr: pr["merged_at"])


def next_version(previous: tuple[int, int, int], categories: set[str]) -> str:
    major, minor, patch = previous
    if "breaking" in categories:
        return f"v{major + 1}.0.0"
    if "type:feature" in categories:
        return f"v{major}.{minor + 1}.0"
    return f"v{major}.{minor}.{patch + 1}"


def main() -> None:
    develop = branch_ref("develop")
    main_ref = branch_ref("main")
    releases = gh_pages("repos/{owner}/{repo}/releases?per_page=100")
    previous_tag = latest_release(releases, main_ref)
    previous = version_parts(previous_tag) if previous_tag else (0, 0, 0)
    prs = gh_pages("repos/{owner}/{repo}/pulls?state=closed&base=develop&per_page=100")
    selected = select_unreleased(prs, develop, previous_tag)
    categories = set().union(*(pr_categories(pr) for pr in selected))
    if not categories:
        print(f"No classified unreleased changes found after {previous_tag or 'initial history'}. No version proposed.")
        return

    print(f"Latest reachable release: {previous_tag or 'none (assuming 0.0.0)'}")
    print(f"Suggested release: {next_version(previous, categories)} (owner approval required)")
    print("Unreleased merged develop PRs:")
    for pr in selected:
        labels = ", ".join(sorted(pr_categories(pr))) or "unclassified; review manually"
        print(f"  #{pr['number']} {pr['title']} [{labels}]")
    print("Review classification, breaking changes, version metadata, and upgrade steps manually.")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        raise SystemExit("Git and GitHub CLI (gh) are required for this read-only suggestion.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"GitHub CLI failed; check authentication/network access: {exc.stderr or exc}") from exc
    except (ValueError, KeyError) as exc:
        raise SystemExit(str(exc)) from exc
