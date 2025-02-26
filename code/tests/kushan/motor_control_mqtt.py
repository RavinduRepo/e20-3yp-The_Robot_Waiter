import RPi.GPIO as GPIO
import time
import paho.mqtt.client as mqtt

# Define GPIO pins
IN1 = 17  # GPIO 17 (Pin 11)
IN2 = 27  # GPIO 27 (Pin 13)

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)

# Function to move motor forward
def motor_forward():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)

# Function to stop motor
def motor_stop():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)

# MQTT callback when connection is established
def on_connect(client, userdata, flags, rc):
    print("Connected to AWS IoT Core with result code " + str(rc))
    # Subscribe to the topic
    client.subscribe("3YP/batch2025/device1")  # Replace with your actual topic

# MQTT callback when a message is received
def on_message(client, userdata, msg):
    print(f"Message received: {msg.payload.decode()}")
    message = msg.payload.decode()

    if message == '{"key":"ArrowUp"}':
        print("Moving motor forward")
        motor_forward()
    else:
        motor_stop()
        print("Motor stopped")

# MQTT client setup
client = mqtt.Client()

# Set up AWS IoT Core credentials using certificates
client.tls_set(ca_certs="../../cert/AmazonRootCA1.pem",
               certfile="../../cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-certificate.pem.crt",
               keyfile="../../cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-private.pem.key")  # Provide paths to your certificates and key

client.on_connect = on_connect
client.on_message = on_message

# Connect to AWS IoT Core
client.connect("a2cdp9hijgdiig-ats.iot.ap-southeast-2.amazonaws.com", 8883, 60)

# Start the MQTT client loop
try:
    print("Starting MQTT client loop...")
    client.loop_start()  # Start the loop to receive messages
    while True:
        time.sleep(1)  # Keep the program running to listen for messages
finally:
    motor_stop()  # Stop the motor before cleanup
    GPIO.cleanup()
    client.loop_stop()  # Stop the MQTT loop
    print("Motor stopped and GPIO cleaned up.")
