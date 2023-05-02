import os
import time
import json
import paho.mqtt.client as mqtt
from queue import Queue, Empty
from threading import Thread, Event
from dotenv import load_dotenv
import logging

# Set up basic logging configuration
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s]: %(message)s')


# Load configuration from .env file
load_dotenv()

# Define constants
TIMEOUT = int(os.getenv('TIMEOUT', 60))  # seconds
RETRY_INTERVAL = int(os.getenv('RETRY_INTERVAL', 5))  # seconds
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 10))
MAX_QUEUE_SIZE = int(os.getenv('MAX_QUEUE_SIZE', 1000))

class MessageBatcher:
    def __init__(self):
        self.message_queue = Queue(MAX_QUEUE_SIZE)
        self.last_received_timestamp = None
        self.batch_start_time = None
        self.stop_event = Event()

    def on_connect(self, client, userdata, flags, rc):
        # Subscribe to the required topic
        topic = os.getenv('TOPIC', 'your/topic/here')
        client.subscribe(topic)

    def on_message(self, client, userdata, msg):
        try:
            # Deserialize the received JSON message
            message = json.loads(msg.payload)
        except json.JSONDecodeError:
            # Handle JSON deserialization error
            print(f"Error decoding JSON: {msg.payload}")
            return

        # Update the last_received_timestamp
        self.last_received_timestamp = time.time()

        # Append the message to the message_queue
        self.message_queue.put(message)

        # Check if it's time to start a new batch
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
            output = {'Messages': batch}
            print(json.dumps(output, indent=2))

        # Reset the batch_start_time
        self.batch_start_time = None

    def process_batches(self):
        while not self.stop_event.is_set():
            if self.last_received_timestamp and (time.time() - self.last_received_timestamp) >= TIMEOUT:
                # Send the batched messages if TIMEOUT has passed
                self.send_batched_messages()

            # Sleep for a short while to reduce CPU usage
            time.sleep(0.1)
            print("Processing batches...")

        # Send any remaining messages before exiting
        self.send_batched_messages()

    def stop(self):
        self.stop_event.set()


def connect_with_retry(client, broker_address, port_number, keep_alive_interval, max_retries=MAX_RETRIES, retry_interval=RETRY_INTERVAL):
    retries = 0
    while retries < max_retries:
        try:
            # Connect to the MQTT broker
            client.connect(broker_address, port_number, keep_alive_interval)
            return True
        except Exception as e:
            print(f"Error connecting to MQTT broker: {e}")
            retries += 1
            print(f"Retrying connection in {retry_interval} seconds... ({retries}/{max_retries})")
            time.sleep(retry_interval)

    print("Failed to connect to MQTT broker after multiple attempts.")
    return False

def main():
    message_batcher = MessageBatcher()

    # Set up MQTT client
    client = mqtt.Client()
    client.on_connect = message_batcher.on_connect
    client.on_message = message_batcher.on_message

    # Connect to the MQTT broker with retry logic
    broker_address = os.getenv('MQTT_BROKER_ADDRESS', 'localhost')
    port_number = int(os.getenv('MQTT_PORT',1883))
    keep_alive_interval = int(os.getenv('MQTT_KEEP_ALIVE_INTERVAL', 60))

    if not connect_with_retry(client, broker_address, port_number, keep_alive_interval):
        print("Unable to establish connection with MQTT broker. Exiting...")
        exit(1)

    # Start the MQTT loop
    client.loop_start()

    # Start the batch processing thread
    batch_processing_thread = Thread(target=message_batcher.process_batches)
    batch_processing_thread.start()

    try:
        # Wait for the batch processing thread to finish
        batch_processing_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down...")

    finally:
        # Stop the MessageBatcher and send any remaining messages before exiting
        message_batcher.stop()

        # Disconnect the MQTT client
        client.loop_stop()
        client.disconnect()

        print("Bye!")

if __name__ == "__main__":
    main()