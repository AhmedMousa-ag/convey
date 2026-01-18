from pydantic import BaseModel
from ml.interface.merge import StrategyType
import json
from configs.paths import METADATA_PATH
from configs.config import CONVERY_FILE_EXT
import os


class MetadataConfig(BaseModel):
    avg_count: int
    merge_strategy: StrategyType
    dataset_path: str
    model_name: str
    weights_path: str

    @staticmethod
    def parse_file(file_path: str) -> "MetadataConfig":

        with open(file_path, "r") as f:
            data = json.load(f)
        return MetadataConfig(**data)

    def save(self, path: str | None = None):
        if path is None:
            path = os.path.join(METADATA_PATH, self.model_name)

        with open(path + CONVERY_FILE_EXT, "w") as f:
            json.dump(self.model_dump(), f, indent=2)


class SLERPMetadataConfig(MetadataConfig):
    t: float
