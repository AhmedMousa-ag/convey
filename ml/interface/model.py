from abc import ABC
from configs.metadata import MetadataConfig


class Model(ABC):

    def __init__(self, meta_data_path: str) -> None:
        self.metadata: MetadataConfig = MetadataConfig.parse_file(
            file_path=meta_data_path
        )
