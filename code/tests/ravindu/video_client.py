import asyncio
import websockets
import cv2
import base64
import numpy as np

async def receive_video():
    uri = "ws://192.168.8.139:8765"  # Replace with Pi's IP
    async with websockets.connect(uri) as websocket:
        while True:
            try:
                data = await websocket.recv()
                jpg_original = base64.b64decode(data)
                np_arr = np.frombuffer(jpg_original, dtype=np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                cv2.imshow("WebSocket Video Feed", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except Exception as e:
                print(f"Error: {e}")
                break
    cv2.destroyAllWindows()

asyncio.get_event_loop().run_until_complete(receive_video())
