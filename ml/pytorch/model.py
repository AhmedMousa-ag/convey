from interface.model import Model
from interface.merge import StrategyType
from typing import List, Union
from torch.nn import Module
from tensorflow.python.keras import Model
from pytorch.merge import Average


class PyTorchModel(Model):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def merge(self, models: List[Union[Module, Model]]):

        match self.metadata.merge_strategy:
            case StrategyType.AVERAGE:
                strategy = Average()
                return strategy.merge(models)
            case _:
                raise NotImplementedError(
                    f"Merge strategy {self.metadata.merge_strategy} not implemented."
                )
