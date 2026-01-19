use crate::configs::pool::{
    add_meta_ip, get_meta_ip_key, get_sender_channel, insert_sender_chan, remove_meta_ip,
    remover_sender_chan,
};
use crate::models::models::{ClientsIPAddresses, MessagesTypes, ServerMessage};
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
                        println!("Client {} sent: {}", addr, text);
                        println!("Got text msg");
                        let client_msg_res = ServerMessage::decode_str(&text.to_string());
                        if let Ok(client_msg)=client_msg_res {
                            match client_msg.msg_type {
                                MessagesTypes::Subscribe=>{
                                    let metadata = client_msg.message.hashed_metadata;
                                    add_meta_ip(&metadata,&ip_add).await;
                                    inform_metadata_clients(&metadata).await;
                                    client_stored_metadata.push(metadata);
                                },
                            }
                        }
                        if let Err(e) = socket.send(Message::Text(text)).await {

                            dbg!("{:?}",e);
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
        inform_metadata_clients(&mtdata).await;
    }
    remover_sender_chan(&ip_add).await;
}

///Informs all clients of each others.
async fn inform_metadata_clients(metadata_hash: &str) {
    let all_ips = get_meta_ip_key(metadata_hash).await;
    let msg_to_send_res = serde_json::to_string(&ClientsIPAddresses {
        hashed_metadata: metadata_hash.to_string(),
        ips: all_ips.clone(),
    });
    if let Ok(msg_to_send) = msg_to_send_res {
        for ip in all_ips {
            let potential_sender = get_sender_channel(&ip).await;
            if let Some(sender) = potential_sender {
                if let Err(e) = sender.send(msg_to_send.clone()) {
                    println!("Error sending internal channel: {}", e);
                }
            }
        }
    }
}
