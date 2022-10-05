
import acconeer.exptool as acconeer
import acconeer.exptool.a111.algo.distance_detector as distance_detector
import numpy as np

class Sensor:
    def __init__(self, dev, min, max):
        acconeer.utils.config_logging()
        self.client = acconeer.a111.Client(link="uart", serial_port=dev, protocol="module", mock=True if dev == "mock" else False) 
        self.econfig = acconeer.a111.EnvelopeServiceConfig()
        # https://docs.acconeer.com/en/latest/handbook/a111/services/envelope.html
        self.econfig.range_interval = [min, max]
        self.econfig.profile = "PROFILE_3"
        self.econfig.downsampling_factor = 4
        self.econfig.hw_accelerated_average_samples = 10
        self.econfig.gain = 0.82
        self.econfig.running_average_factor = 0
        self.econfig.update_rate = 10
        self.dconfig = distance_detector.ProcessingConfiguration()
        # https://docs.acconeer.com/en/latest/exploration_tool/algo/a111/distance_detector.html
        self.dconfig.nbr_average = 5
        self.dconfig.threshold_type = "CFAR"
        self.dconfig.cfar_sensitivity = 0.5
        self.dconfig.cfar_guard_m = 0.12
        self.dconfig.cfar_window_m = 0.03
        self.dconfig.peak_sorting_type = "CLOSEST"
        info = self.client.connect()
        print("Sensor firmware: " + info["version_str"])
        self.session_info = self.client.setup_session(self.econfig)
        self.processor = distance_detector.Processor(self.econfig, self.dconfig, self.session_info)
        self.client.start_session()
    def process(self):
        data_info, data = self.client.get_next()
        # always returns data:
        #   "sweep" and "sweep_index" are updated constantly
        # actual processing is done when the configured number of frames (n) have been averaged, so
        #   "found_peaks" is None except when n frames have been processed AND peaks have been found
        #   "last_mean_sweep", "main_peak_hist_dist"... are updated every n frames
        result = self.processor.process(data, data_info)
        peaks = result["found_peaks"]
        return {
            "distance": result["main_peak_hist_dist"][-1] if (not peaks is None) and (len(peaks) > 0) else None,
            "sweep": result["last_mean_sweep"].astype(int).tolist()
        }
    def __del__(self):
        self.client.stop_session()
        self.client.disconnect()
        print("Sensor disconnected")
