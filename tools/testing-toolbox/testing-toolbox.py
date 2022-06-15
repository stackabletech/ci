import sys
import create_jenkins_jobs
import create_testsuite


if __name__ == "__main__":

    print("stackable.tech testing toolbox")

    if(len(sys.argv) < 2 or sys.argv[1] not in ['create-testsuite', 'create-jenkins-jobs']):
        print("Please supply command [create-testsuite,create-jenkins-jobs]")
        exit(1)

    if("create-testsuite"==sys.argv[1]):
        create_testsuite.create_testsuite()

    if("create-jenkins-jobs"==sys.argv[1]):
        create_jenkins_jobs.create_jenkins_jobs()
