use std::collections::HashMap;
use std::sync::OnceLock;
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
    let mut ip_addresses = conn_pool.get(hashed_metadata).unwrap_or(&vec![]).clone();

    ip_addresses.push(ip_address.to_string());
    conn_pool.insert(hashed_metadata.to_string(), ip_addresses);
}

pub async fn remove_meta_ip(hashed_metadata: &str) {
    get_conn_reference().write().await.remove(hashed_metadata);
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
fn get_channel_pool() -> &'static RwLock<HashMap<String, UnboundedSender<String>>> {
    static CHANNELS_POOL: OnceLock<RwLock<HashMap<String, UnboundedSender<String>>>> =
        OnceLock::new();
    CHANNELS_POOL.get_or_init(|| RwLock::new(HashMap::new()))
}
pub async fn get_sender_channel(ip: &str) -> Option<UnboundedSender<String>> {
    let mapped_ch = get_channel_pool().read().await;
    mapped_ch.get(ip).cloned()
}

pub async fn insert_sender_chan(ip: &str, sender: UnboundedSender<String>) {
    let mut mapped_ch = get_channel_pool().write().await;
    mapped_ch.insert(ip.to_string(), sender);
}

pub async fn remover_sender_chan(ip: &str) {
    get_channel_pool().write().await.remove(ip);
}
