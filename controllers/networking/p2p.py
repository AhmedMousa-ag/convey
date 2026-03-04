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
        print(f"Attempting to read exactly {n} bytes from socket")
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
        print("Waiting to receive framed message (4-byte length prefix)")
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
        print("Will update secret")
        self.metadata_secrets[hashed_metadata] = secret

    def _verify_secret_key(self, conn: socket.socket) -> bool:
        """
        Receive and validate the authentication message from the peer.
        Uses recv_framed so the auth JSON never bleeds into the next recv.
        """
        try:
            data = self.recv_framed(conn)
            auth_msg = AuthenticationMessage.model_validate_json(data)
            print(f"Received authentication message: {auth_msg}")
            received_secret = auth_msg.secret_key
            existing_secret = self.metadata_secrets.get(auth_msg.hashed_metadata)
            if received_secret == existing_secret:
                print("Secret verified.")
                return True
            print(
                f"Couldn't verify secret — received: {received_secret}, "
                f"expected: {existing_secret}"
            )
            return False
        except Exception as e:
            print(f"Error verifying secret: {e}")
            return False

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
        self.peers.add(addr)
        try:
            # --- Authenticate once per connection ---

            while True:
                if not self._verify_secret_key(conn):
                    print(f"Authentication failed for {addr}. Closing connection.")
                    self.close_conn(conn, addr)
                    return
                # Receive the fixed 10-byte message-type header.
                # recv_exact guarantees we always get exactly 10 bytes, even
                # if TCP delivers them in multiple fragments.
                try:
                    msg_type_raw = self.recv_exact(conn, 10)
                except ConnectionError:
                    print(f"Connection closed by {addr}")
                    break

                msg_type = msg_type_raw.decode().strip()
                print(f"Received message type: {msg_type}")

                if not msg_type:
                    break

                if msg_type in ["MODEL", "DATA", "STATIC_MODULES"]:
                    self._receive_file(conn, addr, file_type=msg_type)

                elif msg_type == "TEXT":
                    # recv_framed reads the exact number of bytes that the
                    # sender wrote — no partial reads, no merged messages.
                    try:
                        data = self.recv_framed(conn)
                    except ConnectionError:
                        print(f"Connection closed by {addr} while reading TEXT body")
                        break

                    if not data:
                        break
                    print(f"Received from {addr}: {data.decode()}")
                    hashed_metadata, msg_type_inner, message = (
                        self.serializer.receive_msg(data.decode())
                    )
                    transmitter = TransmitterManager(
                        hashed_metadata, peer_address=addr, p2p_node=self
                    )
                    reply_data = transmitter.reply(msg_type=msg_type_inner, msg=message)
                    if reply_data is None:
                        continue
                    conn.sendall(reply_data.encode())
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

    def _receive_file(self, conn, addr, file_type):
        """
        Receives a file and saves it to the appropriate directory.
        All fixed-size fields use recv_exact to prevent boundary issues.
        """
        try:
            # Filename length (4 bytes) + filename
            filename_len = int.from_bytes(self.recv_exact(conn, 4), byteorder="big")
            filename = self.recv_exact(conn, filename_len).decode()

            # File size (8 bytes)
            filesize = int.from_bytes(self.recv_exact(conn, 8), byteorder="big")
        except ConnectionError as e:
            print(f"Error reading file metadata from {addr}: {e}")
            return

        print(f"Receiving {file_type} '{filename}' ({filesize} bytes) from {addr}")

        # Determine destination directory
        if file_type == "MODEL":
            save_dir = MODELS_DIR
        elif file_type == "DATA":
            save_dir = DATASETS_TEST_DIR
        elif file_type == "STATIC_MODULES":
            save_dir = STATIC_MODULES_PATH
        else:
            save_dir = "received_files"

        os.makedirs(save_dir, exist_ok=True)
        temp_dire = os.path.join(ZIPPED_DIRE, "temp")
        os.makedirs(temp_dire, exist_ok=True)

        filepath = os.path.join(save_dir, filename)
        zip_path = os.path.join(ZIPPED_DIRE, filename)

        # Receive file data in chunks until exactly filesize bytes are read
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
                    f"Files extracted to {temp_dire} before checking and "
                    f"moving to {save_dir}"
                )
                model_name = filename.rsplit(".", 1)[0]
                metadata_path = os.path.join(METADATA_PATH, f"{model_name}.json")
                metadata = MetadataConfig.parse_file(metadata_path)
                if ModelVerifier(metadata).is_better_model(temp_dire):
                    shutil.move(temp_dire, save_dir)
                    print(
                        f"Model '{filename}' from {addr} is better than the "
                        f"current model."
                    )
                else:
                    print(
                        f"Received model from {addr} is not better than the "
                        f"current model. Discarding."
                    )
            else:
                zip_ref.extractall(save_dir)
                print(f"Files extracted to {save_dir}")

        print(
            f"{file_type} '{filename}' received successfully "
            f"({received} bytes) at {filepath}"
        )

        # Acknowledge receipt
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
        message: str,
        hashed_metadata: str,
    ):
        """
        Send a TEXT message.

        Wire format per connection (auth sent once at connection open):
            [framed auth JSON]
            [10-byte msg type header]
            [framed message payload]

        Using send_framed for the payload ensures the receiver's recv_framed
        call reads exactly the right number of bytes and doesn't bleed into
        the next message.
        """
        print(f"Will send p2p message: {message}")
        self._send_secret_key(peer_socket, hashed_metadata)
        peer_socket.sendall(b"TEXT".ljust(10))
        self.send_framed(peer_socket, message.encode())

    def send_file(
        self,
        peer_socket: socket.socket,
        filepath: str,
        hashed_metadata: str,
        file_type: str = "MODEL",
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

        filename = os.path.basename(filepath)

        # Zip directory if needed
        if os.path.isdir(filepath) and not filepath.endswith(".zip"):
            zip_name = f"{filename}.zip"
            filename = zip_name
            zip_path = os.path.join(ZIPPED_DIRE, zip_name)
            self.__zip_folder(filepath, zip_path)
            filepath = zip_path

        if file_type not in ["MODEL", "DATA", "STATIC_MODULES"]:
            raise ValueError(
                f"Invalid file type '{file_type}'. "
                f"Must be 'MODEL', 'STATIC_MODULES', or 'DATA'."
            )

        filesize = os.path.getsize(filepath)
        print(f"Sending {file_type} '{filename}' ({filesize} bytes)")

        # # Auth (framed so it never merges with the header bytes that follow)
        # self._send_secret_key(peer_socket, hashed_metadata)

        # 1. Message type header (fixed 10 bytes)
        peer_socket.sendall(file_type.ljust(10).encode())
        print(f"Sent file type header: '{file_type}'")
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
            print("Connection closed before ACK was received")
            return False

        if ack == b"ACK":
            print("File transfer confirmed by peer")
            return True
        else:
            print("File transfer acknowledgment not received")
            return False

    def __zip_folder(self, filepath: str, zip_path: str):
        print("Will zip folder")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(filepath):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, start=filepath)
                    zipf.write(full_path, arcname=rel_path)


p2p_node = P2PNode()
