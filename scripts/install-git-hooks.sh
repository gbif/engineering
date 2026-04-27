#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

chmod +x "$REPO_ROOT/scripts/check-commit-messages.sh"
chmod +x "$REPO_ROOT/.githooks/pre-push"

git config core.hooksPath .githooks

echo "Git hooks installed."
echo "Configured core.hooksPath=.githooks"
echo "pre-push hook now checks commit messages locally before push."

