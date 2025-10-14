import os
import structlog
from houseagent.house_bot import HouseBot
from houseagent.semantic_memory import SemanticMemory
from houseagent.situation_builder import SituationBuilder
from houseagent.floor_plan import FloorPlanModel
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

        # Situation building
        self.situation_builder = SituationBuilder()
        floor_plan_path = os.getenv("FLOOR_PLAN_PATH", "config/floor_plan.json")
        self.floor_plan = FloorPlanModel.load(floor_plan_path)
        self.last_situation = None

    def on_message(self, client, userdata, msg):
        try:
            batch = json.loads(msg.payload)
            self.logger.debug(f"Received message: {batch}")
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON: {msg.payload}")
            return

        # Extract messages from batch
        # Support both {"messages": [...]} format and direct message
        if "messages" in batch:
            messages = batch["messages"]
        else:
            # Legacy format - treat entire payload as single message wrapped in array
            messages = [batch]

        # Build situation from message batch
        situation = self.situation_builder.build(messages, self.floor_plan)

        # Prepare the content to process (either situation or fallback to messages)
        if situation and situation.requires_response():
            # Convert situation to JSON for prompt
            content_json = json.dumps(situation.to_prompt_json())
            self.logger.info(f"Built situation: {content_json}")
            self.last_situation = situation
        else:
            # Fallback to legacy behavior for single messages or when no situation built
            output = {"messages": messages}
            content_json = json.dumps(output)
            self.logger.debug(
                f"No valid situation built from {len(messages)} messages, using fallback"
            )

        # Add to semantic memory
        if self.semantic_memory:
            self.semantic_memory.add_message(content_json, role="user")

        # Add current content to rolling window history
        self.message_history.append({"role": "user", "content": content_json})

        # Get semantic context if enabled
        semantic_context = []
        if self.semantic_memory:
            # Search for relevant recent messages
            semantic_results = self.semantic_memory.search(
                query=content_json, n_results=3
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
            if len(enhanced_history) > 0:
                enhanced_history.insert(-1, context_message)

        # Generate response
        last_content_json = (
            json.dumps(self.last_situation.to_prompt_json())
            if self.last_situation
            else self.last_batch_messages
        )
        response = self.house_bot.generate_response(
            content_json, last_content_json, enhanced_history
        )

        # Track last batch
        self.last_batch_messages = content_json

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
