#!/bin/bash
docker run --rm -it \
    --env REPLICATED_API_TOKEN=$REPLICATED_API_TOKEN \
    --env UID_GID=1000:1000 \
    --env REPLICATED_DISTRIBUTION=openshift \
    --env TESTSUITE=hello-world-operator \
    --env PLATFORM=openshift \
    --env PLATFORM_VERSION=4.15.0-okd \
    -v $(pwd)/target/:/target/ \
    docker.stackable.tech/replicated-testrunner