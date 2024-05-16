import os
import uuid
import sys
import re
from subprocess import PIPE, TimeoutExpired, Popen
from time import sleep
from datetime import datetime, timedelta

uid_gid_output = '0:0'
replicated_distribution = None
replicated_instance_type = None
replicated_version = None
replicated_disk = None
replicated_nodes = None
operator_under_test = None


TARGET_FOLDER = "/target/"

TESTDRIVER_LOGFILE = f"{TARGET_FOLDER}testdriver.log"
TEST_OUTPUT_LOGFILE = f"{TARGET_FOLDER}test-output.log"
CLUSTER_INFO_FILE = f"{TARGET_FOLDER}cluster-info.txt"
OUTPUT_FILES = [ TESTDRIVER_LOGFILE, TEST_OUTPUT_LOGFILE, CLUSTER_INFO_FILE]

EXIT_CODE_CLUSTER_FAILED = 255

def init():

    global uid_gid_output
    global replicated_distribution 
    global replicated_instance_type
    global replicated_version
    global replicated_disk
    global replicated_nodes
    global operator_under_test

    if not 'REPLICATED_API_TOKEN' in os.environ:
        print("Error: Please supply REPLICATED_API_TOKEN as an environment variable.")
        return False

    if not 'REPLICATED_DISTRIBUTION' in os.environ:
        print("Error: Please supply REPLICATED_DISTRIBUTION as an environment variable.")
        return False

    if not 'REPLICATED_INSTANCE_TYPE' in os.environ:
        print("Error: Please supply REPLICATED_INSTANCE_TYPE as an environment variable.")
        return False

    if not 'REPLICATED_VERSION' in os.environ:
        print("Error: Please supply REPLICATED_VERSION as an environment variable.")
        return False

    if not 'REPLICATED_DISK_SIZE' in os.environ:
        print("Error: Please supply REPLICATED_DISK_SIZE as an environment variable.")
        return False

    if not 'REPLICATED_NODE_COUNT' in os.environ:
        print("Error: Please supply REPLICATED_NODE_COUNT as an environment variable.")
        return False

    if not 'OPERATOR_UNDER_TEST' in os.environ:
        print("Error: Please supply OPERATOR_UNDER_TEST as an environment variable.")
        return False

    replicated_distribution = os.environ['REPLICATED_DISTRIBUTION']
    replicated_instance_type = os.environ['REPLICATED_INSTANCE_TYPE']
    replicated_version = os.environ['REPLICATED_VERSION']
    replicated_disk = os.environ['REPLICATED_DISK_SIZE']
    replicated_nodes = os.environ['REPLICATED_NODE_COUNT']
    operator_under_test = os.environ['OPERATOR_UNDER_TEST']

    if not os.path.isdir(TARGET_FOLDER):
        print(f"Error: A target folder volume has to be supplied as {TARGET_FOLDER}. ")
        return False

    if 'UID_GID' in os.environ:
        uid_gid_output = os.environ['UID_GID']

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
    command = f"replicated cluster create --name {cluster_name} --distribution {replicated_distribution} --instance-type {replicated_instance_type} --version {replicated_version} --disk {replicated_disk} --nodes {replicated_nodes} --ttl 4h"
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


def clone_git_repo(operator):
    exit_code, output = run_command(f"git clone https://github.com/stackabletech/{operator}-operator.git", 'git clone')
    if exit_code != 0:
        for line in output:
            log(line)
        return False
    return True


def run_tests(operator):
    os.system(f"(cd {operator}-operator/ && python ./scripts/run-tests --log-level debug --test-suite nightly --parallel 4 2>&1; echo $? > /test_exit_code) | tee {TEST_OUTPUT_LOGFILE}")
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
    clone_git_repo(operator_under_test)
    log()

    log("Running tests...")
    test_exit_code = run_tests(operator_under_test)
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

