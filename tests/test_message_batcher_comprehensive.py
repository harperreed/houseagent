"""Comprehensive tests for MessageBatcher class"""

from unittest.mock import MagicMock, patch
import json
import time
from houseagent.message_batcher import MessageBatcher


class TestMessageBatcherComprehensive:
    """Comprehensive test suite for MessageBatcher"""

    def test_initialization_default_values(self):
        """Test MessageBatcher initializes with correct defaults"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        assert batcher.client == mock_client
        assert batcher.timeout == 60
        assert not batcher.stopped
        assert batcher.batch_start_time == 0
        assert batcher.message_queue.empty()
        assert batcher.last_batch_messages is None

    def test_on_message_valid_json(self):
        """Test processing valid JSON message"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        msg = MagicMock()
        msg.payload = json.dumps({"sensor": "temp", "value": 72}).encode()

        batcher.on_message(mock_client, None, msg)

        assert not batcher.message_queue.empty()
        assert batcher.batch_start_time > 0

    def test_on_message_invalid_json(self):
        """Test handling invalid JSON gracefully"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        msg = MagicMock()
        msg.payload = b"invalid json"

        batcher.on_message(mock_client, None, msg)

        assert batcher.message_queue.empty()

    def test_on_message_multiple_messages(self):
        """Test batching multiple messages"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        for i in range(5):
            msg = MagicMock()
            msg.payload = json.dumps({"message": i}).encode()
            batcher.on_message(mock_client, None, msg)

        assert batcher.message_queue.qsize() == 5

    def test_on_message_starts_batch_timer(self):
        """Test batch timer starts on first message"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        assert batcher.batch_start_time == 0

        msg = MagicMock()
        msg.payload = json.dumps({"test": "data"}).encode()
        batcher.on_message(mock_client, None, msg)

        assert batcher.batch_start_time > 0

    def test_on_message_doesnt_restart_timer(self):
        """Test subsequent messages don't restart batch timer"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        msg = MagicMock()
        msg.payload = json.dumps({"test": "data"}).encode()

        batcher.on_message(mock_client, None, msg)
        first_timer = batcher.batch_start_time

        time.sleep(0.01)

        batcher.on_message(mock_client, None, msg)
        second_timer = batcher.batch_start_time

        assert first_timer == second_timer

    def test_send_batched_messages_with_messages(self):
        """Test sending batch when messages exist"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        # Add messages to queue
        for i in range(3):
            msg = MagicMock()
            msg.payload = json.dumps({"message": i}).encode()
            batcher.on_message(mock_client, None, msg)

        batcher.send_batched_messages()

        assert batcher.message_queue.empty()
        mock_client.publish.assert_called_once()
        assert batcher.batch_start_time is None

    def test_send_batched_messages_with_empty_queue(self):
        """Test sending batch with empty queue"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        batcher.send_batched_messages()

        mock_client.publish.assert_not_called()
        assert batcher.batch_start_time is None

    def test_send_batched_messages_publishes_to_correct_topic(self, monkeypatch):
        """Test batch publishes to configured topic"""
        monkeypatch.setenv("MESSAGE_BUNDLE_TOPIC", "test/batch/topic")

        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        msg = MagicMock()
        msg.payload = json.dumps({"test": "data"}).encode()
        batcher.on_message(mock_client, None, msg)

        batcher.send_batched_messages()

        args = mock_client.publish.call_args
        assert args[0][0] == "test/batch/topic"

    def test_send_batched_messages_format(self):
        """Test batch message has correct JSON structure"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        test_messages = [
            {"message": "first"},
            {"message": "second"},
            {"message": "third"},
        ]

        for msg_data in test_messages:
            msg = MagicMock()
            msg.payload = json.dumps(msg_data).encode()
            batcher.on_message(mock_client, None, msg)

        batcher.send_batched_messages()

        args = mock_client.publish.call_args
        batch_content = json.loads(args[0][1])

        assert "messages" in batch_content
        assert len(batch_content["messages"]) == 3

    @patch("houseagent.message_batcher.time.sleep")
    @patch("houseagent.message_batcher.time.time")
    def test_run_timeout_triggers_send(self, mock_time, mock_sleep):
        """Test timeout triggers batch send"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=5)

        # Simulate time passing
        mock_time.side_effect = [100, 106]  # 6 seconds passed

        msg = MagicMock()
        msg.payload = json.dumps({"test": "data"}).encode()
        batcher.on_message(mock_client, None, msg)

        batcher.batch_start_time = 100

        def stop_after_one(*args):
            batcher.stopped = True

        mock_sleep.side_effect = stop_after_one

        batcher.run()

        mock_client.publish.assert_called()

    def test_stop_sets_stopped_flag(self):
        """Test stop() sets stopped flag"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        assert not batcher.stopped
        batcher.stop()
        assert batcher.stopped

    def test_debug_mode_enabled(self, monkeypatch):
        """Test debug mode can be enabled"""
        monkeypatch.setenv("DEBUG", "1")

        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        assert batcher.debug == "1"

    def test_last_batch_messages_updates(self):
        """Test last_batch_messages is updated after send"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        assert batcher.last_batch_messages is None

        msg = MagicMock()
        msg.payload = json.dumps({"test": "data"}).encode()
        batcher.on_message(mock_client, None, msg)

        batcher.send_batched_messages()

        assert batcher.last_batch_messages is not None
        assert '"messages"' in batcher.last_batch_messages

    def test_concurrent_message_handling(self):
        """Test handling messages added during processing"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        # Add initial batch
        for i in range(3):
            msg = MagicMock()
            msg.payload = json.dumps({"batch": 1, "message": i}).encode()
            batcher.on_message(mock_client, None, msg)

        # Send first batch
        batcher.send_batched_messages()

        # Verify queue is empty after send
        assert batcher.message_queue.empty()

        # Add new batch
        for i in range(2):
            msg = MagicMock()
            msg.payload = json.dumps({"batch": 2, "message": i}).encode()
            batcher.on_message(mock_client, None, msg)

        assert batcher.message_queue.qsize() == 2

    def test_large_message_batch(self):
        """Test handling large number of messages"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        # Add 100 messages
        for i in range(100):
            msg = MagicMock()
            msg.payload = json.dumps({"message": i}).encode()
            batcher.on_message(mock_client, None, msg)

        assert batcher.message_queue.qsize() == 100

        batcher.send_batched_messages()

        assert batcher.message_queue.empty()
        mock_client.publish.assert_called_once()

    def test_timeout_values(self):
        """Test various timeout values"""
        mock_client = MagicMock()

        for timeout in [1, 10, 60, 300]:
            batcher = MessageBatcher(mock_client, timeout=timeout)
            assert batcher.timeout == timeout

    def test_unicode_in_messages(self):
        """Test handling unicode characters in messages"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=60)

        msg = MagicMock()
        msg.payload = json.dumps({"text": "Hello 世界 مرحبا"}).encode("utf-8")

        batcher.on_message(mock_client, None, msg)

        assert not batcher.message_queue.empty()

        batcher.send_batched_messages()
        mock_client.publish.assert_called_once()

    def test_message_batcher_validates_sensor_messages(self):
        """Test MessageBatcher validates incoming messages with schema"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=1.0)

        # Valid new format message
        valid_msg = {
            "ts": "2025-10-14T10:30:00Z",
            "sensor_id": "motion_01",
            "sensor_type": "motion",
            "zone_id": "lobby",
            "value": {"detected": True},
        }

        msg_mock = MagicMock()
        msg_mock.payload = json.dumps(valid_msg).encode()

        batcher.on_message(mock_client, None, msg_mock)

        # Should be in queue
        assert not batcher.message_queue.empty()

    def test_message_batcher_handles_invalid_messages(self):
        """Test MessageBatcher logs but doesn't crash on invalid messages"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=1.0)

        # Invalid message missing required fields
        invalid_msg = {"sensor_id": "temp_01"}  # Missing many required fields

        msg_mock = MagicMock()
        msg_mock.payload = json.dumps(invalid_msg).encode()

        batcher.on_message(mock_client, None, msg_mock)

        # Should still be in queue with validation_failed flag
        queued_msg = batcher.message_queue.get()
        assert queued_msg.get("validation_failed")

    def test_message_batcher_filters_noise(self):
        """Test MessageBatcher uses NoiseFilter to suppress duplicates"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=1.0)

        # Send same message twice
        msg_data = {
            "ts": "2025-10-14T10:30:00Z",
            "sensor_id": "temp_01",
            "sensor_type": "temperature",
            "zone_id": "lobby",
            "value": {"celsius": 22.0},
        }

        msg_mock1 = MagicMock()
        msg_mock1.payload = json.dumps(msg_data).encode()

        msg_mock2 = MagicMock()
        msg_mock2.payload = json.dumps(msg_data).encode()

        batcher.on_message(mock_client, None, msg_mock1)
        batcher.on_message(mock_client, None, msg_mock2)

        # Only first message should be queued
        assert batcher.message_queue.qsize() == 1

    def test_message_batcher_adds_anomaly_scores(self):
        """Test MessageBatcher adds anomaly scores to detected anomalies"""
        mock_client = MagicMock()
        batcher = MessageBatcher(mock_client, timeout=1.0)

        # Build baseline
        for temp in [20.0, 21.0, 20.5]:
            msg = MagicMock()
            msg.payload = json.dumps(
                {
                    "ts": "2025-10-14T10:30:00Z",
                    "sensor_id": "temp_01",
                    "sensor_type": "temperature",
                    "zone_id": "lobby",
                    "value": {"celsius": temp},
                }
            ).encode()
            batcher.on_message(mock_client, None, msg)

        # Send anomaly
        anomaly_msg = MagicMock()
        anomaly_msg.payload = json.dumps(
            {
                "ts": "2025-10-14T10:35:00Z",
                "sensor_id": "temp_01",
                "sensor_type": "temperature",
                "zone_id": "lobby",
                "value": {"celsius": 45.0},
            }
        ).encode()

        batcher.on_message(mock_client, None, anomaly_msg)

        # Find anomaly message in queue
        found_anomaly = False
        while not batcher.message_queue.empty():
            msg = batcher.message_queue.get()
            if msg.get("value", {}).get("celsius") == 45.0:
                assert "anomaly_score" in msg["value"]
                assert msg["value"]["anomaly_score"] > 2.0
                found_anomaly = True

        assert found_anomaly
