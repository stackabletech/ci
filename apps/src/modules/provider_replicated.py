"""
This module creates replicated.com clusters using the CLI
"""

import re
from time import sleep

from modules.command import run_command


def api_call_create_cluster(cluster_name, spec, platform_version, logger):
    """
    Call replicated.com API to create cluster

    cluster_name        name of the cluster
    spec                dict containing specification of cluster (vendor-specific)
    platform_version    version of the (K8s) platform
    logger              logger (String-consuming function)
    """
    command = f"replicated cluster create --name {cluster_name} --distribution {spec['distribution']} --instance-type {spec['instance-type']} --version {platform_version} --disk {spec['disk-size']} --nodes {spec['node-count']} --ttl 6h"
    logger(f"System call: --> {command}")
    exit_code, output = run_command(command, "replicated cluster create")
    if exit_code != 0:
        logger(
            f"Creating a cluster named '{cluster_name}' failed with exit code {exit_code} and the following message:"
        )
        logger(output)
        return False
    return True


def read_clusters_from_ls_output(output):
    """
    Reads a list of cluster (states) from the output of the Replicated CLI ls (list) command.

    output      string output

    Returns list of dicts (cluster metadata)
    """
    regex = re.compile(r"^([0-9a-f]*)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+.*")
    cluster_states = {}
    for line in output:
        matcher = regex.match(line)
        if matcher:
            cluster_states[matcher.group(2)] = {
                "id": matcher.group(1),
                "name": matcher.group(2),
                "distribution": matcher.group(3),
                "version": matcher.group(4),
                "state": matcher.group(5),
            }
    return cluster_states


def get_clusters():
    """
    Get all currently existing clusters.
    """
    exit_code, output = run_command("replicated cluster ls", "replicated cluster ls")
    if exit_code == 0:
        return read_clusters_from_ls_output(output)
    return {}


def get_cluster(name):
    """
    Get cluster by name
    """
    clusters = get_clusters()
    return clusters[name] if name in clusters else None


def wait_for_running_cluster(name, logger):
    """
    Wait until the named cluster is in the state 'running' (blocking operation)

    name        name of the cluster
    logger              logger (String-consuming function)
    """
    state = None
    while state != "running":
        logger(f"Cluster '{name}' is in state {state}")
        sleep(5)
        cluster = get_cluster(name)
        state = cluster["state"] if cluster else None


def update_kubeconfig(cluster, logger):
    """
    Updates the kubeconfig (in default folder /root/.kube/config/) for the given cluster
    """
    exit_code, output = run_command(
        f"replicated cluster kubeconfig {cluster['id']}", "update kubeconfig"
    )
    if exit_code != 0:
        for line in output:
            logger(line)
        return False
    return True


def write_cluster_info_file(cluster_info_file):
    """
    Writes a file containing basic cluster information
    """
    run_command(f"kubectl get nodes > {cluster_info_file}", "kubectl get nodes")


def create_cluster(id, spec, platform_version, cluster_info_file, logger):
    """
    Creates a replicated.com cluster with the given spec. (Blocking operation)

    id                  UUID of the cluster
    spec                dict containing specification of cluster (vendor-specific)
    platform_version    version of the (K8s) platform
    cluster_info_file   file to write cluster-specific information into
    logger              logger (String-consuming function)

    Returns vendor-specific cluster object.

    If not cluster could be created, the reason is logged and None is returned.
    """

    cluster_name = id

    logger(f"Creating cluster {cluster_name} on replicated.com...")

    if not api_call_create_cluster(cluster_name, spec, platform_version, logger):
        return None

    logger("Polling for the cluster to be up and running...")
    wait_for_running_cluster(cluster_name, logger)

    cluster = get_cluster(cluster_name)

    logger("Updating kubeconfig...")
    if not update_kubeconfig(cluster, logger):
        logger("Error updating kubeconfig.")
        return None

    write_cluster_info_file(cluster_info_file)

    return cluster_name


def terminate_cluster(id, logger):
    """
    Terminates the given cluster. (Blocking operation)

    id                  vendor-specific cluster object which was previously returned by create_cluster()
    logger              logger (String-consuming function)
    """
    logger(f"Terminating a cluster named '{id}' on replicated.com...")
    command = f"replicated cluster rm --name {id}"
    exit_code, output = run_command(command, "replicated cluster rm")
    if exit_code != 0:
        logger(
            f"Deleting the cluster named '{id}' failed with exit code {exit_code} and the following message:"
        )
        logger(output)
        return False
    return True
