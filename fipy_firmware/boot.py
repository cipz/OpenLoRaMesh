import os
import LED
import json
import pycom
from machine import SD
from network import WLAN
from plain_receiver import plain_receiver

print("\n"*10)
print("Booting up ... ")

print("De-initializing WiFi")
# To avoid interference with LoRa, deinit WiFi
wlan = WLAN(mode=WLAN.STA)
wlan.deinit()

pycom.heartbeat(False)

SD_CONFIG_FILE_PATH = "/sd/config.json"
LOCAL_CONFIG_FILE_PATH = "/flash/config.json"
CONFIG_FILE_PATH = None

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
    except Exception as e:
        print("File not accessible")
        print("Exception:", e)
    finally:
        if f:
            f.close()
else:
    CONFIG_FILE_PATH = LOCAL_CONFIG_FILE_PATH

config_file = open(LOCAL_CONFIG_FILE_PATH)

boot_configuration = json.load(config_file)

config_file.close()

boot_mode = boot_configuration["BOOT_MODE"]

if boot_mode == "PLAIN_RECEIVER":
    print("Booting in mode `PLAIN_RECEIVER`")
    plain_receiver()

elif boot_mode == "DEFAULT_BOOT":
    print("Booting in mode `DEFAULT_BOOT`")

else:
    print("Boot mode not recognized")
    print("Booting in mode `DEFAULT_BOOT`")

print("boot.py end")
print("\n"*10)