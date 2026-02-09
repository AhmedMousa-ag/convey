from controllers.networking.pool import (
    add_latest_updates,
    add_latest_ip_updated_models,
    get_latest_ip_updated_models,
    get_connection_p2p_pool,
)
from datetime import datetime
import os
import shutil
from configs.paths import MODELS_DIR, STATIC_MODULES_PATH
from configs.metadata import MetadataConfig
from configs.config import DATEIME_FORMAT
from controllers.ml.interface.model import IStateVerifierModel


# Combine all results, once you've a majority, ask one of the connections that has the latest model to sync
class DateVerifier:
    def __init__(self) -> None:
        pass

    # Get only one pool that has the latest model.
    def verify_latest_model(
        self, hashed_metadata: str, latest_update: datetime, peer_address: str
    ) -> tuple[bool, None | list[str]]:
        list_of_dates = add_latest_updates(
            hashed_metadata=hashed_metadata, latest_update=latest_update
        )
        add_latest_ip_updated_models(
            hashed_metadata=hashed_metadata, ip=peer_address, date=latest_update
        )
        latest_update_value = max(list_of_dates)
        conn_pool = get_connection_p2p_pool(hashed_metadata)
        num_conn = len(conn_pool)
        num_half_conn = int(num_conn / 2) or 1  # If it's 0 return 1
        num_list_if_date = len(list_of_dates)
        num_latest = 0  # TODO you might need to start at one since you're assuming the current device holds the latest model weight.
        for update in list_of_dates:
            if latest_update == update:
                num_latest += 1
        latest_peers_addr = get_latest_ip_updated_models(hashed_metadata)[
            latest_update_value
        ]
        # Wait until you get all the responses
        if (num_latest < num_half_conn) and (num_conn == num_list_if_date):
            # Ask for SYNC
            return (True, latest_peers_addr)
        return False, None


class ModelVerifier:
    def __init__(self, metadata: MetadataConfig) -> None:
        self.metadata: MetadataConfig = metadata

    def is_better_model(self, new_weights_path: str) -> bool:

        # Move the new weights file to the a temporary location in the models directory.
        temp_weights_path = os.path.join(
            MODELS_DIR, f"temp_{self.metadata.model_name}.pth"
        )
        shutil.move(new_weights_path, temp_weights_path)
        print(f"\nNew weights file copied to {temp_weights_path}")
        # Update the metadata to point to the new weights file.
        weights_old_path = self.metadata.weights_path
        self.metadata.weights_path = temp_weights_path
        #  Verify the new model before sending it to others.
        loaded_model: IStateVerifierModel = IStateVerifierModel.load_model_static(
            os.path.join(STATIC_MODULES_PATH, "my_model_slerp.dill")
        )
        loaded_model.metadata = self.metadata
        is_better, new_score = loaded_model.is_better_score()
        if not is_better:
            print("\nThe new model does not have a better score. Update cancelled.")
            os.remove(temp_weights_path)
            input("\nPress Enter to continue...")
            return False

        print(f"Model new weight is better score: {is_better}")
        # Update the metadata file with the new weights path and latest update time.
        self.metadata.latest_updated = datetime.now().strftime(DATEIME_FORMAT)
        self.metadata.best_score = new_score
        self.metadata.weights_path = weights_old_path
        shutil.move(temp_weights_path, weights_old_path)
        self.metadata.save()
        loaded_model.metadata = self.metadata
        return True
