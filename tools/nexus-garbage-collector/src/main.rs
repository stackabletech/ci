use std::{env, process::exit};

use log::{debug, error, info};
use regex::Regex;
use reqwest::StatusCode;
use serde::Deserialize;

#[derive(Deserialize, Debug)]
struct Checksum {
    sha256: String,
}
#[derive(Deserialize, Debug)]
struct Asset {
    path: String,
    #[serde(rename = "contentType")]
    content_type: String,
    checksum: Checksum,
    id: String,
}
#[derive(Deserialize, Debug)]
struct AssetResponse {
    #[serde(rename = "continuationToken")]
    continuation_token: Option<String>,
    items: Vec<Asset>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    env_logger::init();
    let registry_hostname = "repo.stackable.tech";
    let base_url = format!(
        "https://{}/service/rest/v1/assets?repository=docker",
        registry_hostname
    );
    let attestation_tag_regex = Regex::new(r"/manifests/sha256-([0-9a-f]{64}).att$").unwrap();
    let signature_tag_regex = Regex::new(r"/manifests/sha256-([0-9a-f]{64}).sig$").unwrap();
    let mut continuation_token: Option<String> = None;
    let client = reqwest::Client::new();

    let mut signatures = Vec::<(String, String)>::new();
    let mut attestations = Vec::<(String, String)>::new();
    let mut normal_artifacts = Vec::<String>::new();

    let nexus_user = env::var("NEXUS_USER").unwrap();
    let nexus_password = env::var("NEXUS_PASSWORD").unwrap();

    loop {
        // Loop over all repositories, paged
        let mut url = base_url.clone();
        if let Some(continuation_token) = &continuation_token {
            url = format!("{}&continuationToken={}", base_url, continuation_token);
        }

        let resp: AssetResponse = client
            .get(&url)
            .basic_auth(&nexus_user, Some(&nexus_password))
            .send()
            .await?
            .json()
            .await?;

        for asset in &resp.items {
            if asset.content_type != "application/vnd.docker.image.rootfs.diff.tar.gzip"
                && !asset.path.contains("/sha256:")
            {
                if let Some(captures) = attestation_tag_regex.captures(&asset.path) {
                    attestations.push((asset.id.clone(), captures[1].to_string()));
                } else if let Some(captures) = signature_tag_regex.captures(&asset.path) {
                    signatures.push((asset.id.clone(), captures[1].to_string()));
                } else {
                    normal_artifacts.push(asset.checksum.sha256.clone());
                }
            }
        }

        continuation_token = resp.continuation_token;
        if let Some(ref continuation_token_value) = continuation_token {
            debug!(
                "Getting next page with continuation token {}",
                continuation_token_value
            );
        } else {
            // no more pages
            break;
        }
    }
    debug!("paging done!");

    for signature in signatures {
        let artifact = normal_artifacts
            .iter()
            .find(|&artifact| artifact == &signature.1);
        if artifact.is_none() {
            info!(
                "removing signature for {} (id {}) because it does not have a corresponding artifact",
                signature.1, signature.0
            );
            let status_code = client
                .delete(&format!(
                    "https://{}/service/rest/v1/assets/{}",
                    registry_hostname, signature.0
                ))
                .basic_auth(&nexus_user, Some(&nexus_password))
                .send()
                .await?
                .status();
            if status_code != StatusCode::NO_CONTENT {
                error!(
                    "removing signature {} failed with status code {}",
                    signature.1, status_code
                );
                exit(1);
            }
        }
    }
    for attestation in attestations {
        let artifact = normal_artifacts
            .iter()
            .find(|&artifact| artifact == &attestation.1);
        if artifact.is_none() {
            info!(
                "removing attestation for {} (id {}) because it does not have a corresponding artifact",
                attestation.1, attestation.0
            );
            let status_code = client
                .delete(&format!(
                    "https://{}/service/rest/v1/assets/{}",
                    registry_hostname, attestation.0
                ))
                .basic_auth(&nexus_user, Some(&nexus_password))
                .send()
                .await?
                .status();
            if status_code != StatusCode::NO_CONTENT {
                error!(
                    "removing attestation {} failed with status code {}",
                    attestation.1, status_code
                );
                exit(1);
            }
        }
    }

    Ok(())
}
