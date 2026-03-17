from models.fallback import FallbackMessages, FileMsg, StringMsg


fall_back_messages: FallbackMessages = FallbackMessages(messages={})


class FallbacksManager:
    def __new__(cls):
        if not hasattr(cls, "inst"):
            cls.inst = super().__new__(cls)
        return cls.inst

    def register_msg(self, hashed_metadata: str, msg: str):
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
        # print(f"Registering fallback file, file_type={file_type}")
        fall_back_messages.messages.setdefault(hashed_metadata, []).append(
            FileMsg(file_path=file_path, file_type=file_type, ip=str(ip))
        )

    def get_pending_messages(self) -> FallbackMessages:
        return fall_back_messages

    def remove_fallback_message(self, hashed_metadata: str, msg: FileMsg | StringMsg):
        try:
            fall_back_messages.messages.pop(hashed_metadata).remove(msg)
        except Exception as e:
            print("Exception removing fallback messages: ")
