use crate::configs::pool::{
    add_connection, insert_sender_chan, remove_connection, remover_sender_chan,
};
use crate::models::models::MetaDataMessage;
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
    // TODO Notify others
    loop {
        tokio::select! {
            Some(Ok(msg)) = socket.recv() => {
                match msg {


                    Message::Text(text) => {
                        println!("Client {} sent: {}", addr, text);

                        if let Err(e) = socket.send(Message::Text(text)).await {

                            dbg!("{:?}",e);
                        }
                    },
                    Message::Binary(binary_msg)=>{
                        let metadata_msg = MetaDataMessage::decode_bytes(&binary_msg);
                        add_connection(&metadata_msg.hashed_metadata, &ip_add).await;
                        client_stored_metadata.push(metadata_msg.hashed_metadata);

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
    //TODO notify others of the new ip connections map.
    for mtdata in client_stored_metadata {
        remove_connection(&mtdata).await;
    }
    remover_sender_chan(&ip_add).await;
}
