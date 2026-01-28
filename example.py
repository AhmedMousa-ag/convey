from typing import Any, Dict
from configs.metadata import MetadataConfig, METADATA_PATH
from controllers.ml.interface.model import IModelStatic
import torch
from torch.nn import Module
import os


class TestStaticModel(IModelStatic):
    def __init__(self, metadata: MetadataConfig) -> None:
        print("Static model called correctly.")
        super().__init__(metadata)

    def load_weights(self) -> Dict[str, Any]:
        return torch.load(self.metadata.weights_path, weights_only=True)

    def load_model_obj(self) -> Module:

        self.model = torch.load(self.metadata.model_obj_path)
        return self.model

    def load_data(self):
        data_path = self.metadata.dataset_path

    def is_better_score(self, is_higher_target_score: bool) -> bool:
        print("Called is better score")
        is_verified = False
        return is_verified


model = TestStaticModel(
    MetadataConfig.parse_file(os.path.join(METADATA_PATH, "my_model_slerp.json"))
)

model.save_model_static()


loaded_model = TestStaticModel.load_model_static(
    "/home/akm/Work/University/convey/my_model_slerp.dill"
)

loaded_model.is_better_score(True)
