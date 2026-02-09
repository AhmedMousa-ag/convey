from configs.metadata import MetadataConfig

# from controllers.networking.p2p import p2p_node
from controllers.networking.pool import get_connection_p2p_pool, get_socket_connection
import random
from socket import socket
from controllers.networking.serializer import MessageSerializer
from datetime import datetime
from configs.config import DATEIME_FORMAT
from typing import Dict, List
from models.clients import (
    IsLatestModel,
    P2PMessage,
    P2PMessagesTypes,
    ResponseIsLatestModel,
    SyncLatestModel,
)


class BaseReqRepl:
    def __init__(self, metadata: MetadataConfig, p2p_node) -> None:
        self.msg_serializer = MessageSerializer()
        self.metadata = metadata
        self.p2p_node = p2p_node

    def _random_p2p_connection(
        self, list_of_address: List[str] | None = None
    ) -> socket | None:
        ip_pool = list_of_address or get_connection_p2p_pool(self.metadata.hash_self())
        if len(ip_pool) > 0:
            ip_idx = random.randint(1, len(ip_pool))
            return get_socket_connection(ip_pool[ip_idx])
        return None

    def _send_msg_rdnm_conn(
        self, msg: str, list_of_address: List[str] | None = None
    ) -> bool:
        conn = self._random_p2p_connection(list_of_address)
        if conn is None:
            return False
        self.p2p_node.send_message(conn, msg)
        return True

    def _send_file(self, ip: str, file_path: str, file_type: str = "MODEL") -> bool:
        conn = get_socket_connection(ip=ip)
        if conn is None:
            return False
        return self.p2p_node.send_file(conn, filepath=file_path, file_type=file_type)


class Requester(BaseReqRepl):
    def __init__(self, metadata: MetadataConfig, p2p_node) -> None:
        super().__init__(metadata, p2p_node)

    def ask_is_latest(self, hashed_metadata: str, current_date: datetime):
        return self._send_msg_rdnm_conn(
            self.msg_serializer.get_is_latest(
                hashed_metadata, current_date=current_date
            )
        )

    def sync_dataset(self, hashed_metadata: str) -> bool:
        return self._send_msg_rdnm_conn(
            self.msg_serializer.sync_dataset(hashed_metadata).model_dump_json()
        )

    def ask_sync_model(self, latest_peers_addr: list[str]):
        hashed_metadata = self.metadata.hash_self()
        # Get random address of these ones.
        # send a message with SyncModel
        self._send_msg_rdnm_conn(
            msg=P2PMessage(
                msg_type=P2PMessagesTypes.SYNCModel,
                message=SyncLatestModel(),
                hashed_metadata=hashed_metadata,
            ).model_dump_json(),
            list_of_address=latest_peers_addr,
        )

    def update_new_weights(self):
        for ip in get_connection_p2p_pool(self.metadata.hash_self()):
            self._send_file(
                ip=ip, file_path=self.metadata.weights_path, file_type="MODEL"
            )


class Replier(BaseReqRepl):
    def __init__(self, metadata: MetadataConfig, p2p_node) -> None:
        super().__init__(metadata, p2p_node)

    def reply_is_latest(self, msg: Dict) -> str:
        # res_model = self.msg_serializer.response_is_latest(msg)
        is_latest_model = IsLatestModel(**msg)
        latest_update = (
            datetime.min
            if self.metadata.latest_updated is None
            else datetime.strptime(self.metadata.latest_updated, DATEIME_FORMAT)
        )
        is_latest = is_latest_model.current_date < latest_update
        return P2PMessage(
            msg_type=P2PMessagesTypes.ResIsLatest,
            hashed_metadata=self.metadata.hash_self(),
            message=ResponseIsLatestModel(
                is_latest=is_latest, last_update=latest_update
            ),
        ).model_dump_json()

    def reply_sync_model(self, ip: str) -> bool:
        return self._send_file(
            ip=ip, file_path=self.metadata.weights_path, file_type="MODEL"
        )

    def reply_sync_dataset(self, ip: str) -> bool:
        return self._send_file(
            ip=ip, file_path=self.metadata.dataset_path, file_type="DATA"
        )
