import os
import structlog
from houseagent.house_bot import HouseBot
from houseagent.semantic_memory import SemanticMemory
import json
from collections import deque


class AgentListener:
    def __init__(
        self,
        client,
        history_size=10,
        use_semantic_memory=True,
        semantic_time_window=2,
    ):
        self.logger = structlog.getLogger(__name__)
        self.stopped = False
        self.client = client
        self.house_bot = HouseBot()
        self.last_batch_messages = None

        # Rolling window of message history (user inputs + assistant responses)
        self.history_size = history_size
        self.message_history = deque(maxlen=history_size)

        # Semantic memory for long-term, time-aware search
        self.use_semantic_memory = use_semantic_memory
        self.semantic_memory = None
        if use_semantic_memory:
            self.semantic_memory = SemanticMemory(
                time_window_hours=semantic_time_window
            )
            self.logger.info(
                f"Initialized AgentListener with history size: {history_size}, "
                f"semantic memory: enabled (time window: {semantic_time_window}h)"
            )
        else:
            self.logger.info(
                f"Initialized AgentListener with history size: {history_size}"
            )

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

        # Add to semantic memory
        if self.semantic_memory:
            self.semantic_memory.add_message(message, role="user")

        # Add current message to rolling window history
        self.message_history.append({"role": "user", "content": json_output})

        # Get semantic context if enabled
        semantic_context = []
        if self.semantic_memory:
            # Search for relevant recent messages
            semantic_results = self.semantic_memory.search(
                query=json_output, n_results=3
            )
            semantic_context = [
                f"[Recent context: {r['content']}]" for r in semantic_results
            ]
            if semantic_context:
                self.logger.debug(
                    f"Found {len(semantic_context)} relevant semantic matches"
                )

        # Build enhanced message history with semantic context
        enhanced_history = list(self.message_history)
        if semantic_context:
            # Inject semantic context right before the current message
            context_message = {
                "role": "user",
                "content": "Relevant recent history: " + " ".join(semantic_context),
            }
            # Insert before the last user message (the current one)
            # enhanced_history has: [...older messages..., current_user_message]
            # We want: [...older messages..., context_message, current_user_message]
            if len(enhanced_history) > 0:
                enhanced_history.insert(-1, context_message)

        # Generate response with full message history + semantic context
        response = self.house_bot.generate_response(
            json_output, self.last_batch_messages, enhanced_history
        )
        self.last_batch_messages = json_output

        # Add assistant response to both histories
        self.message_history.append({"role": "assistant", "content": response})
        if self.semantic_memory:
            self.semantic_memory.add_message(response, role="assistant")

        self.logger.info(
            f"Message history size: {len(self.message_history)}/{self.history_size}"
        )

        topic = os.getenv("NOTIFICATION_TOPIC", "your/input/topic/here")
        self.client.publish(topic, response)

    def stop(self):
        self.stopped = True
