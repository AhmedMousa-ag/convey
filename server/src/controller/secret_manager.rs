use crate::{
    configs::{
        config::CHANGE_SECRET_INTERVAL_SECONDS,
        pool::{get_meta_ip_cloned, get_sender_channel, insert_metadata_secret_key},
    },
    models::models::SecretMetadataKey,
};
use sha2::Digest;
use std::collections::HashMap;

pub async fn secret_change_interval() {
    // Change the secret every constant time interval, so even if a secret is leaked, it will not be valid for a long time.
    let interval_duration = std::time::Duration::from_secs(CHANGE_SECRET_INTERVAL_SECONDS);
    loop {
        tokio::time::sleep(interval_duration).await;
        inform_metadata_clients_change_secret().await;
    }
}

pub async fn generate_secret_key(metadata: &str) -> String {
    // New secret is the hash of the metadata with the current timestamp + uuid, so it is unique and not guessable.
    let metadata_time_uuid = format!(
        "{}-{}-{}",
        metadata,
        chrono::Utc::now().timestamp(),
        uuid::Uuid::new_v4()
    );
    let metadata_new_secret = format!("{:x}", sha2::Sha256::digest(metadata_time_uuid.as_bytes()));
    insert_metadata_secret_key(&metadata, &metadata_new_secret).await;
    metadata_new_secret
}

/// Informs all clients of the newly changed secret, so they can update their secret key with each others.
async fn inform_metadata_clients_change_secret() {
    let meta_ips: HashMap<String, Vec<String>> = get_meta_ip_cloned().await;
    for (metadata, ips) in meta_ips {
        // Now let's hash265 the metadata_time_uuid to get the new secret.
        let metadata_new_secret = generate_secret_key(&metadata).await;

        let msg_to_send_res = serde_json::to_string(&SecretMetadataKey {
            hashed_metadata: metadata.clone(),
            new_secret: metadata_new_secret.clone(),
        });
        if let Ok(msg_to_send) = msg_to_send_res {
            // Send the new secret to all clients subscribed to this metadata.
            for ip in ips {
                print!("Sending updated secret to: {}", ip);
                let potential_sender = get_sender_channel(&ip).await;
                if let Some(sender) = potential_sender {
                    if let Err(e) = sender.send(msg_to_send.clone()) {
                        println!("Error sending internal channel: {}", e);
                    }
                }
            }
        }
    }
}
