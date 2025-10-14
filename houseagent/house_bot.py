# ABOUTME: HouseBot manages AI-powered home automation responses using OpenAI
# ABOUTME: Processes sensor state changes and generates witty GlaDOS-style responses
import structlog
import json
import os
import re
from openai import OpenAI
from houseagent.tools.router import ToolRouter, ToolRequest
from houseagent.tools.floor_plan_tool import FloorPlanTool
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

        openai_model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        openai_temperature = float(os.getenv("OPENAI_TEMPERATURE", "0"))

        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = openai_model
        self.temperature = openai_temperature

        # Initialize tool framework
        self.tool_router = ToolRouter()

        # Register tools
        floor_plan_path = os.getenv("FLOOR_PLAN_PATH", "config/floor_plan.json")
        floor_plan = FloorPlanModel.load(floor_plan_path)
        self.tool_router.tools["floor_plan_query"] = FloorPlanTool(floor_plan)

    def strip_emojis(self, text):
        RE_EMOJI = re.compile("[\U00010000-\U0010ffff]", flags=re.UNICODE)
        return RE_EMOJI.sub(r"", text)

    def generate_response(self, current_state, last_state, message_history=None):
        self.logger.debug("let's make a request")

        # Format the system prompt with default state
        system_prompt = self.system_prompt_template.format(
            default_state=json.dumps(self.default_state, separators=(",", ":"))
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

        # Make the OpenAI API call directly
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        result = response.choices[0].message.content

        self.logger.debug(f"let's make a request: {result}")

        # Strip emoji
        result = self.strip_emojis(result)

        return result
