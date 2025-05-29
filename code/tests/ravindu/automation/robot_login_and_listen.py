from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
import time
import websocket
import json

# WebSocket message handler
def on_message(ws, message):
    print("WebSocket message received:", message)

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed")

def on_open(ws):
    print("WebSocket connected")
    # Send a registration message (replace 'robot123' with the robot ID used in login)
    ws.send(json.dumps({"type": "register", "robotId": "robot123"}))

# Edge WebDriver setup
edge_options = EdgeOptions()
edge_options.add_argument("--headless")  # Run in headless mode
edge_options.add_argument("--disable-gpu")
edge_options.add_argument("--no-sandbox")

service = EdgeService("path/to/msedgedriver")  # Replace with the path to your Edge WebDriver
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
    websocket_url = "ws://localhost:3000"  # Replace with your WebSocket URL
    robot_auth_token = driver.execute_script("return localStorage.getItem('robotAuthToken');")

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
