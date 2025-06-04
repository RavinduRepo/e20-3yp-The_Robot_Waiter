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
