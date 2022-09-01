import sys
import create_jenkins_jobs
import create_testsuite
import create_platform_test_jobs
import create_platform_testsuite

if __name__ == "__main__":

    print("stackable.tech testing toolbox")

    if(len(sys.argv) < 2 or sys.argv[1] not in ['create-testsuite', 'create-jenkins-jobs', 'create-platform-test-job', 'create-platform-testsuite']):
        print("Please supply command [create-testsuite, create-jenkins-jobs, create-platform-test-job, create-platform-testsuite]")
        exit(1)

    if("create-testsuite"==sys.argv[1]):
        create_testsuite.create_testsuite()

    if("create-jenkins-jobs"==sys.argv[1]):
        create_jenkins_jobs.create_jenkins_jobs()

    if("create-platform-test-job"==sys.argv[1]):
        create_platform_test_jobs.create_platform_test_jobs()

    if("create-platform-testsuite"==sys.argv[1]):
        create_platform_testsuite.create_platform_testsuite()
