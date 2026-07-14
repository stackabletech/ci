FROM oci.stackable.tech/sdp/ubi8-rust-builder AS builder

FROM registry.access.redhat.com/ubi8/ubi-minimal:8.10@sha256:578b238953144445a9b5bb2487eb1d95df4886f98d1f73c4a070b27535f51688 AS operator

ARG VERSION
ARG RELEASE="1"

# Update image
RUN microdnf update && microdnf clean all

COPY --from=builder /app/nexus-garbage-collector  /

ENTRYPOINT ["/nexus-garbage-collector"]
