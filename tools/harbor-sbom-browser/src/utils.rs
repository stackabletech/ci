use crate::structs::{Dsse, InTotoAttestation};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use base64::prelude::BASE64_STANDARD;
use base64::Engine;
use lazy_static::lazy_static;
use regex::Regex;
use snafu::ResultExt;
use snafu::Snafu;
use std::process::Command;
use strum::{EnumDiscriminants, IntoStaticStr};
use tracing::error;

lazy_static! {
    static ref SHA256_REGEX: Regex = Regex::new(r"^[a-f0-9]{64}$").unwrap();
    static ref ALPHANUMERIC_REGEX: Regex = Regex::new(r"^[a-zA-Z0-9\-]+$").unwrap();
}

#[derive(Snafu, Debug, EnumDiscriminants)]
#[strum_discriminants(derive(IntoStaticStr))]
#[snafu(visibility(pub))]
#[allow(clippy::enum_variant_names)]
pub enum DownloadSbomError {
    #[snafu(display("invalid repository or digest"))]
    InvalidSbomParameters,
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
}

impl IntoResponse for DownloadSbomError {
    fn into_response(self) -> Response {
        error!("error: {:?}", self);
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Something went wrong: {}", self),
        )
            .into_response()
    }
}

pub async fn verify_attestation(
    repository: &str,
    digest: &str,
) -> Result<InTotoAttestation, DownloadSbomError> {
    if !SHA256_REGEX.is_match(digest) || !ALPHANUMERIC_REGEX.is_match(repository) {
        return Err(DownloadSbomError::InvalidSbomParameters);
    }
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
        .context(CosignExecutionSnafu)?;

    if !cmd_output.status.success() {
        let stderr_output = String::from_utf8_lossy(&cmd_output.stderr);
        return Err(DownloadSbomError::SbomVerification {
            cosign_stdout: String::from_utf8_lossy(&cmd_output.stdout).to_string(),
            cosign_stderr: stderr_output.to_string(),
            cosign_status: cmd_output.status,
            repository: repository.to_string(),
            digest: digest.to_string(),
        });
    }

    let output = String::from_utf8_lossy(&cmd_output.stdout);
    let dsse = serde_json::from_str::<Dsse>(&output).context(ParseDsseSnafu)?;
    let attestation_bytes = BASE64_STANDARD
        .decode(dsse.payload)
        .context(DecodeDssePayloadSnafu)?;
    let attestation_string =
        std::str::from_utf8(&attestation_bytes).context(ParseDssePayloadAsStringSnafu)?;
    serde_json::from_str::<InTotoAttestation>(attestation_string)
        .context(ParseInTotoAttestationSnafu)
}
