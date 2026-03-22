import asyncio
import websockets
import json
import time
from pydantic import BaseModel
from configs.config import SERVER_URL, WS_CONNECTION_WAIT, CLIENT_PORT
from controllers.networking.messages import get_msg_sender
from models.server import ClientsIPAddresses
from controllers.networking.pool import update_connection_p2p_pool
from controllers.networking.p2p import p2p_node
from models.server import SecretMetadataKey, MessagesTypes
from controllers.networking.perf_logger import perf_log


async def read_handler(websocket):
    """Handles receiving messages from the server."""
    try:
        async for message in websocket:
            t0 = time.time()
            if isinstance(message, str):
                try:
                    # Validate and parse the message
                    data = json.loads(message)
                    msg_data = data.get("message")
                    msg_type = data.get("msg_type")
                    perf_log(f"WS_RECV | type={msg_type} | size={len(message)}B | parse_time={time.time()-t0:.4f}s")
                    # If the message type is for changing the secret key
                    if msg_type == MessagesTypes.ChangeSecret.value:
                        secret_data = SecretMetadataKey(**msg_data)
                        # Update the secret key in the p2p node
                        p2p_node.update_secret(
                            hashed_metadata=secret_data.hashed_metadata,
                            secret=secret_data.new_secret,
                        )
                    elif msg_type == MessagesTypes.SUBSCRIBE.value:
                        # If the message type is for subscribing to a topic
                        # print("Got subscribe message from server................")
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
            t0 = time.time()
            if isinstance(message, BaseModel):
                message = message.model_dump_json()

            await websocket.send(message)
            perf_log(f"WS_SEND | size={len(message) if isinstance(message, str) else 'N/A'}B | elapsed={time.time()-t0:.4f}s")

        await asyncio.sleep(0)


async def server_ws_client():
    while True:  # Reconnection Loop
        try:
            perf_log(f"WS_CONNECT | url={SERVER_URL} | status=attempting")
            conn_t0 = time.time()
            async with websockets.connect(SERVER_URL) as websocket:
                perf_log(f"WS_CONNECT | url={SERVER_URL} | status=connected | elapsed={time.time()-conn_t0:.4f}s")
                # Run both Reader and Writer concurrently
                await asyncio.gather(read_handler(websocket), write_handler(websocket))

        except (websockets.exceptions.ConnectionClosed, OSError) as e:
            perf_log(f"WS_CONNECT | status=lost | error={e}")
            print(f"Connection lost or failed: {e}")
        except Exception as e:
            perf_log(f"WS_CONNECT | status=error | error={e}")
            print(f"Unexpected Error: {e}")

        perf_log(f"WS_RECONNECT | wait={WS_CONNECTION_WAIT}s")
        print(f"Reconnecting in {WS_CONNECTION_WAIT} seconds...")
        # CRITICAL FIX: Do not use time.sleep(), use asyncio.sleep()
        await asyncio.sleep(WS_CONNECTION_WAIT)


if __name__ == "__main__":
    try:
        asyncio.run(server_ws_client())
    except KeyboardInterrupt:
        print("Client stopped manually.")
