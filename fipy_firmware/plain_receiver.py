import time
import loractp

def plain_receiver():
    ctpc = loractp.CTPendpoint()
    print("Executing plain_receiver.py")

    while True:

        print('plain_receiver.py: waiting for data')

        try:
            rcvd_data, addr = ctpc.recvit()
            print("plainreceiver.py: got {} from {}".format(rcvd_data, addr))
        except Exception as e:
            print ("plainreceiver.py: EXCEPTION!! ", e)
            # break