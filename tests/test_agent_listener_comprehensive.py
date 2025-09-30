"""Comprehensive tests for AgentListener class"""

import pytest
from unittest.mock import MagicMock, patch
import json
from houseagent.agent_listener import AgentListener


class TestAgentListenerComprehensive:
    """Comprehensive test suite for AgentListener"""

    @patch("houseagent.agent_listener.HouseBot")
    def test_initialization_with_client(self, mock_house_bot):
        """Test AgentListener initializes with MQTT client"""
        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        assert listener.client == mock_client
        assert not listener.stopped
        assert listener.last_batch_messages is None
        assert listener.house_bot is not None

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message_with_valid_json(self, mock_house_bot):
        """Test processing valid JSON message"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "AI Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        msg = MagicMock()
        msg.payload = json.dumps({"sensor": "temperature", "value": 72}).encode()

        listener.on_message(mock_client, None, msg)

        mock_house_bot_instance.generate_response.assert_called_once()
        mock_client.publish.assert_called_once()

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message_with_invalid_json(self, mock_house_bot):
        """Test handling of invalid JSON in message"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        msg = MagicMock()
        msg.payload = b"invalid json {"

        listener.on_message(mock_client, None, msg)

        # Should not call generate_response or publish on invalid JSON
        mock_house_bot_instance.generate_response.assert_not_called()
        mock_client.publish.assert_not_called()

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message_preserves_last_batch(self, mock_house_bot):
        """Test that last_batch_messages is updated correctly"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        msg1 = MagicMock()
        msg1.payload = json.dumps({"message": "first"}).encode()

        listener.on_message(mock_client, None, msg1)

        assert listener.last_batch_messages is not None
        first_batch = listener.last_batch_messages

        msg2 = MagicMock()
        msg2.payload = json.dumps({"message": "second"}).encode()

        listener.on_message(mock_client, None, msg2)

        # Verify second call received first batch as last_state
        calls = mock_house_bot_instance.generate_response.call_args_list
        assert calls[1][0][1] == first_batch

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message_publishes_to_correct_topic(self, mock_house_bot, monkeypatch):
        """Test message is published to configured topic"""
        monkeypatch.setenv("NOTIFICATION_TOPIC", "test/notification/topic")

        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "AI Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        msg = MagicMock()
        msg.payload = json.dumps({"test": "data"}).encode()

        listener.on_message(mock_client, None, msg)

        mock_client.publish.assert_called_once_with(
            "test/notification/topic", "AI Response"
        )

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message_with_empty_payload(self, mock_house_bot):
        """Test handling of empty message payload"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        msg = MagicMock()
        msg.payload = b""

        listener.on_message(mock_client, None, msg)

        mock_house_bot_instance.generate_response.assert_not_called()
        mock_client.publish.assert_not_called()

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message_with_complex_nested_json(self, mock_house_bot):
        """Test processing complex nested JSON structures"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        complex_data = {
            "sensors": [
                {
                    "id": 1,
                    "type": "temperature",
                    "value": 72,
                    "metadata": {"unit": "F"},
                },
                {"id": 2, "type": "humidity", "value": 45, "metadata": {"unit": "%"}},
            ],
            "timestamp": "2024-01-01T00:00:00Z",
        }

        msg = MagicMock()
        msg.payload = json.dumps(complex_data).encode()

        listener.on_message(mock_client, None, msg)

        mock_house_bot_instance.generate_response.assert_called_once()
        call_args = mock_house_bot_instance.generate_response.call_args
        first_arg = json.loads(call_args[0][0])
        assert "messages" in first_arg
        assert first_arg["messages"] == complex_data

    @patch("houseagent.agent_listener.HouseBot")
    def test_stop_sets_flag(self, mock_house_bot):
        """Test stop() sets stopped flag"""
        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        assert not listener.stopped
        listener.stop()
        assert listener.stopped

    @patch("houseagent.agent_listener.HouseBot")
    def test_multiple_messages_sequence(self, mock_house_bot):
        """Test processing multiple messages in sequence"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        # Send 5 messages
        for i in range(5):
            msg = MagicMock()
            msg.payload = json.dumps({"message_num": i}).encode()
            listener.on_message(mock_client, None, msg)

        assert mock_house_bot_instance.generate_response.call_count == 5
        assert mock_client.publish.call_count == 5

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message_with_unicode(self, mock_house_bot):
        """Test handling messages with unicode characters"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        msg = MagicMock()
        msg.payload = json.dumps({"text": "Hello 世界 🌍"}).encode("utf-8")

        listener.on_message(mock_client, None, msg)

        mock_house_bot_instance.generate_response.assert_called_once()

    @patch("houseagent.agent_listener.HouseBot")
    def test_house_bot_exception_handling(self, mock_house_bot):
        """Test handling when HouseBot raises exception"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.side_effect = Exception("API Error")

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        msg = MagicMock()
        msg.payload = json.dumps({"test": "data"}).encode()

        # Should raise exception (not caught in current implementation)
        with pytest.raises(Exception):
            listener.on_message(mock_client, None, msg)
