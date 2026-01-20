import asyncio
from controllers.networking.threads import start_threads
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
        start_threads()
        st.session_state.threads_started = True
    await streamlit_GUI()


if __name__ == "__main__":
    asyncio.run(main())
