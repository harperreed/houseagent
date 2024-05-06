import time
import json
from queue import Queue, Empty
import logging
import structlog
import os


class MessageBatcher:
    """
    A class to batch messages received over a period and send them in bulk.

    Attributes:
        client: The MQTT client used to publish messages.
        timeout: The maximum time to wait before sending a batch of messages.
    """
    def __init__(self, client, timeout, batch_size_threshold=50, idle_time_threshold=60):
        """
        Initializes the MessageBatcher with a client and timeout.

        Args:
            client: The MQTT client used to publish messages.
            timeout: The maximum time to wait before sending a batch of messages.
        """
        self.logger = structlog.getLogger(__name__)
        self.logger.info("Initialising message batcher")
        self.message_queue = Queue()
        self.last_received_timestamp = time.time()
        self.batch_size_threshold = batch_size_threshold
        self.idle_time_threshold = idle_time_threshold
        self.batch_start_time = 0
        self.timeout = timeout
        self.stopped = False
        self.debug = os.getenv("DEBUG", False)
        self.client = client
        self.last_batch_messages = None

    def on_message(self, client, userdata, msg):
        """
        Callback function for handling incoming messages.

        Args:
            client: The MQTT client instance.
            userdata: The userdata provided on setup (unused).
            msg: The message payload.
        """
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
        """
        Sends all messages in the queue as a single batch.
        """
        batch = []
        self.logger.info("Sending batched messages")
        while not self.message_queue.empty():
            try:
                self.logger.debug("Getting message from queue")
                batch.append(self.message_queue.get_nowait())
            except Empty:
                self.logger.error("Message queue unexpectedly empty")
                break

        if batch:
            self.logger.debug(f"Batch: {batch}")
            output = {"messages": batch}
            json_output = json.dumps(output)

            self.last_batch_messages = json_output

            self.logger.debug(f"Response: {json_output}")

            topic = os.getenv("MESSAGE_BUNDLE_TOPIC", "your/input/topic/here")
            self.client.publish(topic, json.dumps(json_output))
            self.logger.info(f"Sent batched messages: {json_output}")

        self.logger.debug("Resetting batch timer")
        self.batch_start_time = None

    def get_dynamic_timeout(self):
        # Calculate the average time between messages
        if self.message_queue.qsize() > 1:
            total_time = self.last_received_timestamp - self.batch_start_time
            avg_time_between_messages = total_time / (self.message_queue.qsize() - 1)
        else:
            avg_time_between_messages = self.timeout

        # Adjust the timeout based on the average time between messages
        if avg_time_between_messages < self.timeout / 2:
            # If messages are coming in frequently, reduce the timeout
            dynamic_timeout = avg_time_between_messages * 1.5
        elif avg_time_between_messages > self.timeout * 2:
            # If messages are coming in slowly, increase the timeout
            dynamic_timeout = avg_time_between_messages * 0.8
        else:
            # If messages are coming in at a moderate rate, use the default timeout
            dynamic_timeout = self.timeout

        # Ensure the dynamic timeout is within a reasonable range
        min_timeout = 0.1  # Minimum timeout value
        max_timeout = 60.0  # Maximum timeout value
        dynamic_timeout = max(min_timeout, min(dynamic_timeout, max_timeout))

        return dynamic_timeout

    def run(self):
        """
        Main loop to check for messages and send them when the timeout is reached.
        """
        while not self.stopped:
            if self.debug:
                self.logger.debug("Checking for messages")
                self.logger.debug(f"Queue size: {self.message_queue.qsize()}")
                self.logger.debug(f"Batch start time: {self.batch_start_time}")
                self.logger.debug(f"Last received timestamp: {self.last_received_timestamp}")
                if self.batch_start_time:
                    self.logger.debug(f"Timeout remainder: {(time.time() - float(self.batch_start_time))}")
                self.logger.debug(f"Last message received: {(time.time() - float(self.last_received_timestamp))}")
                self.logger.debug(f"timeout: {self.timeout}")

            current_time = time.time()
            elapsed_time = current_time - self.batch_start_time if self.batch_start_time else 0
            idle_time = current_time - self.last_received_timestamp

            # Dynamic Timeout and Batch Size Threshold
            if (
                (elapsed_time >= self.get_dynamic_timeout()) or
                (self.message_queue.qsize() >= self.batch_size_threshold)
            ):
                self.send_batched_messages()

            # Idle Time Detection
            if idle_time >= self.idle_time_threshold and not self.message_queue.empty():
                self.send_batched_messages()

            time.sleep(0.1)

    def stop(self):
        """
        Stops the message batcher from running.
        """
        self.logger.info("Stopping message batcher")
        self.stopped = True
