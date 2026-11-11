"""Validate a VPS deployment report before exposing workflow outputs."""
import json
import os
from pathlib import Path
import re
import sys


def validate(report, commit, image, test_mode, ssh_status):
    if not isinstance(report, dict):
        raise ValueError("report must be a JSON object")
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        raise ValueError("unsupported schema version")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("invalid expected commit")
    if not re.fullmatch(r"ghcr\.io/keruji/tanaspace@sha256:[a-f0-9]{64}", image):
        raise ValueError("invalid expected image")
    if test_mode not in ("true", "false"):
        raise ValueError("invalid expected rollback-test setting")
    if report.get("source_commit") != commit:
        raise ValueError("source commit does not match this run")
    if report.get("candidate_image") != image:
        raise ValueError("candidate image does not match this run")
    if type(report.get("test_rollback")) is not bool:
        raise ValueError("rollback-test setting must be boolean")
    if report["test_rollback"] != (test_mode == "true"):
        raise ValueError("rollback-test setting does not match this run")
    status = report.get("exit_code")
    if type(status) is not int or not 0 <= status <= 255 or status != ssh_status:
        raise ValueError("exit code does not match the SSH result")
    if not isinstance(report.get("previous_image"), str) or not report["previous_image"]:
        raise ValueError("previous image is missing")

    outcome = report.get("outcome")
    stage = report.get("stage")
    switched_stages = {
        "starting_application", "verifying_image", "restarting_proxy",
        "verifying_application", "verifying_assets", "testing_rollback",
        "recording_release",
    }
    if outcome == "deployed":
        valid = status == 0 and stage == "recording_release" and not report["test_rollback"]
    elif outcome == "stopped_before_switch":
        valid = status != 0 and stage == "preflight"
    elif outcome == "rolled_back":
        valid = status != 0 and stage in switched_stages and not report["test_rollback"] and stage != "testing_rollback"
    elif outcome == "rollback_test_passed":
        valid = status != 0 and stage in switched_stages and report["test_rollback"]
    elif outcome == "rollback_failed":
        valid = status != 0 and stage in switched_stages
    else:
        valid = False
    if not valid:
        raise ValueError("outcome, stage, exit code, and test mode are inconsistent")

    return {
        "report_valid": "true",
        "outcome": outcome,
        "stage": stage,
        "source_commit": commit,
        "rollback_test": test_mode,
        "exit_code": str(status),
    }


def main():
    if len(sys.argv) != 6:
        print("Usage: read-deployment-result.py REPORT COMMIT IMAGE TEST_MODE SSH_STATUS", file=sys.stderr)
        return 1
    try:
        report = json.loads(Path(sys.argv[1]).read_text())
        outputs = validate(report, sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    except (OSError, UnicodeError, ValueError, TypeError):
        print("Deployment report is missing, invalid, or inconsistent with this run.", file=sys.stderr)
        return 1

    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a") as output:
            for key, value in outputs.items():
                output.write(f"{key}={value}\n")

    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a") as summary:
            summary.write("## Validated deployment result\n\n")
            summary.write(f"Outcome: {outputs['outcome']}\n\n")
            summary.write(f"Stage: {outputs['stage']}\n\n")
            summary.write(f"Rollback test: {outputs['rollback_test']}\n\n")
            summary.write(f"Source commit: {outputs['source_commit']}\n")

    print(f"Deployment report validated: {outputs['outcome']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
