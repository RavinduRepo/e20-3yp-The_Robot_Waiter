from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
import time
import websocket
import json
import os

def store_data_locally(data):
    try:
        with open("websocket_data.json", "w") as file:
            json.dump(data, file)
        print("WebSocket data stored locally")
    except Exception as e:
        print("Error storing WebSocket data locally:", e)

def get_data_locally():
    try:
        if os.path.exists("websocket_data.json"):
            with open("websocket_data.json", "r") as file:
                return json.load(file)
        else:
            print("No local WebSocket data found")
            return None
    except Exception as e:
        print("Error retrieving WebSocket data locally:", e)
        return None

# WebSocket message handler
def on_message(ws, message):
    print("WebSocket message received:", message)
    try:
        data = json.loads(message)
        store_data_locally(data)  # Store data locally
        if data.get("type") == "auth":
            print(f"Auth token received: {data.get('idToken')}")
    except json.JSONDecodeError:
        print("Failed to decode WebSocket message")

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connected")
    # Send a registration message with the robot ID
    ws.send(json.dumps({"type": "register", "robotId": "ROBOwfyN"}))  # Replace with your Robot ID

# Edge WebDriver setup
edge_options = EdgeOptions()
edge_options.add_argument("--disable-gpu")
edge_options.add_argument("--no-sandbox")

service = EdgeService("C:/Users/ravin/Downloads/edgedriver_win64/msedgedriver.exe")  
driver = webdriver.Edge(service=service, options=edge_options)

try:
    # Navigate to the login page
    driver.get("http://localhost:5001/robot-login")
    time.sleep(2)  # Wait for the page to load

    # Enter Robot ID
    robot_id_input = driver.find_element(By.XPATH, "//input[@placeholder='Robot ID']")
    robot_id_input.send_keys("ROBOwfyN")  # Replace with your Robot ID

    # Enter Password
    password_input = driver.find_element(By.XPATH, "//input[@placeholder='Password']")
    password_input.send_keys("ROBOiYAL")  # Replace with your Password

    # Submit the login form
    password_input.send_keys(Keys.RETURN)
    time.sleep(5)  # Wait for login to complete

    # Retrieve the WebSocket URL and token from localStorage
    websocket_url = "ws://localhost:3000"  # WebSocket server URL
    robot_auth_token = None
    for _ in range(10):  # wait up to 10 seconds
        robot_auth_token = driver.execute_script("return localStorage.getItem('robotAuthToken');")
        if robot_auth_token:
            break
        time.sleep(1)


    if robot_auth_token:
        print("Login successful. Auth token:", robot_auth_token)

        # Connect to WebSocket
        ws = websocket.WebSocketApp(
            websocket_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.on_open = on_open
        ws.run_forever()
    else:
        print("Login failed or WebSocket token not found.")

finally:
    driver.quit()
