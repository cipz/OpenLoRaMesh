from network import Bluetooth
import time

class MegaSense:

    MEGASENSE_ADDR = None

    CONNECTED = False

    def is_connected():
        return

    def read_data():
        return

    def __init__(self, default_megasense_addr = None) -> None:

        print(default_megasense_addr)

        bt = Bluetooth()
        bt.init()

        write_service_leds ="3f4d1701-188d-46bd-869b-e87f342aa36e"

        while( True ):
            if( not bt.isscanning() ):
                bt.start_scan(-1)

            print("Scan")
            adv = bt.get_adv()
            if( adv ):
                bt.stop_scan()
                print( adv.mac )
                try:
                    conn = bt.connect( adv.mac )
                    if( conn ):
                        if( conn.isconnected()):

                            print("CONNECTED")

                            for service in conn.services():
                                try:
                                    print(service.uuid())
                                    print(service.isprimary())
                                    print(service.instance())
                                    print(service.characteristics())
                                    print("service.characteristics()")
                                    for characteristic in service.characteristics():
                                        # print(characteristic)
                                        # print()
                                        # characteristic.read_descriptor()
                                        # characteristic.uuid()
                                        # characteristic.instance()
                                        # characteristic.properties()
                                        # characteristic.read()
                                        print("Value: ")
                                        characteristic.value()
                                        # characteristic.write(value)
                                        # characteristic.read_descriptor(uuid)
                                    service.characteristic(write_service_leds, value=1)
                                except:
                                    print("err")
                                finally:
                                    print()

                            time.sleep(10)
                            print()
                            conn.disconnect()
                            break
                        else:
                            print("Not Connected")
                    else:
                        print("Conn not available")
                except Exception as e:
                    print( e )

            time.sleep( 1 )

        print("Done!")