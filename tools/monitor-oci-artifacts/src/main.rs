use std::{
    fmt::Formatter,
    process::{exit, Command, Stdio},
};

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

                if project_name == "sdp" {
                    if artifact.manifest_media_type
                        != "application/vnd.docker.distribution.manifest.v2+json"
                    {
                        println!(
                            "unexpected manifest media type: {} for {}{} ({})",
                            artifact.manifest_media_type,
                            repository_name,
                            artifact.digest,
                            artifact.tags.as_ref().unwrap()
                        );
                        exit(2);
                    }
                    if artifact.media_type != "application/vnd.docker.container.image.v1+json" {
                        println!(
                            "unexpected media type: {} for {}{} ({})",
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

                let status = Command::new("cosign")
                    .arg("verify")
                    .arg("--certificate-identity-regexp")
                    .arg("^(https://github.com/stackabletech/.+/.github/workflows/.+@.+|.+@stackable.tech)$")
                    .arg("--certificate-oidc-issuer")
                    .arg("^(https://token.actions.githubusercontent.com|https://github.com/login/oauth|https://accounts.google.com)$")
                    .arg(artifact_uri)
                    .stdout(Stdio::inherit())
                    .stderr(Stdio::inherit())
                    .output()
                    .expect("failed to execute cosign")
                    .status;

                if !status.success() {
                    exit(status.code().unwrap_or(1));
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
