"""Regression coverage for commit-based SemVer suggestions."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "propose-version.py"
SPEC = importlib.util.spec_from_file_location("propose_version", SCRIPT)
version = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(version)


def pull_request(number=1, commit="feature-sha", labels=("type:feature",), **overrides):
    pr = {
        "number": number, "title": "feat: new behavior", "merge_commit_sha": commit,
        "merged_at": "2026-11-05T12:01:00Z", "head": {"ref": "feature/new-behavior"},
        "labels": [{"name": label} for label in labels],
    }
    return pr | overrides


class VersionSuggestionTests(unittest.TestCase):
    def test_release_boundary_uses_reachability_not_publication_time(self):
        released = pull_request(1, "released-sha")
        pending = pull_request(2, "pending-sha")

        def ancestor(older, newer):
            return newer == "develop" or older == "released-sha"

        with patch.object(version, "is_ancestor", side_effect=ancestor):
            selected = version.select_unreleased([released, pending], "develop", "v1.0.0")
        self.assertEqual([pr["number"] for pr in selected], [2])

    def test_pr_outside_develop_is_ignored(self):
        with patch.object(version, "is_ancestor", return_value=False):
            self.assertEqual(version.select_unreleased([pull_request()], "develop", None), [])

    def test_initial_release_includes_all_reachable_merged_prs(self):
        with patch.object(version, "is_ancestor", return_value=True):
            selected = version.select_unreleased([pull_request()], "develop", None)
        self.assertEqual(len(selected), 1)

    def test_unmerged_release_sync_and_preparation_prs_are_ignored(self):
        prs = [
            pull_request(1, merged_at=None), pull_request(2, labels=("type:sync",)),
            pull_request(3, labels=("type:release",)),
            pull_request(4, labels=("type:chore",), head={"ref": "chore/release-v1.0.0"}),
        ]
        with patch.object(version, "is_ancestor") as ancestor:
            self.assertEqual(version.select_unreleased(prs, "develop", None), [])
        ancestor.assert_not_called()

    def test_missing_merge_commit_fails_instead_of_silently_omitting_pr(self):
        with self.assertRaisesRegex(ValueError, "no merge commit SHA"):
            version.select_unreleased([pull_request(merge_commit_sha=None)], "develop", None)

    def test_breaking_title_requires_major_without_manual_label(self):
        categories = version.pr_categories(pull_request(title="feat(api)!: remove old route"))
        self.assertIn("breaking", categories)
        self.assertEqual(version.next_version((1, 2, 3), categories), "v2.0.0")

    def test_manual_breaking_label_also_requires_major(self):
        categories = version.pr_categories(pull_request(labels=("type:fix", "breaking")))
        self.assertEqual(version.next_version((1, 2, 3), categories), "v2.0.0")

    def test_compatible_feature_and_fix_suggestions(self):
        self.assertEqual(version.next_version((1, 2, 3), {"type:feature"}), "v1.3.0")
        self.assertEqual(version.next_version((1, 2, 3), {"type:fix"}), "v1.2.4")

    def test_latest_release_is_highest_reachable_stable_semver(self):
        releases = [
            {"tag_name": "v9.0.0", "draft": True},
            {"tag_name": "v8.0.0", "prerelease": True},
            {"tag_name": "nightly"}, {"tag_name": "v3.0.0"},
            {"tag_name": "v1.9.0"}, {"tag_name": "v2.0.0"},
        ]
        with patch.object(version, "is_ancestor", side_effect=lambda tag, _: "v3.0.0" not in tag):
            self.assertEqual(version.latest_release(releases, "main"), "v2.0.0")

    def test_successful_empty_release_listing_means_initial_version(self):
        with patch.object(version, "branch_ref", side_effect=lambda branch: branch), \
                patch.object(version, "gh_pages", side_effect=[[], [pull_request()]]), \
                patch.object(version, "is_ancestor", return_value=True), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            version.main()
        self.assertIn("assuming 0.0.0", output.getvalue())
        self.assertIn("Suggested release: v0.1.0", output.getvalue())

    def test_authentication_error_is_not_treated_as_first_release(self):
        error = subprocess.CalledProcessError(1, ["gh", "api"], stderr="authentication failed")
        with patch.object(version, "branch_ref", side_effect=lambda branch: branch), \
                patch.object(version, "gh_pages", side_effect=error), \
                self.assertRaises(subprocess.CalledProcessError):
            version.main()

    def test_all_pages_are_read_beyond_former_500_pr_limit(self):
        pages = [[pull_request(number) for number in range(start, start + 100)] for start in range(0, 600, 100)]
        result = subprocess.CompletedProcess(["gh"], 0, stdout=json.dumps(pages))
        with patch.object(version.subprocess, "run", return_value=result) as run:
            prs = version.gh_pages("repos/{owner}/{repo}/pulls?per_page=100")
        self.assertEqual(len(prs), 600)
        self.assertIn("--paginate", run.call_args.args[0])
        self.assertIn("--slurp", run.call_args.args[0])

    def test_shallow_history_fails_with_actionable_message(self):
        with patch.object(version, "git", return_value=subprocess.CompletedProcess([], 0, "true\n")), \
                self.assertRaisesRegex(ValueError, "Complete Git history"):
            version.branch_ref("develop")

    def test_missing_develop_fails_instead_of_falling_back_to_master(self):
        responses = [subprocess.CompletedProcess([], 0, "false\n")] + [subprocess.CompletedProcess([], 128)] * 2
        with patch.object(version, "git", side_effect=responses), \
                self.assertRaisesRegex(ValueError, "develop is missing"):
            version.branch_ref("develop")

    def test_missing_commit_fails_with_fetch_instruction(self):
        with patch.object(version, "git", return_value=subprocess.CompletedProcess([], 128)), \
                self.assertRaisesRegex(ValueError, "fetch complete main/develop history"):
            version.is_ancestor("missing-sha", "develop")

    def test_main_merge_release_is_recognized_without_syncing_back_to_develop(self):
        with tempfile.TemporaryDirectory(dir=SCRIPT.parents[1]) as directory:
            def git(*args):
                return subprocess.run(
                    ["git", "-c", "user.name=Template tests", "-c", "user.email=tests@example.invalid", *args],
                    cwd=directory, capture_output=True, text=True, check=True, input="",
                )

            git("init", "--bare", "-b", "main")
            tree = git("mktree").stdout.strip()
            initial = git("commit-tree", tree, "-m", "initial").stdout.strip()
            released = git("commit-tree", tree, "-p", initial, "-m", "feature one").stdout.strip()
            release = git("commit-tree", tree, "-p", initial, "-p", released, "-m", "release").stdout.strip()
            pending = git("commit-tree", tree, "-p", released, "-m", "feature two").stdout.strip()
            git("update-ref", "refs/heads/main", release)
            git("update-ref", "refs/heads/develop", pending)
            git("update-ref", "refs/tags/v1.0.0", release)

            def read_git(*args):
                return subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True)

            with patch.object(version, "git", side_effect=read_git):
                previous = version.latest_release([{"tag_name": "v1.0.0"}], "main")
                self.assertEqual(previous, "v1.0.0")
                prs = [pull_request(1, released), pull_request(2, pending)]
                selected = version.select_unreleased(prs, "develop", previous)
                self.assertEqual([pr["number"] for pr in selected], [2])

    def test_invalid_tag_is_rejected(self):
        for tag in ("v01.0.0", "v1.0", "v1.0.0-beta", "invalid"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                version.version_parts(tag)


if __name__ == "__main__":
    unittest.main()
