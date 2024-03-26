use std::{
    fmt::Formatter,
    process::{exit, Command, Stdio},
};

use regex::Regex;
use serde::Deserialize;
use urlencoding::encode;

#[derive(Deserialize, Debug)]
struct Repository {
    name: String,
}

#[derive(Deserialize, Debug)]
struct Tag {
    name: String,
}

#[derive(Deserialize, Debug)]
struct TagList(Vec<Tag>);

impl std::fmt::Display for TagList {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let mut first = true;
        for tag in &self.0 {
            if first {
                first = false;
            } else {
                write!(f, ", ")?;
            }
            write!(f, "{}", tag.name)?;
        }
        Ok(())
    }
}

impl std::ops::Deref for TagList {
    type Target = Vec<Tag>;

    fn deref(&self) -> &Self::Target {
        &self.0
    }
}

#[derive(Deserialize, Debug)]
struct ArtifactReference {
    child_digest: String,
}
#[derive(Deserialize, Debug)]
struct Artifact {
    digest: String,
    manifest_media_type: String,
    media_type: String,
    tags: Option<TagList>,
    references: Option<Vec<ArtifactReference>>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let registry_hostname = "oci.stackable.tech";
    let base_url = format!("https://{}/api/v2.0", registry_hostname);
    let page_size = 20;
    let mut page = 1;
    let attestation_tag_regex = Regex::new(r"^sha256-[0-9a-f]{64}.att$").unwrap();

    loop {
        let url = format!(
            "{}/repositories?page_size={}&page={}",
            base_url, page_size, page
        );

        let response = reqwest::get(&url).await?;
        let repositories: Vec<Repository> = response.json().await?;

        for repository in &repositories {
            let (project_name, repository_name) = repository.name.split_once('/').unwrap();
            if project_name == "sandbox" {
                continue;
            }

            let mut attestations: Vec<String> = Vec::with_capacity(32);
            let mut potentially_attested_artifacts: Vec<&str> = Vec::with_capacity(32);
            let mut artifacts: Vec<Artifact> = Vec::with_capacity(64);
            let mut page = 1;
            let page_size = 20;
            loop {
                let artifacts_page: Vec<Artifact> = reqwest::get(format!(
                    "{}/projects/{}/repositories/{}/artifacts?page_size={}&page={}",
                    base_url,
                    encode(project_name),
                    encode(repository_name),
                    page_size,
                    page
                ))
                .await?
                .json()
                .await?;

                let number_of_returned_artifacts = artifacts_page.len();
                artifacts.extend(artifacts_page);
                if number_of_returned_artifacts < page_size {
                    break;
                }
                page += 1;
            }

            for artifact in &artifacts {
                if artifact
                    .tags
                    .as_ref()
                    .map(|tags| tags.is_empty())
                    .unwrap_or(true)
                {
                    continue;
                }

                if artifact.manifest_media_type == "application/vnd.oci.image.manifest.v1+json"
                    && artifact.media_type == "application/vnd.oci.image.config.v1+json"
                    && attestation_tag_regex.is_match(&artifact.tags.as_ref().unwrap()[0].name)
                // we can .unwrap() here because we checked that tags are present and not empty at the beginning of the for loop
                {
                    // it's an attestation, attestations artifacts themselves are not signed
                    println!(
                        "skipping attestation {} {} ({})",
                        repository_name,
                        artifact.digest,
                        artifact.tags.as_ref().unwrap()
                    );
                    attestations.push(artifact.tags.as_ref().unwrap()[0].name.clone());
                    continue;
                } else {
                    potentially_attested_artifacts.push(&artifact.digest[7..71]);
                }

                if project_name == "sdp"
                    && (repository_name != "git-sync" && repository_name != "ubi8-rust-builder")
                {
                    if artifact.manifest_media_type
                        != "application/vnd.docker.distribution.manifest.v2+json"
                    {
                        println!(
                            "unexpected manifest media type: {} for {} {} ({})",
                            artifact.manifest_media_type,
                            repository_name,
                            artifact.digest,
                            artifact.tags.as_ref().unwrap()
                        );
                        exit(2);
                    }
                    if artifact.media_type != "application/vnd.docker.container.image.v1+json" {
                        println!(
                            "unexpected media type: {} for {} {} ({})",
                            artifact.media_type,
                            repository_name,
                            artifact.digest,
                            artifact.tags.as_ref().unwrap()
                        );
                        exit(3);
                    }
                }

                let artifact_uri = format!(
                    "{}/{}/{}@{}",
                    registry_hostname, project_name, repository_name, artifact.digest
                );
                println!("trying to verify {}", artifact_uri);

                let cmd_output = Command::new("cosign")
                    .arg("verify")
                    .arg("--certificate-identity-regexp")
                    .arg("^https://github.com/stackabletech/.+")
                    .arg("--certificate-oidc-issuer")
                    .arg("https://token.actions.githubusercontent.com")
                    .arg(&artifact_uri)
                    .stdout(Stdio::inherit())
                    .stderr(Stdio::inherit())
                    .output()
                    .expect("failed to execute cosign");

                if !cmd_output.status.success() {
                    println!("failed to verify {}", artifact_uri);
                    println!(
                        "cosign reported: {}",
                        String::from_utf8_lossy(&cmd_output.stdout)
                    );
                    exit(cmd_output.status.code().unwrap_or(1));
                }
            }

            // remove dangling attestations
            for attestation in attestations {
                if !potentially_attested_artifacts.contains(&&attestation[7..71]) {
                    println!("removing dangling attestation {}", attestation);
                    reqwest::Client::new()
                        .delete(format!(
                            "{}/projects/{}/repositories/{}/artifacts/{}",
                            base_url,
                            encode(project_name),
                            encode(repository_name),
                            attestation
                        ))
                        .basic_auth("robot$stackable-cleanup", Some("XX"))
                        .send()
                        .await?;
                }
            }
        }

        if repositories.len() < page_size {
            // no more pages
            break;
        }
        page += 1;
    }

    let latest_rust_builder_artifact: Artifact = reqwest::Client::new()
        .get(format!(
            "{}/projects/sdp/repositories/ubi8-rust-builder/artifacts/latest",
            base_url,
        ))
        .send()
        .await?
        .json()
        .await?;

    let referenced_digests = latest_rust_builder_artifact
        .references
        .unwrap()
        .into_iter()
        .map(|reference| reference.child_digest)
        .collect::<Vec<String>>();

    let rust_builder_artifacts: Vec<Artifact> = reqwest::get(format!(
        "{}/projects/sdp/repositories/ubi8-rust-builder/artifacts?page_size=100",
        base_url
    ))
    .await?
    .json()
    .await?;

    // keep "latest" and its referenced artifacts
    for artifact in rust_builder_artifacts {
        if artifact.digest != latest_rust_builder_artifact.digest
            && !referenced_digests.contains(&artifact.digest)
        {
            println!(
                "removing dangling rust builder artifact {}",
                artifact.digest
            );
            reqwest::Client::new()
                .delete(format!(
                    "{}/projects/sdp/repositories/ubi8-rust-builder/artifacts/{}",
                    base_url, artifact.digest
                ))
                .basic_auth("robot$stackable-cleanup", Some("XX"))
                .send()
                .await?;
        }
    }

    Ok(())
}
// cachebust
