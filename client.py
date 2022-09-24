import paho.mqtt.client as mqtt
import json

device = "gentry1"
broker_addr = "broker.hivemq.com"
broker_port = 1883
topic = "adwais/gentry"

def emptystatus(bogus):
    return {}



class Client:
    client = mqtt.Client()
    status_buildmessage = emptystatus
    
    def sendstatus(self, event):
        msg = {
            "event":  event,
            "status": self.status_buildmessage()
        }
        self.client.publish(topic+"/"+device, json.dumps(msg), 1, False)
    
    def __on_connect(self, client, userdata, flags, rc):
        print("Connected to broker with result code "+str(rc))
        self.sendstatus("connect")
    
    def __on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " with qos: " + str(granted_qos))
    
    def __on_publish(self, client, userdata, mid):
        print("Published: "+str(mid))
    
    def __on_message(self, client, userdata, message):
        rmsg = json.loads(message.payload.decode("utf-8"))
        print("Got " + rmsg["method"] + " request from " + rmsg["src"])
        msg = {
            "id":   rmsg["id"],
            "method": rmsg["method"],
        }
        if rmsg["method"] == "status":
            msg["result"] = self.status_buildmessage()
            self.client.publish(topic+"/"+device+"/"+rmsg["src"], json.dumps(msg), 1, False)
    
    def __init__(self, status_cb):
        self.status_buildmessage = status_cb
        self.client.on_connect = self.__on_connect
        self.client.on_message = self.__on_message
        self.client.on_subscribe = self.__on_subscribe
        self.client.on_publish = self.__on_publish
        self.client.will_set(topic+"/"+device, json.dumps({"event": "disconnect"}), 1, False)
        self.client.connect(broker_addr, broker_port)
        self.client.subscribe(topic+"/"+device+"/rpc", 1)
        self.client.loop_start()
