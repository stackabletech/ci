/// Crawlers request every SBOM download link (one `cosign` run each) in bursts, which is not
/// what the SBOM browser is for. The links already carry `rel='nofollow'`, but that is only a hint.
const ROBOTS_TXT: &str = "User-agent: *\nDisallow: /sbom/\n";

pub async fn robots_txt() -> &'static str {
    ROBOTS_TXT
}
