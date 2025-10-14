# ABOUTME: Tests for MQTT collector topic subscription and message routing
# ABOUTME: Validates both legacy and hierarchical office topic patterns

from unittest.mock import Mock, patch
import os
import sys

# Add parent directory to path so we can import collector
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@patch("houseagent.message_batcher.MessageBatcher")
@patch("paho.mqtt.client.Client")
def test_collector_subscribes_to_office_topics(mock_client_class, mock_batcher):
    """Test collector subscribes to hierarchical office topics"""
    # Now we can import collector without it trying to connect
    import collector

    client_mock = Mock()

    # Call the on_connect function directly (VERSION2 signature)
    collector.on_connect(client_mock, None, None, 0, None)

    # Verify office pattern subscription
    calls = [call[0][0] for call in client_mock.subscribe.call_args_list]
    assert any("office/" in topic for topic in calls), (
        f"No office topic found in calls: {calls}"
    )
