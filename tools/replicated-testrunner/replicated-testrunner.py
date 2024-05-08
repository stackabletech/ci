import os
import uuid
import re
import logging
from subprocess import PIPE, TimeoutExpired, Popen
from time import sleep

cluster_name = None

def check_prerequisites():
    if not 'REPLICATED_API_TOKEN' in os.environ:
        logging.error("Error: Please supply REPLICATED_API_TOKEN as an environment variable.")
        return False
    return True


def generate_random_cluster_name():
    global cluster_name
    cluster_name = uuid.uuid4().hex


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


def create_cluster():
    logging.info(f"Creating a cluster named '{cluster_name}'")
    command = f"replicated cluster create --name {cluster_name} --distribution openshift --instance-type r1.large --version 4.15.0-okd --ttl 4h  --disk 50"
    exit_code, output = run_command(command, 'replicated cluster create')
    if exit_code != 0:
        logging.error(f"Creating a cluster named '{cluster_name}' failed with exit code {exit_code} and message '{one_line(output)}'")
        return False
    return True


def get_cluster_states_from_ls_output(output):
    regex = re.compile(r'^[0-9a-f]*\s+(\S+)\s+\S+\s+\S+\s+(\S+)\s+.*')
    cluster_states = {}
    for line in output:
        matcher = regex.match(line)
        if matcher:
            cluster_states[matcher.group(1)] = matcher.group(2)
    return cluster_states


def get_cluster_states():
    exit_code, output = run_command('replicated cluster ls', 'replicated cluster ls')
    if exit_code == 0:
        return get_cluster_states_from_ls_output(output)
    return {}


def get_cluster_state():
    cluster_states = get_cluster_states()
    return cluster_states[cluster_name] if cluster_name in cluster_states else None


def wait_for_running_cluster():
    cluster_state = None
    while cluster_state != 'running':
        logging.info(f"Cluster '{cluster_name}' is in state {cluster_state}")
        sleep(5)
        cluster_state = get_cluster_state()


if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)
    logging.info("Started replicated-testrunner by Stackable")

    if not check_prerequisites():
        exit(1)

    generate_random_cluster_name()
    if not create_cluster():
        logging.error("Error creating cluster.")
        exit(1)
    logging.info("Created cluster.")

    logging.info("Polling for cluster to be up and running...")
    wait_for_running_cluster()


    logging.info("Finished replicated-testrunner by Stackable")
