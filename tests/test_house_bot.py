import unittest
from unittest.mock import patch, MagicMock
import json
from houseagent.house_bot import HouseBot


class TestHouseBot(unittest.TestCase):
    def setUp(self):
        self.house_bot = HouseBot()

    def test_initialization(self):
        self.assertIsNotNone(self.house_bot.logger)
        self.assertIsNotNone(self.house_bot.system_message_prompt)
        self.assertIsNotNone(self.house_bot.human_message_prompt)
        self.assertIsNotNone(self.house_bot.chat)

    def test_strip_emojis(self):
        text_with_emojis = "Hello 👋 World 🌍!"
        stripped_text = self.house_bot.strip_emojis(text_with_emojis)
        self.assertEqual(stripped_text, "Hello  World !")

    @patch("houseagent.house_bot.ChatOpenAI")
    @patch("houseagent.house_bot.LLMChain")
    def test_generate_response(self, mock_llm_chain, mock_chat_openai):
        mock_chain = MagicMock()
        mock_llm_chain.return_value = mock_chain
        mock_chain.run.return_value = "Mocked response"

        current_state = json.dumps({"messages": [{"text": "Hello"}]})
        last_state = json.dumps({"messages": [{"text": "Previous message"}]})

        response = self.house_bot.generate_response(current_state, last_state)

        self.assertEqual(response, "Mocked response")
        mock_chain.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
