from tensorflow.python.keras import Model
from configs.metadata import MetadataConfig
from ml.interface.model import IMergerManager
import torch
from typing import Dict, Any
from torch.nn import Module


class TorchMergerManager(IMergerManager):
    def __init__(self, metadata: str | MetadataConfig) -> None:
        super().__init__(metadata)

    def load_weights(self) -> Dict[str, Any]:
        return torch.load(self.metadata.weights_path, weights_only=True)

    def load_model_obj(self) -> Module:

        self.model = torch.load(self.metadata.model_obj_path)
        return self.model

    def is_better_score(self) -> bool:
        is_verified = False
        # Load model new weights.
        if self.model is None:
            self.load_model_obj()
        # Run against the dataset.
        # Compare with old score.
        return is_verified


# Data, previous score, accumulated scores hashed run current score, neg/positive metrics
