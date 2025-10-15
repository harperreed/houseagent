"""Comprehensive tests for HouseBot class"""

import pytest
from unittest.mock import patch, MagicMock, mock_open
from houseagent.house_bot import HouseBot


class TestHouseBotComprehensive:
    """Comprehensive test suite for HouseBot"""

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_initialization_with_default_values(
        self, mock_floor_plan, mock_openai, mock_file, monkeypatch
    ):
        """Test HouseBot initializes with default environment values"""
        # Clear any env vars from .env file to test true defaults
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_TEMPERATURE", raising=False)

        mock_file.return_value.read.side_effect = [
            "sys",
            "human",
            "{}",
            "should_respond",
            "camera_vision",
        ]
        bot = HouseBot()

        assert bot.model == "gpt-5"
        assert bot.temperature == 0.0
        assert bot.system_prompt_template == "sys"
        assert bot.human_prompt_template == "human"

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_initialization_with_custom_env_values(
        self, mock_floor_plan, mock_openai, mock_file, monkeypatch
    ):
        """Test HouseBot respects custom environment variables"""
        monkeypatch.setenv("OPENAI_MODEL", "gpt-5-pro")
        monkeypatch.setenv("OPENAI_TEMPERATURE", "0.7")
        monkeypatch.setenv("OPENAI_API_KEY", "custom-key")

        mock_file.return_value.read.side_effect = [
            "sys",
            "human",
            "{}",
            "should_respond",
            "camera_vision",
        ]
        bot = HouseBot()

        assert bot.model == "gpt-5-pro"
        assert bot.temperature == 0.7

    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    @patch("houseagent.house_bot.OpenAI")
    def test_initialization_missing_prompt_files(self, mock_openai, mock_file):
        """Test HouseBot fails gracefully when prompt files are missing"""
        with pytest.raises(FileNotFoundError):
            HouseBot()

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_strip_emojis_removes_all_emojis(
        self, mock_floor_plan, mock_openai, mock_file
    ):
        """Test emoji stripping with various emoji types"""
        mock_file.return_value.read.side_effect = [
            "sys",
            "human",
            "{}",
            "should_respond",
            "camera_vision",
        ]
        bot = HouseBot()

        test_cases = [
            ("Hello 👋 World 🌍!", "Hello  World !"),
            ("🚀🎉🔥", ""),
            ("No emojis here", "No emojis here"),
            ("Mixed 😀 text 🎯 with 💯 emojis", "Mixed  text  with  emojis"),
        ]

        for input_text, expected_output in test_cases:
            assert bot.strip_emojis(input_text) == expected_output

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_generate_response_success(self, mock_floor_plan, mock_openai, mock_file):
        """Test successful response generation"""
        mock_file.return_value.read.side_effect = [
            "System: {default_state}",
            "Human: {current_state} {last_state}",
            '{"test": "data"}',
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test response"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()
        result = bot.generate_response('{"current": "state"}', '{"last": "state"}')

        assert result == "Test response"
        mock_client.chat.completions.create.assert_called_once()

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_generate_response_with_emojis(
        self, mock_floor_plan, mock_openai, mock_file
    ):
        """Test response with emojis gets stripped"""
        mock_file.return_value.read.side_effect = [
            "sys {default_state}",
            "human {current_state} {last_state}",
            "{}",
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Response with 🎉 emojis 🚀"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()
        result = bot.generate_response('{"state": "data"}', '{"last": "data"}')

        assert result == "Response with  emojis "
        assert "🎉" not in result
        assert "🚀" not in result

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_generate_response_api_error(self, mock_floor_plan, mock_openai, mock_file):
        """Test handling of OpenAI API errors"""
        mock_file.return_value.read.side_effect = [
            "sys {default_state}",
            "human {current_state} {last_state}",
            "{}",
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        bot = HouseBot()

        with pytest.raises(Exception):
            bot.generate_response('{"state": "data"}', '{"last": "data"}')

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_generate_response_rate_limit(
        self, mock_floor_plan, mock_openai, mock_file
    ):
        """Test handling of rate limit errors"""
        mock_file.return_value.read.side_effect = [
            "sys {default_state}",
            "human {current_state} {last_state}",
            "{}",
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception(
            "Rate limit exceeded"
        )

        bot = HouseBot()

        with pytest.raises(Exception):
            bot.generate_response('{"state": "data"}', '{"last": "data"}')

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_generate_response_with_none_values(
        self, mock_floor_plan, mock_openai, mock_file
    ):
        """Test generate_response with None parameters"""
        mock_file.return_value.read.side_effect = [
            "sys {default_state}",
            "human {current_state} {last_state}",
            "{}",
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Response"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()
        result = bot.generate_response('{"state": "data"}', None)

        assert result == "Response"

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_prompt_formatting_with_special_characters(
        self, mock_floor_plan, mock_openai, mock_file
    ):
        """Test prompt formatting handles special characters"""
        mock_file.return_value.read.side_effect = [
            "System: {default_state}",
            "Human: {current_state} {last_state}",
            '{"special": "chars\\"test\\n"}',
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Response"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()
        bot.generate_response('{"data": "test"}', '{"last": "test"}')

        # Verify the API was called with properly formatted messages
        call_args = mock_client.chat.completions.create.call_args
        assert "messages" in call_args[1]
        assert len(call_args[1]["messages"]) == 2

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_temperature_bounds(
        self, mock_floor_plan, mock_openai, mock_file, monkeypatch
    ):
        """Test temperature values at boundaries"""
        for temp in ["0", "0.5", "1.0", "2.0"]:
            monkeypatch.setenv("OPENAI_TEMPERATURE", temp)
            mock_file.return_value.read.side_effect = [
                "sys",
                "human",
                "{}",
                "should_respond",
                "camera_vision",
            ]
            bot = HouseBot()
            assert bot.temperature == float(temp)

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_empty_response_from_api(self, mock_floor_plan, mock_openai, mock_file):
        """Test handling of empty response from OpenAI"""
        mock_file.return_value.read.side_effect = [
            "sys {default_state}",
            "human {current_state} {last_state}",
            "{}",
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = ""
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()
        result = bot.generate_response('{"state": "data"}', '{"last": "data"}')

        assert result == ""

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_house_bot_executes_tools_before_ai(
        self, mock_floor_plan, mock_openai, mock_file
    ):
        """Test HouseBot can execute tools and inject results into prompt"""
        from unittest.mock import Mock

        mock_file.return_value.read.side_effect = [
            "sys {default_state}",
            "human {current_state} {last_state}",
            "{}",
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Tool results received"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()

        # Mock tool router
        bot.tool_router = Mock()
        bot.tool_router.get_catalog.return_value = "floor_plan_query"
        bot.tool_router.execute.return_value = {"zones": ["conf_a"]}

        current_state = {
            "zones": ["lobby"],
            "tool_request": {
                "tool_name": "floor_plan_query",
                "params": {"query": "adjacent_zones", "zone_id": "lobby"},
            },
        }

        bot.generate_response(current_state, None)

        # Verify tool was executed
        assert bot.tool_router.execute.called

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_house_bot_selects_model_by_severity(
        self, mock_floor_plan, mock_openai, mock_file
    ):
        """Test HouseBot uses different models based on situation severity"""

        mock_file.return_value.read.side_effect = [
            "sys {default_state}",
            "human {current_state} {last_state}",
            "{}",
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Response"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()
        bot.classifier_model = "gpt-5-mini"
        bot.synthesis_model = "gpt-5"

        # High severity situation
        high_severity_state = {
            "confidence": 0.9,
            "anomaly_scores": [3.5, 4.2],
            "zones": ["lobby", "conf_a"],  # Multiple zones to push severity > 0.7
        }

        bot.generate_response(high_severity_state, None)

        # Check that gpt-5 was used
        call_kwargs = bot.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-5"

    @patch("builtins.open", new_callable=mock_open, read_data="test")
    @patch("houseagent.house_bot.OpenAI")
    @patch("houseagent.house_bot.FloorPlanModel")
    def test_house_bot_uses_cheap_model_for_low_severity(
        self, mock_floor_plan, mock_openai, mock_file
    ):
        """Test HouseBot uses gpt-5-mini for routine situations"""

        mock_file.return_value.read.side_effect = [
            "sys {default_state}",
            "human {current_state} {last_state}",
            "{}",
            "should_respond",
            "camera_vision",
        ]

        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Response"
        mock_client.chat.completions.create.return_value = mock_response

        bot = HouseBot()
        bot.classifier_model = "gpt-5-mini"
        bot.synthesis_model = "gpt-5"

        # Low severity situation
        low_severity_state = {"confidence": 0.3, "zones": ["lobby"]}

        bot.generate_response(low_severity_state, None)

        # Check that gpt-5-mini was used
        call_kwargs = bot.client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-5-mini"
