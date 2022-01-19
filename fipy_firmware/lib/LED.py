import time
import pycom
import _thread

# https://forum.pycom.io/topic/1393/how-do-i-exit-a-thread/7

FADE_COLOR_KILL = None

def rgb_to_hex(red, green, blue):
    """Return color as #rrggbb for the given color values."""
    return '%02x%02x%02x' % (red, green, blue)

def startFadeColor(cycles = None):
    global FADE_COLOR_KILL
    FADE_COLOR_KILL = False
    _thread.start_new_thread(startFadeColorThread, (cycles, None))

def stopFadeColor():
    global FADE_COLOR_KILL
    FADE_COLOR_KILL = True
    
def startFadeColorThread(cycles = None, args = None):
    global FADE_COLOR_KILL
    if not cycles:
        cycles = 1000
    for j in range(cycles):
        for i in range(256):
            if FADE_COLOR_KILL == True:
                pycom.rgbled(0x0000)
                _thread.exit()
            color = rgb_to_hex(i,i,i)
            pycom.rgbled(256-int(color,16))
            time.sleep(0.005)

# https://docs.pycom.io/tutorials/basic/rgbled/
def semaphore():
    pycom.heartbeat(False)
    for cycles in range(10): # stop after 10 cycles
        pycom.rgbled(0x007f00) # green
        time.sleep(5)
        pycom.rgbled(0x7f7f00) # yellow
        time.sleep(1.5)
        pycom.rgbled(0x7f0000) # red
        time.sleep(4)
