FROM oci.stackable.tech/sdp/ubi9-rust-builder AS builder

FROM registry.access.redhat.com/ubi9/ubi-minimal:9.6@sha256:7c5495d5fad59aaee12abc3cbbd2b283818ee1e814b00dbc7f25bf2d14fa4f0c AS operator

ARG VERSION
ARG RELEASE="1"

# Update image
RUN microdnf install -y yum \
    && yum -y update-minimal --security --sec-severity=Important --sec-severity=Critical \
    && curl -L -O https://github.com/sigstore/cosign/releases/download/v3.0.2/cosign-3.0.2-1.x86_64.rpm \
    && echo "7b6ae0f1e8da49d196f89245d4014887747c01c215e2e7f41e4853c98a28ed9b  cosign-3.0.2-1.x86_64.rpm" > cosign-3.0.2-1.x86_64.rpm.sha256 \
    && sha256sum -c cosign-3.0.2-1.x86_64.rpm.sha256 \
    && rpm -ivh cosign-3.0.2-1.x86_64.rpm \
    && yum clean all \
    && microdnf clean all

COPY --from=builder /app/monitor-oci-artifacts  /

ENTRYPOINT ["/monitor-oci-artifacts"]