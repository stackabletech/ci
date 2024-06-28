pipeline {
    agent any
    options {
        ansiColor('xterm')
        buildDiscarder(logRotator(numToKeepStr: '5', artifactNumToKeepStr: '5'))
    }

    stages {

        stage('Log variables') {
            steps {
                echo "Job Builder"
                echo "Git branch: $BRANCH_NAME"
            }
        }

    }
}
