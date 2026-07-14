FROM oci.stackable.tech/sdp/ubi8-rust-builder AS builder

FROM registry.access.redhat.com/ubi8/ubi-minimal:8.10@sha256:578b238953144445a9b5bb2487eb1d95df4886f98d1f73c4a070b27535f51688 AS operator

ARG VERSION
ARG RELEASE="1"

# Update image
RUN microdnf install -y yum \
    && yum -y update-minimal --security --sec-severity=Important --sec-severity=Critical \
    && yum clean all \
    && microdnf clean all

COPY --from=builder /app/harbor-garbage-collector  /

ENTRYPOINT ["/harbor-garbage-collector"]
