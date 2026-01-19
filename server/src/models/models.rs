use bincode::{Decode, Encode, config};

#[derive(Debug, Clone, Encode, Decode)]
pub struct MetaDataMessage {
    pub hashed_metadata: String,
}
impl MetaDataMessage {
    pub fn encode_bytes(&self) -> Vec<u8> {
        bincode::encode_to_vec(self, config::standard()).unwrap()
    }

    pub fn decode_bytes(bytes: &[u8]) -> Self {
        let (messages, _): (Self, usize) =
            bincode::decode_from_slice(bytes, config::standard()).unwrap();
        messages
    }
}
