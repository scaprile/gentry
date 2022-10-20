import paho.mqtt.client as mqtt
import json

class Client:
    def sendstatus(self, event):
        msg = {
            "event":  event,
            "status": self.status_buildmessage()
        }
        self.client.publish(self.pubtopic, json.dumps(msg), 1, False)
    
    def __on_connect(self, client, userdata, flags, rc):
        print("Connected to broker with result code "+str(rc))
        self.client.subscribe(self.pubtopic+"/rpc", 1)
        self.sendstatus("connect")
    
    def __on_subscribe(self, client, userdata, mid, granted_qos):
        print("Subscribed: " + str(mid) + " with qos: " + str(granted_qos))
    
    def __on_publish(self, client, userdata, mid):
        if self.verbose: print("Published: "+str(mid))
    
    def __on_message(self, client, userdata, message):
        try: rmsg = json.loads(message.payload.decode("utf-8"))
        except json.JSONDecodeError: return
        if "method" not in rmsg or "src" not in rmsg: return
        if self.verbose: print("Got " + rmsg["method"] + " request from " + rmsg["src"])
        msg = {
            "id":   rmsg["id"],
            "method": rmsg["method"],
        }
        if rmsg["method"] == "status" and self.status_buildmessage: msg["result"] = self.status_buildmessage()
        elif rmsg["method"] == "data" and self.data_buildmessage: msg["result"] = self.data_buildmessage()
        else: return
        self.client.publish(self.pubtopic+"/"+rmsg["src"], json.dumps(msg), 1, False)
    
    def __init__(self, broker_addr, broker_port, topic, device, status_cb=None, data_cb=None, verbose=False):
        self.status_buildmessage = status_cb
        self.data_buildmessage = data_cb
        self.verbose = verbose
        self.client = mqtt.Client()
        self.client.on_connect = self.__on_connect
        self.client.on_message = self.__on_message
        self.client.on_subscribe = self.__on_subscribe
        self.client.on_publish = self.__on_publish
        self.pubtopic = topic+"/"+device
        self.client.will_set(self.pubtopic, json.dumps({"event": "disconnect"}), 1, False)
        self.client.connect(broker_addr, broker_port)
        self.client.loop_start()
    def __del__(self):
        self.client.loop_stop()
