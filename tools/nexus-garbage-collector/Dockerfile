FROM docker.stackable.tech/stackable/ubi8-rust-builder AS builder

FROM registry.access.redhat.com/ubi8/ubi-minimal AS operator

ARG VERSION
ARG RELEASE="1"

# Update image
RUN microdnf update && microdnf clean all

COPY --from=builder /app/nexus-garbage-collector  /

ENTRYPOINT ["/nexus-garbage-collector"]
