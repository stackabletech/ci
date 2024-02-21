use axum::{routing::get, Router};
use structs::CachedObject;

pub mod handlers;
pub mod structs;
use crate::handlers::*;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let cached_rendered_artifact_tree = CachedObject::new();

    let app = Router::new()
        .route("/", get(artifact_tree::render_as_html))
        .route("/sbom/:repository/:digest", get(sbom::download))
        .with_state(cached_rendered_artifact_tree);
    let listener = tokio::net::TcpListener::bind("0.0.0.0:9000").await.unwrap();

    axum::serve(listener, app).await.unwrap();
}
