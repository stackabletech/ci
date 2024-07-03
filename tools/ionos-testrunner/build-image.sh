#!/bin/bash
cp ../../catalog/ionos.yaml .
docker build . -t docker.stackable.tech/ionos-testrunner:latest