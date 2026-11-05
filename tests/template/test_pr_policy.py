"""Regression tests for PR metadata validation and coordinated labeling."""

import copy
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import unquote


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pr-policy.py"
SPEC = importlib.util.spec_from_file_location("pr_policy", SCRIPT)
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)


def pull_request(head="feature/add-widget", base="develop", title="feat: add widget", labels=()):
    return {
        "number": 7,
        "title": title,
        "head": {"ref": head, "repo": {"full_name": "owner/repo"}},
        "base": {"ref": base, "repo": {"full_name": "owner/repo"}},
        "labels": [{"name": label} for label in labels],
    }


class FakeAPI:
    def __init__(self, pr):
        self.pr = copy.deepcopy(pr)
        self.repository_labels = set()
        self.calls = []

    def request(self, method, path, data=None):
        self.calls.append((method, path, data))
        if method == "GET" and path == "pulls/7":
            return copy.deepcopy(self.pr)
        if method == "GET" and path.startswith("labels/"):
            if unquote(path.removeprefix("labels/")) not in self.repository_labels:
                raise HTTPError(path, 404, "Not Found", {}, None)
            return {}
        if method == "POST" and path == "labels":
            self.repository_labels.add(data["name"])
            return {}
        if method == "DELETE" and path.startswith("issues/7/labels/"):
            removed = unquote(path.removeprefix("issues/7/labels/"))
            self.pr["labels"] = [item for item in self.pr["labels"] if item["name"] != removed]
            return None
        if method == "POST" and path == "issues/7/labels":
            names = {item["name"] for item in self.pr["labels"]} | set(data["labels"])
            self.pr["labels"] = [{"name": name} for name in sorted(names)]
            return self.pr["labels"]
        raise AssertionError((method, path, data))


class MetadataPolicyTests(unittest.TestCase):
    def test_unlabeled_metadata_can_be_classified_before_labeling(self):
        self.assertEqual(policy.metadata_policy(pull_request()), ("feature", False))

    def test_offline_validation_requires_one_matching_type(self):
        for labels in [(), ("type:fix",), ("type:feature", "type:fix")]:
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                policy.validate_labels(pull_request(labels=labels), policy.Policy("feature", False))

    def test_breaking_title_requires_label(self):
        pr = pull_request(title="feat(api)!: change response", labels=("type:feature",))
        classification = policy.metadata_policy(pr)
        self.assertTrue(classification.breaking)
        with self.assertRaisesRegex(ValueError, "breaking"):
            policy.validate_labels(pr, classification)

    def test_task_branch_and_title_failures(self):
        cases = [
            {"head": "feature/Add-widget"},
            {"head": "feature/add_widget"},
            {"head": "feature/"},
            {"head": "feature/add/widget"},
            {"title": "fix: add widget"},
            {"title": "feat: "},
            {"title": "feat: add widget\nfix: bypass"},
            {"base": "other"},
            {"base": "main"},
            {"head": "hotfix/urgent", "title": "fix: urgent"},
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                policy.metadata_policy(pull_request(**case))

    def test_release_preparation_branch_accepts_version_dots(self):
        pr = pull_request(head="chore/release-v1.2.3", title="chore: prepare v1.2.3")
        self.assertEqual(policy.metadata_policy(pr), ("chore", False))

    def test_hotfix_uses_fix_title_and_targets_main(self):
        pr = pull_request(head="hotfix/urgent", base="main", title="fix: urgent")
        self.assertEqual(policy.metadata_policy(pr), ("hotfix", False))

    def test_release_and_sync_use_own_permanent_branches(self):
        cases = [
            ("develop", "main", "release: v1.2.3", "release"),
            ("main", "develop", "sync: merge main into develop", "sync"),
        ]
        for head, base, title, category in cases:
            pr = pull_request(head=head, base=base, title=title)
            with self.subTest(category=category):
                self.assertEqual(policy.metadata_policy(pr).category, category)
                pr["head"]["repo"]["full_name"] = "fork/repo"
                with self.assertRaisesRegex(ValueError, "this repository"):
                    policy.metadata_policy(pr)

    def test_release_title_requires_strict_semver(self):
        for title in ["release: v01.2.3", "release: v1.2", "release: v1.2.3 extra"]:
            with self.subTest(title=title), self.assertRaises(ValueError):
                policy.metadata_policy(pull_request(head="develop", base="main", title=title))


class CoordinatedLabelTests(unittest.TestCase):
    def test_first_pr_event_passes_after_label_is_added(self):
        api = FakeAPI(pull_request())
        self.assertEqual(policy.synchronize_policy(api, 7), ("feature", False))
        self.assertEqual(api.pr["labels"], [{"name": "type:feature"}])
        self.assertEqual(sum(method == "GET" and path == "pulls/7" for method, path, _ in api.calls), 2)

    def test_stale_type_is_removed_and_other_labels_are_preserved(self):
        api = FakeAPI(pull_request(labels=("type:fix", "important", "breaking")))
        policy.synchronize_policy(api, 7)
        self.assertEqual({item["name"] for item in api.pr["labels"]}, {"type:feature", "important", "breaking"})

    def test_breaking_label_is_inferred_from_title(self):
        api = FakeAPI(pull_request(title="feat!: replace response", labels=("type:feature",)))
        policy.synchronize_policy(api, 7)
        self.assertEqual({item["name"] for item in api.pr["labels"]}, {"type:feature", "breaking"})

    def test_existing_valid_labels_do_not_trigger_writes(self):
        api = FakeAPI(pull_request(labels=("type:feature",)))
        policy.synchronize_policy(api, 7)
        self.assertTrue(all(method == "GET" for method, _, _ in api.calls))

    def test_invalid_metadata_does_not_change_labels(self):
        api = FakeAPI(pull_request(title="wrong title"))
        with self.assertRaises(ValueError):
            policy.synchronize_policy(api, 7)
        self.assertEqual(len(api.calls), 1)

    def test_concurrent_category_change_fails_instead_of_reporting_stale_success(self):
        api = FakeAPI(pull_request())
        original_request = api.request

        def changed_request(method, path, data=None):
            if method == "GET" and path == "pulls/7" and api.calls:
                api.pr["head"]["ref"] = "fix/repair-widget"
                api.pr["title"] = "fix: repair widget"
            return original_request(method, path, data)

        api.request = changed_request
        with self.assertRaisesRegex(ValueError, "changed during labeling"):
            policy.synchronize_policy(api, 7)


class APITests(unittest.TestCase):
    def test_enterprise_api_root_and_repository_are_respected(self):
        environment = {
            "GH_TOKEN": "test-token",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_API_URL": "https://github.example/api/v3/",
        }
        with patch.dict(os.environ, environment, clear=True):
            api = policy.GitHubAPI()
        with patch.object(policy, "urlopen") as open_request:
            open_request.return_value.__enter__.return_value.read.return_value = b'{"number": 7}'
            self.assertEqual(api.request("GET", "pulls/7"), {"number": 7})
            request = open_request.call_args.args[0]
            self.assertEqual(request.full_url, "https://github.example/api/v3/repos/owner/repo/pulls/7")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-token")

    def test_applying_labels_requires_token_and_target_repository(self):
        for environment in [{}, {"GH_TOKEN": "test-token"}]:
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                with self.assertRaises(ValueError):
                    policy.GitHubAPI()


if __name__ == "__main__":
    unittest.main()
