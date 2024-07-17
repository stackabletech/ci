"""
    This module is a facade to the cluster providers.

    Currently, we offer clusters for replicated.com and IONOS.
"""

import modules.provider_ionos as ionos
import modules.provider_replicated as replicated

def create_cluster(provider_id, id, spec, platform_version, cluster_info_file, logger):
    """
        Creates a cluster with the given spec. (Blocking operation)

        provider_id         ID of the cloud provider / vendor
        id                  UUID of the cluster
        spec                dict containing specification of cluster (vendor-specific)
        platform_version    version of the (K8s) platform
        cluster_info_file   file to write cluster-specific information into
        logger              logger (String-consuming function)

        Returns vendor-specific cluster object.

        If not cluster could be created, the reason is logged and None is returned.
    """
    if 'replicated' == provider_id:
        return replicated.create_cluster(id, spec, platform_version, cluster_info_file, logger)
    if 'ionos' == provider_id:
        return ionos.create_cluster(id, spec, platform_version, cluster_info_file, logger)

def terminate_cluster(provider_id, cluster, logger):
    """
        Terminates the given cluster. (Blocking operation)

        provider_id         ID of the cloud provider / vendor
        cluster             vendor-specific cluster object which was previously returned by create_cluster()
        logger              logger (String-consuming function)
    """
    if 'replicated' == provider_id:
        return replicated.terminate_cluster(cluster, logger)
    if 'ionos' == provider_id:
        return ionos.terminate_cluster(cluster, logger)
