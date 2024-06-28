pipeline {
    agent any
    options {
        ansiColor('xterm')
        buildDiscarder(logRotator(numToKeepStr: '5', artifactNumToKeepStr: '5'))
    }

    stages {

        stage('Log variables') {
            steps {
                withCredentials([usernamePassword(credentialsId: 'JENKINS_BOT_CREDENTIALS', passwordVariable: 'JENKINS_BOT_PASSWORD', usernameVariable: 'JENKINS_BOT_USERNAME')]) {
                    sh '''
                        mkdir -p tools/jenkins-job-builder/catalog/
                        cp catalog/*.yaml tools/jenkins-job-builder/catalog/

                        docker build tools/jenkins-job-builder/ -t docker.stackable.tech/jenkins-job-builder:latest

                        docker run --rm \
                            --env JENKINS_URL=https://ci-dev.stackable.tech \
                            --env JENKINS_USERNAME=$JENKINS_BOT_USERNAME \
                            --env JENKINS_PASSWORD=$JENKINS_BOT_PASSWORD \
                            docker.stackable.tech/jenkins-job-builder:latest
                    ''' 
                }            
            }
        }

    }
}
