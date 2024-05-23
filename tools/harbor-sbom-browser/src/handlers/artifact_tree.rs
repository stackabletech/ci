use crate::structs::*;
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::{Html, IntoResponse, Response};
use lazy_static::lazy_static;
use regex::Regex;
use snafu::{OptionExt, ResultExt, Snafu};
use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Mutex};
use strum::{EnumDiscriminants, IntoStaticStr};
use tracing::error;
use urlencoding::encode;

type ArtifactTree = BTreeMap<String, BTreeMap<String, BTreeSet<TagInfo>>>;

#[derive(Snafu, Debug, EnumDiscriminants)]
#[strum_discriminants(derive(IntoStaticStr))]
#[snafu(visibility(pub))]
#[allow(clippy::enum_variant_names)]
pub enum ArtifactTreeError {
    #[snafu(display("cannot get repositories"))]
    GetRepositories { source: reqwest::Error },
    #[snafu(display("cannot parse repositories"))]
    ParseRepositories { source: reqwest::Error },
    #[snafu(display("cannot get artifacts"))]
    GetArtifacts { source: reqwest::Error },
    #[snafu(display("cannot parse artifacts"))]
    ParseArtifacts { source: reqwest::Error },
    #[snafu(display("unexpected repository name"))]
    UnexpectedRepositoryName,
}

impl IntoResponse for ArtifactTreeError {
    fn into_response(self) -> Response {
        error!("error: {:?}", self);
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("Something went wrong: {}", self),
        )
            .into_response()
    }
}

lazy_static! {
    static ref RELEASE_TAG_REGEX: Regex =
        Regex::new(r"^(?P<prefix>.+\-stackable)?(?P<release>\d+\.\d+\.\d+(\-dev)?(\-(?P<architecture>arm64|amd64))?)$").unwrap();
}

pub async fn render_as_html(
    State(cached_rendered_artifact_tree): State<CachedObject<Html<String>>>,
) -> Result<Html<String>, ArtifactTreeError> {
    // if the artifact tree is already cached, return it
    if let Some(html) = cached_rendered_artifact_tree.get() {
        return Ok(html);
    }

    let artifact_tree = build_artifact_tree().await?;

    let mut html = String::with_capacity(64 * 1024); // reserve 64KB to avoid reallocations
    html.push_str(
        r#"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stackable :: SBOM Browser</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 20px;
            font-size: 20px;
        }
        ul {
            list-style-type: none;
            padding: 0;
            cursor: pointer;
        }
        li {
            margin: 6px 0;
            padding-left: 25px;
            position: relative;
            flex-direction: column;
            justify-content: center;
            display: none;
        }
        li::before {
            content: "";
            position: absolute;
            top: 4px;
            left: 0;
            width: 10px;
            height: 10px;
            border-top: 2px solid #000;
            border-right: 2px solid #000;
            transform: rotate(45deg);
        }
        li.open > ul > li, ul#tree > li {
            display: flex;
        }
        li.open::before {
            transform: rotate(135deg);
            top: 2px;
            left: 4px;
        }
        li.artifact::before {
            display: none;
        }
    </style>
</head>
<body>
<div align="center">
    <a href="https://stackable.tech/">Stackable Data Platform</a> |
    <a href="https://docs.stackable.tech/">Documentation</a> |
    <a href="https://github.com/orgs/stackabletech/discussions">Discussions</a> |
    <a href="https://discord.gg/7kZ3BNnCAF">Discord</a>
</div>
    <ul id='tree'>"#,
    );

    for (release_version, repositories) in artifact_tree {
        html.push_str(&format!("<li>Release {}<ul>", release_version));
        for (repository, artifacts) in repositories {
            html.push_str(&format!("<li>{}<ul>", repository));
            for artifact in artifacts {
                html.push_str(&format!(
                    "<li class='artifact'><a href='/sbom/{}/{}'>{}</a></li>",
                    repository, artifact.digest, artifact.name
                ));
            }
            html.push_str("</ul></li>");
        }
        html.push_str("</ul></li>");
    }

    html.push_str(
        r#"</ul>
    <script>
        const tree = document.getElementById("tree");
        tree.addEventListener("click", (event) => {
            const target = event.target;
            if (target.tagName === "LI") {
                target.classList.toggle("open");
            }
        });
    </script>
</body>
</html>
"#,
    );

    let html = Html(html);
    cached_rendered_artifact_tree.set_to(html.clone());
    Ok(html)
}

async fn build_artifact_tree() -> Result<ArtifactTree, ArtifactTreeError> {
    let registry_hostname = "oci.stackable.tech";
    let base_url = format!("https://{}/api/v2.0", registry_hostname);
    let url = format!("{}/repositories?page_size={}&q=name=~sdp/", base_url, 100);

    let response = reqwest::get(&url).await.context(GetRepositoriesSnafu)?;
    let repositories: Vec<Repository> = response.json().await.context(ParseRepositoriesSnafu)?;
    let artifact_tree = Arc::new(Mutex::new(ArtifactTree::new()));

    let mut requests = Vec::new();
    for repository in &repositories {
        let (project_name, repository_name) = repository
            .name
            .split_once('/')
            .context(UnexpectedRepositoryNameSnafu)?;
        requests.push(process_artifacts(
            &base_url,
            project_name,
            repository_name,
            artifact_tree.clone(),
        ));
    }
    futures::future::try_join_all(requests).await?;
    Ok(Arc::try_unwrap(artifact_tree)
        .unwrap()
        .into_inner()
        .unwrap())
}

pub async fn process_artifacts(
    base_url: &str,
    project_name: &str,
    repository_name: &str,
    artifact_tree: Arc<Mutex<ArtifactTree>>,
) -> Result<(), ArtifactTreeError> {
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
        .await
        .context(GetArtifactsSnafu)?
        .json()
        .await
        .context(ParseArtifactsSnafu)?;

        let number_of_returned_artifacts = artifacts_page.len();
        artifacts.extend(artifacts_page);
        if number_of_returned_artifacts < page_size {
            break;
        }
        page += 1;
    }

    for artifact in &artifacts {
        let has_release_tag = artifact.tags.as_ref().and_then(|tags| {
            tags.iter()
                .filter_map(|tag| {
                    RELEASE_TAG_REGEX.captures(&tag.name).map(|captures| {
                        (tag, captures.name("release").unwrap().as_str().to_string(), captures.name("architecture"))
                    })
                })
                .next()
        });

        if let Some(release_artifact) = has_release_tag {
            let mut release_version = release_artifact.1.clone();
            let matches_architecture_regex = &release_artifact.2.is_some();

            let is_multi_arch = release_version.contains("-dev") && !repository_name.contains("-operator");
            if is_multi_arch && !matches_architecture_regex {
                continue;
            }
            release_version = release_version.replace("-arm64", "").replace("-amd64", "");

            artifact_tree
                .lock()
                .unwrap()
                .entry(release_version.to_string())
                .or_default()
                .entry(repository_name.to_string())
                .or_default()
                .insert(TagInfo {
                    name: release_artifact.0.name.clone(),
                    digest: artifact.digest.clone().replace("sha256:", ""),
                });
        }
    }

    Ok(())
}