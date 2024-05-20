#!/bin/bash
cp ../../catalog/replicated.yaml .
docker build . -t docker.stackable.tech/replicated-testrunner:latest