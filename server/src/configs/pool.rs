use std::collections::HashMap;
use std::sync::{Arc, OnceLock};
use tokio::sync::{RwLock, mpsc::UnboundedSender};

type HashedMetadataIpAddress = HashMap<String, Vec<String>>;

pub fn get_conn_reference() -> &'static RwLock<HashedMetadataIpAddress> {
    static CONNECTION: OnceLock<RwLock<HashedMetadataIpAddress>> = OnceLock::new();
    CONNECTION.get_or_init(|| RwLock::new(HashMap::new()))
}

pub async fn get_meta_ip_cloned() -> HashedMetadataIpAddress {
    get_conn_reference().read().await.clone()
}

pub async fn add_meta_ip(hashed_metadata: &str, ip_address: &str) {
    let mut conn_pool = get_conn_reference().write().await;
    let ips = conn_pool.entry(hashed_metadata.to_string()).or_default();
    if !ips.contains(&ip_address.to_string()) {
        ips.push(ip_address.to_string());
    }
}

pub async fn remove_meta_ip(hashed_metadata: &str, ip_address: &str) {
    let mut conn_pool = get_conn_reference().write().await;
    if let Some(ips) = conn_pool.get_mut(hashed_metadata) {
        ips.retain(|ip| ip != ip_address);
        if ips.is_empty() {
            conn_pool.remove(hashed_metadata);
        }
    }
}

pub async fn get_meta_ip_key(hashed_metadata: &str) -> Vec<String> {
    get_meta_ip_cloned()
        .await
        .get(hashed_metadata)
        .cloned()
        .unwrap_or(vec![])
}

//-------------------------------------------
// These channels are used to send messages to all every connected client...etc
fn get_channel_pool() -> &'static RwLock<HashMap<String, Arc<UnboundedSender<String>>>> {
    static CHANNELS_POOL: OnceLock<RwLock<HashMap<String, Arc<UnboundedSender<String>>>>> =
        OnceLock::new();
    CHANNELS_POOL.get_or_init(|| RwLock::new(HashMap::new()))
}
pub async fn get_sender_channel(ip: &str) -> Option<Arc<UnboundedSender<String>>> {
    let mapped_ch = get_channel_pool().read().await;
    mapped_ch.get(ip).cloned()
}

/// Inserts the sender and returns an `Arc` handle the caller must hold to prove ownership.
pub async fn insert_sender_chan(
    ip: &str,
    sender: UnboundedSender<String>,
) -> Arc<UnboundedSender<String>> {
    let arc = Arc::new(sender);
    let mut mapped_ch = get_channel_pool().write().await;
    mapped_ch.insert(ip.to_string(), arc.clone());
    arc
}

/// Removes the sender only if the stored entry is the same `Arc` instance as `owned`.
/// This prevents a reconnecting client's sender from being removed by a stale cleanup task.
pub async fn remover_sender_chan_if_owned(ip: &str, owned: &Arc<UnboundedSender<String>>) {
    let mut mapped_ch = get_channel_pool().write().await;
    if let Some(stored) = mapped_ch.get(ip) {
        if Arc::ptr_eq(stored, owned) {
            mapped_ch.remove(ip);
        }
    }
}

//-------------------------------------------
// This channel pool is to store metadata secret keys upon new client connection...etc.
fn get_metadata_secret_keys_pool() -> &'static RwLock<HashMap<String, String>> {
    static METADATA_SECRET_KEYS_POOL: OnceLock<RwLock<HashMap<String, String>>> = OnceLock::new();
    METADATA_SECRET_KEYS_POOL.get_or_init(|| RwLock::new(HashMap::new()))
}

pub async fn get_metadata_secret_key(metadata: &str) -> Option<String> {
    let mapped_keys = get_metadata_secret_keys_pool().read().await;
    mapped_keys.get(metadata).cloned()
}
pub async fn insert_metadata_secret_key(metadata: &str, secret_key: &str) {
    let mut mapped_keys = get_metadata_secret_keys_pool().write().await;
    mapped_keys.insert(metadata.to_string(), secret_key.to_string());
}
