import socket
import threading
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
                data = conn.recv(1024)
                if not data:
                    break
                print(f"Received from {addr}: {data.decode()}")
                conn.sendall(data)  # Echo back
        finally:
            conn.close()
            self.peers.remove(addr)
            print(f"Disconnected {addr}")

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
        peer_socket.sendall(message.encode())


# Example usage: connect to another peer and send a message
# peer = node.connect_to_peer('127.0.0.1', 5001)
# node.send_message(peer, "Hello, peer!")

p2p_node = P2PNode()
