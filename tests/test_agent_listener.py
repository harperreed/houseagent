import unittest
from unittest.mock import patch, MagicMock
import json
from houseagent.agent_listener import AgentListener


class TestAgentListener(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.agent_listener = AgentListener(self.mock_client)

    def test_initialization(self):
        self.assertIsNotNone(self.agent_listener.logger)
        self.assertFalse(self.agent_listener.stopped)
        self.assertEqual(self.agent_listener.client, self.mock_client)
        self.assertIsNotNone(self.agent_listener.house_bot)
        self.assertIsNone(self.agent_listener.last_batch_messages)

    @patch("houseagent.agent_listener.HouseBot")
    def test_on_message(self, mock_house_bot):
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"text": "Test message"})

        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Mocked response"

        self.agent_listener.on_message(self.mock_client, None, mock_msg)

        mock_house_bot_instance.generate_response.assert_called_once()
        self.mock_client.publish.assert_called_once()

    def test_stop(self):
        self.assertFalse(self.agent_listener.stopped)
        self.agent_listener.stop()
        self.assertTrue(self.agent_listener.stopped)


if __name__ == "__main__":
    unittest.main()
