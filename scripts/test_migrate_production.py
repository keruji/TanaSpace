"""Exercise the real shell helper against a fake Docker boundary, never production."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

SCRIPT = Path(__file__).with_name("migrate-production.sh").resolve()
IMAGE = "ghcr.io/keruji/tanaspace@sha256:" + "a" * 64

DOCKER = r'''
import fcntl
import json
import os
from pathlib import Path
import re
import sys

args = sys.argv[1:]
state = Path(os.environ["DEPLOY_STATE_DIR"])
with (state / "deployment.lock").open("a") as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        held = False
    except BlockingIOError:
        held = True
record = {"args": args, "lock_held": held}
if args[0] == "compose":
    configs = [args[i + 1] for i, arg in enumerate(args) if arg == "-f"]
    assert len(configs) == 2
    override = Path(configs[1])
    record["override_mode"] = override.stat().st_mode & 0o777
    selected = re.search(r"^    image: (.+)$", override.read_text(), re.M)[1]
    record["selected_image"] = selected
with open(os.environ["DOCKER_LOG"], "a") as log:
    log.write(json.dumps(record) + "\n")
if "config" in args:
    image = "wrong:latest" if os.environ.get("WRONG_IMAGE") else selected
    print(json.dumps({"services": {"app": {"image": image, "environment": {"SECRET": "private-sentinel"}}}}))
    sys.exit(0)
if "--plan" in args:
    print("Planned operations: example migration")
    if os.environ.get("FAIL_STAGE") == "plan": sys.exit(17)
if "migrate" in args and "--noinput" in args and "--check" not in args:
    if os.environ.get("FAIL_STAGE") == "apply": sys.exit(18)
if "--check" in args and os.environ.get("FAIL_STAGE") == "verify": sys.exit(19)
'''


class ProductionMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="tanaspace-migration-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "bin"; self.bin.mkdir()
        self.production = self.root / "production"; self.production.mkdir()
        self.state = self.root / "state"; self.state.mkdir()
        (self.production / "compose.production.yml").write_text("services:\n  app:\n    build: .\n    image: tanaspace_prod-app\n")
        (self.production / ".env.production").write_text("PRIVATE=private-sentinel\n")
        self.original = {path.name: path.read_text() for path in self.production.iterdir()}
        docker = self.bin / "docker"
        docker.write_text(f"#!{sys.executable}\n" + DOCKER); docker.chmod(0o755)
        # Keep the script's requested 60-second timeout, but don't wait during
        # the contention test. Still use a real OS lock on the inherited fd.
        flock = self.bin / "flock"
        flock.write_text('#!/bin/bash\n[[ "$1" == "-w" && "$2" == "60" ]] || exit 99\nexec /usr/bin/flock -w 0 "$3"\n')
        flock.chmod(0o755)
        self.log = self.root / "docker.jsonl"
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"],
                    "DEPLOY_PATH": str(self.production), "DEPLOY_STATE_DIR": str(self.state),
                    "PRODUCTION_ENV_FILE": str(self.production / ".env.production"), "DOCKER_LOG": str(self.log)}

    def run_script(self, *args, **env):
        return subprocess.run(["bash", str(SCRIPT), *args], env={**self.env, **env}, text=True, capture_output=True)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def assert_clean(self):
        self.assertEqual(list(self.state.glob("migration.*")), [])
        self.assertEqual({path.name: path.read_text() for path in self.production.iterdir()}, self.original)
        with (self.state / "deployment.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for call in self.calls():
            self.assertTrue(call["lock_held"])
            if "selected_image" in call:
                self.assertEqual(call["selected_image"], IMAGE)
                self.assertEqual(call["override_mode"], 0o600)

    def test_default_is_preview_and_overrides_legacy_image(self):
        result = self.run_script(IMAGE)
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = [call["args"] for call in self.calls()]
        self.assertTrue(any("--plan" in args for args in commands))
        self.assertFalse(any("--noinput" in args for args in commands))
        self.assertIn("No migrations were applied", result.stdout)
        self.assertNotIn("private-sentinel", result.stdout + result.stderr)
        for args in commands:
            if args[0] == "compose":
                self.assertEqual(args[args.index("--project-directory") + 1], str(self.production))
                self.assertEqual(args[args.index("-p") + 1], "tanaspace_prod")
                self.assertNotIn("up", args)
                self.assertNotIn("down", args)
        self.assert_clean()

    def test_apply_runs_plan_apply_then_verification(self):
        result = self.run_script(IMAGE, "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        migrations = [call["args"][-3:] for call in self.calls() if "migrate" in call["args"]]
        self.assertEqual(migrations, [["manage.py", "migrate", "--plan"], ["manage.py", "migrate", "--noinput"], ["migrate", "--check", "--noinput"]])
        self.assertIn("completed and verified", result.stdout)
        self.assert_clean()

    def test_invalid_arguments_never_reach_docker(self):
        for args in [[], ["latest"], [IMAGE, "--force"], [IMAGE, "--apply", "extra"], ["ghcr.io/other/app@sha256:" + "a" * 64]]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_script(*args).returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.run_script("--help").returncode, 0)

    def test_missing_configuration_stops_before_docker(self):
        (self.production / ".env.production").unlink()
        result = self.run_script(IMAGE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr)
        self.assertEqual(self.calls(), [])

    def test_effective_image_mismatch_stops_before_running_containers(self):
        result = self.run_script(IMAGE, "--apply", WRONG_IMAGE="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any("run" in call["args"] for call in self.calls()))
        self.assert_clean()

    def test_plan_failure_does_not_apply(self):
        result = self.run_script(IMAGE, "--apply", FAIL_STAGE="plan")
        self.assertEqual(result.returncode, 17)
        self.assertFalse(any("--noinput" in call["args"] for call in self.calls()))
        self.assert_clean()

    def test_apply_failure_skips_verification_and_success_message(self):
        result = self.run_script(IMAGE, "--apply", FAIL_STAGE="apply")
        self.assertEqual(result.returncode, 18)
        self.assertFalse(any("--check" in call["args"] for call in self.calls()))
        self.assertNotIn("completed and verified", result.stdout)
        self.assert_clean()

    def test_verification_failure_does_not_report_success(self):
        result = self.run_script(IMAGE, "--apply", FAIL_STAGE="verify")
        self.assertEqual(result.returncode, 19)
        self.assertNotIn("completed and verified", result.stdout)
        self.assert_clean()

    def test_existing_deployment_lock_prevents_any_docker_operation(self):
        with (self.state / "deployment.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = self.run_script(IMAGE, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("holds the lock", result.stderr)
        self.assertEqual(self.calls(), [])
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
