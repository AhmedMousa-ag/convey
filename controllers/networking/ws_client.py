import asyncio
import websockets
import json
from pydantic import BaseModel
from configs.config import SERVER_URL, WS_CONNECTION_WAIT, CLIENT_PORT
from controllers.networking.messages import get_msg_sender
from models.server import ClientsIPAddresses
from controllers.networking.pool import update_connection_p2p_pool
from controllers.networking.p2p import p2p_node
from models.server import SecretMetadataKey, MessagesTypes


async def read_handler(websocket):
    """Handles receiving messages from the server."""
    try:
        async for message in websocket:
            if isinstance(message, str):
                try:
                    # Validate and parse the message
                    data = json.loads(message)
                    msg_data = data.get("message")
                    msg_type = data.get("msg_type")
                    print("Server: Recieved msg type: ", msg_type)
                    # If the message type is for changing the secret key
                    if msg_type == MessagesTypes.ChangeSecret.value:
                        secret_data = SecretMetadataKey(**msg_data)
                        # Update the secret key in the p2p node
                        p2p_node.update_secret(
                            secret_data.hashed_metadata, secret_data.new_secret
                        )
                    elif msg_type == MessagesTypes.SUBSCRIBE.value:
                        # If the message type is for subscribing to a topic
                        print("Got subscribe message from server................")
                        client_data = ClientsIPAddresses(**msg_data)
                        conn = p2p_node.connect_to_peer(client_data.ip, CLIENT_PORT)
                        update_connection_p2p_pool(client_data, conn)
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
    while True:  # Reconnection Loop
        try:
            async with websockets.connect(SERVER_URL) as websocket:
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
