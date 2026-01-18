from abc import ABC, abstractmethod
from configs.metadata import MetadataConfig, SLERPMetadataConfig
from typing import Union, Dict, Any
from ml.interface.merge import StrategyType, IGreedySoup, ISLERP


class IMergerManager(ABC):

    def __init__(
        self, metadata: Union[str, MetadataConfig, SLERPMetadataConfig]
    ) -> None:
        if isinstance(metadata, str):
            self.metadata: MetadataConfig = MetadataConfig.parse_file(
                file_path=metadata
            )
        else:
            self.metadata = metadata

    def get_merger(self, weights: Dict[str, Any] | None = None):
        if weights is None:
            weights = self.load_weights()
        model_name = self.metadata.model_name

        match self.metadata.merge_strategy:
            case StrategyType.GREEDYSOUP:
                return IGreedySoup(model_name=model_name, weights=weights)
            case StrategyType.SLERP:
                if not isinstance(self.metadata, SLERPMetadataConfig):
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
