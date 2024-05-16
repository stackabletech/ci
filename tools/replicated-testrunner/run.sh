#!/bin/bash
docker run --rm -it \
    --env REPLICATED_API_TOKEN=$REPLICATED_API_TOKEN \
    --env UID_GID=1000:1000 \
    --env REPLICATED_DISTRIBUTION=openshift \
    --env REPLICATED_INSTANCE_TYPE=r1.medium \
    --env REPLICATED_VERSION=4.15.0-okd \
    --env REPLICATED_DISK_SIZE=50 \
    --env REPLICATED_NODE_COUNT=1 \
    --env OPERATOR_UNDER_TEST=hello-world \
    -v $(pwd)/target/:/target/ \
    docker.stackable.tech/replicated-testrunner