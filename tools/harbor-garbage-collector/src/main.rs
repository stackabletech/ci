use regex::Regex;
use serde::Deserialize;
use std::env;
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
struct ArtifactReference {
    child_digest: String,
}

#[derive(Deserialize, Debug)]
struct Artifact {
    digest: String,
    tags: Option<Vec<Tag>>,
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
        // Loop over all repositories, paged
        let url = format!(
            "{}/repositories?page_size={}&page={}",
            base_url, page_size, page
        );

        let repositories: Vec<Repository> = reqwest::get(&url).await?.json().await?;

        for repository in &repositories {
            let (project_name, repository_name) = repository.name.split_once('/').unwrap();

            if project_name == "sandbox" {
                continue;
            }

            let mut attestations: Vec<&str> = Vec::with_capacity(32);
            let mut potentially_attested_artifacts: Vec<&str> = Vec::with_capacity(32);
            let mut artifacts: Vec<Artifact> = Vec::with_capacity(64);

            let mut page = 1;
            let page_size = 20;

            loop {
                // Loop over pages to get all artifacts
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
                    continue; // Skip artifacts without tags
                }

                if attestation_tag_regex.is_match(&artifact.tags.as_ref().unwrap()[0].name)
                // .unwrap() can be used here because it's checked that tags are present and not empty at the beginning of the for loop
                {
                    // It's an attestation
                    // [7..71] extracts just the sha hash
                    attestations.push(&artifact.tags.as_ref().unwrap()[0].name[7..71]);
                } else {
                    potentially_attested_artifacts.push(&artifact.digest[7..71]);
                }
            }

            // Remove dangling attestations
            for attestation_referenced_sha in attestations {
                if !potentially_attested_artifacts.contains(&attestation_referenced_sha) {
                    let attestation_tag = format!("sha256-{}.att", attestation_referenced_sha);
                    println!("Removing dangling attestation {}", attestation_tag);
                    reqwest::Client::new()
                        .delete(format!(
                            "{}/projects/{}/repositories/{}/artifacts/{}",
                            base_url,
                            encode(project_name),
                            encode(repository_name),
                            attestation_tag
                        ))
                        .basic_auth(
                            "robot$stackable-cleanup",
                            env::var("HARBOR_ROBOT_PASSWORD").ok(),
                        )
                        .send()
                        .await?;
                }
            }
        }

        if repositories.len() < page_size {
            // No more pages
            break;
        }
        page += 1;
    }

    // Cleanup old rust builder artifacts, they don't get garbage collected by Harbor because all of them are tagged
    // Only keep the "latest" manifest and its referenced artifacts
    let latest_rust_builder_manifest_list: Artifact = reqwest::Client::new()
        .get(format!(
            "{}/projects/sdp/repositories/ubi8-rust-builder/artifacts/latest",
            base_url,
        ))
        .send()
        .await?
        .json()
        .await?;

    let referenced_digests = latest_rust_builder_manifest_list
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

    for artifact in rust_builder_artifacts {
        // Keep "latest" and its referenced artifacts
        if artifact.digest != latest_rust_builder_manifest_list.digest
            && !referenced_digests.contains(&artifact.digest)
        {
            println!(
                "Removing dangling rust builder artifact {}",
                artifact.digest
            );
            reqwest::Client::new()
                .delete(format!(
                    "{}/projects/sdp/repositories/ubi8-rust-builder/artifacts/{}",
                    base_url, artifact.digest
                ))
                .basic_auth(
                    "robot$stackable-cleanup",
                    env::var("HARBOR_ROBOT_PASSWORD").ok(),
                )
                .send()
                .await?;
        }
    }

    Ok(())
}
