import re
import os
import os.path
import hiyapyco
import random
from jinja2 import Template

testsuite_name = None
platform_name = None
k8s_version = None
operator_version = None
git_branch = None
metadata_annotations = {}

catalog_platforms = None
catalog_testsuites = None
test_script_template = None

def read_env_input(env_var_name):

    REGEX_RANDOM_SELECTION = re.compile('random\((.*)\)')
    REGEX_LIST = re.compile('([^,\s]+)')

    matcher_random_selection = REGEX_RANDOM_SELECTION.match(os.environ[env_var_name])
    if(matcher_random_selection):
        values = REGEX_LIST.findall(matcher_random_selection.group(1))
        pick = random.choice(values)
        print(f"Randomly picked {pick} from a list in {env_var_name}")
        return pick
    return os.environ[env_var_name]

def read_metadata_annotations_from_env():
    env_prefix = "METADATA_ANNOTATION_"
    return { k[len(env_prefix):] :v for k,v in os.environ.items() if k.startswith(env_prefix)}

def check_prerequisites():
    """ 
        Checks the prerequisites of this module and fails if they are not satisfied.

        mandatory params:
        - TESTSUITE
        - PLATFORM

        optional params:
        - K8S_VERSION
        - GIT_BRANCH
        - OPERATOR_VERSION
        - METADATA_ANNOTATION_xyz
    """
    global testsuite_name
    global platform_name
    global k8s_version
    global operator_version
    global git_branch
    global metadata_annotations
    if not 'TESTSUITE' in os.environ:
        print("Error: Please supply TESTSUITE as an environment variable.")
        exit(1)
    if not 'PLATFORM' in os.environ:
        print("Error: Please supply PLATFORM as an environment variable.")
        exit(1)
    if not os.path.isdir('/target/'):
        print("Error: Please supply /target folder as volume.")
        exit(1)
    testsuite_name = read_env_input("TESTSUITE")
    platform_name = read_env_input("PLATFORM")
    if 'K8S_VERSION' in os.environ:
        k8s_version = read_env_input("K8S_VERSION")
    if 'OPERATOR_VERSION' in os.environ:
        operator_version = read_env_input("OPERATOR_VERSION")
    if 'GIT_BRANCH' in os.environ:
        git_branch = read_env_input("GIT_BRANCH")
    metadata_annotations = read_metadata_annotations_from_env()

def clean_target():
    os.system('rm -rf /target/*')

def read_catalogs():
    global catalog_platforms
    global catalog_testsuites
    catalog_platforms = hiyapyco.load("/catalog/platforms.yaml")
    catalog_testsuites = hiyapyco.load("/catalog/testsuites.yaml")

def read_templates():
    global test_script_template
    with open ("/templates/test.sh.j2", "r") as f:
        test_script_template = Template(f.read())

def read_testsuite_from_catalog(testsuite_name):
    return next(filter(lambda x: x["name"]==testsuite_name, catalog_testsuites), None)

def read_cluster_definition_from_catalog(platform_name):
    return next(filter(lambda x: x["name"]==platform_name, catalog_platforms), None)['cluster_definition']

def read_platform_from_testsuite(testsuite, platform_name):
    return next(filter(lambda x: x["name"]==platform_name, testsuite['platforms']), None)

def write_cluster_definition(cluster_definition):
    with open ('/target/cluster.yaml', 'w') as f:
        f.write(yaml_to_string(cluster_definition))
        f.close()

def write_test_script(testsuite, test_params):
    with open ('/target/test.sh', 'w') as f:
        f.write(test_script_template.render( { 'testsuite': testsuite, 'git_branch': git_branch, 'test_params': test_params }))
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

def create_testsuite():
    """ 
        The entry point method for this module, creates the files for the testsuite.
    """
    print()
    print("create testsuite")
    print()
    check_prerequisites()
    clean_target()
    read_catalogs()
    read_templates()

    testsuite = read_testsuite_from_catalog(testsuite_name)
    if(not testsuite):
        print(f"The testsuite '{testsuite_name}' could not be found in the catalog.")
        exit(1)

    cluster_definition = read_cluster_definition_from_catalog(platform_name)
    if(not cluster_definition):
        print(f"No cluster definition for the platform '{platform_name}' could be found in the catalog.")
        exit(1)

    testsuite_platform_definition = read_platform_from_testsuite(testsuite, platform_name)
    if(not testsuite_platform_definition):
        print(f"No platform definition for '{platform_name}' could be found in the testsuite '{testsuite_name}'.")
        exit(1)

    if('cluster_definition_overlay' in testsuite):
        cluster_definition = merge_yaml(yaml_to_string(cluster_definition), testsuite['cluster_definition_overlay'])

    if('cluster_definition_overlay' in testsuite_platform_definition):
        cluster_definition = merge_yaml(yaml_to_string(cluster_definition), testsuite_platform_definition['cluster_definition_overlay'])

    if(k8s_version):
        cluster_definition['spec']['k8sVersion'] = k8s_version

    if(operator_version):
        cluster_definition['spec']['stackableVersions'][testsuite_name] = operator_version

    if(not cluster_definition['metadata']['annotations'] and len(metadata_annotations)>0):
        cluster_definition['metadata']['annotations'] = {}
    for key,value in metadata_annotations.items():
        cluster_definition['metadata']['annotations'][key] = value

    write_cluster_definition(cluster_definition)
    write_test_script(testsuite, testsuite_platform_definition['test_params'] if 'test_params' in testsuite_platform_definition else '')