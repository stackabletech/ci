# testing.stackable.tech apps

For running our testing platform, we need to perform complex jobs in Jenkins. These jobs are coded in Dockerized apps. As they have common tasks, we maintain a shared codebase for these apps and build different Docker images for them.

## The Apps

We have these two apps:

* **Jenkins Job Builder** is a "seed job" which (re)creates all the jobs in our Jenkins. 
* **Operator Test Runner** is an app which creates/terminates K8s clusters and runs operator integration tests in them.

## Project Structure

The code is documented inline, here's the project structure:

* [docker/](docker/) contains the Docker build resources (`Dockerfile` + ...) for the apps
* [jjb/](jjb/) contains the templates for the jobs for the **Jenkins Job Builder** app.
* [src/](src/) contains the Python sources.
* [src/modules/](src/modules/) contains the common Python modules of this project
* [jenkins-job-builer.py](src/jenkins-job-builder.py) is the main program of the **Jenkins Job Builder** app.
* [operator-test-runner.py](src/operator-test-runner.py) is the main program of the **Operator Test Runner** app.
* [build.sh](build.sh) lets you build the Docker images locally.

## Build process

The [seed job](../jenkins/jobbuilder.groovy) which is created during Jenkins setup and executed every 5 minutes does build the apps as Docker images inside the Jenkins. They are tagged as `latest` and used by the Jenkins jobs, so every code change pushed to the `main` branch is reflected in near-real-time. No external Docker image registry like Nexus or Harbor is needed here.