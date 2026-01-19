from abc import ABC, abstractmethod
from enum import Enum
from typing import Union, Dict, Optional, Any
import os
from configs.paths import MODELS_DIR
import copy
import numpy as np


class StrategyType(Enum):
    # NOTE: if added new strategy, update it in the ml/interface/model file in the switch statement as well.
    GREEDYSOUP = "greedy_soup"
    SOUP = "soup"
    SLERP = "slerp"


class IStrategy(ABC):
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
                self.model_weights = weights
            elif isinstance(weights, str):
                self.weights_path = weights

    @abstractmethod
    def merge(self, new_weights):
        pass


class IGreedySoup(IStrategy):
    count = 1.0

    def __init__(self, model_name, weights: str | Dict[str, Any] | None = None) -> None:
        super().__init__(model_name, weights)

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


class ISLERP(IStrategy):
    def __init__(
        self, model_name, weights: str | Dict[str, Any] | None = None, t=0.3
    ) -> None:
        super().__init__(model_name, weights)
        self.t = t

    def merge(self, new_weights: Dict[str, Any]):
        for layer_name, old_weights in self.model_weights.items():
            layer_new_weights = new_weights[layer_name]
            v0_c = copy.deepcopy(old_weights)
            v1_c = copy.deepcopy(layer_new_weights)
            old_weights = old_weights / np.linalg.norm(old_weights)
            layer_new_weights = layer_new_weights / np.linalg.norm(layer_new_weights)
            dot = np.sum(old_weights * layer_new_weights)
            theta_0 = np.arccos(dot)
            sin_theta_0 = np.sin(theta_0)
            theta_t = theta_0 * self.t
            sin_theta_t = np.sin(theta_t)
            s0 = np.sin(theta_0 - theta_t) / sin_theta_0
            s1 = sin_theta_t / sin_theta_0
            v2 = s0 * v0_c + s1 * v1_c
            self.model_weights[layer_name] = v2
        return self.model_weights
