rm -rf target/
mkdir -p target/

docker run \
    -v$(pwd)/target/:/target/ \
    -v$(pwd)/../../tests/nightly/platforms.yaml:/platforms.yaml \
    -v$(pwd)/../../tests/nightly/tests.yaml:/tests.yaml \
    -eTEST_NAME=$1 \
    -u$(id -u):$(id -g) \
    docker.stackable.tech/ci-preprocessor:latest