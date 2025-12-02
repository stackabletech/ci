# testing.stackable.tech apps

For running our testing platform, we need to perform complex jobs in Jenkins. These jobs are coded in Dockerized apps. As they have common tasks, we maintain a shared codebase for these apps and build different Docker images for them.

## The Apps

We have these two apps:

* **Jenkins Job Builder** is a "seed job" which (re)creates all the jobs in our Jenkins.
* **Operator Test Runner** is an app which creates/terminates K8s clusters and runs operator integration tests in them.

## Configurable Test Scripts

The **Operator Test Runner** supports two test execution strategies:

1. **`run-tests`** (default) - Traditional test runner that executes tests once
2. **`auto-retry-tests.py`** - Intelligent retry test runner that:
   - Runs the full test suite initially
   - Identifies failed tests automatically
   - Retries failed tests with configurable parallel and serial strategies
   - Tracks test runtime history for better estimates
   - Provides comprehensive reporting
   - Optionally keeps failed namespaces for debugging

### Configuration

Test script selection is configured per-operator in `catalog/operator-tests.yaml`:

```yaml
- id: hdfs-operator
  display_name: HDFS Operator
  git_repo: hdfs-operator
  # Test script: "run-tests" (default) or "auto-retry-tests.py"
  test_script: auto-retry-tests.py
  # Auto-retry configuration (only used if test_script is auto-retry-tests.py)
  auto_retry:
    attempts_parallel: 2  # Number of parallel retry attempts (default: 0)
    attempts_serial: 3    # Number of serial retry attempts (default: 3)
    keep_failed_namespaces: false  # Keep namespaces for debugging (default: false)
```

If `test_script` is not specified, the default `run-tests` is used, maintaining backward compatibility with all existing operators.

## Project Structure

The code is documented inline, here's the project structure:

* [docker/](docker/) contains the Docker build resources (`Dockerfile` + ...) for the apps
* [jjb/](jjb/) contains the templates for the jobs for the **Jenkins Job Builder** app.
* [src/](src/) contains the Python sources.
* [src/modules/](src/modules/) contains the common Python modules of this project
* [jenkins-job-builder.py](src/jenkins-job-builder.py) is the main program of the **Jenkins Job Builder** app.
* [operator-test-runner.py](src/operator-test-runner.py) is the main program of the **Operator Test Runner** app.
* [build.sh](build.sh) lets you build the Docker images locally.

## Build process

The [seed job](../jenkins/jobbuilder.groovy) which is created during Jenkins setup and executed every 5 minutes does build the apps as Docker images inside the Jenkins. They are tagged as `latest` and used by the Jenkins jobs, so every code change pushed to the `main` branch is reflected in near-real-time. No external Docker image registry like Nexus or Harbor is needed here.