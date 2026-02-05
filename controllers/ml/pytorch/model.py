from tensorflow.python.keras import Model
from configs.metadata import MetadataConfig
from controllers.ml.interface.model import IMergerManager, IModelStatic
import torch
from typing import Dict, Any
from torch.nn import Module


class TorchModelStatic(IModelStatic):
    def __init__(self, metadata: MetadataConfig) -> None:
        super().__init__(metadata)

    def load_weights(self) -> Dict[str, Any]:
        return torch.load(self.metadata.weights_path, weights_only=True)

    def load_model_obj(self) -> Module:

        self.model = torch.load(self.metadata.model_obj_path, weights_only=False)
        return self.model

    # NOTE: Overwrite it.
    def load_data(self, data_path: str):
        return super().load_data(data_path)


class TorchMergerManager(IMergerManager, TorchModelStatic):
    def __init__(
        self, metadata: str | MetadataConfig, model_loader: IModelStatic
    ) -> None:
        super().__init__(metadata, model_loader)


# Data, previous score, accumulated scores hashed run current score, neg/positive metrics
