import sys
import os
import os.path
import hiyapyco
from jinja2 import Template

testsuite_name = None
platform_name = None
k8s_version = None
operator_version = None
git_branch = None

catalog_platforms = None
catalog_testsuites = None
test_script_template = None

def check_prerequisites():
    """ 
        Checks the prerequisites of this module and fails if they are not satisfied.
    """
    global testsuite_name
    global platform_name
    global k8s_version
    global operator_version
    global git_branch
    if not 'TESTSUITE' in os.environ:
        print("Error: Please supply TESTSUITE as an environment variable.")
        exit(1)
    if not 'PLATFORM' in os.environ:
        print("Error: Please supply PLATFORM as an environment variable.")
        exit(1)
    if not os.path.isdir('/target/'):
        print("Error: Please supply /target folder as volume.")
        exit(1)
    testsuite_name = os.environ["TESTSUITE"]
    platform_name = os.environ["PLATFORM"]
    if 'K8S_VERSION' in os.environ:
        k8s_version = os.environ["K8S_VERSION"]
    if 'OPERATOR_VERSION' in os.environ:
        operator_version = os.environ["OPERATOR_VERSION"]
    if 'GIT_BRANCH' in os.environ:
        git_branch = os.environ["GIT_BRANCH"]

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
        cluster_definition['spec']['versions'][testsuite_name] = operator_version

    write_cluster_definition(cluster_definition)
    write_test_script(testsuite, testsuite_platform_definition['test_params'] if 'test_params' in testsuite_platform_definition else '')