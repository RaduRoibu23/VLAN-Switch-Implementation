# VLAN-Switch-Implementation

The `switch.py` file is the main implementation of a VLAN-enabled switch. It uses Python to interact with the low-level networking library `dlink.so` and implements VLAN, Spanning Tree Protocol (STP), and MAC learning functionalities.

## Key Features

### 1. VLAN Tagging and Trunking
- Handles VLAN-tagged frames.
- Differentiates between access and trunk ports.
- Implements functions for adding and stripping VLAN tags:
  - `create_vlan_tag(vlan_id)`
  - Tagging logic for forwarding on trunk ports or removing tags for access ports.

### 2. MAC Learning
- Dynamically builds a MAC address table by observing the source MAC address of incoming frames.
- Uses this table to determine the correct forwarding port for known destinations.

### 3. Spanning Tree Protocol (STP)
- Sends Bridge Protocol Data Units (BPDUs) periodically to maintain a loop-free topology.
- Implements a basic root bridge election mechanism and root port selection.
- Manages interface states (active/blocking) based on STP decisions.

### 4. Packet Forwarding
- Implements two types of forwarding:
  - **Access Forwarding**: Ensures VLAN tags are stripped when frames are sent to access ports.
  - **Trunk Forwarding**: Retains VLAN tags when forwarding frames to trunk ports.
- Broadcasts frames to all appropriate interfaces if the destination MAC is unknown.

### 5. Configuration Parsing
- Reads the switch configuration file (`configs/switchX.cfg`) to set up:
  - VLAN assignments for each interface.
  - Initial bridge ID for STP.

### 6. Multithreading
- Runs a separate thread to send BPDUs every second using the `send_bdpu_every_sec` function.

## Important Functions
- `init_resources()`: Initializes VLAN and STP settings based on the configuration file.
- `parse_ethernet_header(data)`: Extracts MAC addresses, EtherType, and VLAN ID from Ethernet frames.
- `main()`: Core loop that receives frames, processes them, and determines the appropriate forwarding behavior.

## Notes
- The code includes handling for special cases such as untagged frames and STP BPDUs.
- VLAN and STP logic is tightly integrated with the interface's operational state.

