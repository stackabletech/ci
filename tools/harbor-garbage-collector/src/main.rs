use regex::Regex;
use serde::Deserialize;
use std::env;
use std::time::Duration;
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

const ROBOT_USER: &str = "robot$stackable-cleanup";

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let registry_hostname = "oci.stackable.tech";
    let base_url = format!("https://{}/api/v2.0", registry_hostname);
    let page_size = 20;
    let mut page = 1;
    let attestation_tag_regex = Regex::new(r"^sha256-[0-9a-f]{64}.att$").unwrap();

    // Fail fast if the cleanup credential is missing. Previously this used
    // `.ok()`, so a missing/renamed variable silently produced unauthenticated
    // DELETEs that Harbor rejects while the tool still exits 0.
    let robot_password = env::var("HARBOR_ROBOT_PASSWORD")
        .map_err(|_| "HARBOR_ROBOT_PASSWORD environment variable must be set")?;

    // One shared client with a timeout, so a hung registry can't block forever.
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(30))
        .build()?;

    loop {
        // Loop over all repositories, paged
        let url = format!(
            "{}/repositories?page_size={}&page={}",
            base_url, page_size, page
        );

        let repositories: Vec<Repository> = client.get(&url).send().await?.json().await?;

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
                let artifacts_page: Vec<Artifact> = client
                    .get(format!(
                        "{}/projects/{}/repositories/{}/artifacts?page_size={}&page={}",
                        base_url,
                        encode(project_name),
                        encode(repository_name),
                        page_size,
                        page
                    ))
                    .send()
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
                    client
                        .delete(format!(
                            "{}/projects/{}/repositories/{}/artifacts/{}",
                            base_url,
                            encode(project_name),
                            encode(repository_name),
                            attestation_tag
                        ))
                        .basic_auth(ROBOT_USER, Some(&robot_password))
                        .send()
                        .await?
                        .error_for_status()?;
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

    for ubi_version in &["ubi8", "ubi9"] {
        let latest_url = format!(
            "{}/projects/sdp/repositories/{}-rust-builder/artifacts/latest",
            base_url, ubi_version
        );

        let latest_rust_builder_manifest_list: Artifact =
            client.get(&latest_url).send().await?.json().await?;

        let latest_digest = latest_rust_builder_manifest_list.digest.clone();
        // Tolerate a "latest" that is a plain manifest without references
        // (e.g. temporarily single-arch) instead of panicking.
        let referenced_digests = latest_rust_builder_manifest_list
            .references
            .unwrap_or_default()
            .into_iter()
            .map(|reference| reference.child_digest)
            .collect::<Vec<String>>();

        // Fetch the full artifact list, paginated (a single page_size=100
        // request silently ignored anything beyond the first 100 artifacts).
        let mut rust_builder_artifacts: Vec<Artifact> = Vec::new();
        let mut page = 1;
        let page_size = 100;
        loop {
            let artifacts_page: Vec<Artifact> = client
                .get(format!(
                    "{}/projects/sdp/repositories/{}-rust-builder/artifacts?page_size={}&page={}",
                    base_url, ubi_version, page_size, page
                ))
                .send()
                .await?
                .json()
                .await?;
            let number_of_returned_artifacts = artifacts_page.len();
            rust_builder_artifacts.extend(artifacts_page);
            if number_of_returned_artifacts < page_size {
                break;
            }
            page += 1;
        }

        // Guard against a race: if a new image was tagged "latest" between the
        // snapshot above and now, our referenced-digests set is stale and we
        // could delete the *current* latest. Re-check and skip if it moved.
        let latest_after: Artifact = client.get(&latest_url).send().await?.json().await?;
        if latest_after.digest != latest_digest {
            println!(
                "'latest' for {}-rust-builder changed during the run; skipping cleanup to avoid deleting the current latest.",
                ubi_version
            );
            continue;
        }

        for artifact in rust_builder_artifacts {
            // Keep "latest" and its referenced artifacts
            if artifact.digest != latest_digest && !referenced_digests.contains(&artifact.digest) {
                println!(
                    "Removing dangling rust builder artifact {}",
                    artifact.digest
                );
                client
                    .delete(format!(
                        "{}/projects/sdp/repositories/{}-rust-builder/artifacts/{}",
                        base_url, ubi_version, artifact.digest,
                    ))
                    .basic_auth(ROBOT_USER, Some(&robot_password))
                    .send()
                    .await?
                    .error_for_status()?;
            }
        }
    }

    Ok(())
}
