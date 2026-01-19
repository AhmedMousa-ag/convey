from pydantic import BaseModel
from controllers.ml.interface.merge import StrategyType
import json
from configs.paths import METADATA_PATH
from configs.config import CONVERY_FILE_EXT
import os
import hashlib


class MetadataConfig(BaseModel):
    avg_count: int
    merge_strategy: StrategyType | str
    dataset_path: str
    model_name: str
    weights_path: str
    t: float

    @staticmethod
    def parse_file(file_path: str) -> "MetadataConfig":

        with open(file_path, "r") as f:
            data = json.load(f)
        return MetadataConfig(**data)

    @staticmethod
    def parse_string(file_str: str) -> "MetadataConfig":
        return MetadataConfig(**json.loads(file_str))

    def save(self, path: str | None = None):
        if path is None:
            path = os.path.join(METADATA_PATH, self.model_name)

        with open(path + CONVERY_FILE_EXT, "w") as f:
            json.dump(self.model_dump(), f, indent=2)

    def hash_self(self) -> str:
        mg_strategy = (
            self.merge_strategy
            if isinstance(self.merge_strategy, str)
            else self.merge_strategy.value
        )
        string_to_hast = mg_strategy + self.model_name + str(self.t)
        return hashlib.sha256(string_to_hast.encode()).hexdigest()
