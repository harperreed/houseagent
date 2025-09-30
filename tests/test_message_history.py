"""Tests for message history feature in AgentListener and HouseBot"""

from unittest.mock import MagicMock, patch
import json
from houseagent.agent_listener import AgentListener
from houseagent.house_bot import HouseBot


class TestMessageHistory:
    """Test suite for message history functionality"""

    @patch("houseagent.agent_listener.HouseBot")
    def test_agent_listener_initializes_with_history_size(self, mock_house_bot):
        """Test AgentListener initializes with configurable history size"""
        mock_client = MagicMock()
        listener = AgentListener(mock_client, history_size=20)

        assert listener.history_size == 20
        assert len(listener.message_history) == 0
        assert listener.message_history.maxlen == 20

    @patch("houseagent.agent_listener.HouseBot")
    def test_agent_listener_default_history_size(self, mock_house_bot):
        """Test AgentListener uses default history size of 10"""
        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        assert listener.history_size == 10
        assert listener.message_history.maxlen == 10

    @patch("houseagent.agent_listener.HouseBot")
    def test_message_history_accumulates(self, mock_house_bot):
        """Test message history accumulates user messages and responses"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Response 1"

        mock_client = MagicMock()
        listener = AgentListener(mock_client, history_size=10)

        msg = MagicMock()
        msg.payload = json.dumps({"sensor": "temp", "value": 22}).encode()

        listener.on_message(mock_client, None, msg)

        # Should have 2 entries: user message + assistant response
        assert len(listener.message_history) == 2
        assert listener.message_history[0]["role"] == "user"
        assert listener.message_history[1]["role"] == "assistant"
        assert listener.message_history[1]["content"] == "Response 1"

    @patch("houseagent.agent_listener.HouseBot")
    def test_message_history_passed_to_house_bot(self, mock_house_bot):
        """Test message history is passed to HouseBot.generate_response"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client, history_size=10)

        msg = MagicMock()
        msg.payload = json.dumps({"test": "data"}).encode()

        listener.on_message(mock_client, None, msg)

        # Verify generate_response was called with history
        call_args = mock_house_bot_instance.generate_response.call_args
        assert len(call_args[0]) == 3  # current_state, last_state, message_history
        message_history = call_args[0][2]
        assert isinstance(message_history, list)
        assert len(message_history) == 1  # Just the current user message
        assert message_history[0]["role"] == "user"

    @patch("houseagent.agent_listener.HouseBot")
    def test_message_history_rolling_window(self, mock_house_bot):
        """Test message history maintains rolling window (oldest dropped)"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client, history_size=4)  # Small window

        # Send 3 messages (will create 6 entries: 3 user + 3 assistant)
        for i in range(3):
            msg = MagicMock()
            msg.payload = json.dumps({"message": i}).encode()
            listener.on_message(mock_client, None, msg)

        # Should only keep last 4 entries (maxlen=4)
        assert len(listener.message_history) == 4
        # Should have dropped first 2 entries (message 0 user + assistant)
        # Verify we have a mix of user and assistant messages
        roles = [entry["role"] for entry in listener.message_history]
        assert "user" in roles
        assert "assistant" in roles

    @patch("houseagent.agent_listener.HouseBot")
    def test_multiple_messages_build_context(self, mock_house_bot):
        """Test multiple messages build up conversational context"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.side_effect = [
            "First response",
            "Second response",
        ]

        mock_client = MagicMock()
        listener = AgentListener(mock_client, history_size=10)

        # First message
        msg1 = MagicMock()
        msg1.payload = json.dumps({"message": "first"}).encode()
        listener.on_message(mock_client, None, msg1)

        # Second message
        msg2 = MagicMock()
        msg2.payload = json.dumps({"message": "second"}).encode()
        listener.on_message(mock_client, None, msg2)

        # Second call should have 3 history entries (user1, assistant1, user2)
        second_call_args = mock_house_bot_instance.generate_response.call_args_list[1]
        message_history = second_call_args[0][2]
        assert len(message_history) == 3
        assert message_history[0]["role"] == "user"
        assert message_history[1]["role"] == "assistant"
        assert message_history[1]["content"] == "First response"
        assert message_history[2]["role"] == "user"

    @patch("builtins.open", new_callable=MagicMock)
    @patch("houseagent.house_bot.OpenAI")
    def test_house_bot_uses_message_history(self, mock_openai, mock_file):
        """Test HouseBot uses message history when provided"""
        mock_file.return_value.__enter__.return_value.read.side_effect = [
            "System: {default_state}",
            "Human: {current_state} {last_state}",
            "{}",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "AI Response"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()

        # Call with message history
        message_history = [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
            {"role": "user", "content": "Current message"},
        ]

        bot.generate_response("{}", None, message_history)

        # Verify OpenAI was called with history
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]

        # Should have: system + 3 history messages
        assert len(messages) == 4
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Previous message"
        assert messages[2]["role"] == "assistant"
        assert messages[2]["content"] == "Previous response"
        assert messages[3]["role"] == "user"
        assert messages[3]["content"] == "Current message"

    @patch("builtins.open", new_callable=MagicMock)
    @patch("houseagent.house_bot.OpenAI")
    def test_house_bot_fallback_without_history(self, mock_openai, mock_file):
        """Test HouseBot falls back to old behavior without message history"""
        mock_file.return_value.__enter__.return_value.read.side_effect = [
            "System: {default_state}",
            "Human: {current_state} {last_state}",
            "{}",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "AI Response"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()

        # Call WITHOUT message history (old behavior)
        bot.generate_response('{"current": "state"}', '{"last": "state"}')

        # Verify OpenAI was called with old format
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]

        # Should have: system + single user message (formatted prompt)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "current" in messages[1]["content"]
        assert "last" in messages[1]["content"]
