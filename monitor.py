device = "gentry1"                  # device name
broker_addr = "broker.hivemq.com"   # broker name
broker_port = 1883                  # broker port
topic = "adwais/gentry"             # topic name
DISTANCE_MIN = 0.5
DISTANCE_MAX = 3.0


import matplotlib.pyplot as pyplot
from matplotlib.animation import FuncAnimation
from numpy import linspace
import paho.mqtt.client as mqtt
import json

class Client:
    def __on_connect(self, client, userdata, flags, rc):
        print("Connected to broker with result code "+str(rc))
        self.client.subscribe(self.topic+"/yo", 1)
    
    def __on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " with qos: " + str(granted_qos))
    
    def __on_publish(self, client, userdata, mid):
        #print("Published: "+str(mid))
        pass
    
    def __on_message(self, client, userdata, message):
        rmsg = json.loads(message.payload.decode("utf-8"))
        #print("Got ", rmsg["id"])
        self.data_cb(rmsg["result"])
    
    def __init__(self, broker_addr, broker_port, topic, device, data_cb):
        self.data_cb = data_cb
        self.client = mqtt.Client()
        self.client.on_connect = self.__on_connect
        self.client.on_message = self.__on_message
        self.client.on_subscribe = self.__on_subscribe
        self.client.on_publish = self.__on_publish
        self.topic = topic+"/"+device
        self.client.connect(broker_addr, broker_port)
        self.client.loop_start()
    def __del__(self):
        self.client.loop_stop()
    def publish(self, msg):
        self.client.publish(self.topic+"/rpc", json.dumps(msg), 1, False)

def anim_cb(n):
    msg = {
        "id":   n,
        "method": "data",
        "src":  "yo"
    }
    client.publish(msg)

def data_cb(data):
    sweep = data["left"]["sweep"]
    thres = data["left"]["thres"]
    dist = data["left"]["dist"]
    length = len(sweep)
    x = linspace(DISTANCE_MIN, DISTANCE_MAX, num=length)
    ax1.cla()
    ax2.cla()
    ax1.plot(x, sweep, x, thres)
    ax1.title.set_text("Left sensor")
    ax1.set(xlabel="Distance [m]")
   #ax1.set_ylim(0,10000)
    if dist:
        ax1.axvline(x=dist, color='g', linestyle='--', label=dist)
        ax1.legend(loc="upper right")
    sweep = data["right"]["sweep"]
    thres = data["right"]["thres"]
    dist = data["right"]["dist"]
    length = len(sweep)
    ax2.plot(x, sweep, x, thres)
    ax2.title.set_text("Right sensor")
    ax2.set(xlabel="Distance [m]")
    #ax2.set_ylim(0,10000)
    if dist:
        ax2.axvline(x=dist, color='g', linestyle='--', label=dist)
        ax2.legend(loc="upper right")


client = Client(broker_addr, broker_port, topic, device, data_cb)

fig = pyplot.figure()
ax1 = pyplot.subplot(121)
ax2 = pyplot.subplot(122)

ani = FuncAnimation(fig, anim_cb, interval=1000)
pyplot.show()
