import sys
import os
import hiyapyco
from jinja2 import Template

catalog_platforms = None
catalog_platforms_with_versions = None
platform_custom_test_job_template = None
platform_all_test_job_template = None
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
    global catalog_platforms_with_versions
    catalog_platforms = hiyapyco.load("/catalog/platforms.yaml")
    catalog_platforms_with_versions = [ { 'display_name' : p['description'], 'id': p['name'], 'version': v } for p in catalog_platforms for v in p['k8s_versions'] ]

def read_templates():
    global platform_custom_test_job_template
    global platform_all_test_job_template
    global jjb_conf_template
    with open ("/jjb/platform_test_job_custom.j2", "r") as f:
        platform_custom_test_job_template = Template(f.read())
    with open ("/jjb/platform_test_job_all.j2", "r") as f:
        platform_all_test_job_template = Template(f.read())
    with open ("/jjb/jjb.conf.j2", "r") as f:
        jjb_conf_template = Template(f.read())

def generate_jjb_config():
    with open ("/jjb/jjb.conf", "w") as f:
        f.write(jjb_conf_template.render(os.environ))
        f.close()

def generate_platform_custom_test_job_definition():
    with open ("/jjb/platform_test_custom.yaml", 'w') as f:
        f.write(platform_custom_test_job_template.render( { 'platforms': catalog_platforms_with_versions } ))
        f.close()

def generate_platform_all_test_job_definition():
    with open ("/jjb/platform_test_all.yaml", 'w') as f:
        f.write(platform_all_test_job_template.render( { 'platforms': catalog_platforms } ))
        f.close()

def execute_jjb():
    """
        Executes the Jenkins Job Builder
    """
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/platform_test_custom.yaml")
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/platform_test_all.yaml")

def create_platform_test_jobs():
    """ 
        The entry point method for this module, creates the platform test job on Jenkins .
    """
    print()
    print("create platform test job")
    print()
    check_prerequisites()
    read_catalogs()
    read_templates()
    generate_jjb_config()
    generate_platform_custom_test_job_definition()
    generate_platform_all_test_job_definition()
    execute_jjb()
