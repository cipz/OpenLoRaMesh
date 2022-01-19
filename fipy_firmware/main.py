import gc
import os
import json
import time
import _thread
import hashlib
from lib.megasense import MegaSense
import machine
from machine import SD
from LED import *
from mesh import Node, Mesh, RoutingTable
from L76GNSS import L76GNSS
from pycoproc_2 import Pycoproc

def log(log_file, log_string):
    print(log_string)
    log_file.write(log_string)

def main():

    ## Setting all variables according to configuration file

    SD_CONFIG_FILE_PATH = "/sd/config.json"
    LOCAL_CONFIG_FILE_PATH = "/flash/config.json"
    CONFIG_FILE_PATH = None

    SD_LOG_FILE_PATH = '/sd/log_record.txt'
    LOCAL_LOG_FILE_PATH = '/flash/log_record.txt'
    LOG_FILE_PATH = None

    GPS = False
    DEFAULT_MESH_ID = None
    DEFAULT_NODE_ID = None
    MEGASENSE_CONNECT = False
    MEGASENSE_ADDR = None

    LORA_ANTENNA_LOCK = _thread.allocate_lock()

    # Check for SD card and config file
    try:
        sd = SD()
    except Exception as e:
        sd = None
        print("SD card not accessible")
        print("Exception:", e)

    if sd:
        os.mount(sd, '/sd')
        os.listdir('/sd')
        f = None
        try:
            f = open(SD_CONFIG_FILE_PATH)
            CONFIG_FILE_PATH = SD_CONFIG_FILE_PATH
            LOG_FILE_PATH = SD_LOG_FILE_PATH
        except Exception as e:
            print("File not accessible")
            print("Exception:", e)
        finally:
            if f:
                f.close()
    else:
        LOG_FILE_PATH = LOCAL_LOG_FILE_PATH
        CONFIG_FILE_PATH = LOCAL_CONFIG_FILE_PATH

    # Reading from config file
    config_file = open(CONFIG_FILE_PATH)
    boot_configuration = json.load(config_file)
    config_file.close()

    GPS = boot_configuration["GPS"]
    DEFAULT_MESH_ID = boot_configuration["MESH_ID"]
    DEFAULT_NODE_ID = boot_configuration["NODE_ID"]
    MEGASENSE_CONNECT = boot_configuration["MEGASENSE_CONNECT"]
    MEGASENSE_ADDR = boot_configuration["MEGASENSE_ADDR"]

    # Opening log file
    log_file = open(LOG_FILE_PATH, 'w')

    ## Setting up GPS

    if GPS:
        py = Pycoproc()
        if py.read_product_id() != Pycoproc.USB_PID_PYTRACK:
            GPS = False
            print('Not a Pytrack')
        else:
            l76 = L76GNSS(py, timeout=30, buffer=512)

    ## Check availability of MegaSense device before searching for a network

    if MEGASENSE_CONNECT:
        log(log_file, "Looking for MegaSense device")
        megasense = MegaSense()
    else:
        log(log_file, "MEGASENSE_CONNECT set to False")

    ##
    
    node = Node()
    mesh = None
    routing_table = None

    mesh_id, advertising_node, request_connection = None, None, None

    with LORA_ANTENNA_LOCK:

        # Listening for messages that advertise the mesh
        mesh_id, advertising_node, request_connection = node.listen_for_mesh(180)
        
        # If an advertisement message has been found in the air, 
        # the device requests the information about the mesh from the advertising_node
        if request_connection:

            mesh = Mesh(mesh_id)

            mesh_info = node.request_mesh_info(mesh_id, advertising_node)

            mesh_info = json.loads(mesh_info.decode())

            log(log_file, mesh_info)
            log(log_file, mesh_info["CURR_ROUTING_TABLE_CONTENT"])
            log(log_file, mesh_info["CURR_ROUTING_TABLE_VERSION"])

            received_routing_table_content = mesh_info["CURR_ROUTING_TABLE_CONTENT"]
            received_routing_table_version = mesh_info["CURR_ROUTING_TABLE_VERSION"]

            # Quando viene mandata la tabella di routing faccio append del mio indirizzo, 
            # lo stesso lo fa colui a cui è arrivata la richiesta da parte mia,
            # e mando come ack il nuovo hash (aka la nuova versione) della tabella di routing

            routing_table = RoutingTable(
                received_routing_table_content, 
                received_routing_table_version
            )

        # If no advertising message has been found in the air,
        # the device will initialize the mesh by itself
        else:

            log(log_file, "No advertising message received, initializing node with defaults")
            
            mesh = Mesh(force_new_mesh_id = DEFAULT_MESH_ID)

            new_routing_table_dict = { node.LORA_MAC : "" }
            routing_table = RoutingTable(new_routing_table_dict)

        time.sleep(machine.rng() & 0x0F)

    log(log_file, "Node has been initialized with mesh_id {} and belongs to the routing table\n{}".format(mesh.MESH_ID, routing_table.getRoutingTable()))

    time.sleep(1)

    while True:
        
        log(log_file, "\n\n")

        with LORA_ANTENNA_LOCK:
            
            new_package, device_status, msg = node.listen()
            
            if new_package:

                log(log_file, 'Device status: %d - Message:  %s' % (device_status, msg))

                message_preamble = msg[:7]

                if message_preamble == node.MESH_MESSAGE_PREAMBLE:
                    log(log_file, "Message")

                elif message_preamble == node.MESH_DOWNLOAD_PREAMBLE:
                    
                    log(log_file, msg)

                    # MESSAGE FORMAT:
                    # XXXXXXXX --> REQUESTING NODE ADDR
                    # YYYYYYYY --> DESTINATION NODE ADDR
                    # DWLMESH=XXXXXXXX.YYYYYYYY

                    destination_node_addr = msg[17:]

                    log(log_file, node.get_mac_addr())
                    log(log_file, destination_node_addr)
                    log(log_file, msg[8:16])

                    if destination_node_addr != node.get_mac_addr():

                        log(log_file, "Message not for me")

                        log(log_file, destination_node_addr)
                        log(log_file, msg[8:16])

                        continue
                    
                    requesting_node_addr = msg[8:16]

                    log(log_file, "Sending info to {}".format(requesting_node_addr))

                    # Updating routing table
                    routing_table.addChild(node.get_mac_addr(), requesting_node_addr)

                    log(log_file, "Updated the routing table with the entry: {} {}".format(node.get_mac_addr(), requesting_node_addr))
                    log(log_file, "Current status of routing table: {}".format(routing_table.getRoutingTable()))

                    # Sending routing table to the node that requested it
                    node.send_mesh_info(requesting_node_addr, routing_table)

                else: 

                    log(log_file, "Err: message not recognized or malformed")

        # wait for a random amount of time
        time.sleep(machine.rng() & 0x0F)

        if MEGASENSE_CONNECT:
            log(log_file, "Gathering data from MegaSense device")
            continue

        # Get GPS coordinates
        if GPS:
            print("Gathering GPS coordinates")
            coord = l76.coordinates()
            print("{} - {}".format(coord, gc.mem_free()))

        # wait for a random amount of time
        time.sleep(machine.rng() & 0x0F)

        with LORA_ANTENNA_LOCK:
            
            node.broadcast_mesh_advertisement(mesh.MESH_ID)

        time.sleep(machine.rng() & 0x0F)

        log(log_file, "Current routing table content: {}".format(routing_table.getRoutingTable()))
        # log(log_file, "Routing table version: {}".format(routing_table.getRoutingTableVersion()))

        time.sleep(machine.rng() & 0x0F)

    log_file.close()

if __name__ == '__main__':
    
    main()