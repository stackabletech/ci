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
struct Artifact {
    digest: String,
    manifest_media_type: String,
    media_type: String,
    tags: Option<TagList>,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let registry_hostname = "oci.stackable.tech";
    let base_url = format!("https://{}/api/v2.0", registry_hostname);
    let page_size = 10;
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
            let artifacts: Vec<Artifact> = reqwest::get(format!(
                "{}/projects/{}/repositories/{}/artifacts",
                base_url,
                encode(project_name),
                encode(repository_name)
            ))
            .await?
            .json()
            .await?;
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
                        "skipping attestation {}{} ({})",
                        repository_name,
                        artifact.digest,
                        artifact.tags.as_ref().unwrap()
                    );
                    continue;
                }

                if project_name == "sdp" && repository_name != "git-sync" {
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
        }

        if repositories.len() < page_size {
            // no more pages
            break;
        }
        page += 1;
    }

    Ok(())
}
