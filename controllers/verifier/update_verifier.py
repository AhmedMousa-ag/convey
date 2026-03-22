from controllers.networking.pool import (
    add_latest_updates,
    add_latest_ip_updated_models,
    get_latest_ip_updated_models,
    get_connection_p2p_pool,
)
from datetime import datetime
import os
import shutil
from configs.paths import MODELS_DIR
from configs.metadata import MetadataConfig
from configs.config import DATEIME_FORMAT
from controllers.ml.interface.model import IStateVerifierModel


# Combine all results, once you've a majority, ask one of the connections that has the latest model to sync
class DateVerifier:
    def __init__(self) -> None:
        pass

    # Get only one pool that has the latest model.
    def verify_latest_model(
        self,
        hashed_metadata: str,
        latest_update: datetime,
        peer_address: str,
        peer_has_latest: bool,
    ) -> tuple[bool, None | list[str]]:
        if not peer_has_latest:
            return False, None

        list_of_dates = add_latest_updates(
            hashed_metadata=hashed_metadata, latest_update=latest_update
        )
        add_latest_ip_updated_models(
            hashed_metadata=hashed_metadata, ip=peer_address, date=latest_update
        )
        latest_update_value = max(list_of_dates)
        latest_peers_addr = get_latest_ip_updated_models(hashed_metadata).get(
            latest_update_value, []
        )
        conn_pool = get_connection_p2p_pool(hashed_metadata)
        num_conn = len(conn_pool)
        majority_threshold = (num_conn // 2) + 1 if num_conn > 0 else 1
        num_latest = len(latest_peers_addr)

        if num_latest >= majority_threshold:
            return (True, latest_peers_addr)
        return False, None


class ModelVerifier:
    def __init__(self, metadata: MetadataConfig) -> None:
        self.metadata: MetadataConfig = metadata

    def is_better_model(self, new_weights_path: str) -> bool:
        # If there's no weights, then accept the new model without verification since there's nothing to compare against.
        # Check if the file exists or not
        if not os.path.exists(self.metadata.weights_path):
            print("No existing weights to verify against. Accepting new model.")
            return True

        temp_weights_path = os.path.join(
            MODELS_DIR, f"temp_{self.metadata.model_name}.pth"
        )
        if os.path.exists(temp_weights_path):
            os.remove(temp_weights_path)

        weights_old_path = self.metadata.weights_path
        static_model_path = (
            self.metadata.static_model_path or self.metadata.create_static_path()
        )

        try:
            shutil.move(new_weights_path, temp_weights_path)
            print(f"\nNew weights file copied to {temp_weights_path}")

            self.metadata.weights_path = temp_weights_path

            if not os.path.exists(static_model_path):
                print(
                    "\nStatic verifier model was not found. "
                    f"Expected at: {static_model_path}. Update cancelled."
                )
                return False

            loaded_model: IStateVerifierModel = IStateVerifierModel.load_model_static(
                static_model_path
            )
            loaded_model.metadata = self.metadata

            try:
                verification_result = loaded_model.is_better_score()
            except TypeError:
                verification_result = loaded_model.is_better_score(temp_weights_path)

            if isinstance(verification_result, tuple):
                is_better, new_score = verification_result
            else:
                is_better = bool(verification_result)
                new_score = self.metadata.best_score

            if not is_better:
                print("\nThe new model does not have a better score. Update cancelled.")
                return False

            print(f"Model new weight is better score: {is_better}")
            self.metadata.latest_updated = datetime.now().strftime(DATEIME_FORMAT)
            self.metadata.best_score = new_score
            self.metadata.weights_path = weights_old_path
            shutil.move(temp_weights_path, weights_old_path)
            self.metadata.save()
            loaded_model.metadata = self.metadata
            return True
        finally:
            self.metadata.weights_path = weights_old_path
            if os.path.exists(temp_weights_path):
                os.remove(temp_weights_path)
