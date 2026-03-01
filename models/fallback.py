from pydantic import BaseModel
from typing import List, Dict


class StringMsg(BaseModel):
    msg: str


class FileMsg(BaseModel):
    file_path: str
    ip: str
    file_type: str


class FallbackMessages(BaseModel):
    messages: Dict[str, List[StringMsg | FileMsg]]
