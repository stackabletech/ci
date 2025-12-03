#!/usr/bin/env python3
"""
Update catalog/platforms.yaml with latest Kubernetes versions from Replicated and IONOS APIs.

This script:
1. Fetches available versions from `replicated cluster versions -o json`
2. Fetches available versions from `ionosctl k8s version list --output json`
3. Filters to keep only the latest patch version from each minor version line
4. Adds ARM alternatives where supported (Replicated only)
5. Updates the platforms.yaml file while preserving structure
6. Formats the YAML output using yq for consistency
"""

import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


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

    def __init__(self, platforms_yaml_path: str = "catalog/platforms.yaml"):
        self.platforms_yaml_path = Path(platforms_yaml_path)
        self.replicated_data = None

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

        # Limit to reasonable number of versions (e.g., last 5 minor versions)
        max_versions = 5
        if len(latest_versions) > max_versions:
            latest_versions = latest_versions[:max_versions]

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

        # Create a copy with ARM-specific changes
        arm_platform = platform.copy()
        arm_platform["id"] = platform["id"] + suffix
        # Use "-" instead of parentheses to avoid parsing issues in Jenkins
        arm_platform["name"] = platform["name"] + " - ARM"
        arm_platform["spec"] = platform["spec"].copy()
        arm_platform["spec"]["instance-type"] = arm_instance

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
                # Limit to 5 versions
                if len(latest_versions) > 5:
                    latest_versions = latest_versions[:5]
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

        # Check for missing distributions from Replicated and add them
        print("\n🔍 Checking for missing Replicated distributions...")
        for short_name, dist_data in distribution_lookup.items():
            if self.should_skip_distribution(short_name):
                continue

            platform_id = self.DISTRIBUTION_TO_PLATFORM.get(short_name)
            if not platform_id or platform_id in existing_platform_ids:
                continue  # Already exists or not mapped

            # Create new platform for this distribution
            # Generate name if not provided (rke2, oke don't have "name" field)
            platform_name = dist_data.get("name", f"{short_name.upper()} on replicated.com")
            print(f"  ➕ Adding new platform: {platform_id} ({platform_name})")

            # Get versions
            latest_versions = self.get_latest_patch_versions(
                dist_data["versions"], short_name
            )
            if len(latest_versions) > 5:
                latest_versions = latest_versions[:5]

            new_platform = {
                "id": platform_id,
                "name": platform_name,
                "provider": "replicated",
                "spec": {
                    "distribution": short_name,
                    "instance-type": "r1.xlarge",  # Default instance type
                    "node-count": 3,
                    "disk-size": 100,
                },
                "versions": latest_versions,
            }

            updated_platforms.append(new_platform)
            existing_platform_ids.add(platform_id)

            # Create ARM variant
            arm_platform = self.create_arm_variant(new_platform)
            if arm_platform:
                arm_id = arm_platform["id"]
                print(
                    f"    ➕ Adding ARM variant: {arm_id} (instance: {arm_platform['spec']['instance-type']})"
                )
                new_arm_platforms.append(arm_platform)
                existing_platform_ids.add(arm_id)

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
        """Save updated platforms to YAML file."""
        print(f"\n💾 Saving updated platforms to {self.platforms_yaml_path}...")
        try:
            with open(self.platforms_yaml_path, "w") as f:
                yaml.safe_dump(
                    data,
                    f,
                    sort_keys=True,
                    allow_unicode=True,
                    explicit_start=True,
                    indent=2,
                )
            print("✓ Saved successfully")

            # Fix YAML formatting using yq (PyYAML has known formatting issues)
            # https://github.com/yaml/pyyaml/issues/234
            print("🔧 Fixing YAML formatting with yq...")
            result = subprocess.run(
                ["yq", "-i", "-P", str(self.platforms_yaml_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                print("✓ YAML formatting fixed")
            else:
                print(f"⚠️  yq formatting failed (non-critical): {result.stderr}")
        except Exception as e:
            print(f"❌ Failed to save: {e}")
            sys.exit(1)

    def run(self) -> None:
        """Execute the update process."""
        print("=" * 60)
        print("Platform Version Updater")
        print("=" * 60)

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
