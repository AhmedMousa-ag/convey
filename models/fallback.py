from pydantic import BaseModel
from typing import List, Dict


class StringMsg(BaseModel):
    msg: str


class FileMsg(BaseModel):
    file_path: str
    ip: str
    file_type: str


# class Message(BaseModel):
#     message = StringMsg | FileMsg


class FallbackMessages(BaseModel):
    # Hashed metadata
    messages: Dict[str, List[StringMsg | FileMsg]]
