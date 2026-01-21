import socket
import threading
import os
from configs.config import CLIENT_PORT, CLIENT_HOST


class P2PNode:
    def __init__(self):
        self.host = CLIENT_HOST
        self.port = CLIENT_PORT
        self.peers = set()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((self.host, self.port))
        self.server.listen(5)
        print(f"P2P node listening on {self.host}:{self.port}")

    def handle_peer(self, conn, addr):
        print(f"Connected by {addr}")
        self.peers.add(addr)
        try:
            while True:
                # First, receive the message type (text or file)
                msg_type = conn.recv(10).decode().strip()

                if not msg_type:
                    break

                if msg_type == "FILE":
                    self._receive_file(conn, addr)
                elif msg_type == "TEXT":
                    data = conn.recv(1024)
                    if not data:
                        break
                    print(f"Received from {addr}: {data.decode()}")
                    conn.sendall(data)  # Echo back
                else:
                    break
        finally:
            conn.close()
            self.peers.remove(addr)
            print(f"Disconnected {addr}")

    def _receive_file(self, conn, addr):
        # Receive filename length and filename
        filename_len = int.from_bytes(conn.recv(4), byteorder="big")
        filename = conn.recv(filename_len).decode()

        # Receive file size
        filesize = int.from_bytes(conn.recv(8), byteorder="big")

        print(f"Receiving file '{filename}' ({filesize} bytes) from {addr}")

        # Create received_files directory if it doesn't exist
        os.makedirs("received_files", exist_ok=True)
        filepath = os.path.join("received_files", filename)

        # Receive and write file data
        received = 0
        with open(filepath, "wb") as f:
            while received < filesize:
                chunk = conn.recv(min(4096, filesize - received))
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)

        print(f"File '{filename}' received successfully ({received} bytes)")

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

    def connect_to_peer(self, peer_host, peer_port=CLIENT_PORT):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((peer_host, peer_port))
        print(f"Connected to peer {peer_host}:{peer_port}")
        return s

    def send_message(self, peer_socket, message):
        peer_socket.sendall(b"TEXT".ljust(10))
        peer_socket.sendall(message.encode())

    def send_file(self, peer_socket, filepath):
        """
        Send a file to a connected peer.

        Args:
            peer_socket: Socket connection to the peer
            filepath: Path to the file to send
        """
        if not os.path.exists(filepath):
            print(f"Error: File '{filepath}' not found")
            return False

        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)

        print(f"Sending file '{filename}' ({filesize} bytes)")

        # Send message type
        peer_socket.sendall(b"FILE".ljust(10))

        # Send filename length and filename
        filename_bytes = filename.encode()
        peer_socket.sendall(len(filename_bytes).to_bytes(4, byteorder="big"))
        peer_socket.sendall(filename_bytes)

        # Send file size
        peer_socket.sendall(filesize.to_bytes(8, byteorder="big"))

        # Send file data in chunks
        sent = 0
        with open(filepath, "rb") as f:
            while sent < filesize:
                chunk = f.read(4096)
                if not chunk:
                    break
                peer_socket.sendall(chunk)
                sent += len(chunk)

        print(f"File sent: {sent} bytes")

        # Wait for acknowledgment
        ack = peer_socket.recv(3)
        if ack == b"ACK":
            print("File transfer confirmed by peer")
            return True
        else:
            print("File transfer acknowledgment not received")
            return False


# Example usage:
# peer = node.connect_to_peer('127.0.0.1', 5001)
# node.send_file(peer, "path/to/your/file.txt")
# node.send_message(peer, "Hello, peer!")

p2p_node = P2PNode()
