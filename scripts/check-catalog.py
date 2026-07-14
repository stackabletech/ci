#!/usr/bin/env python3
"""
Validate the catalog files for internal consistency.

platforms.yaml and operator-tests.yaml are maintained separately (the former by
update-platforms.py, the latter by hand), so they can drift apart. This check is
meant to run in CI so that drift is caught at edit time instead of surfacing
mid-test as a confusing "platform does not exist" error.

Checks:
1. Every platform's `provider` refers to a provider defined in platforms.yaml.
2. Every platform ID referenced by an operator test exists in platforms.yaml
   (a dangling reference is an error).
3. Every platform defined in platforms.yaml is used by at least one operator
   test (an unused platform is a warning, not an error).

Exits non-zero if any error-level check fails.
"""

import sys
from pathlib import Path
from typing import List

import yaml


def load_yaml(path: str):
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"❌ File not found: {path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"❌ Failed to parse {path}: {e}")
        sys.exit(1)


def check_catalog(
    platforms_path: str = "catalog/platforms.yaml",
    tests_path: str = "catalog/operator-tests.yaml",
) -> bool:
    """Return True if the catalog is consistent, False if there are errors."""
    print("=" * 60)
    print("Catalog Consistency Check")
    print("=" * 60)

    platforms_yaml = load_yaml(platforms_path)
    operator_tests = load_yaml(tests_path) or []

    platforms = platforms_yaml.get("platforms") or []
    providers = platforms_yaml.get("providers") or []
    provider_ids = {p["id"] for p in providers}
    platform_ids = {p["id"] for p in platforms}

    errors: List[str] = []
    warnings: List[str] = []

    # 1. Each platform's provider must be defined.
    for platform in platforms:
        provider = platform.get("provider")
        if provider not in provider_ids:
            errors.append(
                f"platform '{platform.get('id')}' has unknown provider "
                f"'{provider}' (known providers: {sorted(provider_ids)})"
            )

    # 2. Operator tests may only reference platforms that exist.
    referenced_ids = set()
    for operator_test in operator_tests:
        for platform_ref in operator_test.get("platforms", []):
            ref_id = platform_ref.get("id")
            referenced_ids.add(ref_id)
            if ref_id not in platform_ids:
                errors.append(
                    f"operator test '{operator_test.get('id')}' references "
                    f"platform '{ref_id}' which is not defined in {platforms_path}"
                )

    # 3. Platforms that no test uses are dead weight (warn only).
    for unused in sorted(platform_ids - referenced_ids):
        warnings.append(
            f"platform '{unused}' is defined but not used by any operator test"
        )

    for warning in warnings:
        print(f"⚠️  {warning}")
    for error in errors:
        print(f"❌ {error}")

    print("-" * 60)
    if errors:
        print(f"❌ Catalog validation FAILED with {len(errors)} error(s).")
        return False

    print(
        f"✓ Catalog OK: {len(platform_ids)} platforms, "
        f"{len(operator_tests)} operator tests, {len(warnings)} warning(s)."
    )
    return True


def main():
    # Allow running from anywhere as long as the catalog paths resolve.
    if not Path("catalog/platforms.yaml").exists():
        print("❌ Run this from the repository root (catalog/ not found).")
        sys.exit(1)

    if not check_catalog():
        sys.exit(1)


if __name__ == "__main__":
    main()
