# Internet Architecture Project

This project is a comprehensive simulation of an Internet-like network architecture implemented using Cisco Packet Tracer. It involves routing, addressing, VLAN segmentation, and inter-AS communication.  
Goal was Implementation of a complete network topology in Cisco Packet Tracer with multiple Autonomous Systems (ASes), IPv4/IPv6 addressing, routing (static, OSPF, EIGRP, RIP, BGP), and VLAN configuration.

## Network Topology Overview

The view below shows the overall network topology of the project to be developed in Cisco Packet Tracer

![Network Topology - Slika 1](doc/topology-overview-1.png)

This image shows the layout of the network in the project.

![AS 200nn Configuration - Slika 2](doc/topology-overview-2.png)

## 🔧 Tools & Technologies
- Cisco Packet Tracer
- Cisco 2901 Routers
- Cisco 2960 Switches
- IPv4 and IPv6 addressing
- Routing protocols: OSPF, EIGRP, RIP, BGP

## Network Design
- Autonomous Systems: AS 100nn, 200nn, 300nn, 400nn (ISP)
- IPv4 for all, IPv6 included only in AS 200nn
- VLANs for Development, Marketing, and Management
- Routing domains with internal and external routing protocols

## Project Structure

<!-- project-tree:start -->
<p>
<a href="https://github.com/LazarDavidovic98/internet-architecture-project" title="internet-architecture-project"><img src=".github/readme-tree/00.svg" alt="internet-architecture-project" align="top"></a><br>
<a href="https://github.com/LazarDavidovic98/internet-architecture-project/blob/main/src/ai-project.pkt" title="src/ai-project.pkt"><img src=".github/readme-tree/01.svg" alt="src/ai-project.pkt — Packet Tracer topology (open this)" align="top"></a><br>
<a href="https://github.com/LazarDavidovic98/internet-architecture-project/tree/main/doc" title="doc/"><img src=".github/readme-tree/02.svg" alt="doc/" align="top"></a><br>
<a href="https://github.com/LazarDavidovic98/internet-architecture-project/blob/main/doc/Documentation.md" title="doc/Documentation.md"><img src=".github/readme-tree/03.svg" alt="doc/Documentation.md — addressing, routing, design decisions" align="top"></a><br>
<a href="https://github.com/LazarDavidovic98/internet-architecture-project/blob/main/doc/Report.pdf" title="doc/Report.pdf"><img src=".github/readme-tree/04.svg" alt="doc/Report.pdf — final report" align="top"></a><br>
<a href="https://github.com/LazarDavidovic98/internet-architecture-project/blob/main/doc/topology-overview-1.png" title="doc/topology-overview-1.png"><img src=".github/readme-tree/05.svg" alt="doc/topology-overview-1.png — full topology" align="top"></a><br>
<a href="https://github.com/LazarDavidovic98/internet-architecture-project/blob/main/doc/topology-overview-2.png" title="doc/topology-overview-2.png"><img src=".github/readme-tree/06.svg" alt="doc/topology-overview-2.png — AS 200nn configuration" align="top"></a><br>
</p>

<sub>Every row is a link to that file or folder on GitHub. Purple: folders, green: source code, grey: configuration, data and docs.</sub>
<!-- project-tree:end -->

## How to Run
1. Open `ai-project` using Cisco Packet Tracer
2. Verify routing tables and interfaces
3. Use CLI for testing connectivity (`ping`, `traceroute`, etc.)

## 📄 Documentation
Detailed explanation of addressing, routing configuration and design decisions can be found in [Documentation](doc/Documentation.md)  
Final report for this project can be found in [Report](doc/Report.pdf)
