from configs.metadata import MetadataConfig
from controllers.networking.p2p import p2p_node

# TODO
# Upon socket connection, ask to see if this client is synced with the recent version or not.
# If doesn't have the recent version, send it to the client.
# Create a button for updating a better version for everyone. The current client verifies it themselves first on the test data, and if success, send it to everyone so that they confirm and replace.


class TransmitterManager:
    def __init__(self, metadata: MetadataConfig) -> None:
        pass

    def is_latest(self) -> bool:
        is_latest = False
        return is_latest

    def reply_is_latest(self) -> bool:
        is_latest = False
        return is_latest

    def sync_latest_version(self) -> bool:
        """Ask one client only."""
        success = False
        # Verify the new version.
        return success

    def update_others_of_latest_version(self) -> bool:
        success = False
        return success
