from configs.metadata import MetadataConfig
from ml.interface.model import IMergerManager
import torch
from typing import Dict, Any


class TorchMergerManager(IMergerManager):
    def __init__(self, metadata: str | MetadataConfig) -> None:
        super().__init__(metadata)

    def load_weights(self) -> Dict[str, Any]:
        return torch.load(self.metadata.weights_path, weights_only=True)
