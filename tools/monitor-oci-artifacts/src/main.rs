use std::process::{exit, Command, Stdio};

use serde::Deserialize;
use urlencoding::encode;

#[derive(Deserialize, Debug)]
struct Repository {
    name: String,
}

#[derive(Deserialize, Debug)]
struct Tag {}

#[derive(Deserialize, Debug)]
struct Artifact {
    digest: String,
    tags: Option<Vec<Tag>>,
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
                let artifact_uri = format!(
                    "{}/{}/{}@{}",
                    registry_hostname, project_name, repository_name, artifact.digest
                );
                println!("trying to verify {}", artifact_uri);

                let status = Command::new("cosign")
                    .arg("verify")
                    .arg("--certificate-identity-regexp")
                    .arg("^https://github.com/stackabletech/.+")
                    .arg("--certificate-oidc-issuer")
                    .arg("https://token.actions.githubusercontent.com")
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
