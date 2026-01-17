from abc import ABC, abstractmethod
from enum import Enum
from typing import Union, Dict, Optional, Any
import os
from configs.config import MODELS_DIR
import copy


class StrategyType(Enum):
    AVERAGE = "average"


class BaseStrategy(ABC):
    @abstractmethod
    def merge(self, new_weights):
        pass


class GreedySoup(BaseStrategy):
    count = 1.0
    model_weights: Dict[str, Any] = {}
    model_name: str
    weights_path: str

    def __init__(
        self, model_name, weights: Optional[Union[str, Dict[str, Any]]] = None
    ) -> None:
        self.model_name = model_name
        self.__load_weights(weights)

    def __load_weights(self, weights: Optional[Union[str, Dict[str, Any]]] = None):
        if not weights:
            self.weights_path = os.path.join(MODELS_DIR, self.model_name)
        else:
            if isinstance(weights, Dict):
                self.model_weights = copy.deepcopy(weights)
            elif isinstance(weights, str):
                self.weights_path = weights

    def __calc_average(self, new_weights_dict: Dict[str, Any]):
        self.count += 1.0
        # Iterate through both dictionaries by key
        for layer_name, old_weights in self.model_weights.items():
            new_weights = new_weights_dict[layer_name]
            diff = new_weights - old_weights
            updated_weights = old_weights + (diff / self.count)

            self.model_weights[layer_name] = copy.deepcopy(updated_weights)

    def merge(self, new_weights: Dict[str, Any]) -> Dict[str, Any]:
        self.__calc_average(new_weights)
        return self.model_weights
