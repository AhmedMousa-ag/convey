import asyncio
import websockets
from configs.config import SERVER_URL, WS_CONNECTION_WAIT
from .messages import get_msg_sender
from pydantic import BaseModel
import json
from typing import Dict
from models.server import SubscribeTopic, ClientsIPAddresses
from controllers.networking.p2p import update_connection_p2p_pool
import time


async def server_ws_client():
    while True:  # Always try to connect
        try:
            async with websockets.connect(SERVER_URL) as websocket:
                print(f"Connected to {SERVER_URL}")

                # Start a task to receive messages
                async def receive_messages():
                    try:
                        async for message in websocket:
                            if isinstance(message, str):
                                # We only have this type of address, which should be enough.
                                message: ClientsIPAddresses = ClientsIPAddresses(
                                    **json.loads(message)
                                )
                            hashed_metadata = message.hashed_metadata
                            print("Hashed metadata: ", hashed_metadata)
                            update_connection_p2p_pool(hashed_metadata, message.ips)
                    except websockets.exceptions.ConnectionClosed:
                        print("\nConnection closed by server")

                receive_task = asyncio.create_task(receive_messages())

                # Send messages to the server
                while True:
                    message = await get_msg_sender()
                    if isinstance(message, BaseModel):
                        message = message.model_dump_json()
                    await websocket.send(message)

                receive_task.cancel()

        except Exception as e:
            print(f"Error: {e}")
        time.sleep(WS_CONNECTION_WAIT)


if __name__ == "__main__":
    asyncio.run(server_ws_client())
