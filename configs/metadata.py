from pydantic import BaseModel
from controllers.ml.interface.merge import StrategyType
import json
from configs.paths import METADATA_PATH
from configs.config import CONVERY_FILE_EXT, DATEIME_FORMAT
import os
import hashlib
from typing import List
from datetime import datetime

metadata_hash_pool = {}


class MetadataConfig(BaseModel):
    avg_count: int
    merge_strategy: StrategyType | str
    dataset_path: str
    model_name: str
    weights_path: str
    t: float
    # A list of hashed timestamps of each updated weights
    timestamps: List[str] = []
    latest_updated: str | None

    @staticmethod
    def parse_file(file_path: str) -> "MetadataConfig":
        with open(file_path, "r") as f:
            data = json.load(f)
        return MetadataConfig(**data)

    @staticmethod
    def parse_string(file_str: str) -> "MetadataConfig":
        return MetadataConfig(**json.loads(file_str))

    @staticmethod
    def load_from_hashed_val(hashed_matadata: str) -> "MetadataConfig":
        raw_value = get_raw_hashed_raw_value(hashed_matadata)
        splitted_values = raw_value.split(".")
        strategy = splitted_values[0].replace(".", "")
        model_name = splitted_values[1].replace(".", "")
        # t = splitted_values[2].replace(".", "")

        return MetadataConfig.parse_file(
            os.path.join(METADATA_PATH, model_name + "_" + strategy + CONVERY_FILE_EXT)
        )

    def save(self):
        strategy = (
            self.merge_strategy
            if isinstance(self.merge_strategy, str)
            else self.merge_strategy.value
        )
        path = os.path.join(METADATA_PATH, self.model_name + "_" + strategy)
        with open(path + CONVERY_FILE_EXT, "w") as f:
            json.dump(self.model_dump(), f, indent=2)

    def hash_self(self) -> str:
        return hashlib.sha256(self.get_before_hash().encode()).hexdigest()

    def get_before_hash(self) -> str:
        mg_strategy = (
            self.merge_strategy
            if isinstance(self.merge_strategy, str)
            else self.merge_strategy.value
        )
        return mg_strategy + "." + self.model_name + "." + str(self.t)

    def get_hashed_time_stamped_combined(self) -> str:
        stamped_string = "".join(self.timestamps)
        return hashlib.sha256(stamped_string.encode()).hexdigest()

    def set_latest_update(self, date: datetime):
        self.latest_updated = get_time_string(date)


def get_time_string(date: datetime):
    return date.strftime(DATEIME_FORMAT)


def add_metadata_pool(hashed_value: str, raw_value: str):
    metadata_hash_pool[hashed_value] = raw_value


def get_raw_hashed_raw_value(hashed_value: str) -> str:
    return metadata_hash_pool[hashed_value]
