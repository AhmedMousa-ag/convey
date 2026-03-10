from configs.metadata import MetadataConfig
from configs.paths import METADATA_PATH, STATIC_MODULES_PATH
from controllers.ml.interface.model import IVerifier, IStateVerifierModel
from controllers.ml.pytorch.model import TorchModelStatic
import os
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"


class TestStaticModel(TorchModelStatic, IVerifier):
    def __init__(self, metadata: MetadataConfig) -> None:
        super().__init__(metadata)

    def load_data(self, data_path: str):
        transform_test = transforms.Compose(
            [
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=(0.5071, 0.4867, 0.4408), std=(0.2675, 0.2565, 0.2761)
                ),
            ]
        )
        testset = torchvision.datasets.CIFAR100(
            root=data_path, train=False, download=True, transform=transform_test
        )
        return DataLoader(testset, batch_size=128, shuffle=False, num_workers=4)

    def test_model(self, test_loader: DataLoader, model: torch.nn.Module) -> float:
        model = model.to(device)
        model.eval()
        correct = 0
        total = 0
        # Disable gradient calculation for efficiency and to prevent unintended training
        with torch.no_grad():
            for data, target in test_loader:
                data, target = data.to(device), target.to(device)

                # Forward pass
                outputs = model(data)

                # Get predictions from the maximum value
                _, predicted = torch.max(outputs.data, 1)

                # Statistics
                total += target.size(0)
                correct += (predicted == target).sum().item()

        accuracy = (correct / total) * 100
        return accuracy

    def is_better_score(self, new_weights_path: str) -> bool:
        """target_score: true if higher means better, false if lower means better."""
        is_verified = False
        # Load model new weights.
        model_weights = self.load_weights(new_weights_path)
        print("Loaded weights")
        model_obj = self.load_model_obj()
        print("Load model object")
        model_obj.load_state_dict(model_weights)
        data_loader = self.load_data(self.metadata.dataset_path)
        # Run against the dataset.
        test_acc = self.test_model(data_loader, model_obj)
        # Compare with old score.
        is_verified = self.metadata.best_score > test_acc
        return is_verified


model = TestStaticModel(
    MetadataConfig.parse_file(os.path.join(METADATA_PATH, "my_model_slerp.json"))
)

model.save_model_static()


loaded_model: IStateVerifierModel = IStateVerifierModel.load_model_static(
    os.path.join(STATIC_MODULES_PATH, "my_model_slerp.dill")
)

print(
    f"Is better score: {loaded_model.is_better_score("saved_models/model_1_weights.pth")}"
)
