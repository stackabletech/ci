use regex::Regex;
use serde::Deserialize;
use std::{
    fmt::Formatter,
    process::{exit, Command, Stdio},
};
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
            write!(f, "{tag}", tag = tag.name)?;
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
    let base_url = format!("https://{registry_hostname}/api/v2.0");
    let page_size = 20;
    let mut page = 1;
    let attestation_tag_regex = Regex::new(r"^sha256-[0-9a-f]{64}.att$").unwrap();

    loop {
        let url = format!("{base_url}/repositories?page_size={page_size}&page={page}",);

        let response = reqwest::get(&url).await?;
        let repositories: Vec<Repository> = response.json().await?;

        for repository in &repositories {
            let (project_name, repository_name) = repository.name.split_once('/').unwrap();

            if project_name == "sandbox" {
                continue;
            }

            let mut artifacts: Vec<Artifact> = Vec::with_capacity(64);
            let mut page = 1;
            let page_size = 20;

            loop {
                // Loop over pages to get all artifacts
                let artifacts_page: Vec<Artifact> = reqwest::get(format!(
                    "{base_url}/projects/{encoded_project_name}/repositories/{encoded_repository_name}/artifacts?page_size={page_size}&page={page}",
                    encoded_project_name = encode(project_name),
                    encoded_repository_name = encode(repository_name),
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

                let tags = artifact
                    .tags
                    .as_ref()
                    .expect("tags are checked to be present and not empty above");
                let digest = artifact.digest.as_str();

                if artifact
                    .tags
                    .as_ref()
                    .unwrap()
                    .iter()
                    .any(|tag| tag.name == "artifacthub.io")
                {
                    // Artifact Hub metadata artifacts are not signed
                    println!("skipping Artifact Hub metadata {repository_name} {digest} ({tags})");
                    continue;
                }

                if attestation_tag_regex.is_match(&artifact.tags.as_ref().unwrap()[0].name) {
                    // It's an attestation, attestations artifacts themselves are not signed
                    println!("skipping attestation {repository_name} {digest} ({tags})");
                    continue;
                }

                let artifact_uri =
                    format!("{registry_hostname}/{project_name}/{repository_name}@{digest}");
                println!("trying to verify {artifact_uri}");

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
                    println!("failed to verify {artifact_uri}");
                    println!(
                        "cosign reported: {stdout}",
                        stdout = String::from_utf8_lossy(&cmd_output.stdout)
                    );
                    exit(cmd_output.status.code().unwrap_or(1));
                }
            }
        }

        if repositories.len() < page_size {
            // No more pages
            break;
        }
        page += 1;
    }

    Ok(())
}
