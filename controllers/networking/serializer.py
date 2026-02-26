from models.clients import (
    P2PMessage,
    P2PMessagesTypes,
    IsLatestModel,
    ResponseIsLatestModel,
    SyncLatestModel,
    UpdateOthersLatestModel,
    SyncDataset,
    SyncStaticModules,
)

import json
from datetime import datetime
from typing import Dict, Tuple


class MessageSerializer:

    def get_is_latest(self, hashed_metadata: str, current_date: datetime) -> str:
        return P2PMessage(
            msg_type=P2PMessagesTypes.IsLatest,
            hashed_metadata=hashed_metadata,
            message=IsLatestModel(current_date=current_date),
        ).model_dump_json()

    def serialize_is_latest(self, msg: str) -> IsLatestModel:
        return IsLatestModel(**json.loads(msg))

    def response_is_latest(self, recieved_message: str) -> ResponseIsLatestModel:
        return ResponseIsLatestModel(**json.loads(recieved_message))

    def sync_latest_model(self, hashed_metadata: str) -> P2PMessage:
        return P2PMessage(
            msg_type=P2PMessagesTypes.SYNCModel,
            hashed_metadata=hashed_metadata,
            message=SyncLatestModel(),
        )

    def sync_dataset(self, hashed_metadata: str) -> P2PMessage:
        return P2PMessage(
            msg_type=P2PMessagesTypes.SYNCDataset,
            message=SyncDataset(),
            hashed_metadata=hashed_metadata,
        )

    def sync_static_modules(self, hashed_metadata: str) -> P2PMessage:
        return P2PMessage(
            msg_type=P2PMessagesTypes.SYNCStaticModules,
            message=SyncStaticModules(),
            hashed_metadata=hashed_metadata,
        )

    def update_other_models(self, hashed_metadata: str):
        return P2PMessage(
            msg_type=P2PMessagesTypes.UPDATE,
            hashed_metadata=hashed_metadata,
            message=UpdateOthersLatestModel(),
        )

    def receive_msg(
        self, received_raw_message: str
    ) -> Tuple[str, P2PMessagesTypes, Dict]:
        print(f"Received raw message: {received_raw_message}")
        raw_message: Dict = json.loads(received_raw_message)
        hashed_metadata: str = raw_message["hashed_metadata"]
        message: Dict = raw_message["message"]
        msg_type = P2PMessagesTypes(raw_message["msg_type"])
        return hashed_metadata, msg_type, message
