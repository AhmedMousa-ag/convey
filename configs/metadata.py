from pydantic import BaseModel
from interface.merge import Strategy
import json


class MetadataConfig(BaseModel):
    num_models: int
    merge_strategy: Strategy

    @staticmethod
    def parse_file(file_path: str) -> "MetadataConfig":

        with open(file_path, "r") as f:
            data = json.load(f)
        return MetadataConfig(**data)
