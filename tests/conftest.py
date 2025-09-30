import pytest
from unittest.mock import MagicMock, mock_open
import json


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client for testing"""
    client = MagicMock()
    client.publish = MagicMock()
    client.subscribe = MagicMock()
    return client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client with standard response"""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Mocked AI response"
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_openai_api_key(monkeypatch):
    """Set mock OpenAI API key in environment"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-api-key-12345")


@pytest.fixture
def sample_message():
    """Sample message payload"""
    return {"text": "Sample message", "sensor": "test_sensor"}


@pytest.fixture
def sample_mqtt_message():
    """Sample MQTT message object"""
    msg = MagicMock()
    msg.payload = json.dumps({"text": "Test message"}).encode()
    return msg


@pytest.fixture
def mock_prompt_files():
    """Mock prompt file reads"""
    return mock_open(read_data="test content")


@pytest.fixture
def mock_house_bot_files(monkeypatch):
    """Mock all file reads for HouseBot initialization"""
    file_contents = {
        "prompts/housebot_system.txt": "System prompt: {default_state}",
        "prompts/housebot_human.txt": "Human: {current_state} {last_state}",
        "prompts/default_state.json": '{"default": "state"}',
    }

    original_open = open

    def mock_file_open(filename, mode="r", *args, **kwargs):
        if filename in file_contents:
            return mock_open(read_data=file_contents[filename])()
        return original_open(filename, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_file_open)


@pytest.fixture(autouse=True)
def disable_semantic_memory(monkeypatch):
    """Automatically disable semantic memory for all tests unless explicitly overridden"""
    # Patch AgentListener's __init__ to default use_semantic_memory=False
    from houseagent.agent_listener import AgentListener

    original_init = AgentListener.__init__

    def patched_init(
        self, client, history_size=10, use_semantic_memory=False, semantic_time_window=2
    ):
        original_init(
            self, client, history_size, use_semantic_memory, semantic_time_window
        )

    monkeypatch.setattr(AgentListener, "__init__", patched_init)
