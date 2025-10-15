# ABOUTME: Tests for should_respond filter that gates AI responses
# ABOUTME: Validates GPT-5-mini decision making for notification filtering

import json
import unittest
from unittest.mock import Mock, patch
from houseagent.house_bot import HouseBot


class TestShouldRespondFilter(unittest.TestCase):
    """Tests for should_respond filter using GPT-5-mini"""

    @patch("houseagent.house_bot.OpenAI")
    def test_should_respond_returns_true_for_interesting_situation(self, mock_openai):
        """Filter should return True for multi-sensor interesting events"""
        # Mock OpenAI client to return should_respond=True
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "should_respond": True,
                            "reason": "Multiple sensors in same zone is interesting",
                        }
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        bot = HouseBot()
        situation = json.dumps(
            {
                "zones": ["hack_area"],
                "event_counts": {"motion": 2, "temperature": 1},
                "message_count": 3,
            }
        )

        result = bot.should_respond(situation)

        self.assertTrue(result)
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args[1]["response_format"], {"type": "json_object"})

    @patch("houseagent.house_bot.OpenAI")
    def test_should_respond_returns_false_for_boring_situation(self, mock_openai):
        """Filter should return False for single routine sensor reading"""
        # Mock OpenAI client to return should_respond=False
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps(
                        {
                            "should_respond": False,
                            "reason": "Single routine temperature reading",
                        }
                    )
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        bot = HouseBot()
        situation = json.dumps(
            {
                "zones": ["hack_area"],
                "event_counts": {"temperature": 1},
                "message_count": 1,
            }
        )

        result = bot.should_respond(situation)

        self.assertFalse(result)

    @patch("houseagent.house_bot.OpenAI")
    def test_should_respond_handles_api_error_gracefully(self, mock_openai):
        """Filter should default to True if API call fails"""
        # Mock OpenAI client to raise exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_openai.return_value = mock_client

        bot = HouseBot()
        situation = json.dumps({"zones": ["hack_area"], "message_count": 1})

        result = bot.should_respond(situation)

        # Should fail open (default to True)
        self.assertTrue(result)

    @patch("houseagent.house_bot.OpenAI")
    def test_should_respond_handles_malformed_json(self, mock_openai):
        """Filter should default to True if response JSON is malformed"""
        # Mock OpenAI client to return invalid JSON
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="not valid json"))]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        bot = HouseBot()
        situation = json.dumps({"zones": ["hack_area"]})

        result = bot.should_respond(situation)

        # Should fail open (default to True)
        self.assertTrue(result)

    @patch("houseagent.house_bot.OpenAI")
    def test_should_respond_uses_classifier_model(self, mock_openai):
        """Filter should use classifier model (gpt-5-mini) not synthesis model"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [
            Mock(
                message=Mock(
                    content=json.dumps({"should_respond": True, "reason": "test"})
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        bot = HouseBot()
        situation = json.dumps({"zones": ["hack_area"]})

        bot.should_respond(situation)

        call_args = mock_client.chat.completions.create.call_args
        # Should use classifier_model (gpt-5-mini)
        self.assertEqual(call_args[1]["model"], bot.classifier_model)

    @patch("houseagent.house_bot.OpenAI")
    def test_should_respond_without_prompt_file(self, mock_openai):
        """Filter should default to True if prompt file is missing"""
        mock_client = Mock()
        mock_openai.return_value = mock_client

        # Temporarily break the prompt file path
        with patch.dict("os.environ", {"SHOULD_RESPOND_PROMPT": "/nonexistent/path"}):
            bot = HouseBot()
            situation = json.dumps({"zones": ["hack_area"]})

            result = bot.should_respond(situation)

            # Should fail open (default to True)
            self.assertTrue(result)
            # Should NOT call OpenAI if no prompt
            mock_client.chat.completions.create.assert_not_called()
