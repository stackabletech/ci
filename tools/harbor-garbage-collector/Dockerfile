FROM docker.stackable.tech/stackable/ubi8-rust-builder AS builder

FROM registry.access.redhat.com/ubi8/ubi-minimal AS operator

ARG VERSION
ARG RELEASE="1"

# Update image
RUN microdnf install -y yum \
    && yum -y update-minimal --security --sec-severity=Important --sec-severity=Critical \
    && yum clean all \
    && microdnf clean all

COPY --from=builder /app/harbor-garbage-collector  /

ENTRYPOINT ["/harbor-garbage-collector"]
