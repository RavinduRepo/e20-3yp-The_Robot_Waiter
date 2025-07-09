# The Robot Waiter

---

## Team
- E/20/100, A.I. Fernando, [email](mailto:e20100@eng.pdn.ac.lk)
- E/20/243, K.M.K. Malintha, [email](mailto:e20243@eng.pdn.ac.lk)
- E/20/280, R.S. Pathirage, [email](mailto:e20280@eng.pdn.ac.lk)
- E/20/434, Wickramaarachchi P.A., [email](mailto:e20434@eng.pdn.ac.lk)

---

#### Table of Contents
1. [Introduction](#introduction)
2. [Solution Architecture](#solution-architecture)
3. [Hardware & Software Designs](#hardware-and-software-designs)
4. [Testing](#testing)
5. [Detailed Budget](#detailed-budget)
6. [Conclusion](#conclusion)
7. [Links](#links)

---

## Introduction

The Robot Waiter is a remotely controlled service robot designed to assist in the food and beverage industry. It operates via online connectivity, providing efficient delivery of items to customers without the need for automation. This solution bridges the gap between traditional manual service and fully automated systems, offering flexibility, cost-effectiveness, and ease of use.

![image](https://github.com/user-attachments/assets/3c92a44e-e214-4f95-afcb-72a33cf19e14)

---

# step by step

##  🧠 Step 1: Understand the Roles in the System
There are three main players in this system:

Admin – The boss. Controls everything.

Employee – Waiters or staff who control the robots.

Robot – The actual robot that does tasks (like delivering food).

##  🏗 Step 2: What the System is Made Of (Architecture)
The system is made of different parts that talk to each other:

A cloud database (Firebase) to store information.

A messaging system (AWS MQTT) to send robot commands.

A robot backend program (on Raspberry Pi) that listens and acts.

A web interface for employees and admin to log in and control things.

A temporary communication channel (WebSocket) used once to share robot info.

##  🔐 Step 3: Admin Sets Up the System
What Admin Can Do:
Signs up to the system (using email/password).

Adds employees – gives each one a username and password.

Registers new robots into the system (each gets a unique ID).

Sees a dashboard of robots and employees.

✅ After this, the system is ready to be used.

## 👨‍🍳 Step 4: Employee Logs In
Employee goes to the website.

Logs in using the credentials given by the Admin.

Can now see a list of available robots.

##  🤖 Step 5: Robot is Powered On and Connects to Backend
When a robot is turned on:

The robot backend program (in Python) starts running on the robot.

It waits for a message from the cloud using AWS MQTT on the topic /connect.

It does nothing until an employee selects it.

##  📱 Step 6: Employee Selects a Robot
From their interface, the employee selects a robot from the list.

The selected robot's ID is sent to AWS MQTT to a special channel: /connect.

##  🔁 Step 7: Robot Backend Receives the Connection Request
The robot:

Was listening to the /connect channel.

Now sees a message with its ID.

Once it sees this, it starts a WebSocket connection with the robot’s frontend interface.

##  🌐 Step 8: Robot Shares Its Info Temporarily via WebSocket
The robot and its frontend:

Can’t talk directly, so they use a WebSocket tunnel (temporary).

Through this tunnel, the robot shares its details (status, availability, etc.).

These details go to the Firebase database.

##  🔚 Step 9: WebSocket is Closed
After sharing its info, the WebSocket is closed.

From now on, Firebase stores the robot data.

Backend no longer talks to the frontend directly.

##  📡 Step 10: System Enters Communication Mode (Live Control)
Now everything is set up for real-time control:

Robot:
Subscribes to a channel like robot/123/commands via AWS MQTT.

Waits for commands like “move forward”, “turn left”, etc.

Employee:
Is also connected to AWS MQTT.

Sends commands to the robot by publishing to the same topic (robot/123/commands).

This is how they “talk” to each other.

##  🔁 Step 11: Real-Time Interaction
Employee presses buttons on their interface (like a remote).

Each button sends a command through AWS MQTT.

Robot receives the command and moves accordingly.

##  🔄 Step 12: Repeat as Needed
The robot can update its status to Firebase.

Admin or employee can monitor it.

If a new robot is added, admin registers it again and the same process happens.

## Solution Architecture

The system's architecture integrates the following components:

- **User Interaction**: Users interact with the robot via an online platform, utilizing camera modules and touch displays for real-time feedback.
- **Navigation System**: Powered by DC motors, ultrasonic sensors, and a gyroscope for precise movement and obstacle detection.
- **Power System**: A 12V NiMH battery with a compatible charger ensures sustainable energy for operation.
- **Processing Unit**: The Raspberry Pi 3 B+ and ESP32 microcontroller handle computations and communication, ensuring seamless control.
- **Online Connectivity**: The robot leverages web-based control, allowing users to operate it from a remote location.

---

## Hardware and Software Designs

Detailed designs for the hardware and software components will include:
- Schematics for hardware assembly.
- Software modules for navigation, user interface, and connectivity.
- Integration between Raspberry Pi, ESP32, and sensors.

---

## Testing

Comprehensive testing of both hardware and software components:
- Navigation accuracy and obstacle detection.
- Responsiveness of user controls via the online interface.
- Battery performance under varying workloads.

---

## Detailed Budget

| **Category**         | **Item**                 | **Description**                            | **Quantity** | **Unit Cost (LKR)** | **Total Cost (LKR)** |
|---------------------|--------------------------|--------------------------------------------|--------------|---------------------|-----------------------|
| **User Interaction**| Camera Module            | Raspberry Pi Camera Module 1               | 1            | 1800                | 1800                  |
|                     | Display                  | HDMI Display                               | 1            | 6000                | 6000                  |
| **Power System**    | Battery                  | 12V UPS Battery                            | 1            | 5000                | 5000                  |
|                     | Charger                  | 12V Charger                                | 1            | 2500                | 2500                  |
|                     | Buck Converter           | 12V to 5V Converter                        | 1            | 150                 | 150                   |
| **Navigation**      | Motors                   | JGB 520 100 RPM Gear Motors                | 4            | 1390                | 5560                  |
|                     | Wheels                   | Rubber Wheels                              | 4            | 190                 | 760                   |
|                     | Ultrasonic Sensors       | HC-SR04                                    | 2            | 500                 | 1000                  |
| **Structure**       | Tray Frame               | Aluminium Frame                            | 1            | 2000                | 2000                  |
|                     | Chassis                  | Wooden Chassis + Assembly Cost             | 1            | 1000                | 1000                  |
|                     | Lathe Works              | Axle Lathe Processing                      | 4            | 600                 | 2400                  |
| **Processing Unit** | Raspberry Pi 3 B         | 1.4GHz 64-bit Quad-Core Processor          | 1            | 20000               | 20000                 |

|                     |                          |                                            |              |                     | **Total: 49,970 LKR** |

---



## Conclusion

The Robot Waiter project aims to revolutionize the hospitality industry by providing a practical, remotely controlled robot capable of efficient service. Future developments could include integrating AI for automation, enhancing the robot's scalability, and exploring commercialization opportunities.

---

## Links

- [Main Repository (Raspberry Pi Code)](https://github.com/cepdnaclk/e20-3yp-The_Robot_Waiter)
- [Employee Backend (Node.js)](https://github.com/kushanmalintha/3YP_RW_employee-_backend)
- [Employee Interface (React)](https://github.com/kushanmalintha/3YP_RW_employee_interface)
- [Kitchen Backend (Node.js)](https://github.com/E20434/3YP_RW_kitchen_backend)
- [Kitchen Interface (React)](https://github.com/AIFERNANDOE20100/3YP_RW_kitchen_interface)
- [Department of Computer Engineering](http://www.ce.pdn.ac.lk/)
- [University of Peradeniya](https://eng.pdn.ac.lk/)
- [Project Page](https://cepdnaclk.github.io/eYY-3yp-The_Robot_Waiter){:target="_blank"}
- [Department of Computer Engineering](http://www.ce.pdn.ac.lk/)
- [University of Peradeniya](https://eng.pdn.ac.lk/)
