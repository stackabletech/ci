pipeline {
    agent any
    triggers {
        cron('0 0 * * *')
    }
    options {
        ansiColor('xterm')
        buildDiscarder(logRotator(numToKeepStr: '5', artifactNumToKeepStr: '5'))
    }

    stages {

        stage('Docker Build: Operator Test Runner') {
            steps {
                sh '''
                    rm -rf apps/docker/operator-test-runner/catalog/
                    mkdir -p apps/docker/operator-test-runner/catalog/
                    cp catalog/*.yaml apps/docker/operator-test-runner/catalog/
                    rm -rf apps/docker/operator-test-runner/src/
                    cp -r apps/src/ apps/docker/operator-test-runner/src/

                    docker build apps/docker/operator-test-runner/ -t docker.stackable.tech/operator-test-runner:latest
                ''' 
            }
        }

        stage('Docker Build: Jenkins Job Builder') {
            steps {
                sh '''
                    rm -rf apps/docker/jenkins-job-builder/catalog/
                    mkdir -p apps/docker/jenkins-job-builder/catalog/
                    cp catalog/*.yaml apps/docker/jenkins-job-builder/catalog/
                    rm -rf apps/docker/jenkins-job-builder/src/
                    cp -r apps/src/ apps/docker/jenkins-job-builder
                    rm -rf apps/docker/jenkins-job-builder/jjb/
                    cp -r apps/jjb/ apps/docker/jenkins-job-builder

                    docker build apps/docker/jenkins-job-builder/ -t docker.stackable.tech/jenkins-job-builder:latest
                ''' 
            }
        }

        stage('Create/Edit Jenkins jobs') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'JENKINS_BOT_CREDENTIALS', passwordVariable: 'JENKINS_BOT_PASSWORD', usernameVariable: 'JENKINS_BOT_USERNAME')]) {
                    sh '''
                        docker run --rm \
                            --env JENKINS_URL=https://testing.stackable.tech \
                            --env JENKINS_USERNAME=$JENKINS_BOT_USERNAME \
                            --env JENKINS_PASSWORD=$JENKINS_BOT_PASSWORD \
                            docker.stackable.tech/jenkins-job-builder:latest
                    ''' 
                }            
            }
        }

    }
}
