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
beku_suite = None
metadata_annotations = {}

catalog_platforms = None
catalog_testsuites = None
test_script_template = None

def read_platform_and_k8s_version():
    """
        Reads platform and K8s version from input.

        Example for platform expressions:
        - "ionos-k8s" or "azure-aks"
            ... means exactly that platform.
          The K8S_VERSION is read from the env variable. If not present, the default from the platform definition is used.
        - "ionos-k8s, azure-aks"
            ... means a random choice of the given platforms, each with their default K8s version
                The K8S_VERSION env variable is ignored
        - "ionos-k8s(1.26.7|1.27.4), azure-aks"
                Same as above, but for "ionos-k8s", the version is randomly chosen between 1.26.7 and 1.27.4
        - "ionos-k8s(1.26.7|1.27.4), azure-aks(*))"
                Same as above, but for "azure-aks", the version is randomly chosen from all existing versions
        - If the exact version is not found in the platform list but exactly one matching major/minor version
          is found, it is selected. This is necessary because some cloud providers (namely IONOS currently) do
          require the fix version, but we do not want to change our testsuites.yaml every now and then...
    """

    k8s_version = None
    if 'K8S_VERSION' in os.environ:
        k8s_version = os.environ["K8S_VERSION"]

    platform_expression_list = ''.join(os.environ["PLATFORM"].split())

    if "," in platform_expression_list:
        platform_expression = random.choice(re.compile('([^,\s]+)').findall(platform_expression_list))
    else:
        platform_expression = platform_expression_list

    matcher_wildcard_version = re.compile('(.*)\(\*\)').match(platform_expression)
    if(matcher_wildcard_version):
        platform = matcher_wildcard_version.group(1)
        k8s_version = random.choice(read_k8s_versions_from_catalog(platform))
        return platform, k8s_version

    matcher_version_list = re.compile('(.*)\((.*)\)').match(platform_expression)
    if(matcher_version_list):
        platform = matcher_version_list.group(1)
        k8s_version_list = matcher_version_list.group(2)
        k8s_versions_for_platform = read_k8s_versions_from_catalog(platform)
        k8s_version_expression = random.choice(re.compile('([^\|\s]+)').findall(k8s_version_list))
        k8s_version = next(filter(lambda v: v.startswith(k8s_version_expression), k8s_versions_for_platform), None)
        return platform, k8s_version

    platform = platform_expression
    return platform, k8s_version


def read_metadata_annotations_from_env():
    env_prefix = "METADATA_ANNOTATION_"
    return { k[len(env_prefix):] :v for k,v in os.environ.items() if k.startswith(env_prefix)}


def read_params():
    """ 
        Reads the params for this program. Fails if mandatory params are missing.

        mandatory params:
        - TESTSUITE
        - PLATFORM

        optional params:
        - K8S_VERSION
        - GIT_BRANCH
        - BEKU_SUITE
        - OPERATOR_VERSION
        - METADATA_ANNOTATION_xyz
    """
    global testsuite_name
    global platform_name
    global k8s_version
    global operator_version
    global git_branch
    global beku_suite
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
    testsuite_name = os.environ["TESTSUITE"]
    platform_name, k8s_version = read_platform_and_k8s_version()
    if 'OPERATOR_VERSION' in os.environ:
        operator_version = os.environ["OPERATOR_VERSION"]
    if 'GIT_BRANCH' in os.environ:
        git_branch = os.environ["GIT_BRANCH"]
    if 'BEKU_SUITE' in os.environ:
        beku_suite = os.environ["BEKU_SUITE"]
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
    return next(filter(lambda x: x["name"]==testsuite_name, catalog_testsuites['operator_tests']), None)


def read_cluster_definition_from_catalog(platform_name):
    return next(filter(lambda x: x["name"]==platform_name, catalog_platforms), None)['cluster_definition']


def read_k8s_versions_from_catalog(platform_name):
    return next(filter(lambda x: x["name"]==platform_name, catalog_platforms), None)['k8s_versions']


def read_platform_from_testsuite(testsuite, platform_name):
    return next(filter(lambda x: x["name"]==platform_name, testsuite['platforms']), None)

def write_cluster_definition(cluster_definition):
    with open ('/target/cluster.yaml', 'w') as f:
        f.write(yaml_to_string(cluster_definition))
        f.close()


def write_test_script(testsuite, test_params):
    with open ('/target/test.sh', 'w') as f:
        f.write(test_script_template.render( { 'testsuite': testsuite, 'git_branch': git_branch, 'beku_suite': beku_suite, 'test_params': test_params }))
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
    read_catalogs()
    read_templates()
    read_params()
    clean_target()

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
        if(operator_version!='NONE'):
            cluster_definition['spec']['stackableVersions'][testsuite_name] = operator_version
        else:
            cluster_definition['spec']['stackableVersions'] = { '_-operator': 'NONE' }

    if(not 'metadata' in cluster_definition):
        cluster_definition['metadata'] = {}
    if(not 'annotations' in cluster_definition['metadata'] and len(metadata_annotations)>0):
        cluster_definition['metadata']['annotations'] = {}
    for key,value in metadata_annotations.items():
        cluster_definition['metadata']['annotations'][key] = value

    write_cluster_definition(cluster_definition)
    write_test_script(testsuite, testsuite_platform_definition['test_params'] if 'test_params' in testsuite_platform_definition else '')