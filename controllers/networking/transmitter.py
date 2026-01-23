from configs.metadata import MetadataConfig
from typing import Dict
from models.clients import P2PMessagesTypes
from controllers.networking.req_rep import Requester, Replier
from models.clients import ResponseIsLatestModel
from controllers.verifier.update_verifier import DateVerifier

# TODO
# Upon socket connection, ask to see if this client is synced with the recent version or not.
# If doesn't have the recent version, send it to the client.
# Create a button for updating a better version for everyone. The current client verifies it themselves first on the test data, and if success, send it to everyone so that they confirm and replace.


class TransmitterManager:
    def __init__(self, hashed_metadata: str, peer_address: str):
        self.metadata: MetadataConfig = MetadataConfig.load_from_hashed_val(
            hashed_metadata
        )
        self.requester = Requester(self.metadata)
        self.replier = Replier(self.metadata)
        self.peer_address = peer_address

    def reply(self, msg_type: P2PMessagesTypes, msg: Dict) -> str | None:
        match msg_type:
            case P2PMessagesTypes.IsLatest:
                return self.replier.reply_is_latest(msg)
            case P2PMessagesTypes.ResIsLatest:
                response_model = ResponseIsLatestModel(**msg)
                (
                    need_verifier,
                    latest_peers_addr,
                ) = DateVerifier().verify_latest_model(
                    hashed_metadata=self.metadata.hash_self(),
                    latest_update=response_model.last_update,
                    peer_address=self.peer_address,
                )
                if need_verifier and latest_peers_addr is not None:
                    self.requester.ask_sync_model(latest_peers_addr)
            case P2PMessagesTypes.SYNCModel:
                self.replier.reply_sync_model(self.peer_address)
            case P2PMessagesTypes.SYNCDataset:
                self.replier.reply_sync_dataset(self.peer_address)
            # case P2PMessagesTypes.UPDATE:
            #     self.requester.update_new_weights()
            case _:
                print(f"Message type {msg_type.value} is not supported.")
        return None
