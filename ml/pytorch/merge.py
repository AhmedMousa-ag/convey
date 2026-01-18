from typing import Any, Dict
from ml.interface.merge import IGreedySoup, ISLERP
import torch


class TorchGreedySoup(IGreedySoup):
    def __init__(
        self, model_name, weights: str | Dict[str, float] | None = None
    ) -> None:
        super().__init__(model_name, weights)


class TorchSLERP(ISLERP):
    def __init__(
        self, model_name, weights: str | Dict[str, Any] | None = None, t=0.3
    ) -> None:
        super().__init__(model_name, weights, t)

    def merge(self, new_weights: Dict[str, Any]):
        for layer_name, old_weights in self.model_weights.items():
            layer_new_weights = new_weights[layer_name]
            old_weights = (
                old_weights.float()
                if old_weights.dtype in [torch.int32, torch.int64, torch.long]
                else old_weights
            )
            layer_new_weights = (
                layer_new_weights.float()
                if layer_new_weights.dtype in [torch.int32, torch.int64, torch.long]
                else layer_new_weights
            )

            # Deep copy the tensors
            v0_c = old_weights.clone()
            v1_c = layer_new_weights.clone()
            # Normalize the weights
            old_weights_norm = old_weights / torch.norm(old_weights)
            layer_new_weights_norm = layer_new_weights / torch.norm(layer_new_weights)

            # Compute dot product
            dot = torch.sum(old_weights_norm * layer_new_weights_norm)

            # Clamp dot product to valid range for arccos to avoid numerical issues
            dot = torch.clamp(dot, -1.0, 1.0)

            # Compute angles
            theta_0 = torch.arccos(dot)
            sin_theta_0 = torch.sin(theta_0)
            theta_t = theta_0 * self.t
            sin_theta_t = torch.sin(theta_t)

            # Compute interpolation coefficients
            s0 = torch.sin(theta_0 - theta_t) / sin_theta_0
            s1 = sin_theta_t / sin_theta_0

            # Spherical linear interpolation (SLERP)
            v2 = s0 * v0_c + s1 * v1_c

            self.model_weights[layer_name] = v2

        return self.model_weights
