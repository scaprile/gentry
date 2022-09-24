import paho.mqtt.client as mqtt
import json
import time
import math

device = "gentry1"
broker_addr = "broker.hivemq.com"
broker_port = 1883
topic = "adwais/gentry"

def status_build(now, left, right, out1, out2):
    msg = {
        "now": now,
        "left": left,
        "right": right,
        "out1": out1,
        "out2": out2,
    }
    return msg

left = "idle"
right = "idle"
out1 = "off"
out2 = "off"

def status_buildmessage():
    return status_build(math.floor(time.time()), left, right, out1, out2)

def status_sendmessage(event):
    msg = {
        "event":  event,
        "status": status_buildmessage()
    }
    client.publish(topic+"/"+device, json.dumps(msg), 1, False)

def on_connect(client, userdata, flags, rc):
    print("Connected to broker with result code "+str(rc))
    status_sendmessage("connect")

def on_subscribe(client, userdata, mid, granted_qos):
    print("Subscribed: " + str(mid) + " with qos: " + str(granted_qos))

def on_publish(client, userdata, mid):
    print("Published: "+str(mid))

def on_message(client, userdata, message):
    rmsg = json.loads(message.payload.decode("utf-8"))
    print("Got " + rmsg["method"] + " request from " + rmsg["src"])
    msg = {
        "id":   rmsg["id"],
        "method": rmsg["method"],
    }
    if rmsg["method"] == "status":
        msg["result"] = status_buildmessage()
        client.publish(topic+"/"+device+"/"+rmsg["src"], json.dumps(msg), 1, False)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.on_subscribe = on_subscribe
client.on_publish = on_publish

client.will_set(topic+"/"+device, json.dumps({"event": "disconnect"}), 1, False)
client.connect(broker_addr, broker_port)
client.subscribe(topic+"/"+device+"/rpc", 1)

# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
	

