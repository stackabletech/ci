use std::sync::{Arc, RwLock};
use std::time::Duration;

use serde::Deserialize;
use serde_json::Value;

/// How long a cached object stays valid. This is kept short, because artifacts are deleted from the
/// registry regularly (e.g. dev builds), and links to deleted artifacts do not work any more.
const CACHE_TTL: Duration = Duration::from_secs(600);
#[derive(Deserialize, Debug)]
pub struct Repository {
    pub name: String,
}

#[derive(Deserialize, Debug)]
pub struct Tag {
    pub name: String,
}

#[derive(Deserialize, Debug)]
pub struct Artifact {
    pub digest: String,
    pub tags: Option<Vec<Tag>>,
}

#[derive(Deserialize, Debug)]
pub struct InTotoAttestation {
    pub predicate: Value,
}
#[derive(Deserialize, Debug)]
pub struct Dsse {
    pub payload: String,
}

#[derive(Debug, PartialEq, Eq, PartialOrd, Ord)]
pub struct TagInfo {
    pub name: String,
    pub digest: String,
}

#[derive(Clone, Default)]
pub struct CachedObject<T> {
    cache: Arc<RwLock<Option<T>>>,
}

impl<T> CachedObject<T>
where
    T: Clone + Send + Sync + 'static,
{
    pub fn new() -> Self {
        Self {
            cache: Arc::new(RwLock::new(None)),
        }
    }

    pub fn set_to(&self, value: T) {
        *self.cache.write().unwrap() = Some(value);
        // flush the cache after the TTL has elapsed
        let cache = self.cache.clone();
        tokio::spawn(async move {
            tokio::time::sleep(CACHE_TTL).await;
            *cache.write().unwrap() = None;
        });
    }

    pub fn get(&self) -> Option<T> {
        self.cache.read().unwrap().clone()
    }
}
