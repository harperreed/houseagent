import time
import json
from queue import Queue, Empty
import structlog
import os
from houseagent.schemas import SensorMessage, LegacyMessage
from pydantic import ValidationError


class MessageBatcher:
    def __init__(self, client, timeout):
        self.logger = structlog.getLogger(__name__)
        self.logger.info("Initialising message batcher")
        self.message_queue = Queue()
        self.last_received_timestamp = time.time()
        self.batch_start_time = 0
        self.timeout = timeout
        self.stopped = False
        self.debug = os.getenv("DEBUG", False)
        self.client = client
        self.last_batch_messages = None

        # Schema validation
        self.zone_map = {}  # TODO: Load from config

    def on_message(self, client, userdata, msg):
        try:
            message = json.loads(msg.payload)
            self.logger.debug(f"Received message: {message}")
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON: {msg.payload}")
            return

        # Try to validate as SensorMessage
        try:
            validated = SensorMessage(**message)
            message = validated.model_dump()
        except ValidationError as sensor_error:
            # Try legacy format only if it has legacy fields (sensor, room, value)
            has_legacy_fields = any(
                key in message for key in ["sensor", "room", "value"]
            )
            if has_legacy_fields:
                try:
                    # Validate as legacy message first
                    _ = LegacyMessage(**message)
                    validated = SensorMessage.from_legacy(message, self.zone_map)
                    message = validated.model_dump()
                except ValidationError as e:
                    self.logger.warning(
                        "message.validation_failed", error=str(e), payload=message
                    )
                    message["validation_failed"] = True
            else:
                # Not legacy format, mark as validation failed
                self.logger.warning(
                    "message.validation_failed",
                    error=str(sensor_error),
                    payload=message,
                )
                message["validation_failed"] = True

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
            self.client.publish(topic, json_output)

            # Log the sent batched messages at INFO level
            self.logger.info(f"Sent batched messages: {json_output}")

        self.logger.debug("Resetting batch timer")
        self.batch_start_time = None

    def run(self):
        while not self.stopped:
            if self.debug:
                self.logger.debug("Checking for messages")
                self.logger.debug(f"Queue size: {self.message_queue.qsize()}")
                self.logger.debug(f"Batch start time: {self.batch_start_time}")
                self.logger.debug(
                    f"Last received timestamp: {self.last_received_timestamp}"
                )
                if self.batch_start_time:
                    self.logger.debug(
                        f"Timeout remainder: {(time.time() - float(self.batch_start_time))}"
                    )
                self.logger.debug(
                    f"Last message received: {(time.time() - float(self.last_received_timestamp))}"
                )
                self.logger.debug(f"timeout: {self.timeout}")

            if (
                self.batch_start_time
                and (time.time() - self.batch_start_time) >= self.timeout
            ):
                self.logger.debug("Timeout reached")
                self.send_batched_messages()
            if self.debug:
                self.logger.debug("Sleeping for 0.1 seconds")
            time.sleep(0.1)

    def stop(self):
        self.logger.info("Stopping message batcher")
        self.stopped = True
