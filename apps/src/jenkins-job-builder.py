"""
Main module of the Jenkins Job builder application

See https://jenkins-job-builder.readthedocs.io/en/latest/
"""

import json
import os
import sys

import requests
from jinja2 import Template

import modules.catalog as catalog

# values of the params (given as env vars during Docker run)
param_jenkins_url = None
param_jenkins_username = None
param_jenkins_password = None

# keys for the env vars
PARAM_KEY_JENKINS_URL = "JENKINS_URL"
PARAM_KEY_JENKINS_USERNAME = "JENKINS_USERNAME"
PARAM_KEY_JENKINS_PASSWORD = "JENKINS_PASSWORD"

SLACK_CHANNEL = "#team-testing"
CLUSTER_LOGGING_ENDPOINT = "https://search.t2.stackable.tech"
OPENSEARCH_DASHBOARDS_URL = "https://logs.t2.stackable.tech"


def get_platform_metadata():
    """
    Creates a dict containing display name and version list for a given platform.
    """
    return {
        p["id"]: {"name": p["name"], "versions": list(p["versions"])} for p in catalog.platforms
    }


def init():
    """
    Initializes this app, checks if all params are provided as environment variables.

    Returns True if initialization succeeded, False otherwise.
    """
    global param_jenkins_url
    global param_jenkins_username
    global param_jenkins_password

    if PARAM_KEY_JENKINS_URL not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_JENKINS_URL} as an environment variable.")
        return False

    if PARAM_KEY_JENKINS_USERNAME not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_JENKINS_USERNAME} as an environment variable.")
        return False

    if PARAM_KEY_JENKINS_PASSWORD not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_JENKINS_PASSWORD} as an environment variable.")
        return False

    param_jenkins_url = os.environ[PARAM_KEY_JENKINS_URL]
    param_jenkins_username = os.environ[PARAM_KEY_JENKINS_USERNAME]
    param_jenkins_password = os.environ[PARAM_KEY_JENKINS_PASSWORD]

    return True


def generate_jjb_config():
    """
    Creates the config file for the JJB util using Jinja templating.
    """
    with open("/jjb/jjb.conf.j2") as t:
        template = Template(t.read())
        with open("/jjb/jjb.conf", "w") as f:
            f.write(template.render(os.environ))
            f.close()


def generate_jjb_file_maintenance_jobs():
    """
    Creates the JJB job definition file defining the maintenance jobs using Jinja templating.
    """
    with open("/jjb/maintenance.j2") as t:
        template = Template(t.read())
        with open("/jjb/maintenance.yaml", "w") as f:
            f.write(template.render(os.environ))
            f.close()


def generate_jjb_file_operator_weekly_test_jobs(platform_metadata):
    """
    Creates the JJB job definition files defining the weekly operator test jobs using Jinja templating.
    """
    with open("/jjb/trigger-weekly-tests.groovy.j2") as t:
        template = Template(t.read())
        with open("/jjb/trigger-weekly-tests.groovy", "w") as f:
            f.write(template.render({"testsuites": catalog.operator_tests}))
            f.close()
    with open("/jjb/operator_weekly_tests.j2") as t:
        template = Template(t.read())
        with open("/jjb/operator_weekly_tests.yaml", "w") as f:
            f.write(
                template.render(
                    {
                        "testsuites": catalog.operator_tests,
                        "platforms": platform_metadata,
                        "slack_channel": SLACK_CHANNEL,
                        "cluster_logging_endpoint": CLUSTER_LOGGING_ENDPOINT,
                        "opensearch_dashboards_url": OPENSEARCH_DASHBOARDS_URL,
                    }
                )
            )
            f.close()


def generate_jjb_file_operator_custom_test_jobs(platform_metadata, operator_versions):
    """
    Creates the JJB job definition file defining the custom operator test jobs using Jinja templating.
    """
    with open("/jjb/operator_custom_tests.j2") as t:
        template = Template(t.read())
        with open("/jjb/operator_custom_tests.yaml", "w") as f:
            f.write(
                template.render(
                    {
                        "testsuites": catalog.operator_tests,
                        "platforms": platform_metadata,
                        "operator_versions": operator_versions,
                        "slack_channel": SLACK_CHANNEL,
                        "cluster_logging_endpoint": CLUSTER_LOGGING_ENDPOINT,
                        "opensearch_dashboards_url": OPENSEARCH_DASHBOARDS_URL,
                    }
                )
            )
            f.close()


def execute_jjb():
    """
    Executes JJB for all job definition files
    """
    exit_code = os.system("jenkins-jobs --conf /jjb/jjb.conf update /jjb/maintenance.yaml")
    if exit_code != 0:
        print(
            f"ERROR: jenkins-jobs failed for maintenance.yaml with exit code {exit_code}",
            file=sys.stderr,
        )
        sys.exit(1)

    exit_code = os.system(
        "jenkins-jobs --conf /jjb/jjb.conf update /jjb/operator_weekly_tests.yaml"
    )
    if exit_code != 0:
        print(
            f"ERROR: jenkins-jobs failed for operator_weekly_tests.yaml with exit code {exit_code}",
            file=sys.stderr,
        )
        sys.exit(1)

    exit_code = os.system(
        "jenkins-jobs --conf /jjb/jjb.conf update /jjb/operator_custom_tests.yaml"
    )
    if exit_code != 0:
        print(
            f"ERROR: jenkins-jobs failed for operator_custom_tests.yaml with exit code {exit_code}",
            file=sys.stderr,
        )
        sys.exit(1)


def read_chart_versions() -> dict[str, list[str]]:
    """
    Find operator chart versions.

    Returns a dict like this

    {
        "airflow-operator": [
            "0.0.0-dev",
            "0.0.0-pr604",
            "0.0.0-pr609",
            "24.11.0",
            "24.11.1",
            "24.3.0",
            "24.7.0",
            "25.3.0"
        ],
        "commons-operator": [
            "0.0.0-dev",
            "24.3.0",
            "24.7.0",
            "25.3.0"
        ],
        ...
    }
    """
    ops = [
        "airflow-operator",
        "commons-operator",
        "druid-operator",
        "hbase-operator",
        "hdfs-operator",
        "hive-operator",
        "kafka-operator",
        "listener-operator",
        "nifi-operator",
        "opa-operator",
        "opensearch-operator",
        "secret-operator",
        "spark-k8s-operator",
        "superset-operator",
        "trino-operator",
        "zookeeper-operator",
    ]

    result = {}

    for op_name in ops:
        r = requests.get(
            f"https://oci.stackable.tech/v2/sdp-charts/{op_name}/tags/list", auth=("user", "pass")
        )
        if r.status_code == 200:
            result[op_name] = sorted([tag for tag in r.json()["tags"] if not tag.endswith(".sig")])
        else:
            print(f"failed to get tags for operator {op_name}: {r.text}", file=sys.stderr)
    return result


if __name__ == "__main__":
    print("testing.stackable.tech jenkins-job-builder")
    print()

    print("This app configures the Jenkins jobs.")
    print()

    if not init():
        exit(1)

    print("Step 1: Read current operator versions from Helm repository:")
    operator_versions = read_chart_versions()
    print()
    print(json.dumps(operator_versions, indent=4, sort_keys=True))
    print()

    print("Step 2: Read catalogs:")
    print()
    if not catalog.read_catalog(print):
        print("Error reading catalog, jenkins-job-builder is aborted.")
        exit(1)
    print("Successfully read catalogs.")
    print()

    print("Step 3: Collecting platform metadata (name and versions per platform)...")
    platform_metadata = get_platform_metadata()
    print("Successfully collected platform metadata.")
    print()

    print("Step 4: Generating JJB files...")
    generate_jjb_config()
    generate_jjb_file_maintenance_jobs()
    generate_jjb_file_operator_weekly_test_jobs(platform_metadata)
    generate_jjb_file_operator_custom_test_jobs(platform_metadata, operator_versions)
    print("Successfully generated JJB files.")
    print()

    print("Step 5: Running JJB...")
    execute_jjb()
    print("Successfully created Jenkins jobs.")
    print()
