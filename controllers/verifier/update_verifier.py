from controllers.networking.pool import (
    add_latest_updates,
    add_latest_ip_updated_models,
    get_latest_ip_updated_models,
    get_latest_updates,
    get_connection_p2p_pool,
)
from datetime import datetime


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
        num_latest = 0
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
