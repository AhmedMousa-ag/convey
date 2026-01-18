from typing import List
from tensorflow.python.keras import Model
from ml.interface.merge import IGreedySoup
import tensorflow as tf


class TfGreedySoup(IGreedySoup):
    def __init__(self, model_name) -> None:
        super().__init__(model_name)
        # self.model_weights = tf.load_ #TODO
        pass
