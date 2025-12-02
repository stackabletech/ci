"""
    Main module of the Operator Test Runner application
"""
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta
from time import sleep

from jinja2 import Template

import modules.catalog as catalog
from modules.cluster import create_cluster, terminate_cluster
from modules.cluster_logging import install_cluster_logging
from modules.command import run_command

# values of the params (given as env vars during Docker run)
param_output_file_user = '0:0'
param_platform = None
param_platform_version = None
param_operator = None
param_git_branch = None
param_test_script_params = ''
param_cluster_logging_endpoint = None
param_cluster_logging_username = None
param_cluster_logging_password = None
param_opensearch_dashboards_url = None

# keys for the env vars
PARAM_KEY_PLATFORM = 'PLATFORM'
PARAM_KEY_PLATFORM_VERSION = 'PLATFORM_VERSION'
PARAM_KEY_OPERATOR = 'OPERATOR'
PARAM_KEY_OUTPUT_FILE_USER = 'OUTPUT_FILE_USER'
PARAM_KEY_REPLICATED_API_TOKEN = 'REPLICATED_API_TOKEN'
PARAM_KEY_IONOS_USERNAME = 'IONOS_USERNAME'
PARAM_KEY_IONOS_PASSWORD = 'IONOS_PASSWORD'
PARAM_KEY_GIT_BRANCH = 'GIT_BRANCH'
PARAM_KEY_OPERATOR_VERSION = 'OPERATOR_VERSION'
PARAM_KEY_TEST_SCRIPT_PARAMS = 'TEST_SCRIPT_PARAMS'
PARAM_KEY_CLUSTER_LOGGING_ENDPOINT = 'CLUSTER_LOGGING_ENDPOINT'
PARAM_KEY_CLUSTER_LOGGING_USERNAME = 'CLUSTER_LOGGING_USERNAME'
PARAM_KEY_CLUSTER_LOGGING_PASSWORD = 'CLUSTER_LOGGING_PASSWORD'
PARAM_KEY_OPENSEARCH_DASHBOARDS_URL = 'OPENSEARCH_DASHBOARDS_URL'

# by convention, this is the return code for "unstable cluster"
EXIT_CODE_CLUSTER_FAILED = 255

# constants for the file handling
TARGET_FOLDER = "/target/"
TESTDRIVER_LOGFILE = f"{TARGET_FOLDER}testdriver.log"
TEST_OUTPUT_LOGFILE = f"{TARGET_FOLDER}test-output.log"
CLUSTER_INFO_FILE = f"{TARGET_FOLDER}cluster-info.txt"
LOG_INDEX_LINKS_FILE = f"{TARGET_FOLDER}logs.html"

def init():
    """
        Initializes this app, checks if all params are provided as environment variables.

        Returns True if initialization succeeded, False otherwise.
    """
    global param_platform
    global param_platform_version
    global param_operator
    global param_output_file_user
    global param_operator_version
    global param_git_branch
    global param_test_script_params
    global param_cluster_logging_endpoint
    global param_cluster_logging_username
    global param_cluster_logging_password
    global param_opensearch_dashboards_url

    if PARAM_KEY_REPLICATED_API_TOKEN not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_REPLICATED_API_TOKEN} as an environment variable.")
        return False

    if PARAM_KEY_IONOS_USERNAME not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_IONOS_USERNAME} as an environment variable.")
        return False

    if PARAM_KEY_IONOS_PASSWORD not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_IONOS_PASSWORD} as an environment variable.")
        return False

    if PARAM_KEY_PLATFORM not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_PLATFORM} as an environment variable.")
        return False

    if PARAM_KEY_PLATFORM_VERSION not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_PLATFORM_VERSION} as an environment variable.")
        return False

    if PARAM_KEY_OPERATOR not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_OPERATOR} as an environment variable.")
        return False

    if PARAM_KEY_OPERATOR_VERSION not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_OPERATOR_VERSION} as an environment variable.")
        return False

    if PARAM_KEY_CLUSTER_LOGGING_ENDPOINT not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_CLUSTER_LOGGING_ENDPOINT} as an environment variable.")
        return False

    if PARAM_KEY_CLUSTER_LOGGING_USERNAME not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_CLUSTER_LOGGING_USERNAME} as an environment variable.")
        return False

    if PARAM_KEY_CLUSTER_LOGGING_PASSWORD not in os.environ:
        print(f"Error: Please supply {PARAM_KEY_CLUSTER_LOGGING_PASSWORD} as an environment variable.")
        return False

    param_platform = os.environ[PARAM_KEY_PLATFORM].strip()
    param_platform_version = os.environ[PARAM_KEY_PLATFORM_VERSION].strip()
    param_operator = os.environ[PARAM_KEY_OPERATOR].strip()
    param_operator_version = os.environ[PARAM_KEY_OPERATOR_VERSION].strip()
    param_cluster_logging_endpoint = os.environ[PARAM_KEY_CLUSTER_LOGGING_ENDPOINT].strip()
    param_cluster_logging_username = os.environ[PARAM_KEY_CLUSTER_LOGGING_USERNAME].strip()
    param_cluster_logging_password = os.environ[PARAM_KEY_CLUSTER_LOGGING_PASSWORD].strip()

    if not os.path.isdir(TARGET_FOLDER):
        print(f"Error: A target folder volume has to be supplied as mount on {TARGET_FOLDER}. ")
        return False

    if PARAM_KEY_OUTPUT_FILE_USER in os.environ:
        param_output_file_user = os.environ[PARAM_KEY_OUTPUT_FILE_USER].strip()

    if PARAM_KEY_GIT_BRANCH in os.environ:
        param_git_branch = os.environ[PARAM_KEY_GIT_BRANCH].strip()

    if PARAM_KEY_TEST_SCRIPT_PARAMS in os.environ:
        param_test_script_params = os.environ[PARAM_KEY_TEST_SCRIPT_PARAMS].strip()

    if PARAM_KEY_OPENSEARCH_DASHBOARDS_URL in os.environ:
        param_opensearch_dashboards_url = os.environ[PARAM_KEY_OPENSEARCH_DASHBOARDS_URL].strip()

    return True


def set_target_folder_owner():
    """
        As the Docker container is run with the root user (0:0), the files it produces will not be manageable by the Jenkins user.
        That's why a UID/GID combo is to be specified as the OUTPUT_FILE_USER env var.
        This method recursively sets the ownership of the output files.
    """
    os.system(f"chown -R {param_output_file_user} {TARGET_FOLDER}")


def log(msg=""):
    """ 
        Logs the given text message to stdout AND the logfile.
    """
    print(msg)
    sys.stdout.flush()
    f = open(TESTDRIVER_LOGFILE, "a")
    f.write(f'{datetime.now(UTC):%Y-%m-%d %H:%M:%S.%s} :: ')
    f.write(f"{msg}\n")
    f.close()


def clone_git_repo(repo):
    """
        Clones the given Stackable GitHub repo
    """
    git_branch_option = f"-b { param_git_branch }" if param_git_branch else ""
    exit_code, output = run_command(f"git clone {git_branch_option} https://github.com/stackabletech/{repo}.git", 'git clone')
    if exit_code != 0:
        for line in output:
            log(line)
        return False
    return True


def run_tests(operator, operator_version, test_script_params):
    """
    Runs the tests using the test script in the operator repo.
    The test script can be either 'run-tests' (default) or 'auto-retry-tests.py'
    based on the operator's catalog configuration.

    operator:              name of the operator-repo (usually with suffix '-operator')
    operator_version:      Version of the operator to be tested
    test_script_params:    additional params
    """

    # Get test script configuration from catalog
    test_script = catalog.get_test_script(operator)
    log(f"Using test script: {test_script}")

    # Step 1: Installation of the SDP (retried max. 10 times to reduce flakiness)
    # This step is always done with run-tests regardless of the test script choice
    command_install_sdp = f"cd {operator}/ && python ./scripts/run-tests --skip-tests --operator {operator.replace('-operator','')}={operator_version}"
    log("Running the following command to install SDP for test:")
    log(command_install_sdp)
    exit_code, output = run_command(command_install_sdp, 'install sdp', retries=10, delay=60)
    if exit_code != 0:
        for line in output:
            log(line)
        return exit_code

    # Step 2: Run the actual tests
    # (The aux. method run_command() is NOT used here because we want the output to be streamed, not captured!)
    if test_script == 'auto-retry-tests.py':
        # Use auto-retry test runner
        retry_config = catalog.get_auto_retry_config(operator)
        log(f"Auto-retry configuration: attempts_parallel={retry_config['attempts_parallel']}, "
            f"attempts_serial={retry_config['attempts_serial']}, "
            f"keep_failed_namespaces={retry_config['keep_failed_namespaces']}")

        # Extract parallel value from test_script_params (default to 0)
        parallel_value = "0"
        if '--parallel' in test_script_params:
            try:
                parts = test_script_params.split('--parallel')
                if len(parts) > 1:
                    parallel_value = parts[1].strip().split()[0]
            except:
                pass

        # Build command for auto-retry-tests.py
        command_parts = [
            f"cd {operator}/",
            "&&",
            "python ./scripts/auto-retry-tests.py",
            f"--parallel {parallel_value}",
            f"--attempts-parallel {retry_config['attempts_parallel']}",
            f"--attempts-serial {retry_config['attempts_serial']}",
        ]

        # Add keep-failed-namespaces flag if configured to keep them
        if retry_config['keep_failed_namespaces']:
            command_parts.append("--keep-failed-namespaces")

        # Add extra args from test_script_params (excluding --parallel which we already handled)
        extra_params = []
        skip_next = False
        for param in test_script_params.split():
            if skip_next:
                skip_next = False
                continue
            if param == '--parallel':
                skip_next = True
                continue
            extra_params.append(param)

        if extra_params:
            command_parts.append("--extra-args")
            command_parts.extend(extra_params)

        command_parts.extend(["2>&1", ";", "echo $? > /test_exit_code"])
        command_run_tests = f"({' '.join(command_parts)}) | tee {TEST_OUTPUT_LOGFILE}"

    else:
        # Use traditional run-tests script
        params = " --log-level debug" if "--log-level" not in test_script_params else ""
        command_run_tests = f"(cd {operator}/ && python ./scripts/run-tests --skip-release {params} {test_script_params} 2>&1; echo $? > /test_exit_code) | tee {TEST_OUTPUT_LOGFILE}"

    log("Running the following test command:")
    log(command_run_tests)
    os.system(command_run_tests)
    sleep(15)
    with open ("/test_exit_code") as f:
        return int(f.read().strip())

def write_logs_html(cluster_id, timestamp_start, timestamp_stop, opensearch_dashboards_url):
    """
        The output file 'logs.html' contains links to the OpenSearch Dashboards application which
        are prepared to filter the matching cluster id and timeframe.
    """

    date_from = (timestamp_start - timedelta(hours=0, minutes=5)).strftime("%Y-%m-%dT%H:%M:00Z")
    date_to = (timestamp_stop + timedelta(hours=0, minutes=5)).strftime("%Y-%m-%dT%H:%M:00Z")

    with open ("/src/modules/.cluster_logging/logs.html.j2") as f:
        logs_html = Template(f.read())

    with open (LOG_INDEX_LINKS_FILE, 'w') as f:
        f.write(logs_html.render( { 'cluster_id': cluster_id, 'date_from': date_from, 'date_to': date_to, 'opensearch_dashboards_url': opensearch_dashboards_url } ))
        f.close()


if __name__ == "__main__":

    job_start_timestamp_utc = datetime.now(UTC)

    print("testing.stackable.tech operator-test-runner")
    print()

    print("This app runs an operator integration test.")
    print()

    if not init():
        exit(EXIT_CODE_CLUSTER_FAILED)

    set_target_folder_owner()

    log("Reading catalog...")
    if not catalog.read_catalog(log):
        log("Error reading catalog, operator-test-runner is aborted.")
        exit(EXIT_CODE_CLUSTER_FAILED)

    # Read the platform and version data from the catalog
    platform = catalog.get_platform(param_platform)
    if not platform:
        log(f"The platform '{param_platform}' does not exist.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    if param_platform_version not in platform['versions']:
        log(f"The version '{param_platform_version}' does not exist for platform '{param_platform}'.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log(f"Test running on platform '{platform['id']}', version {param_platform_version}.")

    # Read the cluster spec for the given platform
    cluster_spec = catalog.get_spec_for_operator_test(param_operator, platform['id'], log)
    if not cluster_spec:
        log("Cluster spec could not be determined.")
        exit(EXIT_CODE_CLUSTER_FAILED)

    log(f"Test running on Git Branch {param_git_branch} with the test script parameters '{param_test_script_params}'...")

    # random cluster ID
    cluster_id = uuid.uuid4().hex

    log("Creating cluster...")
    cluster = create_cluster(platform['provider'], cluster_id, cluster_spec, param_platform_version, CLUSTER_INFO_FILE, log)
    if not cluster:
        log("Cluster could not be created.")
        exit(EXIT_CODE_CLUSTER_FAILED)

    log("Cloning git repo...")
    clone_git_repo(param_operator)

    log("Waiting 1 minute for the cluster to become ready...")
    sleep(60)

    log("Install Cluster Logging (powered by Vector)...")
    installed_cluster_logging = install_cluster_logging(cluster_id, param_cluster_logging_endpoint, param_cluster_logging_username, param_cluster_logging_password, log)
    if installed_cluster_logging:
        log("Installed Cluster Logging (powered by Vector).")
    else:
        log("Error installing Cluster Logging, continuing without it...")
    set_target_folder_owner()

    log("Waiting 1 minute for the cluster logging to become ready...")
    sleep(60)

    log("Running tests...")
    test_exit_code = run_tests(param_operator, param_operator_version, param_test_script_params)
    log(f"Test exited with code {test_exit_code}")
    log()

    log("Waiting 1 minute to allow logs to be processed...")
    sleep(60)

    termination_successful = terminate_cluster(platform['provider'], cluster, log)

    job_finished_timestamp_utc = datetime.now(UTC)

    # Write file which links to the logs if URL set
    if param_opensearch_dashboards_url:
        write_logs_html(cluster_id, job_start_timestamp_utc, job_finished_timestamp_utc, param_opensearch_dashboards_url)

    # Set output file ownership recursively
    # This is important as the test script might have added files which are not controlled
    # by this Python script and therefore most probably are owned by root
    set_target_folder_owner()

    if not termination_successful:
        log("Cluster could not be terminated.")
        exit(EXIT_CODE_CLUSTER_FAILED)

    exit(test_exit_code)
