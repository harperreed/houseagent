import time
import json
from queue import Queue, Empty
import logging
import structlog
import os


class MessageBatcher:
    def __init__(self, client, timeout):
        self.logger = structlog.getLogger(__name__)
        self.logger.info("Initialising message batcher")
        self.message_queue = Queue()
        self.last_received_timestamp = time.time()
        self.batch_start_time = 0
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
            self.logger.debug("Starting batch timer")
            self.batch_start_time = self.last_received_timestamp

    def send_batched_messages(self):
        batch = []
        self.logger.info("Sending batched messages")
        while not self.message_queue.empty():
            try:
                self.logger.debug("Getting message from queue")
                batch.append(self.message_queue.get_nowait())
            except Empty:
                break

        if batch:
            self.logger.debug(f"Batch: {batch}")
            output = {"messages": batch}
            json_output = json.dumps(output)

            self.last_batch_messages = json_output

            self.logger.debug(f"Response: {json_output}")

            topic = os.getenv("MESSAGE_BUNDLE_TOPIC", "your/input/topic/here")
            self.client.publish(topic, json.dumps(json_output))

            # Log the sent batched messages at INFO level
            self.logger.info(f"Sent batched messages: {json_output}") 

        self.logger.debug("Resetting batch timer")
        self.batch_start_time = None

    def run(self):
        debug = False
        while not self.stopped:
            if debug:
                self.logger.debug("Checking for messages")
                self.logger.debug(f"Queue size: {self.message_queue.qsize()}")
                self.logger.debug(f"Batch start time: {self.batch_start_time}")
                self.logger.debug(f"Last received timestamp: {self.last_received_timestamp}")
                self.logger.debug(f"Timeout remainder: {(time.time() - float(self.batch_start_time))}")
                self.logger.debug(f"Last message received: {(time.time() - float(self.last_received_timestamp))}")
                self.logger.debug(f"timeout: {self.timeout}")

            if (
                self.batch_start_time
                and (time.time() - self.batch_start_time) >= self.timeout
            ):
                self.logger.debug("Timeout reached")
                self.send_batched_messages()
            if debug:
                self.logger.debug("Sleeping for 0.1 seconds")
            time.sleep(0.1)

    def stop(self):
        self.logger.info("Stopping message batcher")
        self.stopped = True
