from pydantic import BaseModel
from enum import Enum


class MessagesTypes(Enum):
    SUBSCRIBE = "Subscribe"
    ChangeSecret = "ChangeSecret"


class SubscribeTopic(BaseModel):
    hashed_metadata: str


class ClientsIPAddresses(BaseModel):
    hashed_metadata: str
    ip: str
    is_adding: bool


class SecretMetadataKey(BaseModel):
    hashed_metadata: str
    new_secret: str


class ServerMessage(BaseModel):
    msg_type: str | MessagesTypes
    message: SubscribeTopic
