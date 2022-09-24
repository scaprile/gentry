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

left = False
right = False
out1 = False
out2 = False

def status_buildmessage():
    return status_build(now(), left, right, out1, out2)


GPIO.setmode(GPIO.BCM)
for i in range(4):
    GPIO.setup(relay[i], GPIO.OUT)
client = Client(status_buildmessage)
idletime = now() + TIME_IDLE
activetime = 0
inactivetime = 0
out1 = True
oldout = out2
oldright = right
oldleft = left
changes = False

while True:
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
    if changes :
        changes = False
        idletime = now() + TIME_IDLE
        client.sendstatus("activity")
    if timerexpired(idletime):
        idletime = now() + TIME_IDLE
        client.sendstatus("idle")
    if timerexpired(activetime):
        out2 = False
        inactivetime = time.time() + TIME_ACTIVE
    if left or right:
        activetime = now() + TIME_ACTIVE
        if time.time() > inactivetime : out2 = True
    GPIO.output(relay[i], GPIO.HIGH if out2 else GPIO.LOW)
    time.sleep(0.1)

GPIO.cleanup()
