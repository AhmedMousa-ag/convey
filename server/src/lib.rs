pub mod configs;
pub mod controller;
pub mod models;

#[cfg(test)]
mod tests {

    use crate::{
        controller::handler::handler,
        models::models::{ConveyMessage, MessagesTypes, ReqSubscribeTopic, ServerMessage},
    };
    use axum::{Router, routing::get};
    use futures::{SinkExt, StreamExt};
    use std::{
        future::IntoFuture,
        net::{Ipv4Addr, SocketAddr},
    };
    use tokio_tungstenite::tungstenite;

    async fn setup() -> String {
        let bind = tokio::net::TcpListener::bind(SocketAddr::from((Ipv4Addr::UNSPECIFIED, 0)))
            .await
            .unwrap();
        let listener = bind;
        let app = Router::new().route("/ws", get(handler));
        let addr = listener.local_addr().unwrap();
        tokio::spawn(
            axum::serve(
                listener,
                app.into_make_service_with_connect_info::<SocketAddr>(),
            )
            .into_future(),
        );
        // Wait a moment for the server to start up (in a real test, you'd want a more robust way to ensure the server is ready)
        tokio::time::sleep(std::time::Duration::from_millis(100)).await;
        format!("ws://{addr}/ws")
    }
    #[tokio::test]
    async fn ping_test() {
        let addr = setup().await;

        let (_, response) = tokio_tungstenite::connect_async(addr).await.unwrap();

        assert_eq!(response.status(), 101); // 101 Switching Protocols = successful WebSocket upgrade
    }
    #[tokio::test]
    async fn subscribe_metadata_test() {
        let addr = setup().await;

        let (mut socket, _response) = tokio_tungstenite::connect_async(addr).await.unwrap();

        let convey_message = ConveyMessage::ReqSubscribeTopic(ReqSubscribeTopic {
            hashed_metadata: "some_hashed_metadata".to_string(),
        });
        let server_msg = ServerMessage {
            msg_type: MessagesTypes::Subscribe,
            message: convey_message,
        };
        socket
            .send(tungstenite::Message::text(
                serde_json::to_string(&server_msg).unwrap(),
            ))
            .await
            .unwrap();

        let msg = match socket.next().await.unwrap().unwrap() {
            tungstenite::Message::Text(msg) => msg,
            other => panic!("expected a text message but got {other:?}"),
        };

        let server_response: ServerMessage = serde_json::from_str(msg.as_str()).unwrap();

        assert!(matches!(
            server_response.msg_type,
            MessagesTypes::ChangeSecret
        ));

        if let ConveyMessage::SecretMetadataKey(secret) = server_response.message {
            assert_eq!(secret.hashed_metadata, "some_hashed_metadata");
            assert!(!secret.new_secret.is_empty()); // just verify a secret was generated
        } else {
            panic!("expected SecretMetadataKey message");
        }
    }
}
