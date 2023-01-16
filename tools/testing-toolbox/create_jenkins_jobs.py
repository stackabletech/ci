import sys
import os
import hiyapyco
from jinja2 import Template

catalog_platforms = None
catalog_platforms_with_versions = None
catalog_testsuites = None
custom_test_jobs_template = None
nightly_test_jobs_template = None
nightly_test_jobs_summary_template = None
self_service_test_jobs_template = None
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
    global catalog_testsuites
    global catalog_platforms_with_versions
    catalog_platforms = hiyapyco.load("/catalog/platforms.yaml")
    catalog_testsuites = hiyapyco.load("/catalog/testsuites.yaml")
    catalog_platforms_with_versions = { p['name']: [ { 'display_name' : p['description'], 'id': p['name'], 'version': v } for v in p['k8s_versions'] ] for p in catalog_platforms }

def read_templates():
    global custom_test_jobs_template
    global nightly_test_jobs_template
    global nightly_test_jobs_summary_template
    global self_service_test_jobs_template
    global jjb_conf_template
    with open ("/jjb/custom_test_jobs.j2", "r") as f:
        custom_test_jobs_template = Template(f.read())
    with open ("/jjb/nightly_test_jobs.j2", "r") as f:
        nightly_test_jobs_template = Template(f.read())
    with open ("/jjb/nightly_test_jobs_summary.j2", "r") as f:
        nightly_test_jobs_summary_template = Template(f.read())
    with open ("/jjb/self_service_test_jobs.j2", "r") as f:
        self_service_test_jobs_template = Template(f.read())
    with open ("/jjb/jjb.conf.j2", "r") as f:
        jjb_conf_template = Template(f.read())

def generate_jjb_config():
    with open ("/jjb/jjb.conf", "w") as f:
        f.write(jjb_conf_template.render(os.environ))
        f.close()

def generate_custom_test_jobs_definitions():
    platforms_by_testsuite = { t['name']: [ item for sublist in [ catalog_platforms_with_versions[p['name']] for p in t['platforms'] ] for item in sublist ] for t in catalog_testsuites }
    with open ("/jjb/custom_tests.yaml", 'w') as f:
        f.write(custom_test_jobs_template.render( { 'testsuites': catalog_testsuites, 'platforms': platforms_by_testsuite } ))
        f.close()

def generate_nightly_test_jobs_definitions():
    with open ("/jjb/nightly_tests.yaml", 'w') as f:
        f.write(nightly_test_jobs_template.render( { 'testsuites': catalog_testsuites } ))
        f.close()

def generate_nightly_test_jobs_summary_definitions():
    with open ("/jjb/nightly_tests_summary.yaml", 'w') as f:
        f.write(nightly_test_jobs_summary_template.render( { 'testsuites': catalog_testsuites } ))
        f.close()

def generate_self_service_jobs_definitions():
    platforms_by_testsuite = { t['name']: [ item for sublist in [ catalog_platforms_with_versions[p['name']] for p in t['platforms'] ] for item in sublist ] for t in catalog_testsuites }
    with open ("/jjb/self_service_tests.yaml", 'w') as f:
        f.write(self_service_test_jobs_template.render( { 'testsuites': catalog_testsuites, 'platforms': platforms_by_testsuite } ))
        f.close()

def execute_jjb():
    """
        Executes the Jenkins Job Builder
    """
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/custom_tests.yaml")
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/nightly_tests.yaml")
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/nightly_tests_summary.yaml")
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/self_service_tests.yaml")
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/delete_cluster_self_service.yaml")
    os.system(f"jenkins-jobs --conf /jjb/jjb.conf update /jjb/update_deletable_self_service_clusters.yaml")

def create_jenkins_jobs():
    """ 
        The entry point method for this module, creates the Jenkins jobs.
    """
    print()
    print("create jenkins jobs")
    print()
    check_prerequisites()
    read_catalogs()
    read_templates()
    generate_jjb_config()
    generate_custom_test_jobs_definitions()
    generate_nightly_test_jobs_definitions()
    generate_nightly_test_jobs_summary_definitions()
    generate_self_service_jobs_definitions()
    execute_jjb()
