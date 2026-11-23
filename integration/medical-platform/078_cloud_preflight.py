"""Read-only target comparison. This command never provisions or migrates."""
import argparse
import json
from pathlib import Path
import subprocess
from urllib.parse import parse_qs, urlsplit


def checked_info(plan, cloud, folder, database, identity):
    expected = {"cloud_id", "folder_id", "database_id", "database_path",
                "endpoint", "service_account_sid", "production_folder_id",
                "environment"}
    if set(plan) != expected or any(not isinstance(v, str) or not v for v in plan.values()):
        raise ValueError("Incomplete approved plan")
    if plan["environment"] != "isolated-test" or plan["folder_id"] == plan["production_folder_id"]:
        raise ValueError("Dedicated QA folder required")
    actual, approved = urlsplit(database["endpoint"]), urlsplit(plan["endpoint"])
    if (approved.scheme != "grpcs" or approved.path or approved.query or approved.fragment
            or approved.username or approved.password or not approved.hostname
            or not approved.port or actual._replace(query="") != approved
            or parse_qs(actual.query) != {"database": [plan["database_path"]]}):
        raise ValueError("Endpoint or database path mismatch")
    if (cloud["id"] != plan["cloud_id"] or folder["cloud_id"] != plan["cloud_id"]
            or folder["id"] != plan["folder_id"] or database["folder_id"] != folder["id"]
            or database["id"] != plan["database_id"]
            or database["name"] != "medical-platform-pilot"
            or identity != plan["service_account_sid"]):
        raise ValueError("Cloud, folder, database or effective identity mismatch")


def read(*command):
    return subprocess.run(command, capture_output=True, text=True, timeout=30, check=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("approved_plan", type=Path)
    args = parser.parse_args()
    try:
        plan = json.loads(args.approved_plan.read_text())
        cloud = json.loads(read("yc", "resource-manager", "cloud", "get", "--id", plan["cloud_id"], "--format", "json"))
        folder = json.loads(read("yc", "resource-manager", "folder", "get", "--id", plan["folder_id"], "--format", "json"))
        database = json.loads(read("yc", "ydb", "database", "get", "--id", plan["database_id"], "--format", "json"))
        # Identity is checked against the same data-plane endpoint as the plan.
        # Validate discovered resource and URL before connecting to it.
        checked_info(plan, cloud, folder, database, plan["service_account_sid"])
        who = read("ydb", "--endpoint", plan["endpoint"], "--database", plan["database_path"],
                   "--use-metadata-credentials", "discovery", "whoami").strip()
        label = "User SID: "
        if not who.startswith(label):
            raise ValueError("Unknown identity output")
        checked_info(plan, cloud, folder, database, who.removeprefix(label))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        parser.exit(2, "Preflight refused: resource metadata or effective identity could not be verified.\n")
    print("Read-only identity checks passed. Schema and IAM qualification required; writes remain disabled.")


if __name__ == "__main__":
    main()
