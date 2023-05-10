import logging
import json

# from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain import PromptTemplate, LLMChain

from langchain.prompts import (
    ChatPromptTemplate,
    PromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)

class HouseBot:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        with open('housebot_system_prompt.txt', 'r') as f:
            system_prompt_template = f.read()
        with open('housebot_human_prompt.txt', 'r') as f:
            human_prompt_template = f.read()

        with open('default_state.json', 'r') as f:
            self.default_state = f.read()

        self.system_message_prompt = SystemMessagePromptTemplate.from_template(system_prompt_template)
        self.human_message_prompt = HumanMessagePromptTemplate.from_template(human_prompt_template)

        self.chat = ChatOpenAI(temperature=0)

    def generate_response(self, current_state, last_state):
        self.logger.debug("let's make a request")

        chat_prompt = ChatPromptTemplate.from_messages([self.system_message_prompt, self.human_message_prompt])
        # get a chat completion from the formatted messages
        chain = LLMChain(llm=self.chat, prompt=chat_prompt)
        result = chain.run(default_state=json.dumps(self.default_state, separators=(',', ':')), current_state=current_state, last_state=last_state)

        self.logger.debug(f"let's make a request: {result}")
        # print(result.llm_output)
        
        return result
