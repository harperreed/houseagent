#!/usr/bin/env python3
# ABOUTME: Minimal MQTT connection test to diagnose broker issues
# ABOUTME: Tests basic connection stability without any application logic

import os
import time
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

connection_count = 0
disconnect_count = 0


def on_connect(client, userdata, flags, reason_code, properties):
    """Handle connection"""
    global connection_count
    connection_count += 1
    print(
        f"[{time.strftime('%H:%M:%S')}] CONNECTED (attempt #{connection_count}) - reason_code={reason_code}"
    )

    # Subscribe to a test topic
    client.subscribe("test/topic")
    print(f"[{time.strftime('%H:%M:%S')}] Subscribed to test/topic")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Handle disconnection"""
    global disconnect_count
    disconnect_count += 1
    print(
        f"[{time.strftime('%H:%M:%S')}] DISCONNECTED (#{disconnect_count}) - reason_code={reason_code}"
    )


def on_message(client, userdata, msg):
    """Handle incoming message"""
    print(
        f"[{time.strftime('%H:%M:%S')}] Message received on {msg.topic}: {msg.payload}"
    )


if __name__ == "__main__":
    # Create client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, "mqtt_connection_test")

    # Set callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Enable automatic reconnection
    client.reconnect_delay_set(min_delay=1, max_delay=120)

    # Set up authentication if credentials are provided
    mqtt_username = os.getenv("MQTT_USERNAME")
    mqtt_password = os.getenv("MQTT_PASSWORD")
    if mqtt_username and mqtt_password:
        client.username_pw_set(mqtt_username, mqtt_password)
        print(f"Auth configured: username={mqtt_username}")
    else:
        print("No authentication configured")

    # Get connection settings
    broker_address = os.getenv("MQTT_BROKER_ADDRESS", "localhost")
    port_number = int(os.getenv("MQTT_PORT", 1883))
    keep_alive_interval = int(os.getenv("MQTT_KEEP_ALIVE_INTERVAL", 60))

    print(f"\n{'=' * 60}")
    print(f"Testing MQTT connection to {broker_address}:{port_number}")
    print(f"Keepalive: {keep_alive_interval}s")
    print(f"{'=' * 60}\n")

    # Connect
    try:
        client.connect(broker_address, port_number, keep_alive_interval)
    except Exception as e:
        print(f"ERROR: Failed to connect - {e}")
        exit(1)

    # Start loop
    client.loop_start()

    print("Connection test running. Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(5)
            # Print status every 5 seconds
            print(
                f"[{time.strftime('%H:%M:%S')}] Status: {connection_count} connections, {disconnect_count} disconnects"
            )
    except KeyboardInterrupt:
        print("\n\nStopping test...")
        client.loop_stop()
        client.disconnect()

        print(f"\n{'=' * 60}")
        print("Test Summary:")
        print(f"  Total connections: {connection_count}")
        print(f"  Total disconnects: {disconnect_count}")
        print("  Expected disconnects for clean shutdown: 1")
        if disconnect_count > 1:
            print(f"  WARNING: Unexpected disconnects detected: {disconnect_count - 1}")
        else:
            print("  SUCCESS: Connection was stable")
        print(f"{'=' * 60}\n")
