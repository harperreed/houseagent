import os
import structlog
from houseagent.house_bot import HouseBot
import json
from collections import deque


class AgentListener:
    def __init__(self, client, history_size=10):
        self.logger = structlog.getLogger(__name__)
        self.stopped = False
        self.client = client
        self.house_bot = HouseBot()
        self.last_batch_messages = None

        # Rolling window of message history (user inputs + assistant responses)
        self.history_size = history_size
        self.message_history = deque(maxlen=history_size)
        self.logger.info(f"Initialized AgentListener with history size: {history_size}")

    def on_message(self, client, userdata, msg):
        try:
            message = json.loads(msg.payload)
            self.logger.debug(f"Received message: {message}")
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON: {msg.payload}")
            return

        output = {"messages": message}
        json_output = json.dumps(output)

        # Log the sent batched messages at INFO level
        self.logger.info(f"Sent batched messages: {json_output}")

        # Add current message to history
        self.message_history.append({"role": "user", "content": json_output})

        # Generate response with full message history
        response = self.house_bot.generate_response(
            json_output, self.last_batch_messages, list(self.message_history)
        )
        self.last_batch_messages = json_output

        # Add assistant response to history
        self.message_history.append({"role": "assistant", "content": response})

        self.logger.info(
            f"Message history size: {len(self.message_history)}/{self.history_size}"
        )

        topic = os.getenv("NOTIFICATION_TOPIC", "your/input/topic/here")
        self.client.publish(topic, response)

    def stop(self):
        self.stopped = True
