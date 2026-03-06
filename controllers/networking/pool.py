from models.server import ClientsIPAddresses
from socket import socket
from typing import List, Dict
from datetime import datetime

# hashed_metadata -> client IP address.
connection_pool: Dict[str, List[str]] = {}

# hashed metadata -> actual socket connection.
p2p_socket_peer_conn: Dict[str, socket] = {}


verification_pool: Dict[str, Dict[str, List[datetime]]] = {}
# hashed_metadata - > list of ips addressed that has the latest models.
updated_models_ips_pool: Dict[str, Dict[datetime, List[str]]] = {}


def add_latest_ip_updated_models(hashed_metadata: str, ip: str, date: datetime):
    updated_models_ips_pool.setdefault(hashed_metadata, {date: []})[date].append(ip)
    print("Updated latest ip ")


def remove_latest_ip_updated_models(hashed_metadata: str, ip: str):
    pool = updated_models_ips_pool.get(hashed_metadata)
    if pool is None:
        return
    for _, date_ips in pool.items():
        if ip in date_ips:
            date_ips.remove(ip)


def get_latest_ip_updated_models(hashed_metadata: str) -> Dict[datetime, List[str]]:
    return updated_models_ips_pool.setdefault(hashed_metadata, {})


def add_latest_updates(hashed_metadata: str, latest_update: datetime) -> List[datetime]:
    hashed_pool = verification_pool.get(hashed_metadata)
    if hashed_pool is None:
        latest_update_list = [latest_update]
        verification_pool[hashed_metadata] = {"latest_updates": latest_update_list}
        return latest_update_list
    hashed_pool["latest_updates"].append(latest_update)
    return hashed_pool["latest_updates"]


def get_latest_updates(hashed_metadata: str) -> List[datetime]:
    latest_update = verification_pool.get(hashed_metadata)
    if latest_update is None:
        return []
    return latest_update["latest_updates"]


def update_connection_p2p_pool(client_ip_address: ClientsIPAddresses, peer_conn):
    metadata_pool_list = connection_pool.get(client_ip_address.hashed_metadata)
    if not metadata_pool_list:
        metadata_pool_list = []
    if not client_ip_address.is_adding and len(metadata_pool_list) < 1:
        return
    ip = client_ip_address.ip
    match client_ip_address.is_adding:
        case True:
            metadata_pool_list.append(ip)
            if not p2p_socket_peer_conn.get(ip):

                p2p_socket_peer_conn[ip] = peer_conn
        case False:
            if ip in metadata_pool_list:
                metadata_pool_list.remove(ip)
                p2p_socket_peer_conn.pop(ip)
                remove_latest_ip_updated_models(client_ip_address.hashed_metadata, ip)
    connection_pool[client_ip_address.hashed_metadata] = metadata_pool_list


def remove_connection_p2p_pool(hashed_metadata: str, ip: str):
    pool = connection_pool.get(hashed_metadata)
    if not pool:
        return
    if ip in pool:
        pool.remove(ip)


def add_connection_p2p_pool(hashed_metadata: str, ip: str):
    pool = connection_pool.get(hashed_metadata)
    if not pool:
        pool = []
    pool.append(ip)


def get_connection_p2p_pool(hashed_metadata: str) -> List[str]:
    pool = connection_pool.get(hashed_metadata)
    if not pool:
        pool = []
    return pool


def get_socket_connection(ip: str) -> socket | None:
    return p2p_socket_peer_conn.get(ip)
