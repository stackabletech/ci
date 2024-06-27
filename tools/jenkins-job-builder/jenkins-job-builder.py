import os
import hiyapyco
import read_helm_operator_versions
from jinja2 import Template

catalog_replicated = None
replicated_jobs_template = None
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
    global catalog_replicated
    catalog_replicated = hiyapyco.load("/catalog/replicated.yaml")


def read_templates():
    global jjb_conf_template
    global replicated_jobs_template
    with open ("/jjb/jjb.conf.j2", "r") as f:
        jjb_conf_template = Template(f.read())
    with open ("/jjb/replicated_test_jobs.j2", "r") as f:
        replicated_jobs_template = Template(f.read())


def generate_jjb_config():
    with open ("/jjb/jjb.conf", "w") as f:
        f.write(jjb_conf_template.render(os.environ))
        f.close()


def generate_replicated_tests_jobs_definitions():
    with open ("/jjb/replicated_tests.yaml", 'w') as f:
       f.write(replicated_jobs_template.render(catalog_replicated))
       f.close()


def execute_jjb():
    """
        Executes the Jenkins Job Builder
    """
    os.system(f"GIT_BRANCH_OR_TAGS=hurz jenkins-jobs --conf /jjb/jjb.conf update /jjb/replicated_tests.yaml")


if __name__ == "__main__":

    print("stackable.tech Jenkins Job Builder")

    check_prerequisites()
    operator_versions = read_helm_operator_versions.read_helm_operator_versions()
    read_catalogs()
    read_templates()
    generate_jjb_config()
    generate_replicated_tests_jobs_definitions()
    with open("/jjb/replicated_tests.yaml", 'r') as f:
        print(f.read())
        f.close()
    execute_jjb()
