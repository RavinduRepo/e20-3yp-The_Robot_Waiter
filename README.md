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

---

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

| **Category**         | **Item**                 | **Description**                          | **Quantity** | **Unit Cost (LKR)** | **Total Cost (LKR)** |
|-----------------------|--------------------------|------------------------------------------|--------------|---------------------|-----------------------|
| **User Interaction**  | Camera Module           | Raspberry Pi Camera Module 3 (120°)     | 1            | 1800                | 1800                  |
|                       | Display                 | Touch Screen/Display                     | 1            | 3000                | 3000                  |
|                       | Mic                     | Mini USB Microphone for PC               | 2            | 1000                | 2000                  |
| **Power**             | Battery                 | 12V NiMH Battery Pack                    | 1            | 6000                | 6000                  |
|                       | Charger                 | Tenergy TN267 NiMH Charger               | 1            | 2500                | 2500                  |
| **Navigation**        | DC Motors               | N20 Gear Motor                           | 4            | 1200                | 4800                  |
|                       | Ultrasonic Sensor       | HC-SR04                                  | 3            | 500                 | 1500                  |
|                       | Gyroscope               | MPU-9250                                 | 1            | 1000                | 1000                  |
|                       | Wheels                  | Rubber Wheels                            | 4            | 400                 | 1600                  |
| **Processing Unit**   | Raspberry Pi 3 B+       | 1.4GHz 64-bit Quad-Core Processor        | 1            | 12000               | 12000                 |
|                       | ESP32                   | Type C Version                           | 1            | 1000                | 1000                  |
| **Total Cost**        |                          |                                           |              |                     | **36,200**            |

---

## Conclusion

The Robot Waiter project aims to revolutionize the hospitality industry by providing a practical, remotely controlled robot capable of efficient service. Future developments could include integrating AI for automation, enhancing the robot's scalability, and exploring commercialization opportunities.

---

## Links

- [Project Repository](https://github.com/cepdnaclk/eYY-3yp-The_Robot_Waiter){:target="_blank"}
- [Project Page](https://cepdnaclk.github.io/eYY-3yp-The_Robot_Waiter){:target="_blank"}
- [Department of Computer Engineering](http://www.ce.pdn.ac.lk/)
- [University of Peradeniya](https://eng.pdn.ac.lk/)
