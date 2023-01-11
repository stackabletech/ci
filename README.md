# ci
Config files for Jenkins jobs ran by our infrastructure

# Our Kubernetes platforms

## K3s 

* Home: https://k3s.io/
* Release notes: https://github.com/k3s-io/k3s/releases
* API to get versions: https://update.k3s.io/v1-release/channels

## AWS EKS

* Release notes: https://docs.aws.amazon.com/eks/latest/userguide/platform-versions.html

### VM Sizes:

The default AWS test platform has 3 nodes of the type `t2.small`. 

Use the following table to select the appropriate VM size:

| key | # CPUs | RAM in GB  |
|---|---|---|
| `t2.small` | 1 | 2 |
| `t2.medium` | 2 | 4 |
| `t2.large` | 2 | 8 |
| `t2.xlarge` | 4 | 16 |
| `t2.2xlarge` | 8 | 32 |

## Azure AKS

* Release notes: https://github.com/Azure/AKS/releases

### VM Sizes:

We use 2 kinds of VMs in Azure:

* D-Series v3 ("The 3rd generation D family sizes for your general purpose needs")
* E-Series v3 ("The 3rd generation E family sizes for your high memory needs")

The default Azure test platform has 3 nodes of the type `Standard_D2s_v3`. 

Use the following table to select the appropriate VM size:

| key | # CPUs | RAM in GB  |
|---|---|---|
| `Standard_D2s_v3` | 2 | 8 |
| `Standard_D4s_v3` | 4 | 16 |
| `Standard_D8s_v3` | 8 | 32 |
| `Standard_E2s_v3` | 2 | 16 |
| `Standard_E4s_v3` | 4 | 32 |
| `Standard_E8s_v3` | 8 | 64 |

## IONOS K8s

* Home: https://docs.ionos.com/cloud/managed-services/managed-kubernetes

## Google GKE

* Release notes: https://cloud.google.com/kubernetes-engine/docs/release-notes