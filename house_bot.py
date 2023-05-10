from chatgpt import ChatBot

class HouseBot:
    def __init__(self):
        with open('housebot_prompt.txt', 'r') as f:
            prompt = f.read()
        self.system_prompt = prompt
        self.ai = ChatBot(self.system_prompt)

    def generate_response(self, current_state, last_state):
        prompt = f"""# The current state is:
{current_state}

# The previous state was:
{last_state}"""
        response = self.ai(prompt)
        return response
