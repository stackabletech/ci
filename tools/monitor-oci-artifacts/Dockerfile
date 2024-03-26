FROM docker.stackable.tech/stackable/ubi8-rust-builder AS builder

FROM registry.access.redhat.com/ubi8/ubi-minimal AS operator

ARG VERSION
ARG RELEASE="1"

# Update image
RUN microdnf install -y yum \
    && yum -y update-minimal --security --sec-severity=Important --sec-severity=Critical \
    && curl -L -O https://github.com/sigstore/cosign/releases/download/v2.2.3/cosign-2.2.3-1.x86_64.rpm \
    && rpm -ivh cosign-2.2.3-1.x86_64.rpm \
    && yum clean all \
    && microdnf clean all

COPY --from=builder /app/monitor-oci-artifacts  /

ENTRYPOINT ["/monitor-oci-artifacts"]