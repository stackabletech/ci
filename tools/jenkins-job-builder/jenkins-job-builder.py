import os
import hiyapyco
import read_helm_operator_versions
from jinja2 import Template
import json

catalog_platforms = None
catalog_operator_tests = None
catalog_platform_metadata = None
jobs_template_operator_tests_custom = None
jjb_conf_template = None

def check_prerequisites():
    """ 
        Checks the prerequisites of this module and fails if they are not satisfied.
    """
    if not 'JENKINS_URL' in os.environ:
        print("Error: Please supply JENKINS_URL as an environment variable.")
        exit(1)
    if not 'JENKINS_USERNAME' in os.environ:
        print("Error: Please supply JENKINS_USERNAME as an environment variable.")
        exit(1)
    if not 'JENKINS_PASSWORD' in os.environ:
        print("Error: Please supply JENKINS_PASSWORD as an environment variable.")
        exit(1)


def read_catalogs():
    global catalog_platforms
    catalog_platforms = hiyapyco.load("/catalog/platforms.yaml")
    global catalog_operator_tests
    catalog_operator_tests = hiyapyco.load("/catalog/operator-tests.yaml")


def build_derived_catalogs():
    global catalog_platform_metadata
    catalog_platform_metadata = { p['id']: { 'name': p['name'], 'versions': [ v for v in p['versions']] } for p in catalog_platforms['platforms'] }


def read_templates():
    global jjb_conf_template
    global jobs_template_operator_tests_custom
    with open ("/jjb/jjb.conf.j2", "r") as f:
        jjb_conf_template = Template(f.read())
    with open ("/jjb/operator_tests_custom.j2", "r") as f:
        jobs_template_operator_tests_custom = Template(f.read())


def generate_jjb_config():
    with open ("/jjb/jjb.conf", "w") as f:
        f.write(jjb_conf_template.render(os.environ))
        f.close()


def generate_job_definitions_operator_tests_custom(operator_versions):
    with open ("/jjb/operator_tests.yaml", 'w') as f:
       f.write(jobs_template_operator_tests_custom.render({ 'testsuites': catalog_operator_tests, 'platforms': catalog_platform_metadata, 'operator_versions': operator_versions }))
       f.close()


def execute_jjb():
    """
        Executes the Jenkins Job Builder
    """
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/operator_tests.yaml")


if __name__ == "__main__":

    print("stackable.tech Jenkins Job Builder")

    check_prerequisites()

    print("Step 1: detected operator versions:")
    operator_versions = read_helm_operator_versions.read_helm_operator_versions()
    print()
    print(json.dumps(operator_versions, indent=4, sort_keys=True))
    print()
    print()

    print("Step 2: read catalogs:")
    print()
    read_catalogs()
    print("Step 2.1: catalog platforms.yaml:")
    print()
    print(json.dumps(catalog_platforms, indent=4, sort_keys=True))
    print()
    print("Step 2.2: catalog operator-tests.yaml:")
    print()
    print(json.dumps(catalog_operator_tests, indent=4, sort_keys=True))
    print()
    build_derived_catalogs()
    print("Step 2.3: derived catalog containing platform metadata")
    print()
    print(json.dumps(catalog_platform_metadata, indent=4, sort_keys=True))
    print()

    read_templates()
    generate_jjb_config()
    generate_job_definitions_operator_tests_custom(operator_versions)
    execute_jjb()

    with open ("/jjb/operator_tests.yaml", 'r') as f:
        for line in f:
            print(line)

