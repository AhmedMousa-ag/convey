from controllers.networking.ws_client import server_ws_client
import asyncio
from threading import Thread
from controllers.networking.client import P2PNode
from views.streamlit import streamlit_GUI
import streamlit as st


def get_user_input(display_msg: str) -> str:
    user_input = input(display_msg + "\n")
    print(f"You have picked: {user_input}")
    return user_input


async def main():
    # Initialize session state
    if "threads_started" not in st.session_state:
        st.session_state.threads_started = False

    # Only start threads once
    if not st.session_state.threads_started:
        interactive_thread = Thread(
            target=lambda: asyncio.run(server_ws_client()), daemon=True
        )
        p2p_node = P2PNode()
        p2p_thread = Thread(target=lambda: p2p_node.start_server(), daemon=True)

        interactive_thread.start()
        p2p_thread.start()

        # Store references if you need them later
        st.session_state.interactive_thread = interactive_thread
        st.session_state.p2p_node = p2p_node
        st.session_state.p2p_thread = p2p_thread
        st.session_state.threads_started = True
    await streamlit_GUI()
    # interactive_thread.join()
    # p2p_thread.join()


if __name__ == "__main__":
    asyncio.run(main())
