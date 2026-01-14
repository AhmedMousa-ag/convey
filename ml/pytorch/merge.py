from typing import List
from torch.nn import Module
from interface.merge import BaseStrategy


class Average(BaseStrategy):
    def merge(self, models: List[Module]):
        if len(models) < 1:
            raise ValueError(
                "The models list must contain at least one model to merge."
            )

        # Initialize the averaged model with the parameters of the first model
        avg_state_dict = models[0].state_dict()

        # Sum the parameters from all models
        for key in avg_state_dict.keys():
            for model in models[1:]:
                avg_state_dict[key] += model.state_dict()[key]
            avg_state_dict[key] /= len(models)

        # Load averaged parameters back into the first model and return it
        models[0].load_state_dict(avg_state_dict)
        return models[0]
