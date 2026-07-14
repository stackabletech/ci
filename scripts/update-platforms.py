#!/usr/bin/env python3
"""
Update catalog/platforms.yaml with latest Kubernetes versions from Replicated and IONOS APIs.

This script:
1. Fetches available versions from `replicated cluster versions -o json`
2. Fetches available versions from `ionosctl k8s version list --output json`
3. Filters to keep only the latest patch version from each minor version line
4. Adds ARM alternatives where supported (Replicated only)
5. Rewrites platforms.yaml in a canonical, deterministic style

The script owns the layout of platforms.yaml end to end (see _CatalogDumper),
so it needs no external formatter and re-running it on an unchanged catalog
produces no diff. Do not hand-edit platforms.yaml; re-run this script instead.
"""

import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


class _CatalogDumper(yaml.SafeDumper):
    """Emit YAML in the catalog's canonical style so the script fully owns the file.

    Two deviations from PyYAML's defaults keep diffs limited to real changes:
    - Block sequences are indented under their key (the committed 2-space style)
      rather than sitting at the parent's indentation.
    - Anchors/aliases are never emitted: the script owns the whole file, so every
      list is written literally. This keeps entries independent (e.g. OpenShift
      and its ARM variant) instead of coupling them through a shared anchor.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, indentless=False)

    def ignore_aliases(self, data):
        return True


def _represent_str(dumper: yaml.Dumper, data: str):
    """Double-quote scalars that would otherwise parse as a non-string.

    Version lines like "1.34" must stay strings (bare 1.34 is a float). We defer
    the "would this parse as a number/bool/etc.?" decision to PyYAML's own
    resolver, and only override the quote character to double quotes to match the
    committed convention. Genuine strings (ids, names, "1.35.0") stay unquoted.
    """
    node = dumper.represent_scalar("tag:yaml.org,2002:str", data)
    resolved = dumper.resolve(yaml.nodes.ScalarNode, data, (True, False))
    if resolved != "tag:yaml.org,2002:str":
        node.style = '"'
    return node


_CatalogDumper.add_representer(str, _represent_str)


class PlatformUpdater:
    """Updates platforms.yaml with latest versions from Replicated and IONOS."""

    # ARM instance type mappings: x86 -> ARM
    ARM_INSTANCE_MAPPINGS = {
        # AWS EKS
        # There are m6g variants (ARM) but they are not supportey by Replicated so we have to pick the slightly larger m7g version
        "m6i.large": "m7g.large",
        "m6i.xlarge": "m7g.xlarge",
        "m6i.2xlarge": "m7g.2xlarge",
        # Azure AKS
        "Standard_D2S_v5": "Standard_D2ps_v5",
        "Standard_D4S_v5": "Standard_D4ps_v5",
        "Standard_D8S_v5": "Standard_D8ps_v5",
        "Standard_D16S_v5": "Standard_D16ps_v5",
        # GCP GKE
        "e2-standard-2": "t2a-standard-2",
        "e2-standard-4": "t2a-standard-4",
        "e2-standard-8": "t2a-standard-8",
        "e2-standard-16": "t2a-standard-16",
        "n2-standard-2": "t2a-standard-2",
        "n2-standard-4": "t2a-standard-4",
        # Replicated (k3s, kind, rke2)
        "r1.small": "r1a.small",
        "r1.medium": "r1a.medium",
        "r1.large": "r1a.large",
        "r1.xlarge": "r1a.xlarge",
        "r1.2xlarge": "r1a.2xlarge",
        # OKE
        "VM.Standard3.Flex": "VM.Standard.A1.Flex"
    }

    # Distribution short_name -> platform id mapping
    DISTRIBUTION_TO_PLATFORM = {
        "kind": "replicated-kind",
        "aks": "replicated-azure",
        "eks": "replicated-aws",
        "gke": "replicated-gke",
        "openshift": "replicated-openshift",
        "k3s": "replicated-k3s",
        "rke2": "replicated-rke2",
        "oke": "replicated-oke",
    }

    # Distributions to exclude
    EXCLUDED_DISTRIBUTIONS = {"embedded-cluster"}

    # Keep at most this many (latest) minor version lines per platform.
    MAX_VERSIONS_PER_PLATFORM = 5

    def __init__(self, platforms_yaml_path: str = "catalog/platforms.yaml"):
        self.platforms_yaml_path = Path(platforms_yaml_path)
        self.replicated_data = None

    def check_prerequisites(self) -> None:
        """Verify the provider CLIs used to fetch versions are available."""
        print("🔎 Checking prerequisites...")

        # The version data comes from these provider CLIs; fail early with a
        # clear message rather than midway through the update.
        for tool in ("replicated", "ionosctl"):
            if shutil.which(tool) is None:
                print(f"❌ `{tool}` not found on PATH. It is required to fetch versions.")
                sys.exit(1)

        print("✓ Prerequisites OK")

    def fetch_replicated_versions(self) -> List[Dict]:
        """Fetch available versions from Replicated API."""
        print("📡 Fetching versions from Replicated API...")
        try:
            result = subprocess.run(
                ["replicated", "cluster", "versions", "-o", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
            print(f"✓ Fetched data for {len(data)} distributions")
            return data
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to fetch versions: {e}")
            print(f"   stderr: {e.stderr}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            sys.exit(1)

    def fetch_ionos_versions(self) -> List[str]:
        """Fetch available versions from IONOS API."""
        print("📡 Fetching versions from IONOS API...")
        try:
            result = subprocess.run(
                ["ionosctl", "k8s", "version", "list", "--output", "json"],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)

            # `ionosctl ... --output json` does not return a JSON array. It
            # returns a JSON-encoded *string* holding a Go slice literal, e.g.
            #   "[1.34.2 1.33.3 1.32.7]"
            # Iterating that string directly (as this script used to) walks it
            # character by character and produces garbage versions like "7",
            # "6", ... — which silently wiped/corrupted the IONOS entry. Parse
            # the slice literal into an actual list of version strings.
            if isinstance(data, str):
                data = data.strip().strip("[]").split()

            if not isinstance(data, list) or not all(
                self.parse_version(v) != (0, 0, 0) for v in data
            ):
                print(f"❌ Unexpected IONOS version data: {data!r}")
                print("   Expected a list of versions like ['1.34.2', '1.33.3'].")
                sys.exit(1)

            print(f"✓ Fetched {len(data)} versions from IONOS")
            return data
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to fetch IONOS versions: {e}")
            print(f"   stderr: {e.stderr}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse JSON: {e}")
            sys.exit(1)

    @staticmethod
    def parse_version(version: str) -> Tuple[int, int, int]:
        """Parse version string into (major, minor, patch) tuple."""
        # Remove -okd suffix for OpenShift versions
        version = version.replace("-okd", "")
        parts = version.split(".")
        try:
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            patch = int(parts[2]) if len(parts) > 2 else 0
            return (major, minor, patch)
        except (ValueError, IndexError):
            return (0, 0, 0)

    def get_latest_patch_versions(
        self, versions: List[str], distribution: str
    ) -> List[str]:
        """
        Get only the latest patch version for each minor version line.

        For example: [1.30.1, 1.30.2, 1.31.1, 1.31.2] -> [1.30.2, 1.31.2]
        """
        if distribution in ["eks", "aks", "gke"]:
            # These only provide minor versions like "1.31", no filtering needed
            return sorted(versions, key=lambda v: self.parse_version(v), reverse=True)

        # Group versions by major.minor
        version_groups = defaultdict(list)
        for version in versions:
            major, minor, patch = self.parse_version(version)
            if major > 0:  # Skip invalid versions
                key = f"{major}.{minor}"
                version_groups[key].append((version, patch))

        # Get the latest patch version for each minor version
        latest_versions = []
        for minor_key, version_list in version_groups.items():
            # Sort by patch version and take the highest
            version_list.sort(key=lambda x: x[1], reverse=True)
            latest_version = version_list[0][0]
            latest_versions.append(latest_version)

        # Sort by version number, newest first
        latest_versions.sort(key=lambda v: self.parse_version(v), reverse=True)

        return latest_versions

    def get_arm_alternative(self, instance_type: str) -> str | None:
        """Get ARM alternative for an x86 instance type, if available."""
        return self.ARM_INSTANCE_MAPPINGS.get(instance_type)

    def load_existing_platforms(self) -> Dict:
        """Load existing platforms.yaml file."""
        print(f"📖 Loading existing platforms from {self.platforms_yaml_path}...")
        try:
            with open(self.platforms_yaml_path, "r") as f:
                data = yaml.safe_load(f)
            print(f"✓ Loaded {len(data.get('platforms', []))} platforms")
            return data
        except FileNotFoundError:
            print(f"❌ File not found: {self.platforms_yaml_path}")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"❌ Failed to parse YAML: {e}")
            sys.exit(1)

    def update_platform_versions(self, platform: Dict, distribution_data: Dict) -> Dict:
        """Update a platform entry with latest versions from Replicated."""
        distribution = platform["spec"]["distribution"]
        latest_versions = self.get_latest_patch_versions(
            distribution_data["versions"], distribution
        )

        latest_versions = latest_versions[: self.MAX_VERSIONS_PER_PLATFORM]

        platform["versions"] = latest_versions
        return platform

    def create_arm_variant(self, platform: Dict, suffix: str = "-arm") -> Dict | None:
        """Create an ARM variant of a platform if ARM instance type is available."""
        instance_type = platform["spec"].get("instance-type")
        if not instance_type:
            return None

        arm_instance = self.get_arm_alternative(instance_type)
        if not arm_instance:
            return None

        # Create a copy with ARM-specific changes. Copy the nested spec and
        # versions too, so the ARM variant never shares mutable state with its
        # x86 counterpart.
        arm_platform = platform.copy()
        arm_platform["id"] = platform["id"] + suffix
        # Use "-" instead of parentheses to avoid parsing issues in Jenkins
        arm_platform["name"] = platform["name"] + " - ARM"
        arm_platform["spec"] = platform["spec"].copy()
        arm_platform["spec"]["instance-type"] = arm_instance
        if "versions" in platform:
            arm_platform["versions"] = list(platform["versions"])

        return arm_platform

    def should_skip_distribution(self, short_name: str) -> bool:
        """Check if distribution should be skipped."""
        return short_name in self.EXCLUDED_DISTRIBUTIONS

    def update_platforms(self) -> Dict:
        """Main update logic."""
        print("\n🔄 Updating platforms...")

        # Load existing platforms
        platforms_data = self.load_existing_platforms()

        # Fetch latest versions from Replicated
        self.replicated_data = self.fetch_replicated_versions()

        # Fetch latest versions from IONOS
        ionos_versions = self.fetch_ionos_versions()

        # Build a lookup for distribution data
        distribution_lookup = {
            dist["short_name"]: dist for dist in self.replicated_data
        }

        # Build a set of existing platform IDs to avoid duplicates
        existing_platform_ids = {p["id"] for p in platforms_data["platforms"]}

        # Track which platforms we've updated
        updated_platforms = []
        new_arm_platforms = []

        # Update existing platforms
        for platform in platforms_data["platforms"]:
            platform_id = platform["id"]
            distribution = platform["spec"].get("distribution")

            # Handle IONOS platforms separately
            if platform_id.startswith("ionos-"):
                old_versions = platform.get("versions", [])
                # Apply same filtering logic as other platforms
                latest_versions = self.get_latest_patch_versions(
                    ionos_versions, "ionos"
                )
                latest_versions = latest_versions[: self.MAX_VERSIONS_PER_PLATFORM]
                platform["versions"] = latest_versions

                print(f"  ✓ Updated {platform_id}")
                print(f"    Old versions: {old_versions}")
                print(f"    New versions: {latest_versions}")

                updated_platforms.append(platform)
                continue

            # Skip non-replicated platforms
            if not platform_id.startswith("replicated-"):
                print(f"  ⏭️  Skipping {platform_id} (unknown provider)")
                updated_platforms.append(platform)
                continue

            # Skip if distribution not in Replicated data
            if distribution not in distribution_lookup:
                print(
                    f"  ⚠️  Skipping {platform_id} (distribution '{distribution}' not found in Replicated data)"
                )
                updated_platforms.append(platform)
                continue

            # Skip excluded distributions
            if self.should_skip_distribution(distribution):
                print(f"  ⏭️  Skipping {platform_id} (distribution excluded)")
                updated_platforms.append(platform)
                continue

            # Update versions
            distribution_data = distribution_lookup[distribution]
            old_versions = platform.get("versions", [])
            platform = self.update_platform_versions(platform, distribution_data)
            new_versions = platform["versions"]

            print(f"  ✓ Updated {platform_id}")
            print(f"    Old versions: {old_versions}")
            print(f"    New versions: {new_versions}")

            updated_platforms.append(platform)

            # Create ARM variant if available and not already exists
            if not platform_id.endswith("-arm"):
                arm_platform = self.create_arm_variant(platform)
                if arm_platform:
                    arm_id = arm_platform["id"]
                    # Only add if it doesn't exist in the original platforms.yaml
                    if arm_id not in existing_platform_ids:
                        print(
                            f"    ➕ Adding ARM variant: {arm_id} (instance: {arm_platform['spec']['instance-type']})"
                        )
                        new_arm_platforms.append(arm_platform)
                        existing_platform_ids.add(
                            arm_id
                        )  # Track it to avoid future duplicates

        # Warn about distributions Replicated offers that aren't in the catalog.
        # We deliberately do NOT auto-create them: the correct instance-type,
        # node-count and disk-size are provider-specific (a cloud distribution
        # like eks/aks/gke cannot use a Replicated `r1.*` instance type), so a
        # fabricated entry would be wrong and fail at test time. Adding a new
        # distribution is a rare, deliberate act — surface it and let a human
        # add it with the right spec.
        print("\n🔍 Checking for missing Replicated distributions...")
        for short_name, dist_data in distribution_lookup.items():
            if self.should_skip_distribution(short_name):
                continue

            platform_id = self.DISTRIBUTION_TO_PLATFORM.get(short_name)
            if not platform_id or platform_id in existing_platform_ids:
                continue  # Already exists or not mapped

            print(
                f"  ⚠️  Replicated offers distribution '{short_name}' "
                f"(would be '{platform_id}') which is not in {self.platforms_yaml_path}.\n"
                f"      Add it manually with the correct spec if it should be tested."
            )

        # Add new ARM platforms after their x86 counterparts
        final_platforms = []
        for platform in updated_platforms:
            final_platforms.append(platform)
            # Check if there's a pending ARM variant for this platform
            arm_variant = next(
                (p for p in new_arm_platforms if p["id"] == platform["id"] + "-arm"),
                None,
            )
            if arm_variant:
                final_platforms.append(arm_variant)
                new_arm_platforms.remove(arm_variant)

        platforms_data["platforms"] = final_platforms

        return platforms_data

    def save_platforms(self, data: Dict) -> None:
        """Save updated platforms to YAML file.

        The output is produced entirely by `_CatalogDumper`, which emits the
        catalog's canonical style directly. There is deliberately no external
        formatter (previously `yq`): the script owns the format on its own, so
        the result is deterministic regardless of what tools are installed.
        """
        print(f"\n💾 Saving updated platforms to {self.platforms_yaml_path}...")
        try:
            with open(self.platforms_yaml_path, "w") as f:
                yaml.dump(
                    data,
                    f,
                    Dumper=_CatalogDumper,
                    sort_keys=True,
                    allow_unicode=True,
                    explicit_start=True,
                    default_flow_style=False,
                    indent=2,
                )
            print("✓ Saved successfully")
        except Exception as e:
            print(f"❌ Failed to save: {e}")
            sys.exit(1)

    def run(self) -> None:
        """Execute the update process."""
        print("=" * 60)
        print("Platform Version Updater")
        print("=" * 60)

        self.check_prerequisites()
        updated_data = self.update_platforms()
        self.save_platforms(updated_data)

        print("\n" + "=" * 60)
        print("✅ Update complete!")
        print("=" * 60)
        print(f"\n📝 Review changes: git diff {self.platforms_yaml_path}")


def main():
    updater = PlatformUpdater()
    updater.run()


if __name__ == "__main__":
    main()
