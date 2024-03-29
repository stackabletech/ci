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

The default AWS test platform has 3 nodes of the type `t2.large`. 

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

### VM Sizes

The default GKE test platform has 3 nodes of the type `e2-standard-2`. 

Use the following table to select the appropriate VM size:

| key | # CPUs | RAM in GB  |
|---|---|---|
| `e2-standard-2` | 2 | 8 |
| `e2-standard-4` | 4 | 16 |
| `e2-standard-8` | 8 | 32 |
| `e2-standard-16` | 16 | 64 |
| `e2-standard-32` | 32 | 128 |
| `e2-highmem-2` | 2 | 16 |
| `e2-highmem-4` | 4 | 32 |
| `e2-highmem-8` | 8 | 64 |
| `e2-highmem-16` | 16 | 128 |
| `e2-highcpu-2` | 2 | 2 |
| `e2-highcpu-4` | 4 | 4 |
| `e2-highcpu-8` | 8 | 8 |
| `e2-highcpu-16` | 16 | 16 |
| `e2-highcpu-32` | 32 | 32 |
