import asyncio
import websockets
import json
from pydantic import BaseModel
from configs.config import SERVER_URL, WS_CONNECTION_WAIT
from controllers.networking.messages import get_msg_sender
from models.server import ClientsIPAddresses
from controllers.networking.pool import update_connection_p2p_pool


async def read_handler(websocket):
    """Handles receiving messages from the server."""
    print("Started to receive messages")
    try:
        async for message in websocket:
            if isinstance(message, str):
                try:
                    # Validate and parse the message
                    data = json.loads(message)
                    client_data = ClientsIPAddresses(**data)
                    update_connection_p2p_pool(client_data)
                except json.JSONDecodeError:
                    print("Received invalid JSON")
                except Exception as e:
                    print(f"Error processing message: {e}")
    except websockets.exceptions.ConnectionClosed:
        print("Connection closed during read")
        raise  # Raise to trigger the gather handling


async def write_handler(websocket):
    """Handles sending messages to the server."""
    print("Started write handler")
    while True:
        message = await get_msg_sender()

        if message:
            print("Got a message to send")
            if isinstance(message, BaseModel):
                message = message.model_dump_json()

            await websocket.send(message)

        await asyncio.sleep(0)


async def server_ws_client():
    print("Started ws client.")
    while True:  # Reconnection Loop
        try:
            async with websockets.connect(SERVER_URL) as websocket:
                print(f"Connected to {SERVER_URL}")

                # Run both Reader and Writer concurrently
                await asyncio.gather(read_handler(websocket), write_handler(websocket))

        except (websockets.exceptions.ConnectionClosed, OSError) as e:
            print(f"Connection lost or failed: {e}")
        except Exception as e:
            print(f"Unexpected Error: {e}")

        print(f"Reconnecting in {WS_CONNECTION_WAIT} seconds...")
        # CRITICAL FIX: Do not use time.sleep(), use asyncio.sleep()
        await asyncio.sleep(WS_CONNECTION_WAIT)


if __name__ == "__main__":
    try:
        asyncio.run(server_ws_client())
    except KeyboardInterrupt:
        print("Client stopped manually.")
