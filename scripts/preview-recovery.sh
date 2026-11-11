#!/usr/bin/env bash
set -euo pipefail

failed_commit=${1:-}
: "${GH_TOKEN:?Set GH_TOKEN}"
: "${GITHUB_REPOSITORY:?Set GITHUB_REPOSITORY}"

if [[ ! "$failed_commit" =~ ^[a-f0-9]{40}$ ]]; then
  echo "Provide the full commit SHA to preview."
  exit 1
fi

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

check_main() {
  local latest
  latest=$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/main" --jq '.object.sha')
  if [[ "$latest" != "$failed_commit" ]]; then
    echo "STOP: main has advanced. Recovery must not undo newer changes."
    return 1
  fi
}

check_main

read -r -a commit_parts <<< "$(git rev-list --parents -n 1 "$failed_commit")"
if (( ${#commit_parts[@]} != 2 )); then
  echo "STOP: preview supports single-parent squash commits only."
  exit 1
fi
parent_commit=${commit_parts[1]}

message=$(git show -s --format=%B "$failed_commit")
if [[ "$message" == *"TanaSpace-Recovery: revert"* ]]; then
  echo "STOP: recovery commits must not trigger another recovery."
  exit 1
fi

temp_dir=$(mktemp -d)
worktree="$temp_dir/worktree"
cleanup() {
  git worktree remove --force "$worktree" >/dev/null 2>&1 || true
  rm -rf -- "$temp_dir"
}
trap cleanup EXIT

gh api "repos/$GITHUB_REPOSITORY/commits/$failed_commit/pulls?per_page=100" \
  > "$temp_dir/pulls.json"

pr_number=$(python3 - "$temp_dir/pulls.json" "$failed_commit" "$GITHUB_REPOSITORY" <<'PYTHON'
import json
import sys

with open(sys.argv[1]) as source:
    pulls = json.load(source)

matches = [
    pr for pr in pulls
    if pr.get("merged_at")
    and pr.get("merge_commit_sha") == sys.argv[2]
    and pr["base"]["ref"] == "main"
    and pr["base"]["repo"]["full_name"].lower() == sys.argv[3].lower()
]
if len(matches) != 1:
    raise SystemExit("STOP: expected exactly one merged PR for this commit.")
print(matches[0]["number"])
PYTHON
)

git worktree add --detach "$worktree" "$failed_commit"
git -C "$worktree" config user.name "TanaSpace Recovery"
git -C "$worktree" config user.email "recovery@users.noreply.github.com"

commit_date=$(git show -s --format=%cI "$failed_commit")
export GIT_AUTHOR_DATE="$commit_date"
export GIT_COMMITTER_DATE="$commit_date"

git -C "$worktree" revert --no-commit "$failed_commit"
git -C "$worktree" commit \
  -m "revert: recover deployment for #$pr_number" \
  -m "TanaSpace-Recovery: revert"
revert_commit=$(git -C "$worktree" rev-parse HEAD)

if [[ "$(git -C "$worktree" rev-parse HEAD^{tree})" != "$(git rev-parse "$parent_commit^{tree}")" ]]; then
  echo "STOP: revert does not reproduce the parent commit's files."
  exit 1
fi

git -C "$worktree" revert --no-commit "$revert_commit"
git -C "$worktree" commit -m "fix: reapply #$pr_number after failed deployment"
reapply_commit=$(git -C "$worktree" rev-parse HEAD)

if [[ "$(git -C "$worktree" rev-parse HEAD^{tree})" != "$(git rev-parse "$failed_commit^{tree}")" ]]; then
  echo "STOP: replacement does not reproduce the original files."
  exit 1
fi

check_main

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  {
    echo "original_pr=$pr_number"
    echo "source_commit=$failed_commit"
    echo "revert_commit=$revert_commit"
    echo "reapply_commit=$reapply_commit"
  } >> "$GITHUB_OUTPUT"
fi

{
  echo "## Recovery preview"
  echo ""
  echo "Original PR: https://github.com/$GITHUB_REPOSITORY/pull/$pr_number"
  echo "Original commit: $failed_commit"
  echo "Local revert commit: $revert_commit"
  echo "Local reapplication commit: $reapply_commit"
  echo "Proposed branch: recovery/reapply-$pr_number-${failed_commit:0:12}"
  echo ""
  echo "Preview passed. No commits were pushed and no PRs were created."
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
