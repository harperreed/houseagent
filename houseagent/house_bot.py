# ABOUTME: HouseBot manages AI-powered home automation responses using OpenAI
# ABOUTME: Processes sensor state changes and generates witty GlaDOS-style responses
import structlog
import json
import os
import re
from openai import OpenAI
from houseagent.tools.router import ToolRouter, ToolRequest
from houseagent.tools.floor_plan_tool import FloorPlanTool
from houseagent.tools.camera_tool import CameraTool
from houseagent.floor_plan import FloorPlanModel


class HouseBot:
    def __init__(self):
        self.logger = structlog.getLogger(__name__)
        prompt_dir = "prompts"

        human_prompt_filename = "housebot_human.txt"
        system_prompt_filename = "housebot_system.txt"
        default_state_filename = "default_state.json"

        with open(f"{prompt_dir}/{system_prompt_filename}", "r") as f:
            self.system_prompt_template = f.read()
        with open(f"{prompt_dir}/{human_prompt_filename}", "r") as f:
            self.human_prompt_template = f.read()
        with open(f"{prompt_dir}/{default_state_filename}", "r") as f:
            self.default_state = f.read()

        openai_model = os.getenv("OPENAI_MODEL", "gpt-5")
        openai_temperature = float(os.getenv("OPENAI_TEMPERATURE", "0"))

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = openai_model
        self.temperature = openai_temperature

        # Multi-model configuration (GPT-5 models)
        self.classifier_model = os.getenv("CLASSIFIER_MODEL", "gpt-5-mini")
        self.synthesis_model = os.getenv("SYNTHESIS_MODEL", "gpt-5")

        # Initialize tool framework
        self.tool_router = ToolRouter()

        # Register tools
        floor_plan_path = os.getenv("FLOOR_PLAN_PATH", "config/floor_plan.json")
        self.floor_plan = FloorPlanModel.load(floor_plan_path)
        self.tool_router.tools["floor_plan_query"] = FloorPlanTool(self.floor_plan)
        self.tool_router.tools["get_camera_snapshot"] = CameraTool(self.floor_plan)

        # Load should_respond filter prompt
        filter_prompt_path = os.getenv(
            "SHOULD_RESPOND_PROMPT", "prompts/should_respond_filter.txt"
        )
        try:
            with open(filter_prompt_path) as f:
                self.should_respond_prompt = f.read()
        except FileNotFoundError:
            self.logger.warning(
                f"Should respond filter prompt not found: {filter_prompt_path}"
            )
            self.should_respond_prompt = None

    def should_respond(self, situation_json: str) -> bool:
        """
        Ask GPT-5-mini whether the assistant should respond to this situation.

        Uses JSON structured output to get a yes/no decision with reasoning.
        Returns True if assistant should speak up, False otherwise.
        """
        # If no filter prompt loaded, always respond (fail open)
        if not self.should_respond_prompt:
            self.logger.warning("No filter prompt, defaulting to respond=True")
            return True

        try:
            # Build filter messages
            messages = [
                {"role": "system", "content": self.should_respond_prompt},
                {"role": "user", "content": f"Situation data:\n{situation_json}"},
            ]

            # Call GPT-5-mini with JSON mode
            response = self.client.chat.completions.create(
                model=self.classifier_model,
                messages=messages,
                response_format={"type": "json_object"},
            )

            # Parse JSON response
            result_json = json.loads(response.choices[0].message.content)
            should_respond = result_json.get("should_respond", True)
            reason = result_json.get("reason", "No reason provided")

            self.logger.info(
                "Response filter decision",
                should_respond=should_respond,
                reason=reason,
            )

            return should_respond

        except Exception as e:
            self.logger.error(
                "Failed to run should_respond filter, defaulting to True", error=str(e)
            )
            return True

    def strip_emojis(self, text):
        RE_EMOJI = re.compile("[\U00010000-\U0010ffff]", flags=re.UNICODE)
        return RE_EMOJI.sub(r"", text)

    def _classify_severity(self, state):
        """Classify situation severity (0-1)"""
        severity = 0.0

        # Handle state as dict or string
        if isinstance(state, str):
            try:
                state = json.loads(state)
            except (json.JSONDecodeError, TypeError):
                return 0.0

        if not isinstance(state, dict):
            return 0.0

        # High confidence situations
        if state.get("confidence", 0) > 0.8:
            severity += 0.3

        # Anomaly detection
        anomaly_scores = state.get("anomaly_scores", [])
        if any(score > 2.5 for score in anomaly_scores):
            severity += 0.4

        # Multiple zones
        if len(state.get("zones", [])) > 1:
            severity += 0.2

        return min(severity, 1.0)

    def generate_response(self, current_state, last_state, message_history=None):
        self.logger.debug("let's make a request")

        # Classify situation severity
        severity = self._classify_severity(current_state)

        # Select model based on severity
        selected_model = (
            self.synthesis_model if severity > 0.7 else self.classifier_model
        )

        # Format the system prompt with floor plan context instead of default_state
        floor_plan_context = {
            "zones": list(self.floor_plan.zones.keys()),
            "total_zones": len(self.floor_plan.zones),
            "floors": list(
                set(z.get("floor", 1) for z in self.floor_plan.zones.values())
            ),
            "cameras": len(self.floor_plan.cameras),
        }
        system_prompt = self.system_prompt_template.format(
            default_state=json.dumps(floor_plan_context, separators=(",", ":"))
        )

        # Build messages array
        messages = [{"role": "system", "content": system_prompt}]

        # Add tool capability to prompt
        messages[0]["content"] += (
            "\n\nAvailable tools: " + self.tool_router.get_catalog()
        )

        # If we have message history, use it instead of just last_state
        if message_history and len(message_history) > 0:
            # Use the full conversation history
            messages.extend(message_history)
            self.logger.debug(
                f"Using message history with {len(message_history)} messages"
            )
        else:
            # Fallback to old behavior with just current and last state
            human_prompt = self.human_prompt_template.format(
                current_state=current_state, last_state=last_state
            )
            messages.append({"role": "user", "content": human_prompt})

        # Add structured output request for high severity
        if severity > 0.7:
            messages.append(
                {
                    "role": "system",
                    "content": "Respond with both text AND JSON: {severity, tags, actions}",
                }
            )

        # Execute tools if requested
        tool_request = None
        if isinstance(current_state, dict):
            tool_request = current_state.get("tool_request")

        if tool_request:
            tool_result = self.tool_router.execute(
                ToolRequest(
                    tool_name=tool_request["tool_name"], params=tool_request["params"]
                )
            )

            # Inject tool results into conversation
            messages.append(
                {
                    "role": "assistant",
                    "content": f"Tool results: {json.dumps(tool_result)}",
                }
            )

        # Use selected model
        response = self.client.chat.completions.create(
            model=selected_model,
            messages=messages,
        )

        result = response.choices[0].message.content

        self.logger.debug(f"let's make a request: {result}")

        # Strip emoji
        result = self.strip_emojis(result)

        return result
