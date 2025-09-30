import unittest
from unittest.mock import patch, MagicMock
import json
from houseagent.message_batcher import MessageBatcher


class TestMessageBatcher(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.message_batcher = MessageBatcher(self.mock_client, timeout=1)

    def test_initialization(self):
        self.assertIsNotNone(self.message_batcher.logger)
        self.assertIsNotNone(self.message_batcher.message_queue)
        self.assertFalse(self.message_batcher.stopped)
        self.assertEqual(self.message_batcher.client, self.mock_client)
        self.assertIsNone(self.message_batcher.last_batch_messages)

    def test_on_message(self):
        mock_msg = MagicMock()
        mock_msg.payload = json.dumps({"text": "Test message"})

        self.message_batcher.on_message(self.mock_client, None, mock_msg)

        self.assertEqual(self.message_batcher.message_queue.qsize(), 1)

    @patch("houseagent.message_batcher.time.time")
    def test_send_batched_messages(self, mock_time):
        mock_time.return_value = 1000
        self.message_batcher.message_queue.put({"text": "Test message 1"})
        self.message_batcher.message_queue.put({"text": "Test message 2"})

        self.message_batcher.send_batched_messages()

        self.mock_client.publish.assert_called_once()
        self.assertIsNotNone(self.message_batcher.last_batch_messages)

    @patch("houseagent.message_batcher.time.sleep")
    @patch("houseagent.message_batcher.time.time")
    def test_run(self, mock_time, mock_sleep):
        mock_time.return_value = 1000
        self.message_batcher.batch_start_time = 999
        self.message_batcher.message_queue.put({"text": "Test message"})

        def stop_after_one_iteration(*args):
            self.message_batcher.stopped = True

        mock_sleep.side_effect = stop_after_one_iteration

        self.message_batcher.run()

        self.mock_client.publish.assert_called_once()

    def test_stop(self):
        self.assertFalse(self.message_batcher.stopped)
        self.message_batcher.stop()
        self.assertTrue(self.message_batcher.stopped)


if __name__ == "__main__":
    unittest.main()
