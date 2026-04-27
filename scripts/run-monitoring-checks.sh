#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/reports/monitoring}"
MODE="${MODE:-both}"
ADMIN_URL="${ADMIN_URL:-http://ws.gbif.org}"
POLICY_FILE="${POLICY_FILE:-$ROOT_DIR/scripts/policy.json}"

GITHUB_OWNER="${GITHUB_OWNER:-}"
GITHUB_REPO="${GITHUB_REPO:-}"
GITHUB_REF="${GITHUB_REF:-main}"
CONFIG_PATH_TEMPLATE="${CONFIG_PATH_TEMPLATE:-cli/{env}/config.sh}"
ENVS="${ENVS:-dev,test,prod}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

usage() {
  cat <<'EOF'
Usage:
  scripts/run-monitoring-checks.sh [options]

Options:
  --mode [both|github|admin]          Which checks to run (default: both)
  --output-dir <path>                 Directory for logs and summary report
  --admin-url <url>                   Admin URL for ws-services-monitoring.py
  --policy-file <path>                Local policy JSON file (default: scripts/policy.json)
  --github-owner <owner>              GitHub owner/org (required for github mode)
  --github-repo <repo>                GitHub repo name (required for github mode)
  --github-ref <ref>                  Git ref/branch/tag for config files
  --config-path-template <template>   Config path template, e.g. cli/{env}/config.sh
  --envs <csv>                        Comma-separated env list, e.g. dev,test,prod
  --python-bin <python>               Python executable (default: python3)
  -h, --help                          Show this help message

Environment variables:
  GITHUB_TOKEN                        Required for github mode
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --admin-url)
      ADMIN_URL="${2:-}"
      shift 2
      ;;
    --policy-file)
      POLICY_FILE="${2:-}"
      shift 2
      ;;
    --github-owner)
      GITHUB_OWNER="${2:-}"
      shift 2
      ;;
    --github-repo)
      GITHUB_REPO="${2:-}"
      shift 2
      ;;
    --github-ref)
      GITHUB_REF="${2:-}"
      shift 2
      ;;
    --config-path-template)
      CONFIG_PATH_TEMPLATE="${2:-}"
      shift 2
      ;;
    --envs)
      ENVS="${2:-}"
      shift 2
      ;;
    --python-bin)
      PYTHON_BIN="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$MODE" in
  both|github|admin)
    ;;
  *)
    echo "Invalid --mode value: $MODE (expected both, github, or admin)" >&2
    exit 2
    ;;
esac

if [ ! -f "$POLICY_FILE" ]; then
  echo "Policy file not found: $POLICY_FILE" >&2
  exit 2
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  exit 2
fi

mkdir -p "$OUTPUT_DIR"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SUMMARY_FILE="$OUTPUT_DIR/summary-$TIMESTAMP.md"
GITHUB_LOG="$OUTPUT_DIR/github-monitor-$TIMESTAMP.log"
ADMIN_LOG="$OUTPUT_DIR/admin-monitor-$TIMESTAMP.log"

GITHUB_STATUS="SKIPPED"
ADMIN_STATUS="SKIPPED"

run_github_check() {
  if [ -z "$GITHUB_OWNER" ] || [ -z "$GITHUB_REPO" ]; then
    echo "--github-owner and --github-repo are required for github mode" >&2
    return 2
  fi

  if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "GITHUB_TOKEN is required for github mode" >&2
    return 2
  fi

  echo "Running GitHub config policy check..."
  "$PYTHON_BIN" "$ROOT_DIR/scripts/ws-services-monitoring-github.py" \
    --github-owner "$GITHUB_OWNER" \
    --github-repo "$GITHUB_REPO" \
    --github-ref "$GITHUB_REF" \
    --config-path-template "$CONFIG_PATH_TEMPLATE" \
    --envs "$ENVS" \
    --policy-file "$POLICY_FILE" \
    2>&1 | tee "$GITHUB_LOG"
}

run_admin_check() {
  echo "Running WS instances policy check..."
  "$PYTHON_BIN" "$ROOT_DIR/scripts/ws-services-monitoring.py" \
    --admin-url "$ADMIN_URL" \
    2>&1 | tee "$ADMIN_LOG"
}

if [ "$MODE" = "both" ] || [ "$MODE" = "github" ]; then
  if run_github_check; then
    GITHUB_STATUS="PASS"
  else
    GITHUB_STATUS="FAIL"
  fi
fi

if [ "$MODE" = "both" ] || [ "$MODE" = "admin" ]; then
  if run_admin_check; then
    ADMIN_STATUS="PASS"
  else
    ADMIN_STATUS="FAIL"
  fi
fi

{
  echo "# Monitoring Check Summary"
  echo
  echo "- Timestamp (UTC): $TIMESTAMP"
  echo "- Mode: $MODE"
  echo "- GitHub policy check: $GITHUB_STATUS"
  echo "- Admin URL policy check: $ADMIN_STATUS"
  echo
  echo "## Inputs"
  echo "- Policy file: $POLICY_FILE"
  echo "- Environments: $ENVS"
  echo "- GitHub source: ${GITHUB_OWNER:-n/a}/${GITHUB_REPO:-n/a}@$GITHUB_REF"
  echo "- Config path template: $CONFIG_PATH_TEMPLATE"
  echo "- Admin URL: $ADMIN_URL"
  echo
  echo "## Logs"
  [ -f "$GITHUB_LOG" ] && echo "- GitHub check log: $(basename "$GITHUB_LOG")"
  [ -f "$ADMIN_LOG" ] && echo "- Admin check log: $(basename "$ADMIN_LOG")"
} > "$SUMMARY_FILE"

echo "Wrote summary: $SUMMARY_FILE"

if [ "$GITHUB_STATUS" = "FAIL" ] || [ "$ADMIN_STATUS" = "FAIL" ]; then
  echo "Monitoring checks failed. See logs under: $OUTPUT_DIR" >&2
  exit 1
fi

echo "All requested monitoring checks passed."

