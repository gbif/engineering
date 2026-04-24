import argparse
import base64
import json
import os
import re

import requests


DEFAULT_ENV_POLICY = {
  "prod": {
      "allowed_types": {"latest", "specific"},
      "allowed_versions": set(),
  },
  "test": {
      "allowed_types": {"latest", "specific"},
      "allowed_versions": set(),
  },
  "dev": {
      "allowed_types": {"latest", "specific", "snapshot", "unknown"},
      "allowed_versions": set(),
  },
}

DEFAULT_ALLOWED_TYPES = {"latest", "specific", "snapshot", "unknown"}


def load_json_file(file_path: str):
  with open(file_path, "r", encoding="utf-8") as f:
    return json.load(f)


def fetch_file_from_github(owner: str, repo: str, path: str, ref: str, token: str) -> str:
  url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
  headers = {
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
  }
  if token:
    headers["Authorization"] = f"Bearer {token}"

  response = requests.get(url, headers=headers, params={"ref": ref}, timeout=30)
  response.raise_for_status()

  payload = response.json()
  if not isinstance(payload, dict) or "type" not in payload:
    raise ValueError("Unexpected GitHub API response while reading file")

  if payload.get("type") != "file":
    raise ValueError(f"{path} is not a file in {owner}/{repo}@{ref}")

  encoded_content = payload.get("content", "")
  encoding = payload.get("encoding", "")

  if encoding != "base64":
    raise ValueError(f"Unsupported GitHub encoding '{encoding}' for {path}")

  return base64.b64decode(encoded_content).decode("utf-8")


def load_json_from_github(owner: str, repo: str, path: str, ref: str, token: str):
  content = fetch_file_from_github(owner, repo, path, ref, token)
  return json.loads(content)


def normalize_policy(raw_policy: dict) -> dict:
  normalized = {}

  for env, rules in raw_policy.items():
    allowed_types = set(rules.get("allowed_types", [])) if isinstance(rules, dict) else set()
    allowed_versions = set(rules.get("allowed_versions", [])) if isinstance(rules, dict) else set()
    normalized[env.lower()] = {
        "allowed_types": allowed_types,
        "allowed_versions": allowed_versions,
    }

  return normalized


def parse_config_sh(content: str) -> dict[str, str]:
  variables: dict[str, str] = {}
  line_re = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

  for raw_line in content.splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
      continue

    match = line_re.match(line)
    if not match:
      continue

    key = match.group(1)
    value = match.group(2).strip()

    if " #" in value:
      value = value.split(" #", 1)[0].strip()

    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
      value = value[1:-1]

    variables[key] = value

  return variables


def load_env_config_from_github(
    owner: str,
    repo: str,
    path_template: str,
    env: str,
    ref: str,
    token: str,
) -> dict[str, str]:
  path = path_template.format(env=env)
  content = fetch_file_from_github(owner, repo, path, ref, token)
  return parse_config_sh(content)


def classify_version(value: str) -> str:
  normalized = (value or "").strip().upper()
  if not normalized:
    return "unknown"

  if normalized == "LATEST":
    return "latest"

  if "SNAPSHOT" in normalized:
    return "snapshot"

  return "specific"


def validate_component(env: str, component: str, value: str, policy: dict) -> list[str]:
  env_rules = policy.get(env, {})
  value_type = classify_version(value)

  allowed_types = env_rules.get("allowed_types", DEFAULT_ALLOWED_TYPES)
  allowed_versions = env_rules.get("allowed_versions", set())

  errors: list[str] = []

  if value_type not in allowed_types:
    errors.append(f"{value_type} values are not allowed in {env}")

  # If configured, pin allowed exact values per environment.
  if allowed_versions and value not in allowed_versions:
    allowed_csv = ", ".join(sorted(allowed_versions))
    errors.append(f"value {value} is not in allowed values [{allowed_csv}] for {env}")

  return errors


def validate_env_config(env: str, config: dict[str, str], policy: dict) -> list[dict]:
  violations: list[dict] = []

  for component, value in config.items():
    errors = validate_component(env, component, value, policy)
    if not errors:
      continue

    violations.append(
        {
          "env": env,
          "component": component,
          "value": value,
          "value_type": classify_version(value),
          "reason": "; ".join(errors),
        }
    )

  return violations


def parse_env_list(envs_arg: str) -> list[str]:
  return [env.strip().lower() for env in envs_arg.split(",") if env.strip()]


def validate_configs_from_github(args: argparse.Namespace, github_token: str, policy: dict) -> list[dict]:
  violations: list[dict] = []

  for env in parse_env_list(args.envs):
    config = load_env_config_from_github(
        args.github_owner,
        args.github_repo,
        args.config_path_template,
        env,
        args.github_ref,
        github_token,
    )
    violations.extend(validate_env_config(env, config, policy))

  return violations


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
      description="Validate versions in environment config.sh files from a private GitHub repository."
  )

  parser.add_argument("--policy-file", help="Local JSON file with policy")
  parser.add_argument("--github-owner", required=True, help="GitHub repository owner")
  parser.add_argument("--github-repo", required=True, help="GitHub repository name")
  parser.add_argument("--github-ref", default="main", help="Git reference (branch/tag/sha)")
  parser.add_argument("--github-token", help="GitHub token for private repo access (fallback: GITHUB_TOKEN)")
  parser.add_argument(
      "--config-path-template",
      default="cli/{env}/config.sh",
      help="Path template to config file in repo. Use {env} placeholder, e.g. cli/{env}/config.sh",
  )
  parser.add_argument(
      "--envs",
      default="dev,test,prod",
      help="Comma-separated environments to validate, e.g. dev,test,prod",
  )

  return parser.parse_args()


def load_policy(args: argparse.Namespace) -> dict:
  if args.policy_file:
    return normalize_policy(load_json_file(args.policy_file))


  return DEFAULT_ENV_POLICY


def main():
  args = parse_args()
  github_token = args.github_token or os.environ.get("GITHUB_TOKEN", "")

  if not github_token:
    raise ValueError("GitHub token is required. Use --github-token or set GITHUB_TOKEN")

  policy = load_policy(args)
  violations = validate_configs_from_github(args, github_token, policy)

  if not violations:
    print("OK: no version/environment policy violations found.")
    return

  print(f"Found {len(violations)} policy violation(s):")
  for violation in violations:
    print(
        f"- {violation['component']}: env={violation['env']} value={violation['value']} "
        f"({violation['value_type']}) -> {violation['reason']}"
    )

  raise SystemExit(1)


if __name__ == "__main__":
  main()
