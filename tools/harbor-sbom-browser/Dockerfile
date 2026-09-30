FROM oci.stackable.tech/sdp/ubi10-rust-builder AS builder

FROM registry.access.redhat.com/ubi10/ubi-minimal:10.2@sha256:a9f9316ec3a1419a2de6ce4d2d9f034d477e97cdf2a16d6f04b7bd632ac753c4 AS operator

ARG VERSION
ARG RELEASE="1"

# Update image
RUN microdnf install -y yum \
    && yum -y update-minimal --security --sec-severity=Important --sec-severity=Critical \
    && curl -L -O https://github.com/sigstore/cosign/releases/download/v3.1.3/cosign-3.1.3-1.x86_64.rpm \
    && rpm -ivh cosign-3.1.3-1.x86_64.rpm \
    && yum clean all \
    && microdnf clean all

# cosign caches the sigstore trusted root and the ctlog public keys below `$HOME/.sigstore`.
# The container runs as an unprivileged user whose home directory would otherwise be `/`, which
# is not writable, and every attestation verification would fail.
ENV HOME=/tmp

COPY --from=builder /app/harbor-sbom-browser  /

ENTRYPOINT ["/harbor-sbom-browser"]
