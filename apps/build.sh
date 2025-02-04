#!/bin/bash

# operator-test-runner

# copy resources
rm -rf docker/operator-test-runner/catalog/
mkdir -p docker/operator-test-runner/catalog/
cp ../catalog/*.yaml docker/operator-test-runner/catalog/
rm -rf docker/operator-test-runner/src/
cp -r src/ docker/operator-test-runner/src/

# build Docker image
docker build docker/operator-test-runner/ -t oci.stackable.tech/operator-test-runner:latest

# copy resources
rm -rf docker/jenkins-job-builder/catalog/
mkdir -p docker/jenkins-job-builder/catalog/
cp ../catalog/*.yaml docker/jenkins-job-builder/catalog/
rm -rf docker/jenkins-job-builder/src/
cp -r src/ docker/jenkins-job-builder/src/
rm -rf docker/jenkins-job-builder/jjb/
cp -r jjb/ docker/jenkins-job-builder/jjb/

# build Docker image
docker build docker/jenkins-job-builder/ -t oci.stackable.tech/jenkins-job-builder:latest
