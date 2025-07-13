# aruco_server.py
import asyncio
import websockets
import json
import cv2
import numpy as np
import base64
import pickle
import math
import time
from io import BytesIO
from PIL import Image

class ArUcoWebSocketServer:
    def __init__(self, calibration_file="camera_calibration.pkl",
                 dictionary_type=cv2.aruco.DICT_6X6_250, marker_size=100.0):
        """
        Initialize ArUco WebSocket server

        Args:
            calibration_file: path to camera calibration file
            dictionary_type: ArUco dictionary type
            marker_size: actual size of markers in mm
        """
        self.dictionary_type = dictionary_type
        self.marker_size = marker_size
        self.connected_clients = set()

        # Load camera calibration
        self.load_calibration(calibration_file)

        # Create ArUco dictionary and detector parameters
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(dictionary_type)
        self.detector_params = cv2.aruco.DetectorParameters()

        # Optimize detector parameters for better detection
        self.detector_params.adaptiveThreshWinSizeMin = 3
        self.detector_params.adaptiveThreshWinSizeMax = 23
        self.detector_params.adaptiveThreshWinSizeStep = 10
        self.detector_params.adaptiveThreshConstant = 7
        self.detector_params.minMarkerPerimeterRate = 0.03
        self.detector_params.maxMarkerPerimeterRate = 4.0
        self.detector_params.polygonalApproxAccuracyRate = 0.03
        self.detector_params.minCornerDistanceRate = 0.05
        self.detector_params.minDistanceToBorder = 3
        self.detector_params.minMarkerDistanceRate = 0.05

        # Create detector
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.detector_params)

        # Statistics
        self.frame_count = 0
        self.detection_count = 0
        self.start_time = time.time()

        print("ArUco WebSocket Server initialized")
        print(f"Dictionary: {dictionary_type}")
        print(f"Marker size: {marker_size}mm")
        print(f"Calibrated: {self.calibrated}")

    def load_calibration(self, calibration_file):
        """Load camera calibration parameters"""
        try:
            with open(calibration_file, 'rb') as f:
                calibration_data = pickle.load(f)

            self.camera_matrix = calibration_data['camera_matrix']
            self.dist_coeffs = calibration_data['dist_coeffs']
            self.calibrated = True
            print(f"Camera calibration loaded from: {calibration_file}")

        except FileNotFoundError:
            print(f"Calibration file not found: {calibration_file}")
            print("Running without calibration - distance measurements will be inaccurate")
            self.camera_matrix = None
            self.dist_coeffs = None
            self.calibrated = False

    def base64_to_image(self, base64_string):
        """Convert base64 string to OpenCV image"""
        try:
            # Remove data URL prefix if present
            if base64_string.startswith('data:image'):
                base64_string = base64_string.split(',')[1]

            # Decode base64
            image_data = base64.b64decode(base64_string)

            # Convert to PIL Image
            pil_image = Image.open(BytesIO(image_data))

            # Convert to OpenCV format
            opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

            return opencv_image

        except Exception as e:
            print(f"Error converting base64 to image: {e}")
            return None

    def detect_markers(self, frame):
        """Detect ArUco markers in frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, rejected = self.detector.detectMarkers(gray)
        return corners, ids, rejected

    def estimate_pose(self, corners, ids):
        """Estimate pose of detected markers"""
        if not self.calibrated or ids is None:
            return None, None

        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners, self.marker_size, self.camera_matrix, self.dist_coeffs)

        return rvecs, tvecs

    def calculate_distance_and_orientation(self, rvec, tvec):
        """Calculate distance and orientation from pose vectors"""
        distance = np.linalg.norm(tvec)

        rmat, _ = cv2.Rodrigues(rvec)

        sy = math.sqrt(rmat[0, 0] * rmat[0, 0] + rmat[1, 0] * rmat[1, 0])

        singular = sy < 1e-6

        if not singular:
            roll = math.atan2(rmat[2, 1], rmat[2, 2])
            pitch = math.atan2(-rmat[2, 0], sy)
            yaw = math.atan2(rmat[1, 0], rmat[0, 0])
        else:
            roll = math.atan2(-rmat[1, 2], rmat[1, 1])
            pitch = math.atan2(-rmat[2, 0], sy)
            yaw = 0

        roll_deg = math.degrees(roll)
        pitch_deg = math.degrees(pitch)
        yaw_deg = math.degrees(yaw)

        return distance, (roll_deg, pitch_deg, yaw_deg)

    def calculate_centering_metrics(self, marker_center, frame_shape):
        """Calculate how centered a marker is from the frame center"""
        frame_height, frame_width = frame_shape[:2]
        frame_center_x = frame_width // 2
        frame_center_y = frame_height // 2

        offset_x = marker_center[0] - frame_center_x
        offset_y = marker_center[1] - frame_center_y

        distance_from_center = math.sqrt(offset_x**2 + offset_y**2)
        max_distance = math.sqrt(frame_center_x**2 + frame_center_y**2)

        centering_percentage = max(0, 100 - (distance_from_center / max_distance) * 100)
        horizontal_centering = max(0, 100 - (abs(offset_x) / frame_center_x) * 100)
        vertical_centering = max(0, 100 - (abs(offset_y) / frame_center_y) * 100)

        direction = ""
        if abs(offset_x) > 10:
            direction += "Right" if offset_x > 0 else "Left"
        if abs(offset_y) > 10:
            direction += "Bottom" if offset_y > 0 else "Top"
        if not direction:
            direction = "Centered"

        return {
            'offset_x': int(offset_x), # Ensure int type
            'offset_y': int(offset_y), # Ensure int type
            'distance_from_center': float(distance_from_center), # Ensure float
            'centering_percentage': float(centering_percentage), # Ensure float
            'horizontal_centering': float(horizontal_centering), # Ensure float
            'vertical_centering': float(vertical_centering), # Ensure float
            'direction': direction,
            'frame_center': (int(frame_center_x), int(frame_center_y)) # Ensure int type
        }

    def process_frame(self, frame):
        print("Processing frame for ArUco markers...")
        """Process a frame and detect ArUco markers"""
        self.frame_count += 1

        # Detect markers
        corners, ids, rejected = self.detect_markers(frame)

        detection_results = []

        if ids is not None:
            self.detection_count += 1

            # Estimate pose
            rvecs, tvecs = self.estimate_pose(corners, ids)

            for i in range(len(ids)):
                # Ensure marker_center elements are Python ints
                marker_center = np.mean(corners[i][0], axis=0).astype(int)
                centering_metrics = self.calculate_centering_metrics(marker_center, frame.shape)

                marker_result = {
                    'id': int(ids[i][0]), # Ensure int type
                    'center': [int(marker_center[0]), int(marker_center[1])], # Ensure int types
                    'centering_percentage': centering_metrics['centering_percentage'],
                    'horizontal_centering': centering_metrics['horizontal_centering'],
                    'vertical_centering': centering_metrics['vertical_centering'],
                    'direction': centering_metrics['direction'],
                    'offset_x': centering_metrics['offset_x'],
                    'offset_y': centering_metrics['offset_y']
                }

                if self.calibrated and rvecs is not None and tvecs is not None:
                    distance, angles = self.calculate_distance_and_orientation(rvecs[i], tvecs[i])
                    roll, pitch, yaw = angles

                    marker_result.update({
                        'distance_mm': float(distance), # Ensure float type
                        'roll_deg': float(roll),       # Ensure float type
                        'pitch_deg': float(pitch),     # Ensure float type
                        'yaw_deg': float(yaw)          # Ensure float type
                    })

                detection_results.append(marker_result)

                # Print to console
                if self.calibrated and rvecs is not None:
                    print(f"Marker ID {ids[i][0]}: Distance={distance:.1f}mm, "
                          f"Roll={roll:.1f}°, Pitch={pitch:.1f}°, Yaw={yaw:.1f}°, "
                          f"Centering={centering_metrics['centering_percentage']:.1f}%, "
                          f"Direction={centering_metrics['direction']}")
                else:
                    print(f"Marker ID {ids[i][0]}: Centering={centering_metrics['centering_percentage']:.1f}%, "
                          f"Direction={centering_metrics['direction']}")

        return detection_results

    def get_statistics(self):
        """Get processing statistics"""
        elapsed_time = time.time() - self.start_time
        fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0
        detection_rate = (self.detection_count / self.frame_count * 100) if self.frame_count > 0 else 0

        return {
            'frames_processed': int(self.frame_count), # Ensure int type
            'detections': int(self.detection_count),   # Ensure int type
            'fps': float(fps),                         # Ensure float type
            'detection_rate': float(detection_rate),   # Ensure float type
            'elapsed_time': float(elapsed_time)        # Ensure float type
        }

    async def handle_client(self, websocket):
        """Handle WebSocket client connection - FIXED: removed path parameter"""
        self.connected_clients.add(websocket)
        client_addr = websocket.remote_address
        # print(f"Client connected: {client_addr}")

        try:
            # print(f"Handling client {client_addr}")
            # Send connection confirmation
            await websocket.send(json.dumps({
                'type': 'status',
                'message': 'Connected to ArUco detection server'
            }))
            # print(f"Connection confirmation sent to {client_addr}")

            async for message in websocket:
                # print(f"Received message from {client_addr}: {message}")
                try:
                    data = json.loads(message)

                    if data['type'] == 'frame':
                        # Process frame
                        frame = self.base64_to_image(data['data'])

                        if frame is not None:
                            detection_results = self.process_frame(frame)

                            # Send detection results back
                            response = {
                                'type': 'detection_result',
                                'markers_count': len(detection_results),
                                'markers': detection_results,
                                'statistics': self.get_statistics()
                            }

                            await websocket.send(json.dumps(response))
                        else:
                            await websocket.send(json.dumps({
                                'type': 'error',
                                'message': 'Failed to process frame'
                            }))

                    elif data['type'] == 'get_stats':
                        # Send statistics
                        await websocket.send(json.dumps({
                            'type': 'statistics',
                            'data': self.get_statistics()
                        }))

                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': 'Invalid JSON message'
                    }))

                except Exception as e:
                    print(f"Error processing message: {e}")
                    await websocket.send(json.dumps({
                        'type': 'error',
                        'message': str(e)
                    }))

        except websockets.exceptions.ConnectionClosed:
            print(f"Client disconnected: {client_addr}")

        except Exception as e:
            print(f"Error handling client {client_addr}: {e}")

        finally:
            self.connected_clients.discard(websocket)

    async def start_server(self, host='localhost', port=8765):
        """Start the WebSocket server"""
        print(f"Starting ArUco WebSocket server on {host}:{port}")

        async with websockets.serve(self.handle_client, host, port):
            print("Server started. Waiting for connections...")
            print("Press Ctrl+C to stop the server")

            try:
                await asyncio.Future()  # Run forever
            except KeyboardInterrupt:
                print("\nServer stopped by user")

def main():
    """Main function to run the ArUco WebSocket server"""
    server = ArUcoWebSocketServer(
        calibration_file="camera_calibration.pkl",
        dictionary_type=cv2.aruco.DICT_6X6_250,
        marker_size=50.0  # Adjust this to your actual marker size in mm
    )

    # Start the server
    asyncio.run(server.start_server())

if __name__ == "__main__":
    main()