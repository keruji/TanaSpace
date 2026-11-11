"""Recover main after a verified application rollback, then open a draft PR."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def command(args, *, cwd=None, env=None):
    completed = subprocess.run(args, cwd=ROOT if cwd is None else cwd, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode:
        raise RuntimeError(f"Command failed: {args[0]} {args[1]}\n{completed.stderr.strip()}")
    return completed.stdout.strip()


def git(*args, cwd=None, env=None):
    return command(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, env=env)


def run_gh(*args):
    return command(["gh", *args])


def github_json(*args):
    return json.loads(run_gh(*args))


def require_environment(name):
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"Missing environment variable: {name}")
    return value


def recover(report_path):
    if os.environ.get("GITHUB_EVENT_NAME") != "push" or os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Recovery is restricted to main push workflows.")
    require_environment("GH_TOKEN")
    repository = require_environment("GITHUB_REPOSITORY")
    source = require_environment("GITHUB_SHA")
    image = require_environment("CANDIDATE_IMAGE")
    exit_code = int(require_environment("DEPLOYMENT_EXIT_CODE"))
    run_url = require_environment("FAILURE_RUN_URL")
    if not re.fullmatch(r"https://github\.com/" + re.escape(repository) + r"/actions/runs/[0-9]+", run_url):
        raise ValueError("Failure URL must identify a workflow run in this repository.")

    spec = importlib.util.spec_from_file_location(
        "deployment_report", Path(__file__).with_name("read-deployment-result.py")
    )
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    report = json.loads(Path(report_path).read_text())
    reader.validate(report, source, image, "false", exit_code)
    if report["outcome"] != "rolled_back" or exit_code in (0, 130, 143):
        raise ValueError("Recovery requires a verified non-test rollback after failure.")
    if report["stage"] not in {
        "starting_application", "verifying_image", "verifying_application", "verifying_assets"
    }:
        raise ValueError("This failure stage requires investigation rather than automatic code recovery.")
    previous = report.get("previous_commit", "")
    if not re.fullmatch(r"[a-f0-9]{40}", previous):
        raise ValueError("The restored image's source commit is unknown.")

    parents = git("rev-list", "--parents", "-n", "1", source).split()
    if len(parents) != 2:
        raise ValueError("Recovery supports single-parent squash commits only.")
    parent = parents[1]
    if "TanaSpace-Recovery: revert" in git("show", "-s", "--format=%B", source):
        raise ValueError("A recovery revert cannot trigger another recovery.")
    if git("rev-parse", f"{previous}^{{tree}}") != git("rev-parse", f"{parent}^{{tree}}"):
        raise ValueError("Restored production files differ from the proposed main recovery target.")

    pulls = github_json("api", f"repos/{repository}/commits/{source}/pulls?per_page=100")
    matches = [pr for pr in pulls
               if pr.get("merged_at") and pr.get("merge_commit_sha") == source
               and pr["base"]["ref"] == "main"
               and pr["base"]["repo"]["full_name"].lower() == repository.lower()]
    if len(matches) != 1 or type(matches[0]["number"]) is not int:
        raise ValueError("Expected exactly one merged PR for the failed commit.")
    original_pr = matches[0]["number"]
    if original_pr < 1:
        raise ValueError("Invalid original PR number.")
    branch = f"recovery/reapply-{original_pr}-{source[:12]}"

    with tempfile.TemporaryDirectory(prefix="tanaspace-recovery-") as temporary:
        worktree = Path(temporary) / "worktree"
        try:
            git("worktree", "add", "--detach", str(worktree), source)
            date = git("show", "-s", "--format=%cI", source)
            commit_env = dict(os.environ,
                              GIT_AUTHOR_NAME="TanaSpace Recovery",
                              GIT_AUTHOR_EMAIL="recovery@users.noreply.github.com",
                              GIT_COMMITTER_NAME="TanaSpace Recovery",
                              GIT_COMMITTER_EMAIL="recovery@users.noreply.github.com",
                              GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
            git("revert", "--no-commit", source, cwd=worktree, env=commit_env)
            git("commit", "-m", f"revert: recover deployment for #{original_pr}",
                "-m", f"TanaSpace-Recovery: revert\nOriginal-Commit: {source}\nOriginal-PR: #{original_pr}",
                cwd=worktree, env=commit_env)
            revert = git("rev-parse", "HEAD", cwd=worktree)
            if git("rev-parse", f"{revert}^{{tree}}") != git("rev-parse", f"{parent}^{{tree}}"):
                raise ValueError("Revert does not reproduce the working file tree.")
            git("revert", "--no-commit", revert, cwd=worktree, env=commit_env)
            git("commit", "-m", f"fix: reapply #{original_pr} after failed deployment",
                "-m", f"Original-Commit: {source}", cwd=worktree, env=commit_env)
            reapply = git("rev-parse", "HEAD", cwd=worktree)
            if git("rev-parse", f"{reapply}^{{tree}}") != git("rev-parse", f"{source}^{{tree}}"):
                raise ValueError("Replacement does not reproduce the failed change's files.")

            latest = github_json("api", f"repos/{repository}/git/ref/heads/main")["object"]["sha"]
            if latest not in (source, revert):
                raise ValueError("Main advanced beyond this failure; refusing to change it.")
            existing = github_json("pr", "list", "--repo", repository, "--base", "main",
                                   "--head", branch, "--state", "all", "--json", "url,state")
            if len(existing) > 1:
                raise ValueError("Multiple recovery PRs exist; investigate before proceeding.")
            if existing and latest != revert:
                raise ValueError("A recovery PR already exists but main is not at its revert.")

            if not existing:
                # Both refs update together. No force push; a competing main update rejects both.
                git("push", "--atomic", "origin", f"{revert}:refs/heads/main",
                    f"{reapply}:refs/heads/{branch}")
                body = Path(temporary) / "pr.md"
                body.write_text(
                    f"Deployment of #{original_pr} failed and the previous application release "
                    f"was restored and verified.\n\n"
                    f"Original PR: https://github.com/{repository}/pull/{original_pr}\n"
                    f"Failed commit: {source}\n"
                    f"Failed workflow: {run_url}\n"
                    f"Recovery revert: {revert}\n\n"
                    "This draft PR reapplies the original changes. Fix the deployment problem "
                    "here and wait for required checks before merging.\n"
                )
                pr_url = run_gh("pr", "create", "--repo", repository, "--draft", "--base", "main",
                                "--head", branch, "--title", f"Reapply #{original_pr}: deployment failed",
                                "--body-file", str(body))
            else:
                pr_url = existing[0]["url"]

            marker = f"<!-- tanaspace-recovery:{source} -->"
            pages = github_json("api", f"repos/{repository}/issues/{original_pr}/comments?per_page=100",
                                "--paginate", "--slurp")
            if not any(marker in (comment.get("body") or "") for page in pages for comment in page):
                comment = Path(temporary) / "comment.md"
                comment.write_text(
                    f"{marker}\nDeployment failed: {run_url}\n\n"
                    f"The previous production release was restored and verified. "
                    f"Main received recovery revert {revert}.\n\n"
                    f"Replacement PR: {pr_url}\n"
                )
                run_gh("pr", "comment", str(original_pr), "--repo", repository,
                       "--body-file", str(comment))

            summary = (f"## Repository recovery\n\nOriginal PR: #{original_pr}\n\n"
                       f"Main revert: {revert}\n\nReplacement PR: {pr_url}\n")
            print(summary)
            if os.environ.get("GITHUB_STEP_SUMMARY"):
                with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as output:
                    output.write(summary)
            return pr_url
        finally:
            try:
                git("worktree", "remove", "--force", str(worktree))
            except RuntimeError:
                pass


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError("Usage: recover-repository.py DEPLOYMENT_REPORT")
        recover(sys.argv[1])
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as error:
        print(f"Repository recovery stopped: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
