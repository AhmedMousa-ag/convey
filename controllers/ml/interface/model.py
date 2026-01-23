from abc import ABC, abstractmethod
from configs.metadata import MetadataConfig, MetadataConfig
from typing import Union, Dict, Any
from ml.interface.merge import StrategyType, IGreedySoup, ISLERP
from torch.nn import Module
from tensorflow.python.keras import Model


class IMergerManager(ABC):

    def __init__(self, metadata: Union[str, MetadataConfig, MetadataConfig]) -> None:
        if isinstance(metadata, str):
            self.metadata: MetadataConfig = MetadataConfig.parse_file(
                file_path=metadata
            )
        else:
            self.metadata = metadata
            self.model = None

    def get_merger(self, weights: Dict[str, Any] | None = None):
        if weights is None:
            weights = self.load_weights()
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

    @abstractmethod
    def load_weights(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def load_model_obj(self) -> Module | Model:
        pass

    @abstractmethod
    def is_better_score(self) -> bool:
        is_verified = False
        # Load model new weights.
        # Run against the dataset.
        # Compare with old score.
        return is_verified
