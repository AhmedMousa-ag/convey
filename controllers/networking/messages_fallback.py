import asyncio
from models.fallback import FallbackMessages, FileMsg, StringMsg

sender = asyncio.Queue()
receiver = asyncio.Queue()

fall_back_messages: FallbackMessages = FallbackMessages(messages={})


class FallbacksManager:
    def __new__(cls):
        if not hasattr(cls, "inst"):
            cls.inst = super().__new__(cls)
        return cls.inst

    def register_msg(self, hashed_metadata: str, msg: str):
        print("Will register fallback message: ", hashed_metadata)
        fall_back_messages.messages.setdefault(hashed_metadata, []).append(
            StringMsg(msg=msg)
        )

    def register_file(
        self,
        hashed_metadata: str,
        ip: str,
        file_path: str,
        file_type: str,
    ):
        print("Will register fallback file: ", hashed_metadata)
        fall_back_messages.messages.setdefault(hashed_metadata, []).append(
            FileMsg(file_path=file_path, file_type=file_type, ip=ip)
        )

    def get_pending_messages(self) -> FallbackMessages:
        print("Will get all pending fallback messages.")
        return fall_back_messages

    def remove_fallback_message(self, hashed_metadata: str):
        print("Will remove a fallback message...")
        fall_back_messages.messages.pop(hashed_metadata)
