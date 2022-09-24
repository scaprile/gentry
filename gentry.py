# Keep relay on x seconds after no detection
TIME_ACTIVE = 5
# Keep relay off x seconds before reacting to new detection
TIME_INACTIVE = 0.5
# Send idle message with current status every x seconds
TIME_IDLE = 60
# Physical pin number (BOARD): 7, 15, 31, 37
# Chip GPIO pin number, "Broadcomm" (BCM): 4, 22, 6, 26
# anecdotic: wiringPI.h: 7, 3, 22, 25
# 'gpio readall' is your friend
relay = [4, 22, 6, 26]

try:
    import RPi.GPIO as GPIO
except:
    import Mock.GPIO as GPIO
import time
import math
from client import Client

def now():
    return math.floor(time.time())

def timerexpired(timer):
    if now() > timer :
        return True
    return False


def status_build(ts, left, right, out1, out2):
    msg = {
        "timestamp": ts,
        "left": left,
        "right": right,
        "out1": out1,
        "out2": out2,
    }
    return msg

# state variables
left = False
right = False
out1 = False
out2 = False

# status callback
def status_buildmessage():
    return status_build(now(), left, right, out1, out2)


# init relays
GPIO.setmode(GPIO.BCM)
for i in range(4):
    GPIO.setup(relay[i], GPIO.OUT)
# init sensors
# init MQTT client
client = Client(status_buildmessage)
# init timers
idletime = now() + TIME_IDLE
activetime = 0
inactivetime = 0
# init state variables
out1 = True
oldout = out2
oldright = right
oldleft = left
changes = False

while True:
    # detect changes
    if right != oldright :
        oldright = right
        print("right: " + "detect" if right else "idle")
        changes = True
    if left != oldleft :
        oldleft = left
        print("left: " + "detect" if left else "idle")
        changes = True
    if out2 != oldout :
        oldout = out2
        print("out2: " + "on" if out2 else "off")
        changes = True
    # report changes
    if changes :
        changes = False
        idletime = now() + TIME_IDLE
        client.sendstatus("activity")
    # report if idle for too long
    if timerexpired(idletime):
        idletime = now() + TIME_IDLE
        client.sendstatus("idle")
    # set output off on inactivity
    if timerexpired(activetime):
        out2 = False
        inactivetime = time.time() + TIME_ACTIVE
    # set output on on activity
    if left or right:
        activetime = now() + TIME_ACTIVE
        if time.time() > inactivetime : out2 = True
    # relays follow outputs
    GPIO.output(relay[0], GPIO.HIGH if out1 else GPIO.LOW)
    GPIO.output(relay[1], GPIO.HIGH if out2 else GPIO.LOW)
    # process sensors
    # sleep for a while
    time.sleep(0.1)

GPIO.cleanup()
