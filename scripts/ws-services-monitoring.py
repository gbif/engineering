import argparse
import json

import requests


# Per environment:
# - allowed_types: release/snapshot/unknown classification
# - allowed_versions: optional exact versions allowed (empty set means any version)
ENV_POLICY = {
  "prod": {
      "allowed_types": {"release"},
      "allowed_versions": set(),
  },
  "test": {
      "allowed_types": {"release"},
      "allowed_versions": set(),
  },
  "dev": {
      "allowed_types": {"release", "snapshot", "unknown"},
      "allowed_versions": set(),
  },
}

DEFAULT_ALLOWED_TYPES = {"release", "snapshot", "unknown"}


def fetch_instances(admin_url: str) -> list[dict]:
  r = requests.get(f"{admin_url}/instances", headers={"Accept": "application/json"}, timeout=30)
  r.raise_for_status()
  return r.json()


def load_instances_from_file(file_path: str) -> list[dict]:
  with open(file_path, "r", encoding="utf-8") as f:
    return json.load(f)


def get_env(instance: dict) -> str:
  metadata = instance.get("registration", {}).get("metadata", {})
  return (metadata.get("tags.env") or instance.get("tags", {}).get("env") or "unknown").lower()


def get_version(instance: dict) -> str:
  return (
      instance.get("info", {}).get("build", {}).get("version")
      or instance.get("buildVersion")
      or "unknown"
  )


def classify_version(version: str) -> str:
  v = (version or "").upper()
  if not v or v == "UNKNOWN":
    return "unknown"
  if "SNAPSHOT" in v:
    return "snapshot"
  return "release"


def validate_instance(instance: dict) -> list[str]:
  env = get_env(instance)
  version = get_version(instance)
  version_type = classify_version(version)
  policy = ENV_POLICY.get(env)

  allowed_types = (policy or {}).get("allowed_types", DEFAULT_ALLOWED_TYPES)
  allowed_versions = (policy or {}).get("allowed_versions", set())

  errors = []

  if version_type not in allowed_types:
    errors.append(f"{version_type} versions are not allowed in {env}")

  # If allowed_versions is configured for an env, enforce exact version pinning.
  if allowed_versions and version not in allowed_versions:
    allowed_csv = ", ".join(sorted(allowed_versions))
    errors.append(f"version {version} is not in allowed versions [{allowed_csv}] for {env}")

  return errors


def validate_instances(instances: list[dict]) -> list[dict]:
  violations = []

  for instance in instances:
    errors = validate_instance(instance)
    if not errors:
      continue

    violations.append(
        {
          "name": instance.get("registration", {}).get("name", "unknown-service"),
          "env": get_env(instance),
          "version": get_version(instance),
          "version_type": classify_version(get_version(instance)),
          "reason": "; ".join(errors),
        }
    )

  return violations


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(
      description="Validate service versions against environment policy."
  )
  parser.add_argument(
      "--admin-url",
      default="http://ws.gbif.org",
      help="Admin base URL used when fetching /instances",
  )
  parser.add_argument(
      "--instances-file",
      help="Load instances JSON from a local file instead of calling admin URL",
  )
  return parser.parse_args()


def main():
  args = parse_args()
  instances = load_instances_from_file(args.instances_file) if args.instances_file else fetch_instances(args.admin_url)
  violations = validate_instances(instances)

  if not violations:
    print("OK: no version/environment policy violations found.")
    return

  print(f"Found {len(violations)} policy violation(s):")
  for v in violations:
    print(
        f"- {v['name']}: env={v['env']} version={v['version']} "
        f"({v['version_type']}) -> {v['reason']}"
    )

  raise SystemExit(1)


if __name__ == "__main__":
  main()
