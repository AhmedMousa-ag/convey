use crate::configs::pool::{
    add_meta_ip, get_meta_ip_key, get_metadata_secret_key, get_sender_channel, insert_sender_chan,
    remove_meta_ip, remover_sender_chan,
};
use crate::controller::secret_manager::generate_secret_key;
use crate::models::models::{ClientsIPAddresses, ConveyMessage, SecretMetadataKey, ServerMessage};
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
    // 2. Use 'move' to pass the addr into the socket handler
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
                        println!("Got text msg from client: {}\nMessage: {}", ip_add,text);
                        let client_msg_res = ServerMessage::decode_str(&text.to_string());
                        if let Ok(client_msg)=client_msg_res {
                            println!("Got a message type: {:?}",client_msg.msg_type);
                            match client_msg.message {
                                ConveyMessage::SubscribeTopic(subscribe)=>{
                                    println!("Got a subscribe request");
                                    let metadata = subscribe.hashed_metadata;
                                    add_meta_ip(&metadata,&ip_add).await;
                                    inform_metadata_clients(&metadata,&ip_add,true).await;
                                    client_stored_metadata.push(metadata.clone());
                                    //Get the secret key for this metadata and send it to the client so it can use it for authentication in the future.
                                    let secret_key = get_metadata_secret_key(&metadata)
                                        .await//Theoretically, this should not be None since the client should have already got the secret key when it subscribed, but in case of any error, we will generate a new secret key and send it to the client.
                                        .unwrap_or(generate_secret_key(&metadata).await);
                                    let msg_to_send_res = serde_json::to_string(&SecretMetadataKey{
                                        hashed_metadata: metadata,
                                        new_secret:secret_key,
                                    });
                                    if let Ok(msg_to_send) = msg_to_send_res {
                                        if let Err(e) = socket.send(Message::Text(msg_to_send.into())).await{
                                            dbg!("{:?}", e);
                                        }
                                    }

                                }
                                ConveyMessage::SecretMetadataKey(_)=> {
                                    println!("Got a change secret from client which is shall not be invoked by the client... Will Ignore it");
                                }

                            }
                        } else{
                            println!("Error decoding server message: {:?}",client_msg_res)
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
                println!("Will send a message: {:?}",msg);
                if let Err(e) = socket.send(Message::Text(msg.into())).await{
                    dbg!("{:?}", e);
                }
            }
            else => break
        }
    }
    //If reached here, the connection is closed.
    for mtdata in client_stored_metadata {
        remove_meta_ip(&mtdata).await;
        inform_metadata_clients(&mtdata, &ip_add, false).await;
    }
    remover_sender_chan(&ip_add).await;
}

///Informs all clients of each others.
async fn inform_metadata_clients(metadata_hash: &str, curr_ip_address: &str, is_adding: bool) {
    let all_ips = get_meta_ip_key(metadata_hash).await;
    let secret_key = get_metadata_secret_key(metadata_hash)
        .await
        .unwrap_or(generate_secret_key(metadata_hash).await);

    let msg_to_send_res = serde_json::to_string(&ClientsIPAddresses {
        hashed_metadata: metadata_hash.to_string(),
        ip: curr_ip_address.to_string(),
        is_adding,
    });
    if let Ok(msg_to_send) = msg_to_send_res {
        for ip in all_ips {
            if &ip == curr_ip_address {
                continue;
            }
            print!("Sending updated ips to: {}", ip);
            let potential_sender = get_sender_channel(&ip).await;
            if let Some(sender) = potential_sender {
                if let Err(e) = sender.send(msg_to_send.clone()) {
                    println!("Error sending internal channel: {}", e);
                }
                if let Err(e) = sender.send(
                    serde_json::to_string(&SecretMetadataKey {
                        hashed_metadata: metadata_hash.to_string(),
                        new_secret: secret_key.clone(),
                    })
                    .unwrap_or("".to_string()),
                ) {
                    println!("Error sending secret key internal channel: {}", e);
                }
            }
        }
    }
}
