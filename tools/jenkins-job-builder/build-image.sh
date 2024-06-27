#!/bin/bash
mkdir -p catalog/
cp ../../catalog/*.yaml catalog/
docker build . -t docker.stackable.tech/testing-toolbox:latest