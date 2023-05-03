import openai
import logging
import os
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

class ChatBot:


    def __init__(self, system="", log_file="chatbot.log"):
        self.logger = logging.getLogger(__name__)
   
        
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.system = system
        self.messages = []
        self.total_tokens = 0
        self.price_cpm = {
            'gpt-3.5-turbo': 0.002,
            'gpt-4': 0.06,
        }
        self.model = os.getenv("OPENAI_MODEL")

        if self.system:
            self.messages.append({"role": "system", "content": system})
            self.logger.debug(f"System message: {system}")

    def count_tokens(self, usage):
        self.logger.debug(usage)
        self.total_tokens += usage["total_tokens"]
        self.logger.debug(f"Total tokens used: {self.total_tokens}")
        self.logger.debug(f"Cost: {(self.total_tokens/1000)*self.price_cpm[self.model]}")
        return self.total_tokens
    
    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        self.logger.debug(f"User message: {message}")
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        self.logger.debug(f"Assistant message: {result}")
        return result
    
    def execute(self):
        completion = openai.ChatCompletion.create(model=os.getenv("OPENAI_MODEL"), messages=self.messages)
        self.count_tokens(completion.usage)
        return completion.choices[0].message.content