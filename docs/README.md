---
layout: home
permalink: index.html

repository-name: eYY-3yp-The_Robot_Waiter
title: The Robot Waiter
---

[comment]: # "This is the standard layout for the project, but you can clean this and use your own template"

# Robot Waiter

---

## Team
-  E/20/100, A.I. Fernando, [email](mailto:e20100@eng.pdn.ac.lk)
-  E/20/243, K.M.K.Malintha, [email](mailto:e20243@eng.pdn.ac.lk)
-  E/20/280, R.S.Pathirage, [email](mailto:e20280@eng.pdn.ac.lk)
-  E/20/434, Wickramaarachchi P.A. [email](mailto:e20434@eng.pdn.ac.lk)

#### Table of Contents
1. [Introduction](#introduction)
2. [Solution Architecture](#solution-architecture )
3. [Hardware & Software Designs](#hardware-and-software-designs)
4. [Testing](#testing)
5. [Detailed budget](#detailed-budget)
6. [Conclusion](#conclusion)
7. [Links](#links)

## Introduction

In the fast-paced restaurant industry, ensuring quick and efficient service is crucial. Traditional waiter systems face challenges such as delays, human errors, and high labor costs. Our project, "The Robot Waiter," aims to solve these issues by introducing a remotely controlled robot that can deliver orders to customers efficiently. Unlike fully automated systems, this robot offers a balance of human oversight and robotic precision, making it adaptable to dynamic environments.

The impact of this solution includes improved service efficiency, reduced labor dependency, and an enhanced customer experience. By leveraging online control systems, restaurants can operate the robot with minimal training and flexibility, even in complex layouts.

## Solution Architecture

The solution architecture integrates hardware and software components to create a seamless robot waiter system. Below is an overview of the architecture:

### High- Level Diagram
![image](https://github.com/user-attachments/assets/e8c0fe2f-16e6-4dbd-867d-3b828d4a6563)

### Description

1. **Controller App:** A web application allows users to control the robot's movements and tasks remotely. The app communicates with the cloud server to relay commands and receive feedback.
2. **Cloud Server:** Acts as the central communication hub between the controller app and the robot. It processes commands, manages data, and ensures secure communication.
3. **Robot Control Unit:** The onboard microcontroller in the robot executes commands received from the cloud server. It manages the movement and interaction of sensors and motors.
4. **Sensors & Motors:** The robot is equipped with sensors for obstacle detection and motors for smooth navigation. These components ensure the robot can operate safely in a busy restaurant environment.

This architecture ensures the robot can be controlled reliably via the internet, providing real-time adaptability and scalability for various restaurant needs.

## Hardware and Software Designs

Detailed designs with many sub-sections.

## Testing

### Hardware Testing

We conducted individual tests for each sensor to ensure proper functionality:

- **Camera Module:** Verified video streaming capability using IoT Core, ensuring real-time image capture and transmission to the frontend.
- **Ultrasonic Sensors:** Tested distance measurement accuracy, sending real-time obstacle data via AWS IoT Core.
- **Gyroscope Sensor:** Evaluated motion tracking and orientation updates, integrating it with IoT Core for real-time monitoring in the frontend.

### Software Testing

- **MQTT on AWS IoT Core:** Verified stable communication between the robot and the frontend by configuring MQTT publishers (robot commands) and subscribers (robot status updates).
- **AWS Cognito Authentication:** Tested the ability to gain temporary access tokens for the React frontend, reducing the need for constant requests through our Node.js server. This enhances efficiency while ensuring secure access control.
- **WebSockets Integration:** Ensured real-time data exchange between the frontend and the robot, improving response times and interaction reliability.

## Detailed budget

| Item                | Description                          | Quantity | Unit Cost (LKR) | Total Cost (LKR) |
|---------------------|--------------------------------------|----------|-----------------|-----------------|
| **User Interaction**|                                      |          |                 |                 |
| Camera Module       | Raspberry Pi Camera Module 1 | 1        | 1800            | 1800            |
| Display             | Touch Screen / Display              | 1        | 3000            | 3000            |
| Mic                 | Mini USB Microphone for PC          | 2        | 1000            | 2000            |
| **Power**           |                                      |          |                 |                 |
| Battery             | 12V NiMH Battery Pack               | 1        | 6000            | 6000            |
| Charger             | Tenergy TN267 NiMH Charger          | 1        | 2500            | 2500            |
| **Navigation**      |                                      |          |                 |                 |
| DC Motors           | N20 Gear Motor                      | 4        | 1200            | 4800            |
| Ultrasonic Sensor   | HC-SR04                             | 3        | 500             | 1500            |
| Gyroscope           | MPU-6050                            | 1        | 1000            | 1000            |
| Wheels              | Rubber Wheels                       | 4        | 400             | 1600            |
| **Processing Unit** |                                      |          |                 |                 |
| Raspberry Pi 3 B+   | 1.4GHz 64-bit Quad-Core Processor   | 1        | 12000           | 12000           |
| ESP32               | Type C Version                      | 1        | 1000            | 1000            |
|                     |                                      |          |                 | **36200**       |

## Conclusion

What was achieved, future developments, commercialization plans.

## Links

- [Main Repository (Raspberry Pi Code)](https://github.com/cepdnaclk/e20-3yp-The_Robot_Waiter)
- [Employee Backend (Node.js)](https://github.com/kushanmalintha/3YP_RW_employee-_backend)
- [Employee Interface (React)](https://github.com/kushanmalintha/3YP_RW_employee_interface)
- [Kitchen Backend (Node.js)](https://github.com/E20434/3YP_RW_kitchen_backend)
- [Kitchen Interface (React)](https://github.com/AIFERNANDOE20100/3YP_RW_kitchen_interface)
- [Department of Computer Engineering](http://www.ce.pdn.ac.lk/)
- [University of Peradeniya](https://eng.pdn.ac.lk/)

[//]: # (Please refer this to learn more about Markdown syntax)
[//]: # (https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet)
