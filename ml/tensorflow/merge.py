from typing import List
from tensorflow.python.keras import Model
from interface.merge import BaseStrategy


class Average(BaseStrategy):
    def merge(self, models: List[Model]):
        if len(models) < 1:
            raise ValueError(
                "The models list must contain at least one model to merge."
            )
        # Get the weights of each model
        weights = [model.get_weights() for model in models]

        # Average weights
        avg_weights = []
        for weights_tuple in zip(*weights):
            avg_weights.append(sum(w for w in weights_tuple) / len(weights_tuple))

        # Set averaged weights to the first model and return it
        merged_model = models[0]
        merged_model.set_weights(avg_weights)
        return merged_model
