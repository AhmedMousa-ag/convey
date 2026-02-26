use serde::{Deserialize, Serialize};
use serde_json::Error;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReqSubscribeTopic {
    pub hashed_metadata: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientsIPAddresses {
    pub hashed_metadata: String,
    pub ip: String,
    pub is_adding: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecretMetadataKey {
    pub hashed_metadata: String,
    pub new_secret: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum ConveyMessage {
    SubscribeTopic(ClientsIPAddresses),
    SecretMetadataKey(SecretMetadataKey),
    ReqSubscribeTopic(ReqSubscribeTopic),
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MessagesTypes {
    #[serde(rename = "subscribe")]
    Subscribe,
    #[serde(rename = "changeSecret")]
    ChangeSecret,
}

impl MessagesTypes {
    pub fn as_str(&self) -> &'static str {
        match self {
            MessagesTypes::Subscribe => "subscribe",
            MessagesTypes::ChangeSecret => "changeSecret",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerMessage {
    pub msg_type: MessagesTypes,
    pub message: ConveyMessage,
}

impl ServerMessage {
    pub fn decode_str(str_to_decode: &str) -> Result<Self, Error> {
        serde_json::from_str(str_to_decode)
    }
}
