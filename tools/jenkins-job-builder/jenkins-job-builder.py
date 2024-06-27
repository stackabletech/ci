import sys
import os
# import create_jenkins_jobs
# import create_testsuite
# import create_documentation_testsuite
# import create_platform_test_jobs
# import create_platform_testsuite

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

if __name__ == "__main__":

    print("stackable.tech Jenkins Job Builder")

    check_prerequisites()