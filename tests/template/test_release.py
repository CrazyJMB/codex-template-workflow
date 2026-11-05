"""Validate release preflight and draft publication with isolated fixtures."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NOTES = load("extract-release-notes")
PREFLIGHT = load("check-release")
CHECK_TEMPLATE = load("check-template")


class ReleaseNotesTests(unittest.TestCase):
    def test_extracts_only_requested_release(self):
        result = NOTES.extract(
            "## [Unreleased]\n\n### Added\n- Future.\n\n"
            "## [1.2.3] - 2026-11-05\n\n### Fixed\n- Corrected validation.\n\n"
            "## [1.2.2] - 2026-10-01\n\n- Previous.\n", "v1.2.3"
        )
        self.assertIn("Corrected validation.", result)
        self.assertNotIn("Future.", result)
        self.assertNotIn("Previous.", result)

    def test_rejects_impossible_date(self):
        with self.assertRaises(ValueError):
            NOTES.extract("## [1.2.3] - 2026-02-30\n\n- Change.\n", "v1.2.3")

    def test_rejects_empty_placeholder_notes(self):
        for body in ("", "### Added\n\n### Fixed", "<!-- Describe the release -->", "[1.2.3]: https://example.com"):
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, "Empty release notes"):
                NOTES.extract(f"## [1.2.3] - 2026-11-05\n\n{body}\n", "v1.2.3")

    def test_rejects_missing_section_and_noncanonical_tag(self):
        for text, tag in (("## [Unreleased]\n", "v1.2.3"), ("", "v01.2.3")):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                NOTES.extract(text, tag)


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(contextlib.chdir(self.root))
        (self.root / "CHANGELOG.md").write_text(
            "## [Unreleased]\n\n## [1.2.3] - 2026-11-05\n\n### Fixed\n- Corrected validation.\n",
            encoding="utf-8",
        )

    def test_checks_metadata_without_changing_files(self):
        (self.root / "package.json").write_text(json.dumps({"version": "1.2.3"}))
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(PREFLIGHT.check("v1.2.3"), "v1.2.3")
        self.assertEqual(before, {path.name: path.read_bytes() for path in self.root.iterdir()})

    def test_rejects_mismatched_project_version(self):
        (self.root / "VERSION").write_text("1.2.2")
        with self.assertRaisesRegex(ValueError, "mismatches"):
            PREFLIGHT.check("v1.2.3")

    def test_hotfix_can_infer_tag_from_changelog(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(PREFLIGHT.check(), "v1.2.3")

    def test_requires_real_release_notes(self):
        (self.root / "CHANGELOG.md").write_text("## [1.2.3] - 2026-11-05\n\n### Added\n")
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "Empty release notes"):
            PREFLIGHT.check()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "bin").mkdir()
        (self.root / "dist").mkdir()
        for name in ("source.zip", "source.tar.gz", "SHA256SUMS"):
            (self.root / "dist" / name).write_text("fixture")
        self.log = self.root / "commands.log"
        fake = self.root / "bin" / "gh"
        fake.write_text(
            '#!/usr/bin/env bash\nset -euo pipefail\n'
            'printf "%s\\n" "$*" >> "$PUBLICATION_LOG"\n'
            'if [[ "$1" == api ]]; then\n'
            '  [[ "${API_FAILURE:-0}" == 0 ]] || exit 3\n'
            '  printf "%s" "${RELEASE_DRAFT:-}"\n'
            'elif [[ "$1 $2" == "release upload" ]]; then\n'
            '  [[ "${UPLOAD_FAILURE:-0}" == 0 ]] || exit 4\n'
            'fi\n', encoding="utf-8"
        )
        fake.chmod(0o755)
        self.environment = dict(os.environ)
        self.environment.update({
            "PATH": str(self.root / "bin") + os.pathsep + self.environment["PATH"],
            "PUBLICATION_LOG": self.log.as_posix(),
            "GITHUB_REPOSITORY": "owner/project",
            "RELEASE_DRAFT": "",
        })

    def publish(self):
        return subprocess.run(
            [CHECK_TEMPLATE.find_bash(), (ROOT / "scripts/publish-release.sh").as_posix(), "v1.2.3", "notes.md"],
            cwd=self.root, env=self.environment, capture_output=True, text=True, timeout=30,
        )

    def test_creates_draft_and_publishes_after_upload(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = self.log.read_text().splitlines()
        self.assertIn("--draft", commands[1])
        self.assertTrue(commands[2].startswith("release upload"))
        self.assertIn("--draft=false", commands[3])

    def test_retries_existing_draft_without_creating_another(self):
        self.environment["RELEASE_DRAFT"] = "true"
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("release create", self.log.read_text())

    def test_refuses_to_overwrite_published_release(self):
        self.environment["RELEASE_DRAFT"] = "false"
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing to replace", result.stderr)
        self.assertNotIn("release upload", self.log.read_text())

    def test_api_error_is_not_treated_as_missing_release(self):
        self.environment["API_FAILURE"] = "1"
        result = self.publish()
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertNotIn("release create", self.log.read_text())

    def test_upload_failure_does_not_publish_draft(self):
        self.environment["UPLOAD_FAILURE"] = "1"
        result = self.publish()
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertNotIn("release edit", self.log.read_text())


if __name__ == "__main__":
    unittest.main()
