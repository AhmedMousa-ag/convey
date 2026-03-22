from configs.metadata import MetadataConfig
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
    FileType,
)
from models.fallback import FileMsg, StringMsg
from controllers.networking.messages_fallback import FallbacksManager
from controllers.networking.perf_logger import perf_log
import time
import os
from threading import Thread


class BaseReqRepl:
    def __init__(self, metadata: MetadataConfig, p2p_node) -> None:
        self.msg_serializer = MessageSerializer()
        self.metadata = metadata
        self.hashed_metadata = self.metadata.hash_self()
        self.p2p_node = p2p_node
        self.fallback_mng = FallbacksManager()
        fallback_thread = Thread(target=self.__send_pending_messages, daemon=True)
        fallback_thread.start()

    def _random_p2p_connection(
        self, list_of_address: List[str] | None = None
    ) -> socket | None:
        ip_pool = list_of_address or get_connection_p2p_pool(self.metadata.hash_self())
        if len(ip_pool) > 0:
            ip_idx = random.randint(0, len(ip_pool) - 1)
            return get_socket_connection(ip_pool[ip_idx])
        return None

    def _send_msg_rdnm_conn(
        self, msg: str, list_of_address: List[str] | None = None
    ) -> bool:
        t0 = time.time()
        conn = self._random_p2p_connection(list_of_address)
        if conn is None:
            perf_log(f"MSG_SEND | status=fallback | metadata={self.hashed_metadata} | elapsed={time.time()-t0:.4f}s")
            self.fallback_mng.register_msg(self.metadata.hash_self(), msg)
            return False
        """
        peer_socket: socket.socket,
        message,
        hashed_metadata: str,
        """
        self.p2p_node.send_message(conn, msg, self.hashed_metadata)
        perf_log(f"MSG_SEND | status=ok | metadata={self.hashed_metadata} | elapsed={time.time()-t0:.4f}s")
        return True

    def _send_file(self, ip: str, file_path: str, file_type: str = "MODEL") -> bool:
        print(
            f"Requester: Trying to send file to {ip} with path {file_path} and type {file_type}"
        )
        t0 = time.time()
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else -1
        conn = get_socket_connection(ip=ip)
        if conn is None:
            print("Connection is None, registering fallback file.")
            perf_log(f"FILE_SEND | status=fallback | ip={ip} | type={file_type} | size={file_size} | elapsed={time.time()-t0:.4f}s")
            self.fallback_mng.register_file(
                self.metadata.hash_self(), ip, file_path, file_type
            )
            return False
        """
        peer_socket: socket.socket,
        filepath,
        hashed_metadata: str,
        file_type="MODEL",
        """
        result = self.p2p_node.send_file(
            conn,
            filepath=file_path,
            file_type=file_type,
            hashed_metadata=self.hashed_metadata,
        )
        elapsed = time.time() - t0
        throughput = (file_size / elapsed / 1024) if elapsed > 0 and file_size > 0 else 0
        perf_log(f"FILE_SEND | status={'ok' if result else 'fail'} | ip={ip} | type={file_type} | size={file_size} | elapsed={elapsed:.4f}s | throughput={throughput:.1f}KB/s")
        return result

    def __send_pending_messages(self):
        while True:
            time.sleep(60)  # Check every minute

            keys = list(self.fallback_mng.get_pending_messages().messages.keys())
            pending_count = sum(len(self.fallback_mng.get_pending_messages().messages.get(k, [])) for k in keys)
            if pending_count > 0:
                perf_log(f"FALLBACK_RETRY | pending_keys={len(keys)} | pending_messages={pending_count}")

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
                        _ = (
                            self._send_msg_rdnm_conn(
                                msg=message.msg,
                                list_of_address=list_ip_addresses,
                            ),
                        )

                    elif isinstance(message, FileMsg):

                        _ = (
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
        perf_log(f"REQUEST | type=ask_is_latest | metadata={hashed_metadata}")
        return self._send_msg_rdnm_conn(
            self.msg_serializer.get_is_latest(
                hashed_metadata, current_date=current_date
            )
        )

    def sync_dataset(self, hashed_metadata: str) -> bool:
        print("Requester: sync data")
        perf_log(f"REQUEST | type=sync_dataset | metadata={hashed_metadata}")
        return self._send_msg_rdnm_conn(
            self.msg_serializer.sync_dataset(hashed_metadata).model_dump_json()
        )

    def sync_model_weights(self, hashed_metadata: str) -> bool:
        print("Requester: sync model weights")
        perf_log(f"REQUEST | type=sync_model_weights | metadata={hashed_metadata}")
        return self._send_msg_rdnm_conn(
            self.msg_serializer.sync_model_weights(hashed_metadata).model_dump_json()
        )

    def sync_static_modules(self, hashed_metadata: str) -> bool:
        print("Requester: sync modules")
        perf_log(f"REQUEST | type=sync_static_modules | metadata={hashed_metadata}")
        return self._send_msg_rdnm_conn(
            self.msg_serializer.sync_static_modules(hashed_metadata).model_dump_json()
        )

    def ask_sync_model(self, latest_peers_addr: list[str] | None = None):
        print("Requester: ask sync model")
        hashed_metadata = self.metadata.hash_self()
        perf_log(f"REQUEST | type=ask_sync_model | metadata={hashed_metadata} | target_peers={len(latest_peers_addr) if latest_peers_addr else 'random'}")
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
        peers = get_connection_p2p_pool(self.metadata.hash_self())
        perf_log(f"REQUEST | type=update_new_weights | peer_count={len(peers)}")
        for ip in peers:
            self._send_file(
                ip=ip,
                file_path=self.metadata.weights_path,
                file_type=FileType.WEIGHTS.value,
            )


class Replier(BaseReqRepl):
    def __init__(self, metadata: MetadataConfig, p2p_node) -> None:
        super().__init__(metadata, p2p_node)

    def reply_is_latest(self, msg: Dict) -> str:
        t0 = time.time()
        is_latest_model = IsLatestModel(**msg)
        latest_update = (
            datetime.min
            if self.metadata.latest_updated is None
            else datetime.strptime(self.metadata.latest_updated, DATEIME_FORMAT)
        )
        is_latest = is_latest_model.current_date < latest_update
        perf_log(f"REPLY | type=is_latest | result={is_latest} | elapsed={time.time()-t0:.4f}s")
        return P2PMessage(
            msg_type=P2PMessagesTypes.ResIsLatest,
            hashed_metadata=self.metadata.hash_self(),
            message=ResponseIsLatestModel(
                is_latest=is_latest, last_update=latest_update
            ),
        ).model_dump_json()

    def reply_sync_model(self, ip: str) -> bool:
        perf_log(f"REPLY | type=sync_model | target={ip}")
        return self._send_file(
            ip=ip,
            file_path=self.metadata.model_obj_path,
            file_type=FileType.MODEL.value,
        )

    def reply_sync_model_weights(self, ip: str) -> bool:
        perf_log(f"REPLY | type=sync_model_weights | target={ip}")
        return self._send_file(
            ip=ip,
            file_path=self.metadata.weights_path,
            file_type=FileType.WEIGHTS.value,
        )

    def reply_sync_dataset(self, ip: str) -> bool:
        perf_log(f"REPLY | type=sync_dataset | target={ip}")
        return self._send_file(
            ip=ip, file_path=self.metadata.dataset_path, file_type="DATA"
        )

    def reply_sync_static_modules(self, ip: str) -> bool:
        perf_log(f"REPLY | type=sync_static_modules | target={ip}")
        return self._send_file(
            ip=ip,
            file_path=self.metadata.static_model_path,
            file_type=FileType.STATIC_MOD.value,
        )
