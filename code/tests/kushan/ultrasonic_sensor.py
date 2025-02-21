import RPi.GPIO as GPIO
import time

# Define GPIO pins
TRIG = 33  # GPIO23
ECHO = 35  # GPIO24

# Setup GPIO mode
GPIO.setmode(GPIO.BCM)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)

def get_distance():
    # Send a 10µs pulse to trigger the sensor
    GPIO.output(TRIG, True)
    time.sleep(0.00001)  # 10µs pulse
    GPIO.output(TRIG, False)

    # Measure the time for echo signal
    start_time = time.time()
    stop_time = time.time()

    while GPIO.input(ECHO) == 0:
        start_time = time.time()

    while GPIO.input(ECHO) == 1:
        stop_time = time.time()

    # Calculate distance (Speed of sound = 34300 cm/s)
    elapsed_time = stop_time - start_time
    distance = (elapsed_time * 34300) / 2  # Convert to cm

    return round(distance, 2)

try:
    while True:
        dist = get_distance()
        print(f"Distance: {dist} cm")
        time.sleep(1)  # Wait before next measurement

except KeyboardInterrupt:
    print("\nMeasurement stopped by user")
    GPIO.cleanup()

