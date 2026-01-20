from controllers.networking.p2p import p2p_node
from threading import Thread
import asyncio
from controllers.networking.ws_client import server_ws_client


p2p_thread = Thread(target=lambda: p2p_node.start_server(), daemon=True)


server_cl_thread = Thread(target=lambda: asyncio.run(server_ws_client()), daemon=True)


def start_threads():
    server_cl_thread.start()
    p2p_thread.start()
