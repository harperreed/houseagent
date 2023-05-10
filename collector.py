import os

import paho.mqtt.client as mqtt
import logging
from houseagent.message_batcher import MessageBatcher

# Load configuration from .env file
from dotenv import load_dotenv
load_dotenv()


# Set up basic logging configuration
log_format = '%(asctime)s %(name)s [%(levelname)s]: %(message)s'

logging.basicConfig(level=logging.DEBUG, format=log_format)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Create a FileHandler and set its level to INFO
file_handler = logging.FileHandler(os.getenv('COLLECTOR_LOGFILE', 'collector.log'))
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(log_format))

# Add the FileHandler to the root logger
logging.getLogger('').addHandler(file_handler)



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
