from pydantic import BaseModel
from enum import Enum


class MessagesTypes(Enum):
    SUBSCRIBE = "subscribe"


class SubscribeTopic(BaseModel):
    hashed_metadata: str


class ClientsIPAddresses(BaseModel):
    hashed_metadata: str
    ips: list[str]


class ServerMessage(BaseModel):
    msg_type: str | MessagesTypes
    message: SubscribeTopic
