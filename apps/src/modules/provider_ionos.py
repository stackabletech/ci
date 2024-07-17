"""
    This module creates IONOS clusters using the CLI
"""
from modules.command import run_command
from time import sleep

def query_command_for_table(command, description):
    """
        Runs the given command and returns the results as a list of dicts
    """
    cmd_output = run_command(command, description)
    if cmd_output[0] != 0:
        return (cmd_output[0], cmd_output[1])
    if len(cmd_output[1])==0:
        return (0, [])
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

def create_datacenter(name, location, logger):
    """
        Creates a datacenter

        name                name of the DC
        location            location, e.g. 'de/txl'
        logger              logger (String-consuming function)

        Returns the IONOS-internal datacenter ID
    """
    command = f"ionosctl datacenter create --name {name} --location {location}"
    exit_code, output = query_command_for_table(command, 'create datacenter')
    if exit_code != 0:
        logger(f"Creating a datacenter named '{name}' failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return output[0]['DatacenterId']

def get_datacenter(id, logger):
    """
        Reads a datacenter by its IONOS-internal ID

        id                  ID of the DC
        logger              logger (String-consuming function)
    """
    command = f"ionosctl datacenter list"
    exit_code, output = query_command_for_table(command, 'list datacenters')
    if exit_code != 0:
        logger(f"Reading datacenters failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return next(iter([dc for dc in output if dc['DatacenterId']==id]), None)

def delete_datacenter(id, logger):
    """
        Deletes a datacenter

        id                  ID of the DC
        logger              logger (String-consuming function)
    """
    command = f"ionosctl datacenter delete --datacenter-id {id} --force"
    exit_code, output = run_command(command, 'delete datacenter')
    if exit_code != 0:
        logger(f"Deleting the datacenter {id} failed with exit code {exit_code} and the following message:")
        print(output)
        return False
    return True

def wait_for_datacenter_state(id, target_state, logger):
    """
        Waits until a datacenter is in the desired state (blocking method)
        Polls the CLI every 5 seconds.

        id                  ID of the DC
        target_state        desired state
        logger              logger (String-consuming function)
    """
    datacenter = get_datacenter(id, logger)
    state = datacenter['State'] if datacenter else None
    logger(f"Datacenter {id} is in state {state}")
    while state != target_state:
        sleep(5)
        datacenter = get_datacenter(id, logger)
        state = datacenter['State'] if datacenter else None
        logger(f"Datacenter {id} is in state {state}")

def ionosctl_create_cluster(name, k8s_version, logger):
    """
        Creates a K8s cluster

        name                name of the cluster
        k8s_version         K8s version, e.g. '1.29.5'
        logger              logger (String-consuming function)

        Returns the IONOS-internal cluster ID
    """
    command = f"ionosctl k8s cluster create --name {name} --k8s-version {k8s_version}"
    exit_code, output = query_command_for_table(command, 'create cluster')
    if exit_code != 0:
        logger(f"Creating a cluster named '{name}' failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return output[0]['ClusterId']

def get_cluster(id, logger):
    """
        Reads a K8s cluster by its IONOS-internal ID

        id                  ID of the K8s cluster
        logger              logger (String-consuming function)
    """
    command = f"ionosctl k8s cluster list"
    exit_code, output = query_command_for_table(command, 'list clusters')
    if exit_code != 0:
        logger(f"Reading clusters failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return next(iter([c for c in output if c['ClusterId']==id]), None)

def delete_cluster(id, logger):
    """
        Deletes a K8s cluster

        id                  ID of the K8s cluster
        logger              logger (String-consuming function)
    """
    command = f"ionosctl k8s cluster delete --cluster-id {id} --force"
    exit_code, output = run_command(command, 'delete cluster')
    if exit_code != 0:
        logger(f"Deleting the cluster {id} failed with exit code {exit_code} and the following message:")
        print(output)
        return False
    return True

def wait_for_cluster_state(id, target_state, logger):
    """
        Waits until a K8s cluster is in the desired state (blocking method)
        Polls the CLI every 5 seconds.

        id                  ID of the cluster
        target_state        desired state
        logger              logger (String-consuming function)
    """
    cluster = get_cluster(id, logger)
    state = cluster['State'] if cluster else None
    logger(f"Cluster {id} is in state {state}")
    while state != target_state:
        sleep(5)
        cluster = get_cluster(id, logger)
        state = cluster['State'] if cluster else None
        logger(f"Cluster {id} is in state {state}")

def create_nodepool(name, cluster_id, datacenter_id, cores, node_count, ram, disk_type, disk_size, logger):
    """
        Creates a K8s nodepool

        name                name of the cluster
        cluster_id          ID of cluster where this nodepool should be created at
        datacenter_id       ID of the datacenter to put nodepool into
        cores               number of cores per node
        node_count          number of nodes
        ram                 RAM of each Node in MB
        disk_type           'HDD' or 'SSD'
        disk_size           disk size in GB
        logger              logger (String-consuming function)

        Returns the IONOS-internal nodepool ID
    """
    command = f"ionosctl k8s nodepool create --datacenter-id {datacenter_id} --cluster-id {cluster_id} --name {name} --cores {cores} --node-count {node_count} --ram {ram} --storage-type {disk_type} --storage-size {disk_size}"
    exit_code, output = query_command_for_table(command, 'create nodepool')
    if exit_code != 0:
        logger(f"Creating a nodepool named '{name}' failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return output[0]['NodePoolId']

def get_nodepool(id, cluster_id, logger):
    """
        Reads a K8s nodepool by its IONOS-internal ID

        id                  ID of the nodepool
        cluster_id          ID of the K8s cluster
        logger              logger (String-consuming function)
    """
    command = f"ionosctl k8s nodepool list --cluster-id {cluster_id}"
    exit_code, output = query_command_for_table(command, 'list nodepools')
    if exit_code != 0:
        logger(f"Reading nodepools failed with exit code {exit_code} and the following message:")
        print(output)
        return None
    return next(iter([n for n in output if n['NodePoolId']==id]), None)

def delete_nodepool(id, cluster_id, logger):
    """
        Deletes a K8s nodepool

        id                  ID of the nodepool
        cluster_id          ID of the K8s cluster
        logger              logger (String-consuming function)
    """
    command = f"ionosctl k8s nodepool delete --cluster-id {cluster_id} --nodepool-id {id} --force"
    exit_code, output = run_command(command, 'delete nodepool')
    if exit_code != 0:
        logger(f"Deleting the nodepool {id} of cluster {cluster_id} failed with exit code {exit_code} and the following message:")
        print(output)
        return False
    return True

def wait_for_nodepool_state(id, cluster_id, target_state, logger):
    """
        Waits until a K8s nodepool is in the desired state (blocking method)
        Polls the CLI every 5 seconds.

        id                  ID of the nodepool
        cluster_id          ID of the K8s cluster
        target_state        desired state
        logger              logger (String-consuming function)
    """
    nodepool = get_nodepool(id, cluster_id, logger)
    state = nodepool['State'] if nodepool else None
    logger(f"Nodepool {id} is in state {state}")
    while state != target_state:
        sleep(5)
        nodepool = get_nodepool(id, cluster_id, logger)
        state = nodepool['State'] if nodepool else None
        logger(f"Nodepool {id} is in state {state}")

def update_kubeconfig(cluster_id, logger):
    """
        Updates the kubeconfig (in default folder /root/.kube/config/) for the given cluster
    """
    exit_code, output = run_command(f"ionosctl k8s kubeconfig get --cluster-id {cluster_id} > /root/.kube/config", 'update kubeconfig')
    if exit_code != 0:
        for line in output:
            logger(line)
        return False
    return True

def write_cluster_info_file(cluster_info_file):
    """
        Writes a file containing basic cluster information
    """
    run_command(f"kubectl get nodes > {cluster_info_file}", 'kubectl get nodes')

def create_cluster(id, spec, platform_version, cluster_info_file, logger):
    """
        Creates an IONOS cluster with the given spec. (Blocking operation)

        id                  UUID of the cluster
        spec                dict containing specification of cluster (vendor-specific)
        platform_version    version of the (K8s) platform
        cluster_info_file   file to write cluster-specific information into
        logger              logger (String-consuming function)

        Returns vendor-specific cluster object.

        If not cluster could be created, the reason is logged and None is returned.
    """

    # name is first 10 digits of ID
    cluster_name = id[0:10]

    logger(f"Creating cluster {cluster_name} on IONOS...")

    logger(f"Creating datacenter '{cluster_name}'...")
    datacenter_id = create_datacenter(cluster_name, spec['location'], logger)
    if not datacenter_id:
        logger("Error creating datacenter.")
        return None
    logger(f"Created datacenter '{cluster_name}' (id={datacenter_id})")
    wait_for_datacenter_state(datacenter_id, 'AVAILABLE', logger)
    logger(f"Datacenter '{cluster_name}' (id={datacenter_id}) is ready for use.")

    logger(f"Creating K8s cluster '{cluster_name}'...")
    cluster_id = ionosctl_create_cluster(cluster_name, platform_version, logger)
    if not cluster_id:
        logger("Error creating K8s cluster.")
        return None
    logger(f"Created K8s cluster '{cluster_name}' (id={cluster_id})")
    wait_for_cluster_state(cluster_id, 'ACTIVE', logger)
    logger(f"K8s Cluster '{cluster_name}' (id={cluster_id}) is ready for use.")

    logger(f"Creating nodepool '{cluster_name}'...")
    nodepool_id = create_nodepool(cluster_name, cluster_id, datacenter_id, spec['cores'], spec['node-count'], spec['ram'], spec['disk-type'], spec['disk-size'], logger)
    if not nodepool_id:
        logger("Error creating nodepool.")
        return None
    logger(f"Created nodepool '{cluster_name}' (id={nodepool_id})")
    wait_for_nodepool_state(nodepool_id, cluster_id, 'ACTIVE', logger)
    logger(f"Nodepool '{cluster_name}' (id={nodepool_id}) is ready for use.")

    logger("Updating kubeconfig...")
    if not update_kubeconfig(cluster_id, logger):
        logger("Error updating kubeconfig.")
        return None

    write_cluster_info_file(cluster_info_file)

    return {
        'cluster_name': cluster_name,
        'datacenter_id': datacenter_id,
        'cluster_id': cluster_id,
        'nodepool_id': nodepool_id
    }

def terminate_cluster(id, logger):
    """
        Terminates the given cluster. (Blocking operation)

        id                  vendor-specific cluster object which was previously returned by create_cluster()
        logger              logger (String-consuming function)
    """
    if not delete_nodepool(id['nodepool_id'], id['cluster_id'], logger):
        logger('Error deleting nodepool')
        return False

    logger(f"Deleting nodepool for '{id['cluster_name']}'...")
    wait_for_nodepool_state(id['nodepool_id'], id['cluster_id'], None, logger)
    logger(f"Nodepool for '{id['cluster_name']}' successfully deleted.")

    if not delete_cluster(id['cluster_id'], logger):
        logger('Error deleting cluster')
        return False

    logger(f"Deleting cluster for '{id['cluster_name']}'...")
    wait_for_cluster_state(id['cluster_id'], None, logger)
    logger(f"Cluster for '{id['cluster_name']}' successfully deleted.")

    if not delete_datacenter(id['datacenter_id'], logger):
        logger('Error deleting datacenter')
        return False

    logger(f"Deleting datacenter for '{id['cluster_name']}'...")
    wait_for_datacenter_state(id['datacenter_id'], None, logger)
    logger(f"Datacenter for '{id['cluster_name']}' successfully deleted.")

    return True
