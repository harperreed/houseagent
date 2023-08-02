import time
import json
from queue import Queue, Empty
import logging
import structlog
import os


class MessageBatcher:
    def __init__(self, client, timeout):
        self.logger = structlog.getLogger(__name__)
        self.message_queue = Queue()
        self.last_received_timestamp = None
        self.batch_start_time = None
        self.timeout = timeout
        self.stopped = False
        self.client = client
        self.last_batch_messages = None

    def on_message(self, client, userdata, msg):
        try:
            message = json.loads(msg.payload)
            self.logger.debug(f"Received message: {message}")
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON: {msg.payload}")
            return

        self.last_received_timestamp = time.time()
        self.message_queue.put(message)

        if not self.batch_start_time:
            self.batch_start_time = self.last_received_timestamp

    def send_batched_messages(self):
        batch = []
        while not self.message_queue.empty():
            try:
                batch.append(self.message_queue.get_nowait())
            except Empty:
                break

        if batch:
            output = {"messages": batch}
            json_output = json.dumps(output)

            # response = self.house_bot.generate_response(json_output, self.last_batch_messages)
            self.last_batch_messages = json_output

            topic = os.getenv("MESSAGE_BUNDLE_TOPIC", "your/input/topic/here")
            self.client.publish(topic, json.dumps(json_output))

            # Log the sent batched messages at INFO level
            self.logger.info(f"Sent batched messages: {json_output}")
            # self.logger.info(f"Sent openai messages: {response}")

        self.batch_start_time = None

    def run(self):
        while not self.stopped:
            if (
                self.last_received_timestamp
                and (time.time() - self.last_received_timestamp) >= self.timeout
            ):
                self.send_batched_messages()
            time.sleep(0.1)

    def stop(self):
        self.stopped = True
