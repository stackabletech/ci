use axum::{
    extract::Path,
    http::{header, HeaderMap},
};

use crate::utils::{verify_attestation, DownloadSbomError};

pub async fn download(
    Path((repository, digest)): Path<(String, String)>,
) -> Result<(HeaderMap, String), DownloadSbomError> {
    let attestation = verify_attestation(&repository, &digest).await?;
    let mut headers = HeaderMap::new();
    headers.insert(header::CONTENT_TYPE, "application/json".parse().unwrap());
    headers.insert(
        header::CONTENT_DISPOSITION,
        format!("attachment; filename=\"{}-{}.json\"", repository, digest)
            .parse()
            .unwrap(),
    );
    // The SBOM is returned as it is in the attestation instead of being pretty-printed, which would
    // need the whole document parsed into memory.
    let sbom: Box<str> = attestation.predicate.into();
    Ok((headers, sbom.into_string()))
}
