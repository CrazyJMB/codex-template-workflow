"""Exercise CI behavior in isolated projects without installing dependencies."""

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_template", ROOT / "scripts/check-template.py")
CHECK_TEMPLATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK_TEMPLATE)


class CiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        (self.root / "bin").mkdir()
        shutil.copyfile(ROOT / "scripts/ci.sh", self.root / "scripts/ci.sh")
        (self.root / "scripts/check-template.py").write_text(
            "print('Template fixture validated.')\n", encoding="utf-8"
        )
        self.environment = dict(os.environ)
        self.environment["PATH"] = str(self.root / "bin") + os.pathsep + self.environment["PATH"]
        self.environment["CI_COMMAND_LOG"] = (self.root / "commands.log").as_posix()
        self.stub("npm", 'printf "%s\\n" "$*" >> "$CI_COMMAND_LOG"\nexit "${CI_NPM_STATUS:-0}"\n')
        # Only emulate the manifest query; application scripts are recorded by npm.
        query = (
            "import json, sys; "
            "from pathlib import Path; "
            "scripts = json.loads(Path('package.json').read_text()).get('scripts', {}); "
            "script = scripts.get(sys.argv[-1]); "
            "sys.exit(0 if isinstance(script, str) and script.strip() else 1)"
        )
        runner = shlex.quote(Path(sys.executable).as_posix())
        self.stub("node", f'exec {runner} -c {shlex.quote(query)} "$@"\n')

    def stub(self, name, body):
        path = self.root / "bin" / name
        path.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def node_project(self, scripts=None, lock=True):
        (self.root / "package.json").write_text(
            json.dumps({"scripts": scripts or {}}), encoding="utf-8"
        )
        if lock:
            (self.root / "package-lock.json").write_text("{}", encoding="utf-8")

    def python_stub(self):
        runner = shlex.quote(Path(sys.executable).as_posix())
        body = (
            'if [[ "$1" == scripts/check-template.py ]]; then\n'
            f'  exec {runner} "$@"\n'
            'fi\n'
            'printf "%s\\n" "$*" >> "$CI_COMMAND_LOG"\n'
            'if [[ "$*" == "-m ruff --version" ]]; then exit 1; fi\n'
            'exit 0\n'
        )
        self.stub("python", body)
        self.stub("python3", body)

    def run_ci(self):
        return subprocess.run(
            [CHECK_TEMPLATE.find_bash(), "scripts/ci.sh"],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_empty_template_still_runs_its_checks(self):
        result = self.run_ci()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Template fixture validated.", result.stdout)
        self.assertIn("No supported application manifest", result.stdout)

    def test_dependency_installation_is_not_validation(self):
        self.node_project()
        result = self.run_ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Node.js project has no configured", result.stderr)
        self.assertEqual((self.root / "commands.log").read_text().splitlines(), ["ci"])

    def test_project_script_counts_without_counting_installation(self):
        self.node_project({"test": "node --test"})
        result = self.run_ci()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Executed 1 application validation commands", result.stdout)
        self.assertEqual((self.root / "commands.log").read_text().splitlines(), ["ci", "run test"])

    def test_failed_validation_propagates(self):
        self.node_project({"test": "node --test"})
        self.stub("npm", 'if [[ "$1" == run ]]; then exit 7; fi\n')
        result = self.run_ci()
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)

    def test_node_lockfile_is_required(self):
        self.node_project({"test": "node --test"}, lock=False)
        result = self.run_ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Commit a Node lockfile", result.stderr)

    def test_each_detected_stack_needs_checks(self):
        self.node_project({"lint": "eslint ."})
        (self.root / "composer.json").write_text("{}", encoding="utf-8")
        (self.root / "composer.lock").write_text("{}", encoding="utf-8")
        self.stub("composer", "exit 0\n")
        result = self.run_ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PHP project has no configured", result.stderr)

    def test_template_tests_do_not_count_as_python_application_tests(self):
        self.python_stub()
        (self.root / "requirements.txt").write_text("", encoding="utf-8")
        (self.root / "tests/template").mkdir(parents=True)
        (self.root / "tests/template/test_example.py").write_text("", encoding="utf-8")
        result = self.run_ci()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python project has no configured", result.stderr)
        self.assertEqual(
            (self.root / "commands.log").read_text().splitlines(),
            ["-m pip install -r requirements.txt", "-m ruff --version"],
        )

    def test_python_application_tests_run_separately(self):
        self.python_stub()
        (self.root / "requirements.txt").write_text("", encoding="utf-8")
        (self.root / "tests").mkdir()
        (self.root / "tests/test_app.py").write_text("", encoding="utf-8")
        result = self.run_ci()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Executed 1 application validation commands", result.stdout)
        self.assertIn("-m pytest --ignore=tests/template", (self.root / "commands.log").read_text())


if __name__ == "__main__":
    unittest.main()
