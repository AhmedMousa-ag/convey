use crate::configs::pool::{
    add_meta_ip, get_meta_ip_key, get_metadata_secret_key, get_sender_channel,
    insert_metadata_secret_key, insert_sender_chan, remove_meta_ip, remover_sender_chan,
};
use crate::controller::secret_manager::generate_secret_key;
use crate::models::models::{
    ClientsIPAddresses, ConveyMessage, MessagesTypes, SecretMetadataKey, ServerMessage,
};
use axum::{
    extract::{
        connect_info::ConnectInfo,
        ws::{Message, WebSocket, WebSocketUpgrade},
    },
    response::Response,
};
use std::net::SocketAddr;
use tokio::sync::mpsc::unbounded_channel;

pub async fn handler(ws: WebSocketUpgrade, ConnectInfo(addr): ConnectInfo<SocketAddr>) -> Response {
    ws.on_upgrade(move |socket| handle_socket(socket, addr))
}

async fn handle_socket(mut socket: WebSocket, addr: SocketAddr) {
    println!("Connection established from IP: {}", addr);
    let ip_add = addr.ip().to_string();
    let (sender, mut internal_reciver) = unbounded_channel();
    insert_sender_chan(&ip_add, sender).await;
    let mut client_stored_metadata: Vec<String> = Vec::new();
    loop {
        tokio::select! {
            Some(Ok(msg)) = socket.recv() => {
                match msg {
                    Message::Text(text) => {
                        let client_msg_res = ServerMessage::decode_str(&text.to_string());
                        if let Ok(client_msg) = client_msg_res {
                            println!("Got a message type: {:?}", client_msg.msg_type);
                            match client_msg.message {
                                ConveyMessage::ReqSubscribeTopic(subscribe) => {
                                    let metadata = subscribe.hashed_metadata;
                                    add_meta_ip(&metadata, &ip_add).await;
                                    client_stored_metadata.push(metadata.clone());
                                    inform_self_metadata_clients(&metadata, &ip_add).await;
                                    inform_metadata_clients(&metadata, &ip_add, true).await;

                                },
                                _ => {
                                    println!("Got un supported message from client... Will Ignore it\nMessage: {:?}", client_msg.message);
                                }
                            }
                        } else {
                            println!("Error decoding server message: {:?}", client_msg_res)
                        }
                    },
                    Message::Close(_) => {
                        println!("Client {} disconnected", addr);
                        break;
                    }
                    _ => {}
                }
            }
            Some(msg) = internal_reciver.recv() => {
                if let Err(e) = socket.send(Message::Text(msg.into())).await {
                    dbg!("{:?}", e);
                }
            }
            else => break
        }
    }
    // If reached here, the connection is closed.
    remover_sender_chan(&ip_add).await;
    // Run it in another thread in case the client connects again before the cleanup is done.
    tokio::spawn(async move {
        for mtdata in client_stored_metadata {
            remove_meta_ip(&mtdata).await;
            inform_metadata_clients(&mtdata, &ip_add, false).await;
        }
    });
}

async fn inform_self_metadata_clients(metadata_hash: &str, curr_ip_address: &str) {
    let all_ips = get_meta_ip_key(metadata_hash).await;
    let sender = match get_sender_channel(&curr_ip_address).await {
        Some(sender) => sender,
        None => {
            println!("Error: No sender channel found for IP: {}", curr_ip_address);
            return;
        }
    };

    for ip in all_ips {
        if ip == curr_ip_address {
            // Send secret key to self as well, then continue to next ip without sending the subscribe message.
            let secret_key = get_metadata_secret_key(metadata_hash).await.unwrap_or({
                let new_secret = generate_secret_key(metadata_hash).await;
                insert_metadata_secret_key(metadata_hash, &new_secret).await;
                new_secret
            });
            let secret_msg = ServerMessage {
                msg_type: MessagesTypes::ChangeSecret,
                message: ConveyMessage::SecretMetadataKey(SecretMetadataKey {
                    hashed_metadata: metadata_hash.to_string(),
                    new_secret: secret_key.clone(),
                }),
            };
            if let Err(e) = sender.send(serde_json::to_string(&secret_msg).unwrap_or_default()) {
                println!("Error sending secret key internal channel: {}", e);
            }
            continue;
        }
        let msg_to_send_res = serde_json::to_string(&ServerMessage {
            msg_type: MessagesTypes::Subscribe,
            message: ConveyMessage::SubscribeTopic(ClientsIPAddresses {
                hashed_metadata: metadata_hash.to_string(),
                ip: ip.to_string(),
                is_adding: true,
            }),
        });
        if let Ok(msg_to_send) = msg_to_send_res {
            if let Err(e) = sender.send(msg_to_send.clone()) {
                println!("Error sending internal channel: {}", e);
            }
        }
    }
}

/// Informs all clients of each other.
async fn inform_metadata_clients(metadata_hash: &str, curr_ip_address: &str, is_adding: bool) {
    let all_ips = get_meta_ip_key(metadata_hash).await;
    let msg_to_send_res = serde_json::to_string(&ServerMessage {
        msg_type: MessagesTypes::Subscribe,
        message: ConveyMessage::SubscribeTopic(ClientsIPAddresses {
            hashed_metadata: metadata_hash.to_string(),
            ip: curr_ip_address.to_string(),
            is_adding,
        }),
    });
    if let Ok(msg_to_send) = msg_to_send_res {
        for ip in all_ips {
            if &ip == curr_ip_address {
                continue;
            }
            let potential_sender = get_sender_channel(&ip).await;
            if let Some(sender) = potential_sender {
                if let Err(e) = sender.send(msg_to_send.clone()) {
                    println!("Error sending internal channel: {}", e);
                }
            }
        }
    }
}
