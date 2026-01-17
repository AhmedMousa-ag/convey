from typing import Dict
from ml.interface.merge import GreedySoup


class TorchGreedySoup(GreedySoup):
    def __init__(
        self, model_name, weights: str | Dict[str, float] | None = None
    ) -> None:
        super().__init__(model_name, weights)
