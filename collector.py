import os
from dotenv import load_dotenv
import paho.mqtt.client as mqtt
import logging
import structlog
from houseagent.message_batcher import MessageBatcher

# Load configuration from .env file
from dotenv import load_dotenv
load_dotenv()


logger = structlog.get_logger(__name__)

def on_connect(client, userdata, flags, rc):
    topic = os.getenv('SUBSCRIBE_TOPIC', 'your/input/topic/here')
    client.subscribe(topic)
    logger.info(f"Connected with result code {rc}. Subscribed to topic: {topic}")

def on_message(client, userdata, msg):
    message_batcher.on_message(client, userdata, msg)

def on_disconnect(client, userdata, rc):
    logger.info("Disconnected from MQTT broker")
    if rc != 0:
        logger.error(f"Unexpected disconnection. Result code: {rc}")
  

timeout = int(os.getenv('TIMEOUT', 60))

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

broker_address = os.getenv('MQTT_BROKER_ADDRESS', 'localhost')
port_number = int(os.getenv('MQTT_PORT', 1883))
keep_alive_interval = int(os.getenv('MQTT_KEEP_ALIVE_INTERVAL', 120))

client.connect(broker_address, port_number, keep_alive_interval)
logger.debug(f"Connected to MQTT broker at {broker_address}:{port_number}")

message_batcher = MessageBatcher(client, timeout)

client.loop_start()

try:
    message_batcher.run()
except KeyboardInterrupt:
    logger.info("Shutting down...")
    message_batcher.stop()

client.loop_stop()
client.disconnect()

logging.info("Bye!")
