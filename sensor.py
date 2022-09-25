
import acconeer.exptool as acconeer

class Sensor:
    def __init__(self, dev, min, max):
        acconeer.utils.config_logging()
        self.client = acconeer.a111.Client(link="uart", serial_port=dev, protocol="module")
        self.config = acconeer.a111.EnvelopeServiceConfig()
        self.config.range_interval = [0.2, 0.3]#min, max]
        self.config.update_rate = 10
        info = self.client.connect()
        print(info["version_str"])
        self.session_info = self.client.setup_session(self.config)
        print("Session info:\n", self.session_info, "\n")
        self.client.start_session()
    def process(self, threshold):
        data_info, data = self.client.get_next()
    def __del__(self):
        self.client.stop_session()
        self.client.disconnect()
