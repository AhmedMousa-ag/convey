from configs.metadata import MetadataConfig
from typing import Dict
from models.clients import P2PMessagesTypes
from controllers.networking.req_rep import Requester, Replier
from models.clients import ResponseIsLatestModel
from controllers.verifier.update_verifier import DateVerifier


class TransmitterManager:
    def __init__(self, hashed_metadata: str, peer_address: str, p2p_node):
        self.metadata: MetadataConfig = MetadataConfig.load_from_hashed_val(
            hashed_metadata
        )
        self.requester = Requester(self.metadata, p2p_node)
        self.replier = Replier(self.metadata, p2p_node)
        # print("WIll store peer address: ", peer_address)
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
                    peer_has_latest=response_model.is_latest,
                )
                if need_verifier and latest_peers_addr is not None:
                    self.requester.ask_sync_model(latest_peers_addr)
            case P2PMessagesTypes.SYNCModel:
                self.replier.reply_sync_model(self.peer_address)
            case P2PMessagesTypes.SYNCModelWeights:
                self.replier.reply_sync_model_weights(self.peer_address)
            case P2PMessagesTypes.SYNCDataset:
                self.replier.reply_sync_dataset(self.peer_address)
            case P2PMessagesTypes.SYNCStaticModules:
                self.replier.reply_sync_static_modules(self.peer_address)
            # case P2PMessagesTypes.UPDATE:
            #     self.requester.update_new_weights()
            case _:
                print(f"Message type {msg_type.value} is not supported.")
        return None
