# ultrasonic_thread2.py
import RPi.GPIO as GPIO
import time
import multiprocessing
import signal
import sys

# GPIO pin pairs for two sensors: (TRIG, ECHO)
SENSORS = [(5, 6), (24, 25)]  # Sensor 1 (front), Sensor 2 (back)

# Global shutdown event
shutdown_event = multiprocessing.Event()

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n🛑 Ultrasonic sensor received signal {sig}, shutting down...")
    shutdown_event.set()
    cleanup_gpio()
    sys.exit(0)

def setup_gpio():
    """Setup GPIO pins for ultrasonic sensors"""
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        for trig, echo in SENSORS:
            GPIO.setup(trig, GPIO.OUT)
            GPIO.setup(echo, GPIO.IN)
        
        print("✅ Ultrasonic GPIO setup completed")
        return True
    except Exception as e:
        print(f"❌ Error setting up GPIO: {e}")
        return False

def cleanup_gpio():
    """Clean up GPIO resources"""
    try:
        GPIO.cleanup()
        print("✅ Ultrasonic GPIO cleanup completed")
    except Exception as e:
        print(f"⚠️ Error during GPIO cleanup: {e}")

def measure_single_sensor(trig_pin, echo_pin, sensor_id):
    """Measure distance for a single ultrasonic sensor"""
    try:
        # Trigger pulse
        GPIO.output(trig_pin, True)
        time.sleep(0.00001)  # 10 microseconds
        GPIO.output(trig_pin, False)

        # Wait for echo start
        pulse_start = time.time()
        timeout_start = pulse_start + 0.04  # 40ms timeout
        
        while GPIO.input(echo_pin) == 0 and time.time() < timeout_start:
            pulse_start = time.time()
        
        # If timeout occurred waiting for echo start
        if time.time() >= timeout_start:
            print(f"⚠️ Sensor {sensor_id} timeout waiting for echo start")
            return 400  # Return max distance on timeout

        # Wait for echo end
        pulse_end = time.time()
        timeout_end = pulse_end + 0.04  # 40ms timeout
        
        while GPIO.input(echo_pin) == 1 and time.time() < timeout_end:
            pulse_end = time.time()
        
        # If timeout occurred waiting for echo end
        if time.time() >= timeout_end:
            print(f"⚠️ Sensor {sensor_id} timeout waiting for echo end")
            return 400  # Return max distance on timeout

        # Calculate distance
        pulse_duration = pulse_end - pulse_start
        distance = (pulse_duration * 34300) / 2  # Speed of sound = 343 m/s
        
        # Clamp distance to reasonable values
        if distance < 2:
            distance = 2  # Minimum detectable distance
        elif distance > 400:
            distance = 400  # Maximum sensor range
        
        return distance
        
    except Exception as e:
        print(f"⚠️ Error measuring sensor {sensor_id}: {e}")
        return 100  # Return safe default distance

def measure_distance(shared_distances):
    """Main function to continuously measure distances from both sensors"""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("📏 Starting ultrasonic distance measurement...")
    
    # Setup GPIO
    if not setup_gpio():
        print("❌ Failed to setup GPIO for ultrasonic sensors")
        return
    
    measurement_count = 0
    error_count = [0, 0]  # Error count for each sensor
    max_errors = 10  # Maximum consecutive errors before declaring sensor dead
    
    try:
        while not shutdown_event.is_set():
            for i, (trig_pin, echo_pin) in enumerate(SENSORS):
                if shutdown_event.is_set():
                    break
                
                try:
                    distance = measure_single_sensor(trig_pin, echo_pin, i + 1)
                    
                    # Update shared distance array
                    shared_distances[i] = distance
                    
                    # Reset error count on successful measurement
                    error_count[i] = 0
                    
                    # Print distance every 20 measurements to reduce spam
                    if measurement_count % 20 == 0:
                        print(f"📏 Sensor {i+1} ({'Front' if i == 0 else 'Back'}): {distance:.2f} cm")
                    
                except Exception as e:
                    error_count[i] += 1
                    print(f"⚠️ Error measuring sensor {i+1}: {e} (Error count: {error_count[i]})")
                    
                    # If too many consecutive errors, set safe default distance
                    if error_count[i] >= max_errors:
                        print(f"❌ Sensor {i+1} appears to be malfunctioning, using default distance")
                        shared_distances[i] = 100  # Safe default distance
                        error_count[i] = 0  # Reset counter
                
                # Small delay between sensors to avoid interference
                if not shutdown_event.is_set():
                    time.sleep(0.05)
            
            measurement_count += 1
            
            # Longer delay between measurement cycles
            if not shutdown_event.is_set():
                time.sleep(0.1)
    
    except Exception as e:
        print(f"💥 Critical error in ultrasonic measurement: {e}")
    
    finally:
        print("🛑 Stopping ultrasonic distance measurement...")
        cleanup_gpio()
        print("✅ Ultrasonic sensor process terminated")

def test_sensors():
    """Test function to verify both sensors are working"""
    print("🧪 Testing ultrasonic sensors...")
    
    if not setup_gpio():
        return False
    
    try:
        for i, (trig_pin, echo_pin) in enumerate(SENSORS):
            print(f"Testing sensor {i+1} (TRIG: {trig_pin}, ECHO: {echo_pin})...")
            
            # Take 5 measurements
            distances = []
            for _ in range(5):
                distance = measure_single_sensor(trig_pin, echo_pin, i + 1)
                distances.append(distance)
                time.sleep(0.1)
            
            avg_distance = sum(distances) / len(distances)
            print(f"✅ Sensor {i+1} average distance: {avg_distance:.2f} cm")
            print(f"   Measurements: {[f'{d:.1f}' for d in distances]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Sensor test failed: {e}")
        return False
    
    finally:
        cleanup_gpio()

if __name__ == "__main__":
    # If run directly, perform sensor test
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_sensors()
    else:
        # Create shared memory for testing
        test_distances = multiprocessing.Array('d', [100.0, 100.0])
        measure_distance(test_distances)