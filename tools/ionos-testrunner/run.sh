#!/bin/bash
docker run --rm -it \
    --env IONOS_USERNAME=$IONOS_USERNAME \
    --env IONOS_PASSWORD=$IONOS_PASSWORD \
    --env UID_GID=1000:1000 \
    --env TESTSUITE=hello-world-operator \
    --env K8S_VERSION=1.29.5 \
    --env OPERATOR_VERSION=0.0.0-dev \
    -v $(pwd)/target/:/target/ \
    docker.stackable.tech/ionos-testrunner