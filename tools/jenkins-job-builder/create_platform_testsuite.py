import sys
import os
import os.path
import hiyapyco
from jinja2 import Template

platform_name = None
k8s_version = None
metadata_annotations = {}

catalog_platforms = None

def read_metadata_annotations_from_env():
    env_prefix = "METADATA_ANNOTATION_"
    return { k[len(env_prefix):] :v for k,v in os.environ.items() if k.startswith(env_prefix)}

def check_prerequisites():
    """ 
        Checks the prerequisites of this module and fails if they are not satisfied.

        mandatory params:
        - PLATFORM

        optional params:
        - K8S_VERSION
        - METADATA_ANNOTATION_xyz
    """
    global platform_name
    global k8s_version
    global metadata_annotations
    if not 'PLATFORM' in os.environ:
        print("Error: Please supply PLATFORM as an environment variable.")
        exit(1)
    if not os.path.isdir('/target/'):
        print("Error: Please supply /target folder as volume.")
        exit(1)
    platform_name = os.environ["PLATFORM"]
    if 'K8S_VERSION' in os.environ:
        k8s_version = os.environ["K8S_VERSION"]
    metadata_annotations = read_metadata_annotations_from_env()

def clean_target():
    os.system('rm -rf /target/*')

def read_catalogs():
    global catalog_platforms
    catalog_platforms = hiyapyco.load("/catalog/platforms.yaml")

def read_cluster_definition_from_catalog(platform_name):
    return next(filter(lambda x: x["name"]==platform_name, catalog_platforms), None)['cluster_definition']

def write_cluster_definition(cluster_definition):
    with open ('/target/cluster.yaml', 'w') as f:
        f.write(yaml_to_string(cluster_definition))
        f.close()

def write_test_script():
    with open ('/target/test.sh', 'w') as f:
        f.write("""sleep 300
kubectl get nodes
echo ""
echo ""
helm list""")
        f.close()

def yaml_to_string(yaml):
    return hiyapyco.dump(yaml, default_flow_style=False, width=1000)

def merge_yaml(base_yaml, yaml_to_merge):
    """ 
        Merges the yaml_to_merge into the base_yaml.
        Both params have to be given as strings.
        Returns merged YAML
    """
    return hiyapyco.load([base_yaml, yaml_to_merge], method=hiyapyco.METHOD_MERGE)

def create_platform_testsuite():
    """ 
        The entry point method for this module, creates the files for the testsuite.
    """
    print()
    print("create platform testsuite")
    print()
    check_prerequisites()
    clean_target()
    read_catalogs()

    cluster_definition = read_cluster_definition_from_catalog(platform_name)
    if(not cluster_definition):
        print(f"No cluster definition for the platform '{platform_name}' could be found in the catalog.")
        exit(1)

    if(k8s_version):
        cluster_definition['spec']['k8sVersion'] = k8s_version

    if(not 'metadata' in cluster_definition):
        cluster_definition['metadata'] = {}
    if(not 'annotations' in cluster_definition['metadata'] and len(metadata_annotations)>0):
        cluster_definition['metadata']['annotations'] = {}
    for key,value in metadata_annotations.items():
        cluster_definition['metadata']['annotations'][key] = value

    write_cluster_definition(cluster_definition)
    write_test_script()