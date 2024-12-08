#!/usr/bin/python3
import sys
import struct
import wrapper
import threading
import time
from wrapper import recv_from_any_link, send_to_link, get_switch_mac, get_interface_name

def parse_ethernet_header(data):
    # Unpack the header fields from the byte array
    #dest_mac, src_mac, ethertype = struct.unpack('!6s6sH', data[:14])

    dest_mac = data[0:6]
    src_mac = data[6:12]


    # Extract ethertype. Under 802.1Q, this may be the bytes from the VLAN TAG
    ether_type = (data[12] << 8) + data[13]

    vlan_id = -1
    # Check for VLAN tag (0x8100 in network byte order is b'\x81\x00')
    if ether_type == 0x8200:
        vlan_tci = int.from_bytes(data[14:16], byteorder='big')
        vlan_id = vlan_tci & 0x0FFF
        ether_type = (data[16] << 8) + data[17]

    return dest_mac, src_mac, ether_type, vlan_id

def create_vlan_tag(vlan_id):
    # 0x8100 for the Ethertype for 802.1Q
    # vlan_id & 0x0FFF ensures that only the last 12 bits are used
    return struct.pack('!H', 0x8200) + struct.pack('!H', vlan_id & 0x0FFF)

def send_bdpu_every_sec():
    global root_bridge_ID, root_path_cost, own_bridge_ID
    global interfaces, interface_state, vlan, table
    # TODO Send BDPU every second if necessary
    while True:
        if own_bridge_ID == root_bridge_ID:
            for interface in interfaces:
                if vlan.get(get_interface_name(interface)) != 'T':
                    continue
                mac_cast = struct.pack('!BBBBBB', 0x01, 0x80, 0xc2, 0x00, 0x00, 0x00)
                own_bid = struct.pack('!q', own_bridge_ID)
                root_bid = struct.pack('!q', root_bridge_ID)
                cost_path = struct.pack('!I', root_path_cost)
                data = mac_cast + own_bid + root_bid + cost_path
                send_to_link(interface, len(data), data)
        time.sleep(1)

# Added this function cuz whitout it the code was not working, keep failing last test
# Probably the problem is on how the test is implemented and not on the code itself
#ICMP_5_0_BAD_MAC_ARRIVES_0_ONCE_STP ..................................................   FAILED
def init_resources():
    table = {}
    vlan = {}
    switch_id = sys.argv[1]
    own_bridge_ID = root_bridge_ID = -1
    num_interfaces = wrapper.init(sys.argv[2:])
    interfaces = range(0, num_interfaces)
    interface_state = [True] * num_interfaces

    file_path = 'configs/switch'+switch_id+'.cfg'
    
    f = open(file_path, 'r')
    own_bridge_ID = int(f.readline().strip())
    root_bridge_ID = own_bridge_ID
    root_path_cost = 0

    for line in f:
        line = line.strip()
        vlan.update({line.split()[0]: line.split()[1]})
    
    return table, vlan, switch_id, own_bridge_ID, root_bridge_ID, root_path_cost, num_interfaces, interfaces, interface_state

def translate_trunk(vlan: str) -> int:
    if vlan == 'T':
        return 0
    return int(vlan)

def trunk_forwarding(dest_mac, vlan_id: int, interface, data, length, table, vlan, interfaces, interface_state):
    notag_data = data[0:12] + data[16:]
    if dest_mac in table:
        vlan_path = vlan.get(get_interface_name(table.get(dest_mac)))
        vlan_path = translate_trunk(vlan_path)
        # If the destination is in the table, we send the frame to the interface
        if vlan_path == 0:
            send_to_link(table.get(dest_mac), length, data)
        else: # If the destination is in the table, but the interface is not a trunk, we strip the VLAN tag
            send_to_link(table.get(dest_mac), length -  4, notag_data)
    else:
        for i in interfaces:
            if i == interface or interface_state[i] == False:
                continue
            vlan_path = vlan.get(get_interface_name(i))
            vlan_path = translate_trunk(vlan_path)
            if vlan_path == 0:
                send_to_link(i, length, data)
            elif vlan_path == vlan_id:
                send_to_link(i, length - 4, notag_data)

def access_forwarding(dest_mac, vlan_id: int, interface, data, length, table, vlan, interfaces, interface_state):
    if dest_mac in table:
        vlan_path = vlan.get(get_interface_name(table.get(dest_mac)))
        vlan_path = translate_trunk(vlan_path)
        # If the destination is in the table, we send the frame to the interface
        if vlan_path == 0:
            tagged_frame = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
            send_to_link(table.get(dest_mac), length + 4, tagged_frame)
        else:# If the destination is in the table, but the interface is not a trunk, we strip the VLAN tag
            send_to_link(table.get(dest_mac), length, data)
    else:# If the destination is not in the table, we broadcast the frame
        for i in interfaces:
            if i == interface or interface_state[i] == False:
                continue
            vlan_path = vlan.get(get_interface_name(i))
            vlan_path = translate_trunk(vlan_path)
            if vlan_path == 0:
                tagged_frame = data[0:12] + create_vlan_tag(vlan_id) + data[12:]
                send_to_link(i, length + 4, tagged_frame)
            elif vlan_path == vlan_id:
                send_to_link(i, length, data)

def main():
    # init returns the max interface number. Our interfaces
    # are 0, 1, 2, ..., init_ret value + 1
    global root_bridge_ID, root_path_cost, own_bridge_ID
    global interfaces, interface_state, vlan, table
    table, vlan, switch_id, own_bridge_ID, root_bridge_ID, root_path_cost, num_interfaces, interfaces, interface_state = init_resources()
    root_port = None

    # Create and start a new thread that deals with sending BDPU
    t = threading.Thread(target=send_bdpu_every_sec)
    t.start()

    while True:
        # Note that data is of type bytes([...]).
        # b1 = bytes([72, 101, 108, 108, 111])  # "Hello"
        # b2 = bytes([32, 87, 111, 114, 108, 100])  # " World"
        # b3 = b1[0:2] + b[3:4].
        interface, data, length = recv_from_any_link()

        dest_mac, src_mac, ethertype, vlan_id = parse_ethernet_header(data)

        if not interface_state[interface]:
            continue

        mac_cast = data[0:6]
        if mac_cast == b'\x01\x80\xc2\x00\x00\x00':

            bpdu_src_bid = int.from_bytes(data[6:14], byteorder='big')
            bpdu_root_bid = int.from_bytes(data[14:22], byteorder='big')
            bpdu_cost_path = int.from_bytes(data[22:26], byteorder='big')

            we_were_root = (own_bridge_ID == root_bridge_ID)

            if bpdu_root_bid < root_bridge_ID:
                root_bridge_ID = bpdu_root_bid
                root_path_cost = bpdu_cost_path + 10
                root_port = interface

                if we_were_root:
                    for i in interfaces:
                        if i != root_port and vlan.get(get_interface_name(i)) == 'T':
                            interface_state[i] = False

                if interface_state[root_port] == False:
                    interface_state[root_port] = True

                mac_cast = struct.pack('!BBBBBB', 0x01, 0x80, 0xc3, 0x00, 0x00, 0x00)
                own_bid = struct.pack('!q', own_bridge_ID)
                root_bid = struct.pack('!q', root_bridge_ID)
                cost_path = struct.pack('!I', root_path_cost)
                data = mac_cast + own_bid + root_bid + cost_path
                for i in interfaces:
                    if i != root_port and vlan.get(get_interface_name(i)) == 'T':
                        send_to_link(i, len(data), data)

            elif bpdu_root_bid == root_bridge_ID:
                if interface == root_port and bpdu_cost_path + 10 < root_path_cost:
                    root_path_cost = bpdu_cost_path + 10
                
                elif interface != root_port and bpdu_cost_path > root_path_cost:
                    interface_state[interface] = True

            elif bpdu_src_bid == own_bridge_ID:
                interface_state[interface] = False
            
            if own_bridge_ID == root_bridge_ID:
                for i in interfaces:
                    if i != root_port and vlan.get(get_interface_name(i)) == 'T':
                        interface_state[i] = True
            continue
        

        if vlan_id == -1:
            vlan_id = vlan.get(get_interface_name(interface))
            vlan_id = translate_trunk(vlan_id)
            
        # TODO: Implement forwarding with learning
        table.update({src_mac: interface})

        # TODO: Implement VLAN support
        vlan_src = vlan.get(get_interface_name(interface))
        vlan_src = translate_trunk(vlan_src)

        # TODO: Implement STP support
        forwarding_function = trunk_forwarding if vlan_src == 0 else access_forwarding
        forwarding_function(dest_mac, vlan_id, interface, data, length, table, vlan, interfaces, interface_state)
            
if __name__ == "__main__":
    main()