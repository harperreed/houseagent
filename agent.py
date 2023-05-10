import os
import json
import paho.mqtt.client as mqtt
import logging
from dotenv import load_dotenv
import time
from house_bot import HouseBot

# Load configuration from .env file
load_dotenv()

# Set up basic logging configuration
log_format = '%(asctime)s %(name)s [%(levelname)s]: %(message)s'
logging.basicConfig(level=logging.DEBUG, format=log_format)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Create a FileHandler and set its level to INFO
file_handler = logging.FileHandler(os.getenv('AGENT_LOGFILE', 'bot.log'))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(log_format))

# Add the FileHandler to the root logger
logging.getLogger('').addHandler(file_handler)

class AgentListener:
    def __init__(self, client, timeout):
        self.logger = logging.getLogger(__name__)
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

        output = {'messages': message}
        json_output = json.dumps(output)

        # Log the sent batched messages at INFO level
        self.logger.info(f"Sent batched messages: {json_output}")

        response = self.house_bot.generate_response(json_output, self.last_batch_messages)
        self.last_batch_messages = json_output

        topic = os.getenv('NOTIFICATION_TOPIC', 'your/input/topic/here')
        self.client.publish(topic, response)

    def stop(self):
        self.stopped = True

def on_connect(client, userdata, flags, rc):
    topic = os.getenv('SUBSCRIBE_TOPIC', 'your/input/topic/here')
    client.subscribe(topic)
    logging.info(f"Connected with result code {rc}. Subscribed to topic: {topic}")

def on_message(client, userdata, msg):
    agent_client.on_message(client, userdata, msg)

timeout = int(os.getenv('TIMEOUT', 60))

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

broker_address = os.getenv('MQTT_BROKER_ADDRESS', 'localhost')
port_number = int(os.getenv('MQTT_PORT', 1883))
keep_alive_interval = int(os.getenv('MQTT_KEEP_ALIVE_INTERVAL', 60))

client.connect(broker_address, port_number, keep_alive_interval)
logging.debug(f"Connected to MQTT broker at {broker_address}:{port_number}")

agent_client = AgentListener(client, timeout)

client.loop_start()

try:
    while not agent_client.stopped:
        time.sleep(1)
except KeyboardInterrupt:
    logging.info("Shutting down...")
    agent_client.stop()

client.loop_stop()
client.disconnect
