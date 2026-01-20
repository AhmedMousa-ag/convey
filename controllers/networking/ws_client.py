import asyncio
import websockets
from configs.config import SERVER_URL, WS_CONNECTION_WAIT
from controllers.networking.messages import get_msg_sender
from pydantic import BaseModel
import json
from models.server import ClientsIPAddresses
from controllers.networking.pool import update_connection_p2p_pool
import time


async def server_ws_client():
    print("Started ws client.")
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

                            update_connection_p2p_pool(message)
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
