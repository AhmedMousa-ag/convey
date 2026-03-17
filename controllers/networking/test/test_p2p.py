import io
import os
import zipfile
import unittest
from unittest.mock import MagicMock, patch, mock_open
from controllers.networking.p2p import P2PNode, TransferPathManager
from configs.paths import ZIPPED_DIRE


def make_node() -> "P2PNode":  # noqa: F821
    """Return a fresh P2PNode, bypassing the singleton for testing."""

    # Delete cached instance so __new__ creates a fresh one
    if hasattr(P2PNode, "inst"):
        del P2PNode.inst
    node = P2PNode.__new__(P2PNode)
    # Manually init without binding a real socket
    node._initialized = True
    node.host = "127.0.0.1"
    node.port = 5000
    node.peers = set()
    node.server = MagicMock()
    node.serializer = MagicMock()
    node.path_manager = TransferPathManager(ZIPPED_DIRE)
    node.metadata_secrets = {}
    return node


class FakeSocket:
    """Minimal socket fake that reads from a pre-loaded BytesIO buffer."""

    def __init__(self, data: bytes = b""):
        self._buf = io.BytesIO(data)
        self.sent = bytearray()

    def recv(self, n: int) -> bytes:
        return self._buf.read(n)

    def sendall(self, data: bytes):
        self.sent.extend(data)

    def close(self):
        pass


def framed(payload: bytes) -> bytes:
    """Prepend a 4-byte big-endian length prefix."""
    return len(payload).to_bytes(4, "big") + payload


# ============================================================
# Tests
# ============================================================


class TestSingleton(unittest.TestCase):
    def test_singleton_returns_same_instance(self):
        if hasattr(P2PNode, "inst"):
            del P2PNode.inst
        with patch("socket.socket"):
            a = P2PNode()
            b = P2PNode()
        self.assertIs(a, b)


class TestUpdateSecret(unittest.TestCase):
    def setUp(self):
        self.node = make_node()

    def test_stores_secret(self):
        self.node.update_secret("hash123", "mysecret")
        self.assertEqual(self.node.metadata_secrets["hash123"], "mysecret")

    def test_overwrites_existing_secret(self):
        self.node.update_secret("hash123", "old")
        self.node.update_secret("hash123", "new")
        self.assertEqual(self.node.metadata_secrets["hash123"], "new")


class TestVerifySecretKey(unittest.TestCase):
    def setUp(self):
        self.node = make_node()

    def _make_auth_message(self, hashed_metadata: str, secret_key: str) -> bytes:
        import json

        payload = json.dumps(
            {"hashed_metadata": hashed_metadata, "secret_key": secret_key}
        ).encode()
        return framed(payload)

    def test_returns_true_for_valid_secret(self):
        self.node.metadata_secrets["myhash"] = "correct_secret"

        # Build a fake AuthenticationMessage
        auth_obj = MagicMock()
        auth_obj.secret_key = "correct_secret"
        auth_obj.hashed_metadata = "myhash"

        sock = FakeSocket(b"\x00" * 100)  # dummy bytes (recv_framed mocked)

        with patch.object(self.node, "recv_framed", return_value=b"{}"):
            with patch(
                "models.clients.AuthenticationMessage.model_validate_json",
                return_value=auth_obj,
            ):
                result = self.node._verify_secret_key(sock)

        self.assertEqual(result, (True, "myhash"))

    def test_returns_false_for_wrong_secret(self):
        self.node.metadata_secrets["myhash"] = "correct_secret"

        auth_obj = MagicMock()
        auth_obj.secret_key = "wrong_secret"
        auth_obj.hashed_metadata = "myhash"

        sock = MagicMock()

        with patch.object(self.node, "recv_framed", return_value=b"{}"):
            with patch(
                "models.clients.AuthenticationMessage.model_validate_json",
                return_value=auth_obj,
            ):
                result = self.node._verify_secret_key(sock)

        self.assertEqual(result, (False, "myhash"))

    def test_returns_false_on_exception(self):
        sock = MagicMock()
        with patch.object(
            self.node, "recv_framed", side_effect=ConnectionError("boom")
        ):
            result = self.node._verify_secret_key(sock)
        self.assertEqual(result, (False, ""))

    def test_returns_false_for_unknown_hash(self):
        auth_obj = MagicMock()
        auth_obj.secret_key = "any_secret"
        auth_obj.hashed_metadata = "unknown_hash"

        sock = MagicMock()
        with patch.object(self.node, "recv_framed", return_value=b"{}"):
            with patch(
                "models.clients.AuthenticationMessage.model_validate_json",
                return_value=auth_obj,
            ):
                result = self.node._verify_secret_key(sock)

        self.assertEqual(result, (False, "unknown_hash"))


class TestCloseConn(unittest.TestCase):
    def setUp(self):
        self.node = make_node()

    def test_closes_socket_and_removes_peer(self):
        addr = ("127.0.0.1", 9999)
        self.node.peers.add(addr)
        conn = MagicMock()
        self.node.close_conn(conn, addr)
        conn.close.assert_called_once()
        self.assertNotIn(addr, self.node.peers)

    def test_does_not_raise_if_peer_not_in_set(self):
        conn = MagicMock()
        addr = ("10.0.0.1", 1234)
        # addr not in peers — should not raise
        self.node.close_conn(conn, addr)
        conn.close.assert_called_once()


class TestSendMessage(unittest.TestCase):
    def setUp(self):
        self.node = make_node()
        self.node.metadata_secrets["myhash"] = "secret"

    def test_sends_text_header_and_framed_payload(self):
        sock = MagicMock()
        with patch.object(self.node, "_send_secret_key") as mock_auth:
            with patch.object(self.node, "send_framed") as mock_framed:
                self.node.send_message(sock, "hello", "myhash")

        mock_auth.assert_called_once_with(sock, "myhash")
        # Header must be exactly 10 bytes
        header_call = sock.sendall.call_args_list[0]
        self.assertEqual(len(header_call[0][0]), 10)
        self.assertTrue(header_call[0][0].startswith(b"TEXT"))
        mock_framed.assert_called_once_with(sock, b"hello")


class TestSendFile(unittest.TestCase):
    def setUp(self):
        self.node = make_node()
        self.node.metadata_secrets["myhash"] = "secret"

    def test_returns_false_for_missing_file(self):
        sock = MagicMock()
        result = self.node.send_file(sock, "/nonexistent/file.zip", "myhash")
        self.assertFalse(result)

    def test_raises_for_invalid_file_type(self):
        sock = MagicMock()
        with patch("os.path.exists", return_value=True):
            with self.assertRaises(ValueError):
                self.node.send_file(
                    sock, "/fake/file.zip", "myhash", file_type="BADTYPE"
                )

    def test_sends_file_and_returns_true_on_ack(self):
        fake_data = b"fake zip content"
        sock = MagicMock()

        with patch("os.path.exists", return_value=True), patch.object(
            self.node.path_manager,
            "prepare_transfer_file",
            return_value=("/fake/model.zip", "model.zip"),
        ), patch("os.path.getsize", return_value=len(fake_data)), patch(
            "builtins.open", mock_open(read_data=fake_data)
        ), patch.object(
            self.node, "recv_exact", return_value=b"ACK"
        ):
            result = self.node.send_file(
                sock, "/fake/model.zip", "myhash", file_type="MODEL"
            )

        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
