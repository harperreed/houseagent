import os
import time
import json
from queue import Queue, Empty
import paho.mqtt.client as mqtt
from threading import Thread
import logging
from chatgpt import ChatBot

# Load configuration from .env file
from dotenv import load_dotenv
load_dotenv()


# Set up basic logging configuration
log_format = '%(asctime)s %(name)s [%(levelname)s]: %(message)s'

logging.basicConfig(level=logging.DEBUG, format=log_format)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Create a FileHandler and set its level to INFO
file_handler = logging.FileHandler(os.getenv('LOGFILE', 'bot.log'))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(log_format))

# Add the FileHandler to the root logger
logging.getLogger('').addHandler(file_handler)

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
        logging.info(response)
        return response


class MessageBatcher:
    def __init__(self, client, timeout):

        self.logger = logging.getLogger(__name__)
        self.message_queue = Queue()
        self.last_received_timestamp = None
        self.batch_start_time = None
        self.timeout = timeout
        self.stopped = False
        self.client = client
        self.house_bot = HouseBot()
        self.last_batch_messages = None

    def on_message(self, client, userdata, msg):
        try:
            message = json.loads(msg.payload)
            self.logger.debug(f"Received message: {message}")
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON: {msg.payload}")
            return

        self.last_received_timestamp = time.time()
        self.message_queue.put(message)

        if not self.batch_start_time:
            self.batch_start_time = self.last_received_timestamp

    def send_batched_messages(self):
        batch = []
        while not self.message_queue.empty():
            try:
                batch.append(self.message_queue.get_nowait())
            except Empty:
                break

        if batch:
            output = {'messages': batch}
            json_output = json.dumps(output)
            

            response = self.house_bot.generate_response(json_output, self.last_batch_messages)
            self.last_batch_messages = json_output

            topic = os.getenv('PUBLISH_TOPIC', 'your/input/topic/here')
            self.client.publish(topic, response)

            # Log the sent batched messages at INFO level
            self.logger.info(f"Sent batched messages: {json_output}")
            self.logger.info(f"Sent openai messages: {response}")

        self.batch_start_time = None

    def run(self):
        while not self.stopped:
            if self.last_received_timestamp and (time.time() - self.last_received_timestamp) >= self.timeout:
                self.send_batched_messages()
            time.sleep(0.1)

    def stop(self):
        self.stopped = True

def on_connect(client, userdata, flags, rc):
    topic = os.getenv('SUBSCRIBE_TOPIC', 'your/input/topic/here')
    client.subscribe(topic)
    logging.info(f"Connected with result code {rc}. Subscribed to topic: {topic}")

def on_message(client, userdata, msg):
    message_batcher.on_message(client, userdata, msg)


timeout = int(os.getenv('TIMEOUT', 60))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

broker_address = os.getenv('MQTT_BROKER_ADDRESS', 'localhost')
port_number = int(os.getenv('MQTT_PORT', 1883))
keep_alive_interval = int(os.getenv('MQTT_KEEP_ALIVE_INTERVAL', 60))

client.connect(broker_address, port_number, keep_alive_interval)
logging.debug(f"Connected to MQTT broker at {broker_address}:{port_number}")

message_batcher = MessageBatcher(client, timeout)

client.loop_start()

try:
    message_batcher.run()
except KeyboardInterrupt:
    logging.info("Shutting down...")
    message_batcher.stop()

client.loop_stop()
client.disconnect()

logging.info("Bye!")
