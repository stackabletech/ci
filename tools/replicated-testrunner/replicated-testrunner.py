import os
import uuid
import sys
import re
import hiyapyco
from subprocess import PIPE, TimeoutExpired, Popen
from time import sleep
from datetime import datetime, timedelta

uid_gid_output = '0:0'
testsuite = None
platform = None
platform_version = None
git_branch = None

catalog = None

TARGET_FOLDER = "/target/"

TESTDRIVER_LOGFILE = f"{TARGET_FOLDER}testdriver.log"
TEST_OUTPUT_LOGFILE = f"{TARGET_FOLDER}test-output.log"
CLUSTER_INFO_FILE = f"{TARGET_FOLDER}cluster-info.txt"
OUTPUT_FILES = [ TESTDRIVER_LOGFILE, TEST_OUTPUT_LOGFILE, CLUSTER_INFO_FILE]

EXIT_CODE_CLUSTER_FAILED = 255

def init():

    global uid_gid_output
    global testsuite
    global platform
    global platform_version
    global git_branch
    global catalog

    if not 'REPLICATED_API_TOKEN' in os.environ:
        print("Error: Please supply REPLICATED_API_TOKEN as an environment variable.")
        return False

    if not 'TESTSUITE' in os.environ:
        print("Error: Please supply TESTSUITE as an environment variable.")
        return False

    if not 'PLATFORM' in os.environ:
        print("Error: Please supply PLATFORM as an environment variable.")
        return False

    if not 'PLATFORM_VERSION' in os.environ:
        print("Error: Please supply VERSION as an environment variable.")
        return False


    testsuite = os.environ['TESTSUITE']
    platform = os.environ['PLATFORM']
    platform_version = os.environ['PLATFORM_VERSION']

    if not os.path.isdir(TARGET_FOLDER):
        print(f"Error: A target folder volume has to be supplied as {TARGET_FOLDER}. ")
        return False

    if 'UID_GID' in os.environ:
        uid_gid_output = os.environ['UID_GID']

    if 'GIT_BRANCH' in os.environ:
        git_branch = os.environ['GIT_BRANCH']

    catalog = hiyapyco.load("/replicated.yaml")

    return True


def set_target_folder_owner():
    """
        The target folder must be owned by the user/group given as UID_GID.
    """
    os.system(f"chown -R {uid_gid_output} {TARGET_FOLDER}")


def log(msg=""):
    """ Logs the given text message to stdout AND the logfile """
    print(msg)
    sys.stdout.flush()
    f = open(TESTDRIVER_LOGFILE, "a")
    f.write('{:%Y-%m-%d %H:%M:%S.%s} :: '.format(datetime.now()))
    f.write(f"{msg}\n")
    f.close()    


def output_to_string_array(byte_stream):
    return [line.strip() for line in byte_stream.decode("utf-8").splitlines()]


def one_line(string_array):
    return "\\n".join(string_array)


def run_command(command, description, timeout=60):
    """
        Execute command.
        Returns tuple (exit_code, output as multi-line)
    """
    proc = Popen(['/bin/bash', '-c', command], stdout=PIPE, stderr=PIPE)
    try:
        output, errs = proc.communicate(timeout=timeout)
    except TimeoutExpired:
        proc.kill()
        _, errs = proc.communicate()
        return -1, f"{description} timed out after {timeout} seconds."
    if proc.returncode != 0:
        return proc.returncode, output_to_string_array(errs)
    return 0, output_to_string_array(output)


def create_cluster(cluster_name):
    log(f"Creating a cluster named '{cluster_name}'")
    distribution = catalog['platforms'][platform]['distribution']
    instance_type = None
    if("instance-type" in catalog['testsuites'][testsuite]['platforms'][platform]):
        instance_type = catalog['testsuites'][testsuite]['platforms'][platform]['instance-type']
    else: 
        instance_type = catalog['platforms'][platform]['instance-type']
    disk_size = None
    if("disk-size" in catalog['testsuites'][testsuite]['platforms'][platform]):
        disk_size = catalog['testsuites'][testsuite]['platforms'][platform]['disk-size']
    else: 
        disk_size = catalog['platforms'][platform]['disk-size']
    node_count = None
    if("node-count" in catalog['testsuites'][testsuite]['platforms'][platform]):
        node_count = catalog['testsuites'][testsuite]['platforms'][platform]['node-count']
    else: 
        node_count = catalog['platforms'][platform]['node-count']
    command = f"replicated cluster create --name {cluster_name} --distribution {distribution} --instance-type {instance_type} --version {platform_version} --disk {disk_size} --nodes {node_count} --ttl 4h"
    exit_code, output = run_command(command, 'replicated cluster create')
    if exit_code != 0:
        log(f"Creating a cluster named '{cluster_name}' failed with exit code {exit_code} and message '{one_line(output)}'")
        return False
    return True


def terminate_cluster(cluster_name):
    log(f"Terminating a cluster named '{cluster_name}'")
    command = f"replicated cluster rm --name {cluster_name}"
    exit_code, output = run_command(command, 'replicated cluster rm')
    if exit_code != 0:
        log(f"Deleting the cluster named '{cluster_name}' failed with exit code {exit_code} and message '{one_line(output)}'")
        return False
    return True


def read_clusters_from_ls_output(output):
    regex = re.compile(r'^([0-9a-f]*)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+.*')
    cluster_states = {}
    for line in output:
        matcher = regex.match(line)
        if matcher:
            cluster_states[matcher.group(2)] = {
                'id': matcher.group(1),
                'name': matcher.group(2),
                'distribution': matcher.group(3),
                'version': matcher.group(4),
                'state': matcher.group(5)
            }
    return cluster_states


def get_clusters():
    exit_code, output = run_command('replicated cluster ls', 'replicated cluster ls')
    if exit_code == 0:
        return read_clusters_from_ls_output(output)
    return {}


def update_kubeconfig(cluster):
    exit_code, output = run_command(f"replicated cluster kubeconfig {cluster['id']}", 'update kubeconfig')
    if exit_code != 0:
        for line in output:
            log(line)
        return False
    return True


def clone_git_repo(repo):
    git_branch_option = f"-b { git_branch }" if git_branch else ""
    exit_code, output = run_command(f"git clone {git_branch_option} https://github.com/stackabletech/{repo}.git", 'git clone')
    if exit_code != 0:
        for line in output:
            log(line)
        return False
    return True


def run_tests(operator):
    os.system(f"(cd {operator}/ && python ./scripts/run-tests --log-level debug --test-suite nightly --parallel 4 2>&1; echo $? > /test_exit_code) | tee {TEST_OUTPUT_LOGFILE}")
    sleep(15)
    with open ("/test_exit_code", "r") as f:
        return int(f.read().strip())


def get_cluster(name):
    clusters = get_clusters()
    return clusters[name] if name in clusters else None


def wait_for_running_cluster(name):
    state = None
    while state != 'running':
        log(f"Cluster '{name}' is in state {state}")
        sleep(5)
        cluster = get_cluster(name)
        state = cluster['state'] if cluster else None


def get_cluster_info():
    exit_code, output = run_command('kubectl get nodes', 'kubectl get nodes')
    if exit_code == 0:
        return output
    return []


if __name__ == "__main__":

    print("Started replicated-testrunner by Stackable")
    print()

    if not init():
        exit(EXIT_CODE_CLUSTER_FAILED)

    set_target_folder_owner()

    if(not testsuite in catalog['testsuites']):
        log(f"The testsuite '{testsuite}' does not exist.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log(f"Selected testsuite: {testsuite}")

    if(not platform in catalog['platforms']):
        log(f"The platform '{platform}' does not exist.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    if(not platform_version in catalog['platforms'][platform]['versions']):
        log(f"The platform '{platform}' does not have a version {platform_version}.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log(f"Selected platform: {platform}, version {platform_version}")


    cluster_name = uuid.uuid4().hex
    log(f"Creating cluster {cluster_name}...")
    if not create_cluster(cluster_name):
        log("Error creating cluster.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log()

    log("Polling for the cluster to be up and running...")
    wait_for_running_cluster(cluster_name)
    cluster = get_cluster(cluster_name)
    log()

    log("Updating kubeconfig...")
    if not update_kubeconfig(cluster):
        log("Error updating kubeconfig.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log()

    cluster_info = get_cluster_info()
    if len(cluster_info) == 0:
        log("Error getting cluster info.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    for line in cluster_info:
        log(line)
    log()

    log("Cloning git repo...")
    clone_git_repo(testsuite)
    log()

    log("Running tests...")
    test_exit_code = run_tests(testsuite)
    log(f"Test exited with code {test_exit_code}")
    log()

    log(f"Terminating cluster {cluster_name}...")
    if not terminate_cluster(cluster_name):
        log("Error terminating cluster.")
    log()

    # Set output file ownership recursively 
    # This is important as the test script might have added files which are not controlled
    # by this Python script and therefore most probably are owned by root
    set_target_folder_owner()

    # The test's exit code is the container's exit code
    exit(test_exit_code)

