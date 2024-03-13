use axum::{
    extract::Path,
    http::{header, HeaderMap},
};
use axum_extra::response::ErasedJson;

use crate::utils::{verify_attestation, DownloadSbomError};

pub async fn download(
    Path((repository, digest)): Path<(String, String)>,
) -> Result<(HeaderMap, ErasedJson), DownloadSbomError> {
    let attestation = verify_attestation(&repository, &digest).await?;
    let mut headers = HeaderMap::new();
    headers.insert(header::CONTENT_TYPE, "application/json".parse().unwrap());
    headers.insert(
        header::CONTENT_DISPOSITION,
        format!("attachment; filename=\"{}-{}.json\"", repository, digest)
            .parse()
            .unwrap(),
    );
    Ok((headers, ErasedJson::pretty(attestation.predicate)))
}
