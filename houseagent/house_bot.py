# ABOUTME: HouseBot manages AI-powered home automation responses using OpenAI
# ABOUTME: Processes sensor state changes and generates witty GlaDOS-style responses
import structlog
import json
import os
import re
from openai import OpenAI


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

        # Make the OpenAI API call directly
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            messages=messages,
        )

        result = response.choices[0].message.content

        self.logger.debug(f"let's make a request: {result}")

        # Strip emoji
        result = self.strip_emojis(result)

        return result
