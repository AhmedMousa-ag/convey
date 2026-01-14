from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Union
from torch.nn import Module
from tensorflow.python.keras import Model


class StrategyType(Enum):
    AVERAGE = "average"


class BaseStrategy(ABC):
    @abstractmethod
    def merge(self, models: List[Union[Module, Model]]):
        pass
