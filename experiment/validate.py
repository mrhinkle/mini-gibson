"""Validate the Jev extension without credentials or provider calls."""
import argparse
import json
from experiment.manifest import load_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--arm")
    args = parser.parse_args()
    try:
        policy = load_manifest(args.manifest, args.arm)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Jev manifest validation failed: {exc}\n")
    print(json.dumps({"enabled": policy.config.enabled, "scored": policy.scored,
                      "scored_loop": policy.config.scored_loop, "policy_sha256": policy.policy_sha256}, sort_keys=True))


if __name__ == "__main__":
    main()
