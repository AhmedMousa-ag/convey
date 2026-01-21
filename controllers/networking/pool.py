from models.server import ClientsIPAddresses
from controllers.networking.threads import p2p_node
from configs.config import CLIENT_PORT

# hashed_metadata -> client IP address.
connection_pool = {}

# hashed metadata -> actual socket connection.
p2p_socket_peer_conn = {}


def update_connection_p2p_pool(client_ip_address: ClientsIPAddresses):
    metadata_pool_list = connection_pool.get(client_ip_address.hashed_metadata)
    if not metadata_pool_list:
        metadata_pool_list = []
    if not client_ip_address.is_adding and len(metadata_pool_list) < 1:
        return
    match client_ip_address.is_adding:
        case True:
            metadata_pool_list.append(client_ip_address.ip)
            if not p2p_socket_peer_conn.get(client_ip_address.ip):
                peer_conn = p2p_node.connect_to_peer(client_ip_address.ip, CLIENT_PORT)
                p2p_socket_peer_conn[client_ip_address.ip, peer_conn]
        case False:
            metadata_pool_list.remove(client_ip_address.ip)
            p2p_socket_peer_conn.pop(client_ip_address.ip)
    connection_pool[client_ip_address.hashed_metadata] = metadata_pool_list
    print(f"Connection Pool: {connection_pool}")
    print(f"IP Socket: {p2p_socket_peer_conn}")


def remove_connection_p2p_pool(hashed_metadata: str, ip: str):
    pool = connection_pool.get(hashed_metadata)
    if not pool:
        return
    pool.remove(ip)


def add_connection_p2p_pool(hashed_metadata: str, ip: str):
    pool = connection_pool.get(hashed_metadata)
    if not pool:
        pool = []
    pool.append(ip)
