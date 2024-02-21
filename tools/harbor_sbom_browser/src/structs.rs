use std::sync::{Arc, RwLock};

use serde::Deserialize;
use serde_json::Value;
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
        // flush the cache after 1 hour
        let cache = self.cache.clone();
        tokio::spawn(async move {
            tokio::time::sleep(std::time::Duration::from_secs(3600)).await;
            *cache.write().unwrap() = None;
        });
    }

    pub fn get(&self) -> Option<T> {
        self.cache.read().unwrap().clone()
    }
}
