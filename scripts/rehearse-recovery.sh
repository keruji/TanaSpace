#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?Set GH_TOKEN}"
: "${GITHUB_REPOSITORY:?Set GITHUB_REPOSITORY}"
: "${SOURCE_COMMIT:?Set SOURCE_COMMIT}"
: "${REVERT_COMMIT:?Set REVERT_COMMIT}"
: "${REAPPLY_COMMIT:?Set REAPPLY_COMMIT}"
: "${ORIGINAL_PR:?Set ORIGINAL_PR}"

for commit in "$SOURCE_COMMIT" "$REVERT_COMMIT" "$REAPPLY_COMMIT"; do
  if [[ ! "$commit" =~ ^[a-f0-9]{40}$ ]]; then
    echo "Invalid commit reference."
    exit 1
  fi
done

if [[ ! "$ORIGINAL_PR" =~ ^[1-9][0-9]*$ ]]; then
  echo "Invalid original PR number."
  exit 1
fi

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

base_branch="recovery/rehearsal-base-${SOURCE_COMMIT:0:12}"
head_branch="recovery/rehearsal-reapply-${SOURCE_COMMIT:0:12}"

latest=$(gh api "repos/$GITHUB_REPOSITORY/git/ref/heads/main" --jq '.object.sha')
if [[ "$latest" != "$SOURCE_COMMIT" ]]; then
  echo "STOP: main has advanced. Rerun the rehearsal for current main."
  exit 1
fi

existing=$(gh pr list --repo "$GITHUB_REPOSITORY" \
  --base "$base_branch" --head "$head_branch" --state all \
  --json url --jq '.[0].url // empty')

if [[ -n "$existing" ]]; then
  echo "Rehearsal PR already exists: $existing"
  exit 0
fi

parent_commit=$(git rev-parse "$SOURCE_COMMIT^")
if [[ "$(git rev-parse "$REVERT_COMMIT^")" != "$SOURCE_COMMIT" ||
      "$(git rev-parse "$REAPPLY_COMMIT^")" != "$REVERT_COMMIT" ||
      "$(git rev-parse "$REVERT_COMMIT^{tree}")" != "$(git rev-parse "$parent_commit^{tree}")" ||
      "$(git rev-parse "$REAPPLY_COMMIT^{tree}")" != "$(git rev-parse "$SOURCE_COMMIT^{tree}")" ]]; then
  echo "STOP: rehearsal commits do not match the verified recovery structure."
  exit 1
fi

git push --atomic origin \
  "$REVERT_COMMIT:refs/heads/$base_branch" \
  "$REAPPLY_COMMIT:refs/heads/$head_branch"

body_file=$(mktemp)
trap 'rm -f -- "$body_file"' EXIT

cat > "$body_file" <<BODY
This is a repository recovery rehearsal, not a production deployment failure.

Source PR: https://github.com/$GITHUB_REPOSITORY/pull/$ORIGINAL_PR
Source commit: $SOURCE_COMMIT

The base branch contains a revert of the source commit. This draft PR
reapplies those changes. Both branches are temporary rehearsal branches.

The main branch and production application were not changed by this rehearsal.

Do not merge this PR. Close it after inspecting the changes.
BODY

pr_url=$(gh pr create --repo "$GITHUB_REPOSITORY" \
  --draft --base "$base_branch" --head "$head_branch" \
  --title "Recovery rehearsal: reapply #$ORIGINAL_PR" \
  --body-file "$body_file")

{
  echo "## Repository recovery rehearsal"
  echo ""
  echo "Draft PR: $pr_url"
  echo "Base: $base_branch"
  echo "Head: $head_branch"
  echo ""
  echo "Rehearsal complete. Main and production were not changed."
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
