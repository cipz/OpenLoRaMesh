import gc
import time
import ujson
import struct
import socket
import loractp
import machine
import hashlib
import binascii
from network import LoRa

# A basic package header, 
#   B: 1 byte for the node_id, 
#   B: 1 byte for the pkg size, 
#   %ds: Formatted string for string
_LORA_PKG_FORMAT     = "!BB%ds"
_LORA_PKG_ACK_FORMAT = "!BB%ds"

class Node:    
    """
        Class that defines a node connected to the mesh
    """

    MESH_MESSAGE_PREAMBLE   = b"MSGMESH"
    MESH_PING_PREAMBLE      = b"PINMESH"
    MESH_PONG_PREAMBLE      = b"PONMESH"
    MESH_ADVERTISE_PREAMBLE = b"ADVMESH"
    MESH_DOWNLOAD_PREAMBLE  = b"DWLMESH"
    MESH_UPDATE_PREAMBLE    = b"UPDMESH"
    MESH_CHECK_PREAMBLE     = b"CHKMESH"

    LORA_NETWORK = None
    LORA_SOCKET = None
    LORA_MAC = None
    NODE_ID = None

    def get_mac_addr(self):
        return self.LORA_MAC

    def listen(self):

        print("Any messages in the air ... ?")

        new_package = False
        device_id, msg = None, None        
        
        self.LORA_SOCKET.setblocking(False)

        # In case of ValueError: buffer too small
        try:

            recv_pkg = self.LORA_SOCKET.recv(512)

            if (len(recv_pkg) > 2):

                recv_pkg_len = recv_pkg[1]
                device_id, pkg_len, msg = struct.unpack(_LORA_PKG_FORMAT % recv_pkg_len, recv_pkg)

                new_package = True

                # ack_pkg = struct.pack(_LORA_PKG_ACK_FORMAT, device_id, 1, 200)
                # s.send(ack_pkg)

            return new_package, device_id, msg

        except Exception as e:

            print("Exception:", e)

            return None, None, None

    def broadcast(self, msg):

        print("Sending [\"{}\"] in broadcast".format(msg))

        pkg = struct.pack(_LORA_PKG_FORMAT % len(msg), self.NODE_ID , len(msg), msg)

        self.LORA_SOCKET.setblocking(True)
        self.LORA_SOCKET.send(pkg)

        return

    def send_mesh_info(self, rcv_addr, routing_table):

        gc.enable()

        ctpc = loractp.CTPendpoint()

        myaddr, rcvraddr, quality, result = ctpc.connect(rcv_addr)

        if (result == 0):
            print("ping.py: connected to {} (myaddr = {}, quality {})".format(rcvraddr, myaddr, quality))
        else:
            print("ping.py: failed connection to {} (myaddr = {}, quality {})".format(rcvraddr, myaddr, quality))

        time.sleep(1)

        curr_routing_table_content = routing_table.getRoutingTable()
        curr_routing_table_version = routing_table.getVersion()

        print(curr_routing_table_content)
        print(curr_routing_table_version)

        t0 = time.time()
        
        tbs_ = {
            "type": "PING", 
            "CURR_ROUTING_TABLE_CONTENT": curr_routing_table_content, 
            "CURR_ROUTING_TABLE_VERSION" : curr_routing_table_version , 
            "time": time.time()
        }

        tbsj = ujson.dumps(tbs_)
        tbsb = str.encode(tbsj)
        try:
            addr, quality, result = ctpc.sendit(rcvraddr, tbsb)
            print("ping.py: ACK from {} (quality = {}, result {})".format(addr, quality, result))
        except Exception as e:
            print ("ping.py: EXCEPTION when sending -> ", e)
            return

        print('ping.py: waiting pong from: ', rcvraddr)
        try:
            rcvd_data, addr = ctpc.recvit(rcvraddr)
            print("ping.py: pong {} from {}".format(rcvd_data, addr))
        except Exception as e:
            print ("ping.py: EXCEPTION when receiving ->", e)
            return
        t1 = time.time()
        print ("ping.py: elapsed time = ", t1-t0)

        tbs = ""
        tbsj = ""
        tbsb = ""
        gc.collect()

        print("\n"*4)

        return

    def request_mesh_info(self, mesh_id, sndr_addr, routing_table):
        # TODO MODIFICARE, al posto di mesh id, mandare il proprio indirizzo

        print(mesh_id)
        print(routing_table)

        # Send plain message to ask for data from other node

        msg = self.MESH_DOWNLOAD_PREAMBLE.decode() + "=" + self.getMACAddr().decode() + "." + sndr_addr.decode()
        ack_pkg = struct.pack(_LORA_PKG_ACK_FORMAT % len(msg), self.NODE_ID , len(msg), msg)
        self.LORA_SOCKET.send(ack_pkg)

        # Wait for incoming loractp connection from other node with data regarding the mesh

        time.sleep(1)

        gc.enable()

        ctpc = loractp.CTPendpoint()

        myaddr, rcvraddr, status = ctpc.listen(sndr_addr)

        if (status == 0):
            print("pong.py: connection from {} to me ({})".format(rcvraddr, myaddr))
        else:
            print("pong.py: failed connection from {} to me ({})".format(rcvraddr, myaddr))

        print('pong.py: waiting for data from ', rcvraddr)
        try:
            rcvd_data, addr = ctpc.recvit(rcvraddr)
            print("pong.py: got ", rcvd_data, addr)
        except Exception as e:
            print ("pong.py: EXCEPTION!! ", e)
            return

        tbs = {"type": "PONG", "value": rcvd_data, "time": time.time()}
        tbsj = ujson.dumps(tbs)
        tbsb = str.encode(tbsj)
        print('--->pong.py: sending ', tbsb)
        try:
            addr, quality, result = ctpc.sendit(rcvraddr, tbsb)
            print("pong.py: ACK from {} (quality = {}, result = {})".format(addr, quality, result))
        except Exception as e:
            print ("pong.py: EXCEPTION!! ", e)
            return

        tbs = ""
        tbsj = ""
        tbsb = ""
        gc.collect()

        return rcvd_data

    def broadcast_mesh_advertisement(self, mesh_id):

        msg = self.MESH_ADVERTISE_PREAMBLE.decode() + "=" + mesh_id + "." + self.LORA_MAC.decode()
        self.broadcast(msg)

        return

    def listen_for_mesh(self, LISTEN_TIMEOUT = 180):

        # Add a random amount of time to the listen timeout so that they do not overlap
        LISTEN_TIMEOUT += machine.rng() & 0x1F

        mesh_id, advertising_node = None, None

        mesh_init_time = time.time()

        existing_mesh = False

        print("Searching for an existing mesh network for max {} seconds".format(LISTEN_TIMEOUT), end = " ")

        while time.time() - mesh_init_time < LISTEN_TIMEOUT and not existing_mesh:

            self.LORA_SOCKET.setblocking(False)

            recv_pkg = self.LORA_SOCKET.recv(512)

            if (len(recv_pkg) > 2):

                recv_pkg_len = recv_pkg[1]

                device_status, pkg_len, msg = struct.unpack(_LORA_PKG_FORMAT % recv_pkg_len, recv_pkg)

                print('Device with status %d sent message: %s' % (device_status, msg))

                if msg[:7] == self.MESH_ADVERTISE_PREAMBLE:

                    existing_mesh = True

                    mesh_id = msg[8:16]
                    advertising_node = msg[17:]

                    print("Got a message from {}, with an existing mesh id ({})".format(advertising_node, mesh_id))
                    print("MESH {}".format(msg[:7]))
                    print("mesh_id {}".format(msg[8:16]))
                    print("advertising_node {}".format(msg[17:]))

                    continue

            print(".", end = "")

            # wait 3 + random amount of time to increase chances of not interlacing
            rnd_sleep_time = 3 + machine.rng() & 0x0F
            time.sleep(rnd_sleep_time)

        print()

        return mesh_id, advertising_node, existing_mesh

    def __init__(self, default_node_id = 0x00) -> None:

        self.LORA_NETWORK = LoRa(mode=LoRa.LORA, region=LoRa.EU868)
        self.LORA_SOCKET = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        self.LORA_MAC = binascii.hexlify(LoRa().mac())[8:]
        self.NODE_ID = default_node_id

class Mesh:
    """
        Class that contains the information about the mesh itself
    """

    MESH_ID = None

    def generate_mesh_id(self) -> bytes:
        """
            Based on the LoRa MAC, generates a new mesh_id
        """
        h = hashlib.sha256(binascii.hexlify(LoRa().mac()))
        ha = binascii.hexlify(h.digest())

        mesh_id = ha[-8:]

        return mesh_id

    def set_mesh_id(self, new_mesh_id) -> None:
        self.MESH_ID = new_mesh_id
        
    def get_mesh_id(self):
        return self.MESH_ID

    def __init__(self, existing_mesh_id = None, force_new_mesh_id = None) -> None:

        if existing_mesh_id:
            self.set_mesh_id(existing_mesh_id)
        elif force_new_mesh_id:
            self.set_mesh_id(force_new_mesh_id)
        else:
            self.set_mesh_id(self.generate_mesh_id())

class RoutingTable:
    """
        Class that keeps track of the devices connected to the mesh.
    """

    VERSION = None # Define version, the higher the newer
    ROOT_ADDR = None
    ROUTING_TABLE = dict()

    def check_version(self, other_version) -> bool:
        return self.get_version() == other_version

    def calculate_version(self):

        rt = str(self.get_routing_table())

        print(rt)

        h = hashlib.sha256(rt)
        ha = binascii.hexlify(h.digest())

        version = ha[-5:]

        return version

    def set_version(self, new_version) -> None:
        self.VERSION = new_version

    def get_version(self):
        return self.VERSION

    def get_routing_table(self):
        return self.ROUTING_TABLE

    def set_routing_table(self, new_routing_table) -> None:
        self.ROUTING_TABLE = new_routing_table

    def add_child(self, parent_addr, child_addr) -> None:
        self.ROUTING_TABLE[child_addr] = parent_addr
        self.set_version(self.calculate_version()) # Recalculating the version of the routing table

    def remove_child(self, remove_addr) -> None:
        del self.ROUTING_TABLE[remove_addr]

    def get_root(self):
        return self.ROOT_ADDR

    def set_root(self, new_root_addr) -> None:
        self.ROOT_ADDR = new_root_addr

    def __init__(self, existing_routing_table_content = {}, existing_routing_table_version = None) -> None:

        self.set_root(list(existing_routing_table_content.keys())[0])

        self.set_routing_table(existing_routing_table_content)
        
        if existing_routing_table_version:
            self.set_version(existing_routing_table_version)    
        else:
            self.set_version(self.calculate_version())

        print(self.get_routing_table())
        print(self.get_version())

        return