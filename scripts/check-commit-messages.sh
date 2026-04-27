#!/usr/bin/env bash

set -euo pipefail

MIN_LENGTH="${MIN_LENGTH:-20}"
ISSUE_PATTERN="${ISSUE_PATTERN:-(#[0-9]+|https://github.com/.*/issues/[0-9]+)}"
ZERO_SHA="0000000000000000000000000000000000000000"

usage() {
  cat <<'EOF'
Usage:
  scripts/check-commit-messages.sh --base-sha <sha> --head-sha <sha>
  scripts/check-commit-messages.sh --range <git-revision-range>

Examples:
  scripts/check-commit-messages.sh --base-sha "$BASE_SHA" --head-sha "$HEAD_SHA"
  scripts/check-commit-messages.sh --range "origin/main..HEAD"
EOF
}

BASE_SHA=""
HEAD_SHA=""
RANGE=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-sha)
      BASE_SHA="${2:-}"
      shift 2
      ;;
    --head-sha)
      HEAD_SHA="${2:-}"
      shift 2
      ;;
    --range)
      RANGE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -n "$RANGE" ] && { [ -n "$BASE_SHA" ] || [ -n "$HEAD_SHA" ]; }; then
  echo "Use either --range OR --base-sha/--head-sha, not both." >&2
  exit 2
fi

if [ -z "$RANGE" ] && { [ -z "$BASE_SHA" ] || [ -z "$HEAD_SHA" ]; }; then
  echo "Missing required arguments." >&2
  usage >&2
  exit 2
fi

if [ -n "$RANGE" ]; then
  COMMITS="$(git rev-list "$RANGE" || true)"
else
  if [ "$BASE_SHA" = "$ZERO_SHA" ]; then
    COMMITS="$(git log "$HEAD_SHA" -1 --format='%H' || true)"
  else
    COMMITS="$(git rev-list "${BASE_SHA}..${HEAD_SHA}" || true)"
  fi
fi

if [ -z "$COMMITS" ]; then
  echo "No commits to check"
  exit 0
fi

FAILED=0

for COMMIT in $COMMITS; do
  MSG="$(git log --format=%B -n 1 "$COMMIT" | tr -d '\r')"
  SHORT="$(printf '%s\n' "$MSG" | head -1)"

  echo "-----------------------------"
  echo "Commit: $COMMIT"
  echo "Subject: $SHORT"

  # Keep behavior aligned with CI: merge commits are ignored.
  if printf '%s\n' "$SHORT" | grep -qE '^Merge (pull request|branch)'; then
    echo "SKIP: merge commit"
    continue
  fi

  if [ "${#SHORT}" -lt "$MIN_LENGTH" ]; then
    echo "FAIL: subject too short (${#SHORT} chars, min $MIN_LENGTH)"
    FAILED=1
  else
    echo "PASS: subject length"
  fi

  if ! printf '%s\n' "$MSG" | grep -qE "$ISSUE_PATTERN"; then
    echo "FAIL: missing issue reference (example: #123)"
    FAILED=1
  else
    echo "PASS: issue reference"
  fi
done

echo "-----------------------------"
if [ "$FAILED" -eq 1 ]; then
  echo "Commit message policy violation detected."
  echo "Rules:"
  echo "  - First line must be at least $MIN_LENGTH characters"
  echo "  - Message must include an issue reference (#123 or issue URL)"
  exit 1
fi

echo "All commit messages are valid"

