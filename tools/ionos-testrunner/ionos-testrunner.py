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
k8s_version = None
git_branch = None
operator_version = None
test_script_params = ''

catalog = None

TARGET_FOLDER = "/target/"

TESTDRIVER_LOGFILE = f"{TARGET_FOLDER}testdriver.log"
TEST_OUTPUT_LOGFILE = f"{TARGET_FOLDER}test-output.log"
OUTPUT_FILES = [ TESTDRIVER_LOGFILE, TEST_OUTPUT_LOGFILE]

EXIT_CODE_CLUSTER_FAILED = 255

def init():

    global uid_gid_output
    global testsuite
    global k8s_version
    global git_branch
    global operator_version
    global test_script_params
    global catalog

    if not 'IONOS_USERNAME' in os.environ:
        print("Error: Please supply IONOS_USERNAME as an environment variable.")
        return False

    if not 'IONOS_PASSWORD' in os.environ:
        print("Error: Please supply IONOS_PASSWORD as an environment variable.")
        return False

    if not 'TESTSUITE' in os.environ:
        print("Error: Please supply TESTSUITE as an environment variable.")
        return False

    if not 'K8S_VERSION' in os.environ:
        print("Error: Please supply K8S_VERSION as an environment variable.")
        return False

    if not 'OPERATOR_VERSION' in os.environ:
        print("Error: Please supply K8S_VERSION as an environment variable.")
        return False

    testsuite = os.environ['TESTSUITE']
    k8s_version = os.environ['K8S_VERSION']
    operator_version = os.environ['OPERATOR_VERSION']

    if not os.path.isdir(TARGET_FOLDER):
        print(f"Error: A target folder volume has to be supplied as {TARGET_FOLDER}. ")
        return False

    if 'UID_GID' in os.environ:
        uid_gid_output = os.environ['UID_GID']

    if 'GIT_BRANCH' in os.environ:
        git_branch = os.environ['GIT_BRANCH']

    if 'TEST_SCRIPT_PARAMS' in os.environ:
        test_script_params = os.environ['TEST_SCRIPT_PARAMS']

    catalog = hiyapyco.load("/ionos.yaml")

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


def get_testsuite_config(testsuite):
    testsuite_config = catalog['testsuites'][testsuite]
    if 'location' not in testsuite_config or 'cores' not in testsuite_config or 'node-count' not in testsuite_config or 'ram' not in testsuite_config:
        return None
    return testsuite_config


def output_to_string_array(byte_stream):
    return [line.strip() for line in byte_stream.decode("utf-8").splitlines()]


def run_command(command, description, timeout=60):
    """
        Execute command.
        Returns tuple (exit_code, output as line array)
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


def get_cluster_info():
    exit_code, output = run_command('kubectl get nodes', 'kubectl get nodes')
    if exit_code == 0:
        return output
    return []


def query_command_for_table(command, description):
    """
        Runs the given command and returns the results as a list of dicts
    """
    cmd_output = run_command(command, description)
    if cmd_output[0] != 0:
        return (cmd_output[0], None)
    headers = cmd_output[1][0]
    column_names = [c for c in headers.split(' ') if len(c)>0]
    columns = []
    index = 0
    while index < len(column_names):
        if index < len(column_names)-1:
            columns.append((column_names[index], headers.find(column_names[index]), headers.find(column_names[index+1])))
        else:
            columns.append((column_names[index], headers.find(column_names[index]), -1))
        index = index + 1
    result = []
    for line in cmd_output[1][1:]:
        result.append({ name: line[start:end].strip() if end != -1 else line[start:].strip() for (name, start, end) in columns })
    return (0, result)


def create_datacenter(name, location):
    command = f"ionosctl datacenter create --name {name} --location {location}"
    exit_code, output = query_command_for_table(command, 'create datacenter')
    if exit_code != 0:
        log(f"Creating a datacenter named '{name}' failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return output[0]['DatacenterId']


def get_datacenter(id):
    command = f"ionosctl datacenter list"
    exit_code, output = query_command_for_table(command, 'list datacenters')
    if exit_code != 0:
        log(f"Reading datacenters failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return next(iter([dc for dc in output if dc['DatacenterId']==id]), None)


def delete_datacenter(id):
    command = f"ionosctl datacenter delete --datacenter-id {id} --force"
    exit_code, output = run_command(command, 'delete datacenter')
    if exit_code != 0:
        log(f"Deleting the datacenter {id} failed with exit code {exit_code} and the following message:")
        print(output)
        return False
    return True


def wait_for_datacenter_state(id, target_state):
    datacenter = get_datacenter(id)
    state = datacenter['State'] if datacenter else None
    log(f"Datacenter {id} is in state {state}")
    while state != target_state:
        sleep(5)
        datacenter = get_datacenter(id)
        state = datacenter['State'] if datacenter else None
        log(f"Datacenter {id} is in state {state}")


def create_cluster(name, k8s_version):
    command = f"ionosctl k8s cluster create --name {name} --k8s-version {k8s_version}"
    exit_code, output = query_command_for_table(command, 'create cluster')
    if exit_code != 0:
        log(f"Creating a cluster named '{name}' failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return output[0]['ClusterId']


def get_cluster(id):
    command = f"ionosctl k8s cluster list"
    exit_code, output = query_command_for_table(command, 'list clusters')
    if exit_code != 0:
        log(f"Reading clusters failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return next(iter([c for c in output if c['ClusterId']==id]), None)


def delete_cluster(id):
    command = f"ionosctl k8s cluster delete --cluster-id {id} --force"
    exit_code, output = run_command(command, 'delete cluster')
    if exit_code != 0:
        log(f"Deleting the cluster {id} failed with exit code {exit_code} and the following message:")
        print(output)
        return False
    return True


def wait_for_cluster_state(id, target_state):
    cluster = get_cluster(id)
    state = cluster['State'] if cluster else None
    log(f"Cluster {id} is in state {state}")
    while state != target_state:
        sleep(5)
        cluster = get_cluster(id)
        state = cluster['State'] if cluster else None
        log(f"Cluster {id} is in state {state}")


def create_nodepool(name, cluster_id, datacenter_id, cores, node_count, ram):
    command = f"ionosctl k8s nodepool create --datacenter-id {datacenter_id} --cluster-id {cluster_id} --name {name} --cores {cores} --node-count {node_count} --ram {ram}"
    exit_code, output = query_command_for_table(command, 'create nodepool')
    if exit_code != 0:
        log(f"Creating a nodepool named '{name}' failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return output[0]['NodePoolId']


def get_nodepool(id, cluster_id):
    command = f"ionosctl k8s nodepool list --cluster-id {cluster_id}"
    exit_code, output = query_command_for_table(command, 'list nodepools')
    if exit_code != 0:
        log(f"Reading nodepools failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return next(iter([n for n in output if n['NodePoolId']==id]), None)


def delete_nodepool(id, cluster_id):
    command = f"ionosctl k8s nodepool delete --cluster-id {cluster_id} --nodepool-id {id} --force"
    exit_code, output = run_command(command, 'delete nodepool')
    if exit_code != 0:
        log(f"Deleting the nodepool {id} of cluster {cluster_id} failed with exit code {exit_code} and the following message:")
        print(output)
        return False
    return True


def wait_for_nodepool_state(id, cluster_id, target_state):
    nodepool = get_nodepool(id, cluster_id)
    state = nodepool['State'] if nodepool else None
    log(f"Nodepool {id} is in state {state}")
    while state != target_state:
        sleep(5)
        nodepool = get_nodepool(id, cluster_id)
        state = nodepool['State'] if nodepool else None
        log(f"Nodepool {id} is in state {state}")


def update_kubeconfig(cluster_id):
    exit_code, output = run_command(f"ionosctl k8s kubeconfig get --cluster-id {cluster_id} > /root/.kube/config", 'update kubeconfig')
    if exit_code != 0:
        for line in output:
            log(line)
        return False
    return True


def get_cluster_info():
    exit_code, output = run_command('kubectl get nodes', 'kubectl get nodes')
    if exit_code == 0:
        return output
    return []


def clone_git_repo(repo):
    git_branch_option = f"-b { git_branch }" if git_branch else ""
    exit_code, output = run_command(f"git clone {git_branch_option} https://github.com/stackabletech/{repo}.git", 'git clone')
    if exit_code != 0:
        for line in output:
            log(line)
        return False
    return True


def run_tests(operator, operator_version, parallel, test_script_params):
    """ 
    Runs the tests using the test script in the operator repo.

    operator:              name of the operator-repo (usually with suffix '-operator')
    operator_version:      Version of the operator to be tested
    parallel:              How many parallel tests should be run
    test_script_params:    additional (overriding) params
                           Every option included in this string replaces the default option value
    """ 
    params = ""
    params += " --log-level debug" if "--log-level" not in test_script_params else ""
    params += f" --operator {operator.replace('-operator','')}={operator_version}" if "--operator" not in test_script_params else ""
    params += f" --parallel {parallel}" if "--parallel" not in test_script_params else ""

    command = f"(cd {operator}/ && python ./scripts/run-tests {params} {test_script_params} 2>&1; echo $? > /test_exit_code) | tee {TEST_OUTPUT_LOGFILE}"
    log("Running the following test command:")
    log(command)
    os.system(command)
    sleep(15)
    with open ("/test_exit_code", "r") as f:
        return int(f.read().strip())


if __name__ == "__main__":

    # TODO Wenn Liste leer ist, gibt es Fehler, weil Ausgabe leer ist, das müssen wir abfangen!!!!!!!

    print("Started IONOS testrunner by Stackable")
    print()

    if not init():
        exit(EXIT_CODE_CLUSTER_FAILED)

    set_target_folder_owner()

    cluster_name = uuid.uuid4().hex[0:10]

    testsuite_config = get_testsuite_config(testsuite)
    if not testsuite_config:
        log(f"The testsuite {testsuite} is not correctly defined in the YAML file.")
        exit(EXIT_CODE_CLUSTER_FAILED)

    log(f"Creating datacenter '{cluster_name}'...")
    datacenter_id = create_datacenter(cluster_name, testsuite_config['location'])
    if not datacenter_id:
        log("Error creating datacenter.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log(f"Created datacenter '{cluster_name}' (id={datacenter_id})")
    wait_for_datacenter_state(datacenter_id, 'AVAILABLE')
    log(f"Datacenter '{cluster_name}' (id={datacenter_id}) is ready for use.")
    log()

    log(f"Creating K8s cluster '{cluster_name}'...")
    cluster_id = create_cluster(cluster_name, k8s_version)
    if not cluster_id:
        log("Error creating K8s cluster.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log(f"Created K8s cluster '{cluster_name}' (id={cluster_id})")
    wait_for_cluster_state(cluster_id, 'ACTIVE')
    log(f"K8s Cluster '{cluster_name}' (id={cluster_id}) is ready for use.")
    log()

    log(f"Creating nodepool '{cluster_name}'...")
    nodepool_id = create_nodepool(cluster_name, cluster_id, datacenter_id, testsuite_config['cores'], testsuite_config['node-count'], testsuite_config['ram'])
    if not nodepool_id:
        log("Error creating nodepool.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log(f"Created nodepool '{cluster_name}' (id={nodepool_id})")
    wait_for_nodepool_state(nodepool_id, cluster_id, 'ACTIVE')
    log(f"Nodepool '{cluster_name}' (id={nodepool_id}) is ready for use.")
    log()

    log("Updating kubeconfig...")
    if not update_kubeconfig(cluster_id):
        log("Error updating kubeconfig.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    log()

    log("Waiting 1 minute for the Cluster to become ready...")
    sleep(60)

    cluster_info = get_cluster_info()
    if len(cluster_info) == 0:
        log("Error getting cluster info.")
        exit(EXIT_CODE_CLUSTER_FAILED)
    for line in cluster_info:
        log(line)
    log()

    log(f"Selected testsuite: {testsuite}")

    log("Cloning git repo...")
    clone_git_repo(testsuite)
    log()

    log("Running tests...")
    parallel = testsuite_config['parallel'] if 'parallel' in testsuite_config else ''
    test_exit_code = run_tests(testsuite, operator_version, parallel, test_script_params)
    log(f"Test exited with code {test_exit_code}")
    log()

    if not delete_nodepool(nodepool_id, cluster_id):
        log('Error deleting nodepool')
        exit(EXIT_CODE_CLUSTER_FAILED)
    
    log(f"Deleting nodepool '{cluster_name}'...")
    wait_for_nodepool_state(nodepool_id, cluster_id, None)
    log(f"Nodepool '{cluster_name}' successfully deleted.")
    sleep(30)

    if not delete_cluster(cluster_id):
        log('Error deleting cluster')
        exit(EXIT_CODE_CLUSTER_FAILED)
    
    log(f"Deleting cluster '{cluster_name}'...")
    wait_for_cluster_state(cluster_id, None)
    log(f"Cluster '{cluster_name}' successfully deleted.")
    sleep(30)

    if not delete_datacenter(datacenter_id):
        log('Error deleting datacenter')
        exit(EXIT_CODE_CLUSTER_FAILED)
    
    log(f"Deleting datacenter '{cluster_name}'...")
    wait_for_datacenter_state(datacenter_id, None)
    log(f"Datacenter '{cluster_name}' successfully deleted.")

    # Set output file ownership recursively 
    # This is important as the test script might have added files which are not controlled
    # by this Python script and therefore most probably are owned by root
    set_target_folder_owner()

    # The test's exit code is the container's exit code
    #exit(test_exit_code)
