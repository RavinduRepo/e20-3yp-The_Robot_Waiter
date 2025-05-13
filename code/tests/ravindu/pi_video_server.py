import asyncio
import websockets
import cv2
import base64
import numpy as np
from picamera2 import Picamera2
import time
import zlib

picam2 = Picamera2()
picam2.configure(picam2.create_video_configuration(main={"size": (640, 480)}))  # Lower resolution
picam2.start()

# Previous frame for motion detection
prev_frame = None

# Motion detection (to detect if there is a significant change in the frame)
def is_significant_change(prev_frame, current_frame):
    # Convert to grayscale and compute the difference
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    curr_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    
    # Compute absolute difference between the current and previous frame
    diff = cv2.absdiff(prev_gray, curr_gray)
    non_zero_count = np.count_nonzero(diff)

    # If there is significant change (more than 5% of the pixels changed)
    height, width = diff.shape
    total_pixels = height * width
    return non_zero_count > total_pixels * 0.05  # 5% change threshold

async def video_stream(websocket):  # Include 'path' parameter!
    print(f"[+] Client connected: {websocket.remote_address}")
    global prev_frame
    try:
        while True:
            frame = picam2.capture_array()

            # Skip frame if no significant change is detected
            if prev_frame is not None and not is_significant_change(prev_frame, frame):
                continue

            # JPEG compression (quality=80)
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            # Optional: Compress frame data further using zlib for more compression
            compressed_data = zlib.compress(buffer)

            # Convert compressed data to base64
            encoded = base64.b64encode(compressed_data).decode('utf-8')

            # Send encoded compressed data to the client
            await websocket.send(encoded)
            prev_frame = frame  # Update the previous frame for motion detection
            await asyncio.sleep(0.1)  # Lower frame rate to reduce bandwidth

    except websockets.exceptions.ConnectionClosed as e:
        print(f"[x] WebSocket closed: {e}")
    except Exception as e:
        print(f"[!] Error during stream: {e}")

async def main():
    server = await websockets.serve(video_stream, '0.0.0.0', 8765, compression=True)
    print("[*] WebSocket server started on ws://0.0.0.0:8765")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
