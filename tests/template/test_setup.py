"""Check local bootstrap diagnostics without changing repository configuration."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_setup", ROOT / "scripts/check-setup.py")
SETUP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SETUP)


class SetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "README.md").write_text("# Fixture\n")
        self.enterContext(patch.object(SETUP, "bash_path", return_value="bash"))
        self.enterContext(patch.object(SETUP.shutil, "which", return_value="git"))

    def git_fixture(self, root, *args):
        if args == ("rev-parse", "--is-inside-work-tree"):
            return "true"
        if args == ("remote", "get-url", "origin"):
            return "https://github.com/owner/project.git"
        return "fixture-sha"

    def test_configured_repository_passes(self):
        with patch.object(SETUP, "git", side_effect=self.git_fixture):
            self.assertEqual(SETUP.inspect(self.root), [])

    def test_reports_remote_and_branches_missing(self):
        with patch.object(SETUP, "git", side_effect=lambda root, *args: "true" if args == ("rev-parse", "--is-inside-work-tree") else ""):
            problems = SETUP.inspect(self.root)
        self.assertEqual(len(problems), 3)
        self.assertTrue(any("origin" in problem for problem in problems))
        self.assertTrue(any("main branch" in problem for problem in problems))
        self.assertTrue(any("develop branch" in problem for problem in problems))

    def test_accepts_fetched_remote_branches(self):
        def remote_only(root, *args):
            if args[:2] == ("rev-parse", "--verify") and args[2].startswith("refs/heads/"):
                return ""
            return self.git_fixture(root, *args)
        with patch.object(SETUP, "git", side_effect=remote_only):
            self.assertEqual(SETUP.inspect(self.root), [])

    def test_missing_readme_and_bash_are_actionable(self):
        root = self.root / "empty"
        root.mkdir()
        with patch.object(SETUP, "git", side_effect=self.git_fixture), patch.object(SETUP, "bash_path", return_value=None):
            problems = SETUP.inspect(root)
        self.assertTrue(any("README.md" in problem for problem in problems))
        self.assertTrue(any("Bash" in problem for problem in problems))


if __name__ == "__main__":
    unittest.main()
