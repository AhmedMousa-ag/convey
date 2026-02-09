from abc import ABC, abstractmethod
from configs.metadata import MetadataConfig, MetadataConfig
from typing import Union, Dict, Any, TypeVar
from controllers.ml.interface.merge import StrategyType, IGreedySoup, ISLERP
from torch.nn import Module
from tensorflow.python.keras import Model
from dill import dump, load
import torch
from torch.utils.data import DataLoader
from tensorflow.python.keras.models import Model
from tensorflow.python.data import Dataset

T = TypeVar("T", bound="IModelStatic")


class IModelStatic(ABC):
    def __init__(self, metadata: MetadataConfig) -> None:
        self.metadata = metadata

    @abstractmethod
    def load_weights(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def load_model_obj(self) -> Module | Model:
        pass

    @abstractmethod
    def load_data(self, data_path: str):
        pass

    def save_model_static(self, path: str | None = None):
        if path is None:
            path = self.metadata.create_static_path()
        with open(path, "wb") as f:
            dump(self, f)
        print(f"Saved static model at: {path}")

    @staticmethod
    def load_model_static(path: str) -> T:
        with open(path, "rb") as f:
            return load(f)


class IVerifier(IModelStatic):
    @abstractmethod
    def is_better_score(self) -> bool:
        """target_score: true if higher means better, false if lower means better."""
        is_verified = False
        # Load model new weights.
        self.load_data(self.metadata.dataset_path)
        _ = self.load_weights()
        _ = self.load_model_obj()
        # Run against the dataset.
        # Compare with old score.
        return is_verified

    @abstractmethod
    def test_model(
        self, test_loader: DataLoader | Dataset, model: torch.nn.Module | Model
    ) -> float | Any:
        result = 0.0
        return result


class IStateVerifierModel(IVerifier):
    def __init__(self, metadata: MetadataConfig) -> None:
        super().__init__(metadata)


class IMergerManager:

    def __init__(
        self,
        metadata: Union[str, MetadataConfig, MetadataConfig],
        model_loader: IModelStatic,
    ) -> None:
        if isinstance(metadata, str):
            self.metadata: MetadataConfig = MetadataConfig.parse_file(
                file_path=metadata
            )
        else:
            self.metadata = metadata
            self.model = None
        self.model_loader = model_loader

    def get_merger(self, weights: Dict[str, Any] | None = None):
        if weights is None:
            weights = self.model_loader.load_weights()
        model_name = self.metadata.model_name

        match self.metadata.merge_strategy:
            case StrategyType.GREEDYSOUP:
                return IGreedySoup(model_name=model_name, weights=weights)
            case StrategyType.SLERP:
                if not isinstance(self.metadata, MetadataConfig):
                    raise ValueError(
                        f"Expected 'SLERPMetadataConfig', but found {type(self.metadata)}"
                    )
                return ISLERP(model_name=model_name, weights=weights, t=self.metadata.t)
            case _:
                raise ValueError(
                    f"Expected a strategy type, but found {self.metadata.merge_strategy}"
                )
