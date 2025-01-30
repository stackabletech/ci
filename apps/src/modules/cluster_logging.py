"""
    This module installs the "cluster logging" on a test cluster.

    "cluster logging" refers to the ability of a cluster to forward the logs
    (K8s Events, Stackable Operator, Stackable Products) to our centralized
    log index.
"""

from modules.command import run_command

def install_cluster_logging(cluster_id, endpoint, username, password, logger):
    """
        Installs cluster logging capabilities powered by Vector

        cluster_id          ID of the cluster to be included in the logging data
        endpoint            Logging endpoint (OpenSearch)
        username            username for OpenSearch
        password            password for OpenSearch
        logger              logger (String-consuming function)
    """

    logger("Creating configmap 'cluster-metadata' to be used by Vector aggretator and agent...")
    exit_code, output = run_command(f"kubectl create configmap cluster-metadata --from-literal=T2_CLUSTER_ID={cluster_id}", 'create configmap cluster-metadata')
    if exit_code != 0:
        for line in output:
            logger(line)
        return False

    logger("Create secret containing the credentials and endpoint for target logging system...")
    exit_code, output = run_command(f"kubectl create secret generic cluster-logging-target  --from-literal=endpoint='{endpoint}' --from-literal=user='{username}' --from-literal=password='{password}'", 'create secret for logging target')
    if exit_code != 0:
        for line in output:
            logger(line)
        return False

    logger("Create configmap for Vector agent containing transformation rules...")
    exit_code, output = run_command(f"kubectl apply -f /src/modules/.cluster_logging/vector-agent-transforms.yaml", 'kubectl apply')
    if exit_code != 0:
        for line in output:
            logger(line)
        return False

    logger("Install Vector agent using Helm...")
    exit_code, output = run_command(f"helm install vector-agent vector/vector --version 0.40.0  --values /src/modules/.cluster_logging/vector-agent-values.yaml --wait", 'helm install')
    if exit_code != 0:
        for line in output:
            logger(line)
        return False

    logger("Install Vector aggregator using Helm...")
    exit_code, output = run_command(f"helm install vector-aggregator vector/vector --version 0.40.0  --values /src/modules/.cluster_logging/vector-aggregator-values.yaml --wait", 'helm install')
    if exit_code != 0:
        for line in output:
            logger(line)
        return False

    logger("Install eventrouter container to pipe K8s events to stdout to be grabbed by Vector agent...")
    exit_code, output = run_command(f"kubectl apply -f /src/modules/.cluster_logging/eventrouter.yaml", 'install eventrouter')
    if exit_code != 0:
        for line in output:
            logger(line)
        return False

    return True
