use serde::{Deserialize, Serialize};
use serde_json::Error;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubscribeTopic {
    pub hashed_metadata: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientsIPAddresses {
    pub hashed_metadata: String,
    pub ips: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MessagesTypes {
    Subscribe,
}

impl MessagesTypes {
    pub fn as_str(&self) -> &'static str {
        match self {
            MessagesTypes::Subscribe => "Subscribe",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerMessage {
    pub msg_type: MessagesTypes,
    pub message: SubscribeTopic,
}

impl ServerMessage {
    pub fn decode_str(str_to_decode: &str) -> Result<Self, Error> {
        serde_json::from_str(str_to_decode)
    }
}
