# CI catalog files

## platforms 

tbd

## testsuites

To select the platform for the nightly tests, you can use a simple syntax which is explained here by example:

* "`azure-aks`" Azure AKS cluster with the default version
* "`azure-aks, ionos-k8s(*)`" Random selection:
    * Azure AKS cluster with the default version
    * **OR** random version of IONOS managed K8s
* "`azure-aks, ionos-k8s(*), gke(1.26|1.27)`" Random selection:
    * Azure AKS cluster with the default version
    * **OR** random version of IONOS managed K8s
    * **OR** Google GKE 1.26 or 1.27 (randomly selected)

(TODO: Document the rest of the structure)