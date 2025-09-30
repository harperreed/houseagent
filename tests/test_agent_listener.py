import unittest
from unittest.mock import patch, MagicMock
import json
from houseagent.agent_listener import AgentListener


class TestAgentListener(unittest.TestCase):
    @patch('houseagent.agent_listener.HouseBot')
    def setUp(self, mock_house_bot):
        self.mock_client = MagicMock()
        self.agent_listener = AgentListener(self.mock_client)

    @patch('houseagent.agent_listener.HouseBot')
    def test_initialization(self, mock_house_bot):
        agent_listener = AgentListener(self.mock_client)
        self.assertIsNotNone(agent_listener.logger)
        self.assertFalse(agent_listener.stopped)
        self.assertEqual(agent_listener.client, self.mock_client)
        self.assertIsNotNone(agent_listener.house_bot)
        self.assertIsNone(agent_listener.last_batch_messages)

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message(self, mock_house_bot):
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Mocked response"

        agent_listener = AgentListener(self.mock_client)

        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"text": "Test message"})

        agent_listener.on_message(self.mock_client, None, mock_msg)

        mock_house_bot_instance.generate_response.assert_called_once()
        self.mock_client.publish.assert_called_once()

    @patch('houseagent.agent_listener.HouseBot')
    def test_stop(self, mock_house_bot):
        agent_listener = AgentListener(self.mock_client)
        self.assertFalse(agent_listener.stopped)
        agent_listener.stop()
        self.assertTrue(agent_listener.stopped)


if __name__ == "__main__":
    unittest.main()
