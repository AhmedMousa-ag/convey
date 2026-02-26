import socket
import threading
import os
from configs.config import CLIENT_PORT, CLIENT_HOST
from configs.paths import (
    DATASETS_TEST_DIR,
    MODELS_DIR,
    ZIPPED_DIRE,
    METADATA_PATH,
    STATIC_MODULES_PATH,
)
import zipfile
from controllers.networking.serializer import MessageSerializer
from controllers.networking.transmitter import TransmitterManager
from configs.metadata import MetadataConfig
import shutil
from controllers.verifier.update_verifier import ModelVerifier
from typing import Dict
from models.clients import AuthenticationMessage


class P2PNode:
    """Shared state, #TODO you might consider it.
    _shared = {}

    def __new__(cls, *args, **kwargs):
        obj = super().__new__(cls, *args, **kwargs)
        obj.__dict__ = cls._shared
        return obj
    """

    # Singleton pattern
    def __new__(cls):
        if not hasattr(cls, "inst"):
            cls.inst = super().__new__(cls)
        return cls.inst

    def __init__(self):
        self.host = CLIENT_HOST
        self.port = CLIENT_PORT
        self.peers = set()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.serializer = MessageSerializer()

        # TODO probably you should split secret manager to apply SOLID Principles.
        # Hashed Metadata and the reflected secret key.
        self.metadata_secrets: Dict[str, str] = {}
        print(f"P2P node listening on {self.host}:{self.port}")

    def update_secret(self, hashed_metadata: str, secret: str):
        print("Will update secret")
        self.metadata_secrets[hashed_metadata] = secret

    def handle_peer(self, conn: socket.socket, addr):
        print(f"Connected by {addr}")
        self.peers.add(addr)
        try:
            while True:
                print(
                    f"Recieving message, checking if connection closed: {conn.fileno()}"
                )
                # Recieve the secret first
                if not self._verify_secret_key(conn):
                    print(f"Authentication failed for {addr}. Closing connection.")
                    self.close_conn(conn, addr)
                    return

                # First, receive the message type (fixed 10 bytes)
                # This could be "TEXT", "MODEL", or "DATA"

                msg_type = conn.recv(10).decode().strip()
                print(f"Recived message type: {msg_type}")
                if not msg_type:
                    break

                # Check if the message type corresponds to a file transfer
                if msg_type in ["MODEL", "DATA"]:
                    self._receive_file(conn, addr, file_type=msg_type)

                elif msg_type == "TEXT":
                    data = conn.recv(1024)
                    if not data:
                        break
                    print(f"Received from {addr}: {data.decode()}")
                    hashed_metadata, msg_type, message = self.serializer.receive_msg(
                        data.decode()
                    )
                    transmitter = TransmitterManager(
                        hashed_metadata, peer_address=addr, p2p_node=self
                    )
                    reply_data = transmitter.reply(msg_type=msg_type, msg=message)
                    if reply_data is None:
                        continue
                    conn.sendall(reply_data.encode())
                else:
                    # Unknown header type
                    print(f"Unknown message type received: {msg_type}")
                    break
        finally:
            self.close_conn(conn, addr)

    def close_conn(self, conn: socket.socket, addr: str):
        conn.close()
        if addr in self.peers:
            self.peers.remove(addr)
        print(f"Disconnected {addr}")

    def _verify_secret_key(self, conn: socket.socket) -> bool:
        try:
            data = conn.recv(1024).decode()
            auth_msg = AuthenticationMessage.model_validate_json(data)
            if auth_msg.secret_key == self.metadata_secrets.get(
                auth_msg.hashed_metadata
            ):
                print("Secret verified.")
                return True
            print(
                f"Couldn't verify secret as recieved: {auth_msg.secret_key}, expected: {self.metadata_secrets.get(auth_msg.hashed_metadata)}"
            )
            return False
        except Exception as e:
            print(f"Error verifying secret: {e}")
            return False

    def _send_secret_key(self, peer_socket: socket.socket, hashed_metadata: str):
        """
        Send the secret key to the peer for authentication before each transmission.
        Returns True if authentication succeeds, False otherwise.
        """
        auth_msg = AuthenticationMessage(
            hashed_metadata=hashed_metadata,
            secret_key=self.metadata_secrets.get(hashed_metadata) or "",
        )
        # TODO you might consider sending the file length first.
        peer_socket.sendall(auth_msg.model_dump_json().encode())

    def _receive_file(self, conn, addr, file_type):
        """
        Receives a file and saves it to the appropriate directory based on file_type.
        """
        # Receive filename length and filename
        filename_len_data = conn.recv(4)
        if not filename_len_data:
            return
        filename_len = int.from_bytes(filename_len_data, byteorder="big")
        filename = conn.recv(filename_len).decode()

        # Receive file size
        filesize = int.from_bytes(conn.recv(8), byteorder="big")

        print(f"Receiving {file_type} '{filename}' ({filesize} bytes) from {addr}")

        # Determine destination directory based on file_type
        if file_type == "MODEL":
            save_dir = MODELS_DIR
        elif file_type == "DATA":
            save_dir = DATASETS_TEST_DIR
        elif file_type == "STATIC_MODULES":
            save_dir = STATIC_MODULES_PATH
        else:
            save_dir = "received_files"

        # Create directory if it doesn't exist
        os.makedirs(save_dir, exist_ok=True)
        temp_dire = os.path.join(ZIPPED_DIRE, "temp")
        os.makedirs(temp_dire, exist_ok=True)
        filepath = os.path.join(save_dir, filename)
        zip_path = os.path.join(ZIPPED_DIRE, filename)
        # Receive and write file data
        received = 0
        with open(zip_path, "wb") as f:
            while received < filesize:
                chunk = conn.recv(min(4096, filesize - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            print("Will unzip folder")
            if file_type == "MODEL":

                zip_ref.extractall(temp_dire)
                print(
                    f"Files extracted to {temp_dire} before checking and moving to {save_dir}"
                )
                # Extract the metadata file from  the file name and load the
                model_name = filename.rsplit(".", 1)[0]  # Remove .zip extension
                metadata_path = os.path.join(METADATA_PATH, f"{model_name}.json")
                metadata = MetadataConfig.parse_file(metadata_path)
                if ModelVerifier(metadata).is_better_model(temp_dire):
                    shutil.move(temp_dire, save_dir)
                    print(
                        f"Model '{filename}' from {addr} is better than the current model."
                    )
                else:
                    print(
                        f"Received model from {addr} is not better than the current model. Discarding."
                    )
            else:
                zip_ref.extractall(save_dir)
                print(
                    f"Files extracted to {save_dir} before checking and moving to {save_dir}"
                )

        print(
            f"{file_type} '{filename}' received successfully ({received} bytes) at {filepath}"
        )

        # Send acknowledgment
        conn.sendall(b"ACK")

    def start_server(self):
        def run():
            while True:
                conn, addr = self.server.accept()
                threading.Thread(
                    target=self.handle_peer, args=(conn, addr), daemon=True
                ).start()

        threading.Thread(target=run, daemon=True).start()

    def connect_to_peer(self, peer_host, peer_port=CLIENT_PORT) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((peer_host, peer_port))
        print(f"Connected to peer {peer_host}:{peer_port}")
        return s

    def send_message(
        self,
        peer_socket: socket.socket,
        message,
        hashed_metadata: str,
    ):
        print(f"Will send p2p message: {message}")
        self._send_secret_key(peer_socket, hashed_metadata)
        peer_socket.sendall(b"TEXT".ljust(10))
        peer_socket.sendall(message.encode())

    def send_file(
        self,
        peer_socket: socket.socket,
        filepath,
        hashed_metadata: str,
        file_type="MODEL",
    ):
        """
        Send a file to a connected peer with a specific type (MODEL or DATA).
        """
        if not os.path.exists(filepath):
            print(f"Error: File '{filepath}' not found")
            return False
        # print(f"Will send file: {filepath}")
        filename = os.path.basename(filepath)
        if os.path.isdir(filepath) and not filepath.endswith(".zip"):
            zip_name = f"{filename}.zip"
            filename = zip_name
            zip_path = os.path.join(ZIPPED_DIRE, zip_name)
            self.__zip_folder(filepath, zip_path)

        # Ensure file_type is valid (Optional validation depending on your strictness)
        if file_type not in ["MODEL", "DATA", "STATIC_MODULES"]:
            raise ValueError(
                f"Invalid file type '{file_type}'. Must be 'MODEL', 'STATIC_MODULES', or 'DATA'."
            )
        print("Will send file type: ", file_type)
        filesize = os.path.getsize(filepath)

        print(f"Sending {file_type} '{filename}' ({filesize} bytes)")
        self._send_secret_key(peer_socket, hashed_metadata)
        # 1. Send message type (padded to 10 bytes).
        # We send "MODEL" or "DATA" directly, not "FILE/"
        peer_socket.sendall(file_type.ljust(10).encode())

        # 2. Send filename length and filename.
        filename_bytes = filename.encode()
        peer_socket.sendall(len(filename_bytes).to_bytes(4, byteorder="big"))
        peer_socket.sendall(filename_bytes)

        # 3. Send file size.
        peer_socket.sendall(filesize.to_bytes(8, byteorder="big"))

        # 4. Send file data in chunks.
        sent = 0
        with open(filepath, "rb") as f:
            while sent < filesize:
                chunk = f.read(4096)
                if not chunk:
                    break
                peer_socket.sendall(chunk)
                sent += len(chunk)

        print(f"File sent: {sent} bytes")

        # 5. Wait for acknowledgment.
        ack = peer_socket.recv(3)
        if ack == b"ACK":
            print("File transfer confirmed by peer")
            return True
        else:
            print("File transfer acknowledgment not received")
            return False

    def __zip_folder(self, filepath, zip_path):
        print("Will zip folder")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 2. Use os.walk to catch all files in subdirectories
            for root, _, files in os.walk(filepath):
                for file in files:
                    # Create the full path to the file on disk
                    full_path = os.path.join(root, file)

                    # This ensures the zip structure matches the folder structure
                    rel_path = os.path.relpath(full_path, start=filepath)

                    zipf.write(full_path, arcname=rel_path)


p2p_node = P2PNode()
