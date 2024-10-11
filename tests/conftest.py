import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_mqtt_client():
    return MagicMock()


@pytest.fixture
def mock_openai_api():
    with pytest.MonkeyPatch.context() as m:
        m.setenv("OPENAI_API_KEY", "mock_api_key")
        yield


@pytest.fixture
def sample_message():
    return {"text": "Sample message"}
