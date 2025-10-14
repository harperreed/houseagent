import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
from houseagent.house_bot import HouseBot


class TestHouseBot(unittest.TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="test content")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def setUp(self, mock_floor_plan, mock_openai, mock_file):
        # Mock the file reads for prompts
        mock_file.return_value.read.side_effect = [
            "System prompt: {default_state}",
            "Human prompt: {current_state} {last_state}",
            '{"default": "state"}',
        ]
        self.house_bot = HouseBot()

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_initialization(self, mock_floor_plan, mock_openai, mock_file):
        mock_file.return_value.read.side_effect = ["sys", "human", "{}"]
        bot = HouseBot()
        self.assertIsNotNone(bot.logger)
        self.assertIsNotNone(bot.system_prompt_template)
        self.assertIsNotNone(bot.human_prompt_template)
        self.assertIsNotNone(bot.client)

    def test_strip_emojis(self):
        text_with_emojis = "Hello 👋 World 🌍!"
        stripped_text = self.house_bot.strip_emojis(text_with_emojis)
        self.assertEqual(stripped_text, "Hello  World !")

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_generate_response(self, mock_floor_plan, mock_openai, mock_file):
        # Setup mocks
        mock_file.return_value.read.side_effect = [
            "System: {default_state}",
            "Human: {current_state} {last_state}",
            '{"test": "data"}',
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Mocked response"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()

        current_state = json.dumps({"messages": [{"text": "Hello"}]})
        last_state = json.dumps({"messages": [{"text": "Previous message"}]})

        response = bot.generate_response(current_state, last_state)

        self.assertEqual(response, "Mocked response")
        mock_client.chat.completions.create.assert_called_once()

        # Verify the call was made with correct structure
        call_args = mock_client.chat.completions.create.call_args
        self.assertIn("messages", call_args[1])
        self.assertEqual(len(call_args[1]["messages"]), 2)
        self.assertEqual(call_args[1]["messages"][0]["role"], "system")
        self.assertEqual(call_args[1]["messages"][1]["role"], "user")


if __name__ == "__main__":
    unittest.main()
