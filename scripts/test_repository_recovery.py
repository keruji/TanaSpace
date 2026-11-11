"""Exercise real local Git pushes with a mocked GitHub API."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location(
    "repository_recovery", Path(__file__).with_name("recover-repository.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RepositoryRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.repo = self.directory / "repo"
        self.repo.mkdir()
        self.remote = self.directory / "remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.repo / "feature.txt").write_text("working\n")
        self.git("add", ".")
        self.git("commit", "-m", "working release")
        self.previous = self.git("rev-parse", "HEAD")
        (self.repo / "feature.txt").write_text("failed change\n")
        self.git("commit", "-am", "feature (#42)")
        self.source = self.git("rev-parse", "HEAD")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "origin", "main")
        self.image = "ghcr.io/keruji/tanaspace@sha256:" + "b" * 64
        self.report = {
            "schema_version": 1, "outcome": "rolled_back", "exit_code": 1,
            "stage": "verifying_application", "test_rollback": False,
            "source_commit": self.source, "candidate_image": self.image,
            "previous_image": "tanaspace:previous", "previous_commit": self.previous,
        }
        self.report_file = self.directory / "report.json"
        self.prs = []
        self.comments = []
        self.fail_create = False
        self.fail_comment = False
        self.race_commit = None
        self.pr_creations = 0
        env = {
            "GH_TOKEN": "mock", "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_SHA": self.source, "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/main", "CANDIDATE_IMAGE": self.image,
            "DEPLOYMENT_EXIT_CODE": "1",
            "FAILURE_RUN_URL": "https://github.com/owner/repo/actions/runs/123",
            "GITHUB_STEP_SUMMARY": str(self.directory / "summary"),
        }
        for patcher in [mock.patch.dict(os.environ, env),
                        mock.patch.object(module, "ROOT", self.repo),
                        mock.patch.object(module, "run_gh", side_effect=self.fake_gh)]:
            patcher.start()
            self.addCleanup(patcher.stop)

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.repo), "-c", "commit.gpgsign=false", *args],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()

    def remote_main(self):
        return self.git("ls-remote", "origin", "refs/heads/main").split()[0]

    def fake_gh(self, *args):
        if args[0] == "api" and "/commits/" in args[1]:
            return json.dumps([{
                "number": 42, "merged_at": "2026-01-01",
                "merge_commit_sha": self.source,
                "base": {"ref": "main", "repo": {"full_name": "owner/repo"}},
            }])
        if args[0] == "api" and "/git/ref/" in args[1]:
            current = self.remote_main()
            if self.race_commit:
                subprocess.run(["git", "--git-dir", str(self.remote), "update-ref",
                                "refs/heads/main", self.race_commit], check=True)
                self.race_commit = None
            return json.dumps({"object": {"sha": current}})
        if args[:2] == ("pr", "list"):
            return json.dumps(self.prs)
        if args[:2] == ("pr", "create"):
            if self.fail_create:
                self.fail_create = False
                raise RuntimeError("Simulated PR API outage")
            self.assertIn("--draft", args)
            self.assertEqual(args[args.index("--base") + 1], "main")
            self.assertTrue(args[args.index("--head") + 1].startswith("recovery/reapply-42-"))
            self.pr_creations += 1
            url = "https://github.com/owner/repo/pull/99"
            self.prs = [{"url": url, "state": "OPEN"}]
            return url
        if args[0] == "api" and "/comments?" in args[1]:
            return json.dumps([[{"body": body} for body in self.comments]])
        if args[:2] == ("pr", "comment"):
            if self.fail_comment:
                self.fail_comment = False
                raise RuntimeError("Simulated comment API outage")
            self.assertEqual(args[2], "42")
            self.comments.append(Path(args[args.index("--body-file") + 1]).read_text())
            return ""
        self.fail(f"Unexpected GitHub operation: {args}")

    def recover(self):
        self.report_file.write_text(json.dumps(self.report))
        return module.recover(self.report_file)

    def test_reverts_main_and_creates_one_replacement_and_comment(self):
        self.recover()
        revert = self.remote_main()
        self.assertNotEqual(revert, self.source)
        self.assertEqual(self.git("rev-parse", revert + "^{tree}"),
                         self.git("rev-parse", self.previous + "^{tree}"))
        branch = f"recovery/reapply-42-{self.source[:12]}"
        head = self.git("ls-remote", "origin", "refs/heads/" + branch).split()[0]
        self.assertEqual(self.git("rev-parse", head + "^{tree}"),
                         self.git("rev-parse", self.source + "^{tree}"))
        self.assertEqual(self.git("rev-parse", head + "^"), revert)
        self.recover()
        self.assertEqual(self.pr_creations, 1)
        self.assertEqual(len(self.comments), 1)
        self.assertEqual(self.remote_main(), revert)

    def test_accepts_restored_commit_with_identical_files(self):
        tree = self.git("rev-parse", self.previous + "^{tree}")
        equivalent = self.git("commit-tree", tree, "-p", self.previous,
                              "-m", "different commit with identical working files")
        self.report["previous_commit"] = equivalent
        self.recover()
        self.assertEqual(self.pr_creations, 1)

    def test_retry_after_pr_api_failure(self):
        self.fail_create = True
        with self.assertRaisesRegex(RuntimeError, "PR API outage"):
            self.recover()
        reverted_main = self.remote_main()
        self.assertNotEqual(reverted_main, self.source)
        self.recover()
        self.assertEqual(self.remote_main(), reverted_main)
        self.assertEqual(self.pr_creations, 1)

    def test_retry_after_comment_api_failure(self):
        self.fail_comment = True
        with self.assertRaisesRegex(RuntimeError, "comment API outage"):
            self.recover()
        self.recover()
        self.assertEqual(self.pr_creations, 1)
        self.assertEqual(len(self.comments), 1)

    def test_refuses_newer_main(self):
        (self.repo / "newer.txt").write_text("newer")
        self.git("add", ".")
        self.git("commit", "-m", "newer change")
        newer = self.git("rev-parse", "HEAD")
        self.git("push", "origin", "main")
        with self.assertRaisesRegex(ValueError, "Main advanced"):
            self.recover()
        self.assertEqual(self.remote_main(), newer)
        self.assertFalse(self.prs)

    def test_competing_push_rejects_both_recovery_refs(self):
        self.git("checkout", "-b", "competing")
        (self.repo / "newer.txt").write_text("newer")
        self.git("add", ".")
        self.git("commit", "-m", "competing change")
        newer = self.git("rev-parse", "HEAD")
        self.git("push", "origin", "competing")
        self.git("checkout", "main")
        self.race_commit = newer
        with self.assertRaises(RuntimeError):
            self.recover()
        self.assertEqual(self.remote_main(), newer)
        self.assertFalse(self.git("ls-remote", "origin", "refs/heads/recovery/*"))
        self.assertFalse(self.prs)

    def test_rejects_test_unknown_restore_and_infrastructure_failures(self):
        for changes in [
            {"test_rollback": True, "outcome": "rollback_test_passed"},
            {"previous_commit": ""},
            {"previous_commit": "invalid"},
            {"previous_commit": None},
            {"previous_commit": self.source},
            {"outcome": "rollback_failed"},
            {"stage": "restarting_proxy"},
            {"stage": "recording_release"},
        ]:
            with self.subTest(changes=changes):
                original = copy.deepcopy(self.report)
                self.report.update(changes)
                with self.assertRaises(ValueError):
                    self.recover()
                self.report = original
                self.assertEqual(self.remote_main(), self.source)
                self.assertFalse(self.prs)

    def test_requires_main_push_context(self):
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_NAME": "workflow_dispatch"}):
            with self.assertRaisesRegex(ValueError, "main push"):
                self.recover()
        self.assertEqual(self.remote_main(), self.source)

    def test_rejects_recovery_commit_loops(self):
        self.git("commit", "--allow-empty", "-m", "TanaSpace-Recovery: revert")
        self.source = self.git("rev-parse", "HEAD")
        self.git("push", "origin", "main")
        self.report["source_commit"] = self.source
        with mock.patch.dict(os.environ, {"GITHUB_SHA": self.source}):
            with self.assertRaisesRegex(ValueError, "another recovery"):
                self.recover()
        self.assertEqual(self.remote_main(), self.source)


if __name__ == "__main__":
    unittest.main()
