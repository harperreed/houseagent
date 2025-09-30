"""Integration tests for HouseAgent system"""
import pytest
from unittest.mock import MagicMock, patch
import json
from houseagent.message_batcher import MessageBatcher
from houseagent.agent_listener import AgentListener


class TestIntegration:
    """Integration tests for complete message flow"""

    @patch('houseagent.message_batcher.time.sleep')
    @patch('houseagent.message_batcher.time.time')
    def test_message_batcher_to_agent_flow(self, mock_time, mock_sleep):
        """Test complete flow from message batcher to agent listener"""
        mock_collector_client = MagicMock()
        mock_agent_client = MagicMock()

        # Create message batcher (collector side)
        batcher = MessageBatcher(mock_collector_client, timeout=5)

        # Simulate receiving multiple sensor messages
        sensor_messages = [
            {"sensor": "temperature", "value": 72, "room": "living_room"},
            {"sensor": "humidity", "value": 45, "room": "living_room"},
            {"sensor": "motion", "detected": True, "room": "kitchen"}
        ]

        for sensor_data in sensor_messages:
            msg = MagicMock()
            msg.payload = json.dumps(sensor_data).encode()
            batcher.on_message(mock_collector_client, None, msg)

        # Verify messages are queued
        assert batcher.message_queue.qsize() == 3

        # Trigger batch send
        batcher.send_batched_messages()

        # Verify batch was published
        mock_collector_client.publish.assert_called_once()

        # Extract the published message
        publish_call = mock_collector_client.publish.call_args
        published_topic = publish_call[0][0]
        published_payload = publish_call[0][1]

        # Verify the payload structure
        batch_data = json.loads(published_payload)
        assert 'messages' in batch_data
        assert len(batch_data['messages']) == 3

    @patch('houseagent.agent_listener.HouseBot')
    def test_agent_listener_processes_batch(self, mock_house_bot):
        """Test agent listener processes batched messages"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "AI generated response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        # Simulate receiving a batched message
        batch_data = {
            "messages": [
                {"sensor": "temperature", "value": 72},
                {"sensor": "humidity", "value": 45}
            ]
        }

        msg = MagicMock()
        msg.payload = json.dumps(batch_data).encode()

        listener.on_message(mock_client, None, msg)

        # Verify AI was called
        mock_house_bot_instance.generate_response.assert_called_once()

        # Verify response was published
        mock_client.publish.assert_called_once_with(
            'your/input/topic/here',  # default topic
            'AI generated response'
        )

    @patch('houseagent.agent_listener.HouseBot')
    def test_multiple_message_cycles(self, mock_house_bot):
        """Test multiple cycles of message processing"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.side_effect = [
            "First response",
            "Second response",
            "Third response"
        ]

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        # Process 3 message cycles
        for i in range(3):
            msg = MagicMock()
            msg.payload = json.dumps({"cycle": i, "data": f"message {i}"}).encode()
            listener.on_message(mock_client, None, msg)

        # Verify 3 AI calls were made
        assert mock_house_bot_instance.generate_response.call_count == 3

        # Verify 3 responses were published
        assert mock_client.publish.call_count == 3

        # Verify each call had access to previous state
        calls = mock_house_bot_instance.generate_response.call_args_list
        assert calls[0][0][1] is None  # First call has no previous state
        assert calls[1][0][1] is not None  # Second call has previous state
        assert calls[2][0][1] is not None  # Third call has previous state

    def test_message_format_consistency(self):
        """Test message format remains consistent through pipeline"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        original_message = {
            "sensor_id": "temp_001",
            "location": {"room": "bedroom", "floor": 2},
            "reading": {"value": 72.5, "unit": "F", "timestamp": "2024-01-01T00:00:00Z"}
        }

        msg = MagicMock()
        msg.payload = json.dumps(original_message).encode()

        batcher.on_message(mock_client, None, msg)
        batcher.send_batched_messages()

        # Extract published message
        published_payload = mock_client.publish.call_args[0][1]
        batch_data = json.loads(published_payload)

        # Verify original structure is preserved
        assert batch_data['messages'][0] == original_message

    @patch('houseagent.agent_listener.HouseBot')
    def test_error_handling_in_pipeline(self, mock_house_bot):
        """Test error handling doesn't break message flow"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance

        # First call fails, second succeeds
        mock_house_bot_instance.generate_response.side_effect = [
            Exception("API Error"),
            "Success response"
        ]

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        # First message causes error
        msg1 = MagicMock()
        msg1.payload = json.dumps({"test": "first"}).encode()

        with pytest.raises(Exception):
            listener.on_message(mock_client, None, msg1)

        # Second message should still work
        msg2 = MagicMock()
        msg2.payload = json.dumps({"test": "second"}).encode()

        listener.on_message(mock_client, None, msg2)

        # Verify second message was processed
        assert mock_house_bot_instance.generate_response.call_count == 2
        mock_client.publish.assert_called_once()

    def test_high_throughput_scenario(self):
        """Test system handles high message throughput"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        # Simulate 1000 messages
        for i in range(1000):
            msg = MagicMock()
            msg.payload = json.dumps({"message_id": i, "data": f"test_{i}"}).encode()
            batcher.on_message(mock_client, None, msg)

        assert batcher.message_queue.qsize() == 1000

        # Batch and send
        batcher.send_batched_messages()

        assert batcher.message_queue.empty()
        mock_client.publish.assert_called_once()

        # Verify all messages are in the batch
        published_payload = mock_client.publish.call_args[0][1]
        batch_data = json.loads(published_payload)
        assert len(batch_data['messages']) == 1000

    @patch('houseagent.agent_listener.HouseBot')
    def test_state_preservation_across_messages(self, mock_house_bot):
        """Test state is correctly preserved between message cycles"""
        mock_house_bot_instance = MagicMock()
        mock_house_bot.return_value = mock_house_bot_instance
        mock_house_bot_instance.generate_response.return_value = "Response"

        mock_client = MagicMock()
        listener = AgentListener(mock_client)

        messages = [
            {"temperature": 70},
            {"temperature": 72},
            {"temperature": 75}
        ]

        previous_states = []

        for msg_data in messages:
            msg = MagicMock()
            msg.payload = json.dumps(msg_data).encode()
            listener.on_message(mock_client, None, msg)
            previous_states.append(listener.last_batch_messages)

        # Verify each subsequent message has previous state
        calls = mock_house_bot_instance.generate_response.call_args_list

        assert calls[0][0][1] is None  # First has no previous
        assert calls[1][0][1] == previous_states[0]  # Second has first as previous
        assert calls[2][0][1] == previous_states[1]  # Third has second as previous