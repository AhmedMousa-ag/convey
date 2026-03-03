import pytest
import asyncio
from unittest.mock import Mock, patch
from models.fallback import FallbackMessages, FileMsg, StringMsg
from controllers.networking.messages_fallback import (
    FallbacksManager,
    fall_back_messages,
)


@pytest.fixture
def fallback_manager():
    """Fixture to provide a fresh FallbacksManager instance and reset state."""

    # Clear the singleton instance
    if hasattr(FallbacksManager, "inst"):
        delattr(FallbacksManager, "inst")
    manager = FallbacksManager()
    manager.fall_back_messages = fall_back_messages
    yield manager
    # Cleanup
    if hasattr(FallbacksManager, "inst"):
        delattr(FallbacksManager, "inst")


class TestFallbacksManager:
    """Unit tests for FallbacksManager class."""

    def test_singleton_pattern(self):
        """Test that FallbacksManager follows singleton pattern."""

        if hasattr(FallbacksManager, "inst"):
            delattr(FallbacksManager, "inst")

        manager1 = FallbacksManager()
        manager2 = FallbacksManager()
        assert manager1 is manager2

    def test_register_msg(self, fallback_manager):
        """Test registering a string message."""
        hashed_metadata = "test_hash_1"
        msg = "test message"

        fallback_manager.register_msg(hashed_metadata, msg)

        assert hashed_metadata in fallback_manager.fall_back_messages.messages
        assert len(fallback_manager.fall_back_messages.messages[hashed_metadata]) == 1
        assert isinstance(
            fallback_manager.fall_back_messages.messages[hashed_metadata][0], StringMsg
        )
        assert (
            fallback_manager.fall_back_messages.messages[hashed_metadata][0].msg == msg
        )

    def test_get_pending_messages(self, fallback_manager):
        """Test retrieving pending messages."""
        fallback_manager.register_msg("hash1", "msg1")
        fallback_manager.register_msg("hash2", "msg2")

        pending = fallback_manager.get_pending_messages()

        assert isinstance(pending, FallbackMessages)
        assert len(pending.messages) == 3

    def test_remove_fallback_message_string_msg(self, fallback_manager):
        """Test removing a string message."""
        hashed_metadata = "test_hash"
        msg = StringMsg(msg="test")
        fallback_manager.fall_back_messages.messages[hashed_metadata] = [msg]

        fallback_manager.remove_fallback_message(hashed_metadata, msg)

        assert hashed_metadata not in fallback_manager.fall_back_messages.messages
