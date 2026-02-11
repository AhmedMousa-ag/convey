use axum::{Router, routing::get};
use convey_server::{
    configs::config::{HOST, PORT},
    controller::{handler::handler, secret_manager::secret_change_interval},
};
use std::net::SocketAddr;
#[tokio::main]
async fn main() {
    let app = Router::new().route("/ws", get(handler));
    let server_address = format!("{}:{}", HOST, PORT);
    let listener = tokio::net::TcpListener::bind(&server_address)
        .await
        .unwrap();
    // Start the secret change interval task
    tokio::spawn(async {
        secret_change_interval().await;
    });
    println!("Will start convery server at: {}", server_address);
    axum::serve(
        listener,
        app.into_make_service_with_connect_info::<SocketAddr>(),
    )
    .await
    .unwrap();
}
