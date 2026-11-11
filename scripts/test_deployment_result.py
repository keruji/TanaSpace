import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "deployment_result", Path(__file__).with_name("read-deployment-result.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DeploymentReportTests(unittest.TestCase):
    def setUp(self):
        self.commit = "a" * 40
        self.image = "ghcr.io/keruji/tanaspace@sha256:" + "b" * 64
        self.report = {
            "schema_version": 1,
            "outcome": "deployed",
            "exit_code": 0,
            "stage": "recording_release",
            "test_rollback": False,
            "source_commit": self.commit,
            "candidate_image": self.image,
            "previous_image": "tanaspace:previous",
        }

    def validate(self, report, status=0, test_mode="false"):
        return module.validate(report, self.commit, self.image, test_mode, status)

    def test_successful_deployment(self):
        self.assertEqual(self.validate(self.report)["outcome"], "deployed")

    def test_each_failure_outcome_remains_a_failure(self):
        for outcome, stage, test_mode in [
            ("stopped_before_switch", "preflight", "false"),
            ("rolled_back", "verifying_application", "false"),
            ("rollback_test_passed", "testing_rollback", "true"),
            ("rollback_failed", "starting_application", "false"),
        ]:
            with self.subTest(outcome=outcome):
                report = dict(self.report, outcome=outcome, stage=stage,
                              exit_code=1, test_rollback=test_mode == "true")
                self.assertEqual(self.validate(report, 1, test_mode)["exit_code"], "1")
                with self.assertRaises(ValueError):
                    self.validate(report, 0, test_mode)

    def test_rejects_stale_or_malformed_reports(self):
        for field, bad_value in [
            ("schema_version", True),
            ("source_commit", "c" * 40),
            ("candidate_image", "different-image"),
            ("test_rollback", "false"),
            ("test_rollback", True),
            ("exit_code", False),
            ("exit_code", 255),
            ("outcome", "unknown"),
            ("stage", "preflight"),
            ("previous_image", ""),
        ]:
            with self.subTest(field=field, bad_value=bad_value):
                report = copy.deepcopy(self.report)
                report[field] = bad_value
                with self.assertRaises(ValueError):
                    self.validate(report)

    def test_test_run_cannot_claim_normal_rollback(self):
        report = dict(self.report, outcome="rolled_back", stage="testing_rollback",
                      exit_code=1, test_rollback=True)
        with self.assertRaises(ValueError):
            self.validate(report, 1, "true")

    def test_report_for_ssh_connection_failure_is_rejected(self):
        with self.assertRaises(ValueError):
            self.validate(self.report, 255)


if __name__ == "__main__":
    unittest.main()
