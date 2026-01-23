import socket
import threading
import os
from configs.config import CLIENT_PORT, CLIENT_HOST
from configs.paths import DATASETS_TEST_DIR, MODELS_DIR, ZIPPED_DIRE
import zipfile
from controllers.networking.serializer import MessageSerializer
from controllers.networking.transmitter import TransmitterManager


class P2PNode:
    def __init__(self):
        self.host = CLIENT_HOST
        self.port = CLIENT_PORT
        self.peers = set()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        self.serializer = MessageSerializer()
        print(f"P2P node listening on {self.host}:{self.port}")

    def handle_peer(self, conn, addr):
        print(f"Connected by {addr}")
        self.peers.add(addr)
        try:
            while True:
                # First, receive the message type (fixed 10 bytes)
                # This could be "TEXT", "MODEL", or "DATA"
                msg_type = conn.recv(10).decode().strip()

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
                        data
                    )
                    transmitter = TransmitterManager(
                        hashed_metadata, peer_address=addr, p2p_node=self
                    )
                    reply_data = transmitter.reply(msg_type=msg_type, msg=message)
                    if reply_data is None:
                        continue
                    conn.sendall(reply_data)
                else:
                    # Unknown header type
                    print(f"Unknown message type received: {msg_type}")
                    break
        finally:
            conn.close()
            if addr in self.peers:
                self.peers.remove(addr)
            print(f"Disconnected {addr}")

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
        else:
            save_dir = "received_files"

        # Create directory if it doesn't exist
        os.makedirs(save_dir, exist_ok=True)
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
            zip_ref.extractall(save_dir)
            print(f"Files extracted to {save_dir}")
        print(
            f"{file_type} '{filename}' received successfully ({received} bytes) at {filepath}"
        )

        # Send acknowledgment
        conn.sendall(b"ACK")

    def start_server(self):
        print("Started p2p server.")

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

    def send_message(self, peer_socket, message):
        print(f"Will send message: {message}")
        peer_socket.sendall(b"TEXT".ljust(10))
        peer_socket.sendall(message.encode())

    def send_file(self, peer_socket, filepath, file_type="MODEL"):
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
        if file_type not in ["MODEL", "DATA"]:
            print(f"Warning: Unknown file type '{file_type}'. Sending anyway.")

        filesize = os.path.getsize(filepath)

        print(f"Sending {file_type} '{filename}' ({filesize} bytes)")

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
