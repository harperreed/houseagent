import openai
import logging
import os
# from dotenv import load_dotenv

# load_dotenv()  # take environment variables from .env.

class ChatBot:
    def __init__(self, system=""):
        openai.api_key = os.getenv("OPENAI_API_KEY")
        self.system = system
        self.messages = []
        self.total_tokens = 0
        self.price_cpm = 0.002

        if self.system:
            self.messages.append({"role": "system", "content": system})

    def count_tokens(self, usage):
        logging.debug(usage)
        self.total_tokens += usage["total_tokens"]
        logging.debug(self.total_tokens)
        return self.total_tokens
    
    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result
    
    def execute(self):
        completion = openai.ChatCompletion.create(model=os.getenv("OPENAI_MODEL"), messages=self.messages)
        self.count_tokens(completion.usage)
        return completion.choices[0].message.content