# Measuring range in meters, presence will be detected
# between MIN and THRESHOLD
DISTANCE_MIN = 0.5
DISTANCE_MAX = 3.0
# Presence detection threshold
DISTANCE_THRESHOLD = 2.3
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
# MQTT stuff
device = "gentry1"                  # device name
broker_addr = "broker.hivemq.com"   # broker name
broker_port = 1883                  # broker port
topic = "adwais/gentry"             # topic name


# Assign sensors; we've already made proper udev rules, overwrite if necessary
from os import getenv
l = getenv("SENSOR0") 
r = getenv("SENSOR1") 
module = {
    "left": l if l else "/dev/sensor0",
    "right": r if r else "/dev/sensor1"
}
print(module)
exitcode = 1

try:
    import RPi.GPIO as GPIO
except:
    import Mock.GPIO as GPIO
import time
import math
from threading import Lock
from client import Client
from sensor import Sensor

def now():
    return time.time()

def timerexpired(timer):
    return True if now() > timer else False


def status_build(ts, left, right, out1, out2):
    return {
        "timestamp": ts,
        "left": left,
        "right": right,
        "out1": out1,
        "out2": out2,
    }

# state variables
left = False
right = False
out1 = False
out2 = False

lock = Lock()
sweep_left = []
sweep_right = []
# These run on the MQTT client thread context
# status callback, worst case it has an old value in some variables
def status_buildmessage():
    return status_build(math.floor(now()), left, right, out1, out2)
# data callback, using 'lock'
def data_buildmessage():
    with lock:
        msg = {
            "left": { "dist": dist_left, "sweep": sweep_left,"thres": thres_left},
            "right": {"dist": dist_right, "sweep": sweep_right, "thres": thres_right}
        }
    return msg

try:
    # init relays, avoid stupid warnings, we need the relays to stay off (safety) so we won't "cleanup" on exit
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    for i in range(4):
        GPIO.setup(relay[i], GPIO.OUT)
    # init MQTT client
    client = Client(broker_addr, broker_port, topic, device, status_buildmessage, data_buildmessage)
    # init sensors
    time.sleep(0.1)
    sensor_left = Sensor(module["left"], DISTANCE_MIN, DISTANCE_MAX)
    sensor_right = Sensor(module["right"], DISTANCE_MIN, DISTANCE_MAX)
    # init timers
    idletime = now() + TIME_IDLE
    activetime = now() + TIME_ACTIVE
    inactivetime = 0
    # init out1
    out1 = True
    # init state variables
    oldout1 = out2
    oldout2 = out2
    oldright = right
    oldleft = left
    changes = False

    while True:
        looptime = now()
        # process sensors
        sensordata = sensor_left.process()
        distance = sensordata["distance"]
        left = True if distance and distance <= DISTANCE_THRESHOLD else False
        with lock:
            dist_left = distance
            sweep_left = sensordata["sweep"]
            thres_left = sensordata["thres"]
        sensordata = sensor_right.process()
        distance = sensordata["distance"]
        right = True if distance and distance <= DISTANCE_THRESHOLD else False
        with lock:
            dist_right = distance
            sweep_right = sensordata["sweep"]
            thres_right = sensordata["thres"]
        # detect changes
        if right != oldright :
            oldright = right
            print("right: " + ("detect" if right else "idle"))
            changes = True
        if left != oldleft :
            oldleft = left
            print("left: " + ("detect" if left else "idle"))
            changes = True
        # set output on on activity, off on inactivity
        if left or right: activetime = now() + TIME_ACTIVE
        if timerexpired(activetime):
            out2 = False
            inactivetime = now() + TIME_INACTIVE
        else:
            if timerexpired(inactivetime): out2 = True
        if out2 != oldout2 :
            oldout2 = out2
            print("out2: " + "on" if out2 else "off")
            changes = True
        # out1 not processed
        # report changes
        if changes :
            changes = False
            idletime = now() + TIME_IDLE
            client.sendstatus("activity")
        # report if idle for too long
        if timerexpired(idletime):
            idletime = now() + TIME_IDLE
            client.sendstatus("idle")
        # relays follow outputs
        GPIO.output(relay[0], GPIO.HIGH if out1 else GPIO.LOW)
        GPIO.output(relay[1], GPIO.HIGH if out2 else GPIO.LOW)
        # sleep for a while
        looptime = 0.2 -(now() - looptime)
        if looptime > 0: time.sleep(looptime)

except KeyboardInterrupt:
    print(" exiting on user request")
    print("Outputs set to off")
    for i in range(4):
        GPIO.output(relay[i], GPIO.LOW)
    exitcode = 0

#except:
#    print("*** Exception")
#    exitcode = 2

finally:
    del sensor_left
    del sensor_right
    del client
    exit(exitcode)
