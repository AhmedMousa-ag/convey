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
from models.fallback import FileMsg, StringMsg
from controllers.networking.messages_fallback import FallbacksManager
import time
from threading import Thread
import copy


class BaseReqRepl:
    def __init__(self, metadata: MetadataConfig, p2p_node) -> None:
        self.msg_serializer = MessageSerializer()
        self.metadata = metadata
        self.p2p_node = p2p_node
        self.fallback_mng = FallbacksManager()
        fallback_thread = Thread(target=self.__send_pending_messages, daemon=True)
        fallback_thread.start()

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
            self.fallback_mng.register_msg(self.metadata.hash_self(), msg)
            return False
        self.p2p_node.send_message(conn, msg)
        return True

    def _send_file(self, ip: str, file_path: str, file_type: str = "MODEL") -> bool:
        conn = get_socket_connection(ip=ip)
        if conn is None:
            self.fallback_mng.register_file(
                self.metadata.hash_self(), ip, file_path, file_type
            )
            return False
        return self.p2p_node.send_file(conn, filepath=file_path, file_type=file_type)

    def __send_pending_messages(self):
        while True:
            time.sleep(60)  # Check every minute

            keys = list(self.fallback_mng.get_pending_messages().messages.keys())

            if len(keys) < 1:
                continue
            for hashed_metadata in keys:
                messages = self.fallback_mng.get_pending_messages().messages.get(
                    hashed_metadata
                )
                if not messages:
                    print("No messages line.")
                    continue
                for message in messages:
                    self.fallback_mng.remove_fallback_message(hashed_metadata, message)
                    if isinstance(message, StringMsg):
                        list_ip_addresses = get_connection_p2p_pool(hashed_metadata)
                        print("List of addresses: ", list_ip_addresses)
                        print(
                            "Success sending message: ",
                            self._send_msg_rdnm_conn(
                                msg=message.msg,
                                list_of_address=list_ip_addresses,
                            ),
                        )

                    elif isinstance(message, FileMsg):
                        print(
                            "Success sending file: ",
                            self._send_file(
                                ip=message.ip,
                                file_path=message.file_path,
                                file_type=message.file_type,
                            ),
                        )
                    else:
                        print(
                            f"Warning: message type {type(message)} is not supported yet."
                        )


class Requester(BaseReqRepl):
    def __init__(self, metadata: MetadataConfig, p2p_node) -> None:
        super().__init__(metadata, p2p_node)

    def ask_is_latest(self, hashed_metadata: str, current_date: datetime):
        print("Requester: Will ask is latest")
        return self._send_msg_rdnm_conn(
            self.msg_serializer.get_is_latest(
                hashed_metadata, current_date=current_date
            )
        )

    def sync_dataset(self, hashed_metadata: str) -> bool:
        print("Requester: sync data")
        return self._send_msg_rdnm_conn(
            self.msg_serializer.sync_dataset(hashed_metadata).model_dump_json()
        )

    def sync_static_modules(self, hashed_metadata: str) -> bool:
        print("Requester: sync modules")
        return self._send_msg_rdnm_conn(
            self.msg_serializer.sync_static_modules(hashed_metadata).model_dump_json()
        )

    def ask_sync_model(self, latest_peers_addr: list[str] | None = None):
        print("Requester: ask sync model")
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
        print("Requester: update new weights")
        for ip in get_connection_p2p_pool(self.metadata.hash_self()):
            self._send_file(
                ip=ip, file_path=self.metadata.weights_path, file_type="MODEL"
            )


class Replier(BaseReqRepl):
    def __init__(self, metadata: MetadataConfig, p2p_node) -> None:
        super().__init__(metadata, p2p_node)

    def reply_is_latest(self, msg: Dict) -> str:
        # res_model = self.msg_serializer.response_is_latest(msg)
        print("Reply: is latest model.")
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
        print("Reply: sync model.")
        return self._send_file(
            ip=ip, file_path=self.metadata.weights_path, file_type="MODEL"
        )

    def reply_sync_dataset(self, ip: str) -> bool:
        print("Reply: sync dataset.")
        return self._send_file(
            ip=ip, file_path=self.metadata.dataset_path, file_type="DATA"
        )

    def reply_sync_static_modules(self, ip: str) -> bool:
        print("Reply: sync static modules.")
        return self._send_file(
            ip=ip,
            file_path=self.metadata.static_model_path,
            file_type="STATIC_MODULES",
        )
