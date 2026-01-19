from controllers.networking.ws_client import interactive_client
import asyncio
from threading import Thread
import os
from views.streamlit import streamlit_GUI


def get_user_input(display_msg: str) -> str:
    user_input = input(display_msg + "\n")
    print(f"You have picked: {user_input}")
    return user_input


async def main():
    interactive_thread = Thread(
        target=lambda: asyncio.run(interactive_client()), daemon=True
    )
    interactive_thread.start()
    await streamlit_GUI()
    interactive_thread.join()


if __name__ == "__main__":

    asyncio.run(main())
