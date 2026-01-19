import asyncio
import websockets
from configs.config import SERVER_URL
from .messages import get_msg_sender


async def interactive_client():

    try:
        async with websockets.connect(SERVER_URL) as websocket:
            print(f"Connected to {SERVER_URL}")

            # Start a task to receive messages
            async def receive_messages():
                try:
                    async for message in websocket:
                        print(f"\nReceived: {message}")
                        print("> ", end="", flush=True)
                except websockets.exceptions.ConnectionClosed:
                    print("\nConnection closed by server")

            receive_task = asyncio.create_task(receive_messages())

            # Send messages to the server
            while True:
                message = await get_msg_sender()

                await websocket.send(message)

            receive_task.cancel()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(interactive_client())
