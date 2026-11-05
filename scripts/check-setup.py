#!/usr/bin/env python3
"""Report missing local template prerequisites without modifying configuration."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def bash_path() -> str | None:
    if os.name == "nt":
        git_exe = shutil.which("git")
        if git_exe:
            candidate = Path(git_exe).resolve().parent.parent / "bin" / "bash.exe"
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash")


def inspect(root: Path) -> list[str]:
    problems = []
    if sys.version_info < (3, 11):
        problems.append("Install Python 3.11 or newer.")
    if not (root / "README.md").is_file():
        problems.append("Add a project README.md with setup and check commands.")
    if not bash_path():
        problems.append("Install Bash (Git Bash on Windows).")
    if not shutil.which("git"):
        problems.append("Install Git and make it available on PATH.")
        return problems
    if git(root, "rev-parse", "--is-inside-work-tree") != "true":
        problems.append("Run this command from an initialized Git repository.")
        return problems
    if not git(root, "remote", "get-url", "origin"):
        problems.append("Configure the GitHub remote named origin.")
    for branch in ("main", "develop"):
        if not any(
            git(root, "rev-parse", "--verify", ref)
            for ref in (f"refs/heads/{branch}", f"refs/remotes/origin/{branch}")
        ):
            problems.append(f"Create or fetch the permanent {branch} branch.")
    return problems


def main() -> int:
    problems = inspect(Path.cwd())
    if problems:
        print("Local setup is incomplete:")
        for problem in problems:
            print(f"- {problem}")
        print("See WORKFLOW.md. GitHub branch rules and permissions require manual verification.")
        return 1
    print("Local prerequisites found. Verify GitHub rules and Actions permissions in WORKFLOW.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
