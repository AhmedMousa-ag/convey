import socket
import threading
import os
import time
from configs.config import CLIENT_PORT, CLIENT_HOST
from configs.paths import (
    ZIPPED_DIRE,
)
import zipfile
from controllers.networking.serializer import MessageSerializer
from controllers.networking.transmitter import TransmitterManager
from configs.metadata import MetadataConfig
import shutil
from controllers.verifier.update_verifier import ModelVerifier
from typing import Dict, Tuple
from models.clients import AuthenticationMessage, FileType
from controllers.networking.perf_logger import perf_log


class TransferPathManager:
    def __init__(self, zipped_dir: str) -> None:
        self.zipped_dir = zipped_dir

    def get_target_path(self, metadata: MetadataConfig, file_type: str) -> str:
        if file_type == FileType.MODEL.value:
            return metadata.model_obj_path
        if file_type == FileType.WEIGHTS.value:
            return metadata.weights_path
        if file_type == FileType.DATA.value:
            return metadata.dataset_path
        if file_type == FileType.STATIC_MOD.value:
            return metadata.static_model_path
        return "received_files"

    def is_directory_target(self, file_type: str, target_path: str) -> bool:
        return file_type == FileType.DATA.value and (
            os.path.isdir(target_path)
            or os.path.splitext(os.path.basename(target_path))[1] == ""
        )

    def move_and_overwrite(self, source: str, destination: str):
        parent_dir = os.path.dirname(destination)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        if os.path.exists(destination):
            if os.path.isdir(destination):
                shutil.rmtree(destination)
            else:
                os.remove(destination)
        shutil.move(source, destination)

    def move_directory_contents(self, source_dir: str, destination_dir: str):
        os.makedirs(destination_dir, exist_ok=True)
        for item in os.listdir(source_dir):
            self.move_and_overwrite(
                os.path.join(source_dir, item),
                os.path.join(destination_dir, item),
            )

    def get_single_extracted_file(self, extract_dir: str) -> str:
        extracted_files = []
        for root, _, files in os.walk(extract_dir):
            for file in files:
                extracted_files.append(os.path.join(root, file))

        if len(extracted_files) != 1:
            raise ValueError(
                f"Expected a single file in archive, found {len(extracted_files)}"
            )

        return extracted_files[0]

    def prepare_transfer_file(self, filepath: str) -> tuple[str, str]:
        source_path = os.path.abspath(filepath)
        source_name = os.path.basename(os.path.normpath(source_path))
        archive_path = os.path.join(self.zipped_dir, f"{source_name}.zip")

        if os.path.exists(archive_path):
            os.remove(archive_path)

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            if os.path.isdir(source_path):
                print("Will zip directory before sending")
                for root, _, files in os.walk(source_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, start=source_path)
                        zipf.write(full_path, arcname=rel_path)
            else:
                print("Will zip file before sending")
                zipf.write(source_path, arcname=os.path.basename(source_path))

        return archive_path, os.path.basename(archive_path)

    def get_temp_extract_dir(self, filename: str) -> str:
        return os.path.join(self.zipped_dir, "temp", filename.split(".")[0])

    def get_incoming_archive_path(self, filename: str) -> str:
        return os.path.join(self.zipped_dir, filename)

    def cleanup_path(self, path: str):
        if not os.path.exists(path):
            return
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)


class P2PNode:
    # Singleton pattern
    def __new__(cls):
        if not hasattr(cls, "inst"):
            cls.inst = super().__new__(cls)
        return cls.inst

    def __init__(self):
        # Guard against re-initialization on singleton re-use
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.host = CLIENT_HOST
        self.port = CLIENT_PORT
        self.peers = set()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.serializer = MessageSerializer()
        self.path_manager = TransferPathManager(ZIPPED_DIRE)

        # Hashed Metadata and the reflected secret key.
        self.metadata_secrets: Dict[str, str] = {}
        print(f"P2P node listening on {self.host}:{self.port}")

    def recv_exact(self, conn: socket.socket, n: int) -> bytes:
        """
        Read *exactly* n bytes from the socket.
        Loops internally to handle partial reads that TCP may deliver,
        which is the root cause of 'several messages arriving at the same time'.
        Raises ConnectionError if the socket closes before n bytes arrive.
        """
        # print(f"Attempting to read exactly {n} bytes from socket")
        buf = bytearray()
        while len(buf) < n:
            chunk = conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("Socket closed before all bytes were received")
            buf.extend(chunk)
        return bytes(buf)

    def recv_framed(self, conn: socket.socket) -> bytes:
        """
        Receive a length-prefixed message.
        Wire format:  [4-byte big-endian length][payload bytes]
        Guarantees that exactly one logical message is returned per call.
        """
        # print("Waiting to receive framed message (4-byte length prefix)")
        length_bytes = self.recv_exact(conn, 4)
        length = int.from_bytes(length_bytes, byteorder="big")
        return self.recv_exact(conn, length)

    def send_framed(self, conn: socket.socket, data: bytes):
        """
        Send data with a 4-byte big-endian length prefix so the receiver
        knows exactly how many bytes to read for this message.
        """
        conn.sendall(len(data).to_bytes(4, byteorder="big") + data)

    def update_secret(self, hashed_metadata: str, secret: str):
        self.metadata_secrets[hashed_metadata] = secret

    def _verify_secret_key(self, conn: socket.socket) -> Tuple[bool, str]:
        """
        Receive and validate the authentication message from the peer.
        Uses recv_framed so the auth JSON never bleeds into the next recv.
        """
        try:
            data = self.recv_framed(conn)
            auth_msg = AuthenticationMessage.model_validate_json(data)
            # print(f"Received authentication message: {auth_msg}")
            received_secret = auth_msg.secret_key
            existing_secret = self.metadata_secrets.get(auth_msg.hashed_metadata)
            if received_secret == existing_secret:
                # print("Secret verified.")
                return True, auth_msg.hashed_metadata
            print(
                f"Couldn't verify secret — received: {received_secret}, "
                f"expected: {existing_secret}"
            )
            return False, auth_msg.hashed_metadata
        except Exception as e:
            print(f"Error verifying secret: {e}")
            return False, ""

    def _send_secret_key(self, peer_socket: socket.socket, hashed_metadata: str):
        """
        Send the secret key to the peer for authentication before each transmission.
        Uses send_framed so the auth JSON is length-prefixed and never merges
        with the message-type header that follows immediately.
        """
        auth_msg = AuthenticationMessage(
            hashed_metadata=hashed_metadata,
            secret_key=self.metadata_secrets.get(hashed_metadata) or "",
        )
        self.send_framed(peer_socket, auth_msg.model_dump_json().encode())

    def handle_peer(self, conn: socket.socket, addr):
        print(f"Connected by {addr}")
        perf_log(f"PEER_CONNECTED | addr={addr}")
        self.peers.add(addr)
        try:
            while True:
                is_verified, hashed_metadata = self._verify_secret_key(conn)
                if not is_verified:
                    perf_log(f"AUTH_FAIL | addr={addr}")
                    print(f"Authentication failed for {addr}. Closing connection.")
                    self.close_conn(conn, addr)
                    return

                # Receive the fixed 10-byte message-type header.
                try:
                    msg_type_raw = self.recv_exact(conn, 10)
                except ConnectionError:
                    print(f"Connection closed by {addr}")
                    break

                msg_type = msg_type_raw.decode().strip()
                # print(f"Received message type: {msg_type}")

                if not msg_type:
                    print(f"No message type received from {addr}. Closing connection.")
                    break

                if msg_type in [
                    FileType.MODEL.value,
                    FileType.DATA.value,
                    FileType.STATIC_MOD.value,
                    FileType.WEIGHTS.value,
                ]:
                    perf_log(f"P2P_RECV_FILE | type={msg_type} | addr={addr}")

                    self._receive_file(
                        conn=conn,
                        addr=addr,
                        file_type=msg_type,
                        hashed_metadata=hashed_metadata,
                    )

                elif msg_type == "TEXT":
                    try:
                        # print("Receiving TEXT message body...")
                        t0 = time.time()
                        data = self.recv_framed(conn)
                    except ConnectionError:
                        print(f"Connection closed by {addr} while reading TEXT body")
                        break

                    if not data:
                        break
                    # print(f"Received from {addr}: {data.decode()}")
                    hashed_metadata, msg_type_inner, message = (
                        self.serializer.receive_msg(data.decode())
                    )
                    perf_log(
                        f"P2P_RECV_TEXT | type={msg_type_inner.value} | size={len(data)}B | addr={addr} | elapsed={time.time()-t0:.4f}s"
                    )
                    transmitter = TransmitterManager(
                        hashed_metadata,
                        peer_address=addr[0],
                        p2p_node=self,
                    )
                    reply_data = transmitter.reply(msg_type=msg_type_inner, msg=message)
                    if reply_data is None:
                        continue
                    # FIX 1: Use send_framed so the reply is length-prefixed.
                    # Previously conn.sendall(reply_data.encode()) sent raw bytes,
                    # causing the next recv_framed call to misread the reply
                    # text as a 4-byte length prefix → garbage length → hang.
                    self.send_framed(conn, reply_data.encode())
                else:
                    print(f"Unknown message type received: {msg_type}")
                    break
        finally:
            self.close_conn(conn, addr)

    def close_conn(self, conn: socket.socket, addr: str):
        conn.close()
        if addr in self.peers:
            self.peers.remove(addr)
        print(f"Disconnected {addr}")

    def _receive_file(self, conn, addr, file_type, hashed_metadata):
        """
        Receives an archived file payload and restores it to the appropriate path.
        All fixed-size fields use recv_exact to prevent boundary issues.
        """
        try:
            # Filename length (4 bytes) + filename
            filename_len = int.from_bytes(self.recv_exact(conn, 4), byteorder="big")
            # print(f"Filename length: {filename_len} bytes")
            filename = self.recv_exact(conn, filename_len).decode()
            # print(f"Filename: {filename}")
            # File size (8 bytes)
            filesize = int.from_bytes(self.recv_exact(conn, 8), byteorder="big")
            # print(f"File size: {filesize} bytes")
        except ConnectionError as e:
            print(f"Error reading file metadata from {addr}: {e}")
            return

        print(f"Receiving {file_type} '{filename}' ({filesize} bytes) from {addr}")
        recv_t0 = time.time()
        metadata = MetadataConfig.load_from_hashed_val(hashed_metadata)
        target_path = self.path_manager.get_target_path(metadata, file_type)
        temp_dire = self.path_manager.get_temp_extract_dir(filename)
        self.path_manager.cleanup_path(temp_dire)
        os.makedirs(temp_dire, exist_ok=True)

        zip_path = self.path_manager.get_incoming_archive_path(filename)

        # Receive file data in chunks until exactly filesize bytes are read
        received = 0
        with open(zip_path, "wb") as f:
            while received < filesize:
                chunk = conn.recv(min(4096, filesize - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)

        # Acknowledge receipt
        conn.sendall(b"ACK")
        recv_elapsed = time.time() - recv_t0
        throughput = (
            (received / recv_elapsed / 1024) if recv_elapsed > 0 and received > 0 else 0
        )
        perf_log(
            f"FILE_RECV | type={file_type} | filename={filename} | size={received}B | addr={addr} | elapsed={recv_elapsed:.4f}s | throughput={throughput:.1f}KB/s"
        )

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # print("Will unzip received archive")
                zip_ref.extractall(temp_dire)

            if self.path_manager.is_directory_target(file_type, target_path):
                self.path_manager.move_directory_contents(temp_dire, target_path)
                final_path = target_path
            elif file_type == FileType.WEIGHTS.value:
                extracted_file = self.path_manager.get_single_extracted_file(temp_dire)
                had_existing_weights = os.path.exists(target_path)
                if ModelVerifier(metadata).is_better_model(extracted_file):
                    if not had_existing_weights and os.path.exists(extracted_file):
                        self.path_manager.move_and_overwrite(
                            extracted_file, target_path
                        )
                    final_path = target_path
                    print(
                        f"Weights '{filename}' from {addr} were accepted at {target_path}"
                    )
                else:
                    print(
                        f"Received weights from {addr} are not better than the current model. Discarding."
                    )
                    final_path = target_path
            else:
                extracted_file = self.path_manager.get_single_extracted_file(temp_dire)
                self.path_manager.move_and_overwrite(extracted_file, target_path)
                final_path = target_path

            print(
                f"{file_type} '{filename}' received successfully "
                f"({received} bytes) at {final_path}"
            )
        finally:
            self.path_manager.cleanup_path(zip_path)
            self.path_manager.cleanup_path(temp_dire)

    def start_server(self):
        def run():
            while True:
                conn, addr = self.server.accept()
                threading.Thread(
                    target=self.handle_peer, args=(conn, addr), daemon=True
                ).start()

        threading.Thread(target=run, daemon=True).start()

    def connect_to_peer(self, peer_host, peer_port=CLIENT_PORT) -> socket.socket:
        t0 = time.time()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((peer_host, peer_port))
        perf_log(
            f"PEER_CONNECT | host={peer_host} | port={peer_port} | elapsed={time.time()-t0:.4f}s"
        )
        print(f"Connected to peer {peer_host}:{peer_port}")
        return s

    def send_message(
        self,
        peer_socket: socket.socket,
        message: str,
        hashed_metadata: str,
    ):
        """
        Send a TEXT message.

        Wire format per loop iteration (auth sent before every message):
            [framed auth JSON]
            [10-byte msg type header]
            [framed message payload]
        """
        self._send_secret_key(peer_socket, hashed_metadata)
        peer_socket.sendall(b"TEXT".ljust(10))
        self.send_framed(peer_socket, message.encode())
        perf_log(f"P2P_SEND_TEXT | size={len(message)}B | metadata={hashed_metadata}")

    def send_file(
        self,
        peer_socket: socket.socket,
        filepath: str,
        hashed_metadata: str,
        file_type: str = FileType.MODEL.value,
    ) -> bool:
        """
        Send a file to a connected peer.

        Wire format:
            [framed auth JSON]
            [10-byte file_type header]
            [4-byte filename length]
            [filename bytes]
            [8-byte file size]
            [raw file bytes]
        """
        if not os.path.exists(filepath):
            print(f"Error: File '{filepath}' not found")
            return False

        if file_type not in [
            FileType.MODEL.value,
            FileType.DATA.value,
            FileType.STATIC_MOD.value,
            FileType.WEIGHTS.value,
        ]:
            raise ValueError(
                f"Invalid file type '{file_type}'. "
                f"Must be 'MODEL', 'STATIC_MOD', or 'DATA'."
            )

        filepath, filename = self.path_manager.prepare_transfer_file(filepath)
        filesize = os.path.getsize(filepath)
        send_t0 = time.time()
        # print(f"Sending {file_type} '{filename}' ({filesize} bytes)")

        # FIX 2: Auth must be sent before every message since the receiver
        # loop calls _verify_secret_key at the top of every iteration.
        # Previously this was commented out, causing auth verification to
        # read the file_type header bytes as the auth payload → failure.
        self._send_secret_key(peer_socket, hashed_metadata)

        # 1. Message type header (fixed 10 bytes)
        peer_socket.sendall(file_type.ljust(10).encode())
        # print(f"Sent file type header: '{file_type}'")

        # 2. Filename length + filename
        filename_bytes = filename.encode()
        peer_socket.sendall(len(filename_bytes).to_bytes(4, byteorder="big"))
        peer_socket.sendall(filename_bytes)

        # 3. File size
        peer_socket.sendall(filesize.to_bytes(8, byteorder="big"))

        # 4. File data
        sent = 0
        with open(filepath, "rb") as f:
            while sent < filesize:
                chunk = f.read(4096)
                if not chunk:
                    break
                peer_socket.sendall(chunk)
                sent += len(chunk)

        print(f"File sent: {sent} bytes")

        # 5. Wait for ACK
        try:
            ack = self.recv_exact(peer_socket, 3)
        except ConnectionError:
            perf_log(
                f"P2P_SEND_FILE | type={file_type} | size={sent}B | status=no_ack | elapsed={time.time()-send_t0:.4f}s"
            )
            print("Connection closed before ACK was received")
            return False
        print(f"Received ACK: {ack}")
        send_elapsed = time.time() - send_t0
        throughput = (
            (sent / send_elapsed / 1024) if send_elapsed > 0 and sent > 0 else 0
        )
        if ack == b"ACK":
            perf_log(
                f"P2P_SEND_FILE | type={file_type} | size={sent}B | status=ok | elapsed={send_elapsed:.4f}s | throughput={throughput:.1f}KB/s"
            )
            print("File transfer confirmed by peer")
            return True
        else:
            perf_log(
                f"P2P_SEND_FILE | type={file_type} | size={sent}B | status=bad_ack | elapsed={send_elapsed:.4f}s"
            )
            print("File transfer acknowledgment not received")
            return False


p2p_node = P2PNode()
