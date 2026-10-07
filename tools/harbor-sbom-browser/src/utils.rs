use std::time::Duration;

use crate::structs::{Dsse, InTotoAttestation};
use axum::http::{header, StatusCode};
use axum::response::{IntoResponse, Response};
use base64::prelude::BASE64_STANDARD;
use base64::Engine;
use lazy_static::lazy_static;
use regex::Regex;
use snafu::ResultExt;
use snafu::Snafu;
use strum::{EnumDiscriminants, IntoStaticStr};
use tokio::process::Command;
use tokio::sync::Semaphore;
use tracing::{error, warn};

/// How many `cosign verify-attestation` processes may run at the same time. Each one needs up to
/// about 170 MiB for the larger SBOMs, and crawlers request dozens of SBOMs at once, which
/// otherwise gets the container OOMKilled.
const MAX_CONCURRENT_COSIGN_RUNS: usize = 4;

/// How long a request waits for a free cosign slot before it is rejected. Waiting requests cost
/// next to no memory, but without a bound a crawler burst queues for minutes.
const COSIGN_PERMIT_TIMEOUT: Duration = Duration::from_secs(10);

/// Sent with the 503 response when all cosign slots are taken.
const RETRY_AFTER_SECONDS: &str = "30";

lazy_static! {
    static ref SHA256_REGEX: Regex = Regex::new(r"^[a-f0-9]{64}$").unwrap();
    static ref ALPHANUMERIC_REGEX: Regex = Regex::new(r"^[a-zA-Z0-9\-]+$").unwrap();
    static ref COSIGN_PERMITS: Semaphore = Semaphore::new(MAX_CONCURRENT_COSIGN_RUNS);
}

#[derive(Snafu, Debug, EnumDiscriminants)]
#[strum_discriminants(derive(IntoStaticStr))]
#[snafu(visibility(pub))]
#[allow(clippy::enum_variant_names)]
pub enum DownloadSbomError {
    #[snafu(display("invalid repository or digest"))]
    InvalidSbomParameters,
    #[snafu(display("no SBOM attestation found for {repository}@sha256:{digest}"))]
    SbomNotFound { repository: String, digest: String },
    #[snafu(display("failed to verify SBOM"))]
    SbomVerification {
        cosign_stdout: String,
        cosign_stderr: String,
        cosign_status: std::process::ExitStatus,
        repository: String,
        digest: String,
    },
    #[snafu(display("cannot parse DSSE"))]
    ParseDsse { source: serde_json::Error },
    #[snafu(display("cannot decode DSSE payload"))]
    DecodeDssePayload { source: base64::DecodeError },
    #[snafu(display("cannot parse DSSE payload as string"))]
    ParseDssePayloadAsString { source: std::str::Utf8Error },
    #[snafu(display("cannot parse in-toto attestation"))]
    ParseInTotoAttestation { source: serde_json::Error },
    #[snafu(display("failed to execute cosign"))]
    CosignExecution { source: std::io::Error },
    #[snafu(display("too many SBOM downloads at the moment, try again later"))]
    CosignBusy,
}

impl DownloadSbomError {
    fn status_code(&self) -> StatusCode {
        match self {
            Self::InvalidSbomParameters => StatusCode::BAD_REQUEST,
            Self::SbomNotFound { .. } => StatusCode::NOT_FOUND,
            Self::CosignBusy => StatusCode::SERVICE_UNAVAILABLE,
            _ => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }
}

impl IntoResponse for DownloadSbomError {
    fn into_response(self) -> Response {
        let status_code = self.status_code();
        // Only unexpected failures are logged as errors. Requests for unknown images are expected,
        // because links to deleted artifacts (e.g. dev builds) are crawled long after the artifacts
        // are gone.
        if status_code == StatusCode::INTERNAL_SERVER_ERROR {
            error!("error: {:?}", self);
        } else {
            warn!("error: {:?}", self);
        }
        if matches!(self, Self::CosignBusy) {
            return (
                status_code,
                [(header::RETRY_AFTER, RETRY_AFTER_SECONDS)],
                self.to_string(),
            )
                .into_response();
        }
        (status_code, self.to_string()).into_response()
    }
}

pub async fn verify_attestation(
    repository: &str,
    digest: &str,
) -> Result<InTotoAttestation, DownloadSbomError> {
    if !SHA256_REGEX.is_match(digest) || !ALPHANUMERIC_REGEX.is_match(repository) {
        return Err(DownloadSbomError::InvalidSbomParameters);
    }
    // Held until the attestation is parsed, because parsing also holds copies of the whole SBOM.
    let _permit = tokio::time::timeout(COSIGN_PERMIT_TIMEOUT, COSIGN_PERMITS.acquire())
        .await
        .map_err(|_| DownloadSbomError::CosignBusy)?
        .expect("the cosign semaphore is never closed");
    let cmd_output = Command::new("cosign")
        .arg("verify-attestation")
        .arg("--type")
        .arg("cyclonedx")
        .arg("--certificate-identity-regexp")
        .arg("^https://github.com/stackabletech/.+/.github/workflows/.+@.+")
        .arg("--certificate-oidc-issuer")
        .arg("https://token.actions.githubusercontent.com")
        .arg(format!(
            "oci.stackable.tech/sdp/{}@sha256:{}",
            repository, digest
        ))
        .output()
        .await
        .context(CosignExecutionSnafu)?;

    if !cmd_output.status.success() {
        let stderr_output = String::from_utf8_lossy(&cmd_output.stderr);
        // cosign reports the same error for images without a CycloneDX attestation and for images
        // which do not exist (any more).
        if stderr_output.contains("no matching attestations") {
            return Err(DownloadSbomError::SbomNotFound {
                repository: repository.to_string(),
                digest: digest.to_string(),
            });
        }
        return Err(DownloadSbomError::SbomVerification {
            cosign_stdout: String::from_utf8_lossy(&cmd_output.stdout).to_string(),
            cosign_stderr: stderr_output.to_string(),
            cosign_status: cmd_output.status,
            repository: repository.to_string(),
            digest: digest.to_string(),
        });
    }

    parse_attestation(cmd_output.stdout)
}

fn parse_attestation(cosign_stdout: Vec<u8>) -> Result<InTotoAttestation, DownloadSbomError> {
    let dsse = serde_json::from_slice::<Dsse>(&cosign_stdout).context(ParseDsseSnafu)?;
    // Drop the cosign stdout to free memory before decoding the payload, which is a copy of the stdout.
    drop(cosign_stdout);
    let attestation_bytes = BASE64_STANDARD
        .decode(dsse.payload)
        .context(DecodeDssePayloadSnafu)?;
    let attestation_string =
        std::str::from_utf8(&attestation_bytes).context(ParseDssePayloadAsStringSnafu)?;
    serde_json::from_str::<InTotoAttestation>(attestation_string)
        .context(ParseInTotoAttestationSnafu)
}
