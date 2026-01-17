from pydantic import BaseModel
from ml.interface.merge import StrategyType
import json
from configs.config import METADATA_PATH


class MetadataConfig(BaseModel):
    num_models: int
    merge_strategy: StrategyType
    dataset_path: str

    @staticmethod
    def parse_file(file_path: str) -> "MetadataConfig":

        with open(file_path, "r") as f:
            data = json.load(f)
        return MetadataConfig(**data)

    def dump(self, path):
        pass
