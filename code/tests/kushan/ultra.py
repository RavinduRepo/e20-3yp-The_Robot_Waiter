import RPi.GPIO as GPIO
import time

# Define GPIO pins
TRIG = 23  # GPIO23 (Physical pin 16)
ECHO = 24  # GPIO24 (Physical pin 18)

# Setup GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def get_distance():
    print("Trying to measure distance...")

    # Ensure trigger is low initially
    GPIO.output(TRIG, False)
    time.sleep(0.1)  # Sensor stabilization time

    # Send a 10µs pulse to trigger the sensor
    GPIO.output(TRIG, True)
    time.sleep(0.00001)  # 10µs pulse
    GPIO.output(TRIG, False)

    # Wait for echo signal to start
    start_time = time.time()
    timeout_start = time.time()
    while GPIO.input(ECHO) == 0:
        start_time = time.time()
        if time.time() - timeout_start > 0.02:  # 20ms timeout
            print("Echo signal not received!")
            return -1

    # Wait for echo signal to end
    stop_time = time.time()
    timeout_start = time.time()
    while GPIO.input(ECHO) == 1:
        stop_time = time.time()
        if time.time() - timeout_start > 0.02:  # 20ms timeout
            print("Echo response took too long!")
            return -1

    # Calculate distance
    elapsed_time = stop_time - start_time
    distance = (elapsed_time * 34300) / 2  # Convert to cm

    return round(distance, 2)

try:
    while True:
        dist = get_distance()
        if dist != -1:  # Ignore invalid readings
            print(f"Distance: {dist} cm")
        else:
            print("Invalid reading, retrying...")

        time.sleep(0.5)  # Reduce CPU load and ensure sensor stability

except KeyboardInterrupt:
    print("\nMeasurement stopped by user")
    GPIO.cleanup()

