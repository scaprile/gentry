# Configured to average 5 frames, assumes the process() method will be called every 200ms
# so it will return one new measurement per second, repeating same data in next 4 calls
# process() returns data for current measurement period (1s):
# "distance": latest measured distance, or None
# "sweep": latest averaged sweep
# "thres": latest threshold

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
        self.econfig.profile = acconeer.a111.EnvelopeServiceConfig.Profile.PROFILE_3
        self.econfig.downsampling_factor = 4
        self.econfig.hw_accelerated_average_samples = 10
        self.econfig.gain = 0.82
        self.econfig.running_average_factor = 0
        self.econfig.update_rate = 5
        self.dconfig = distance_detector.ProcessingConfiguration()
        # https://docs.acconeer.com/en/latest/exploration_tool/algo/a111/distance_detector.html
        self.dconfig.nbr_average = 5
        self.dconfig.threshold_type = distance_detector.ProcessingConfiguration.ThresholdType.CFAR
        self.dconfig.cfar_sensitivity = 0.4
        self.dconfig.cfar_guard_m = 0.2
        self.dconfig.cfar_window_m = 0.06
        self.dconfig.peak_sorting_type = distance_detector.ProcessingConfiguration.PeakSorting.CLOSEST
        info = self.client.connect()
        print("Sensor firmware: " + info["version_str"])
        self.session_info = self.client.setup_session(self.econfig)
        self.processor = distance_detector.Processor(self.econfig, self.dconfig, self.session_info)
        self.client.start_session()
        self.distance = None
        self.threshold = []
    def process(self):
        """ Acconeer process() method always returns data:
            - "sweep", "threshold" and "sweep_index" are updated constantly
            - actual processing is done when the configured number of frames (dconfig.nbr_average) have been averaged, so
            - "found_peaks" is None except when dconfig.nbr_average frames have been processed AND peaks have been found
            - "last_mean_sweep", "main_peak_hist_dist"... are updated every dconfig.nbr_average frames
            - "*_idx_s" indicate time distance, in segundos, to current time, assuming we call the process
            frequently enough and give data at the configured update frequency (econfig.update_rate, in Hz):
                0 => just measured; -0.4 => 400ms ago
            - ("sweep_index" + 1) / dconfig.nbr_average:
                integer => measurement time ; otherwise => averaging """
#   cómo resincronizo ? yo pondría el índice en cero o reiniciaría el sensor...
#   si no mide nada por un tiempo muy largo tal vez convenga reiniciar el sensor también...
        data_info, data = self.client.get_next()            # read the sensor
        result = self.processor.process(data, data_info)    # call the processor
        if len(result["main_peak_hist_sweep_s"]):
            peaks = result["found_peaks"]
            frnbr = (result["sweep_index"]+1) / self.dconfig.nbr_average
            if np.floor(frnbr) == frnbr:
                if not result["found_peaks"]: self.distance = None # No detection
                else: # detection(s), return the current main one
                    self.distance = result["main_peak_hist_dist"][-1].round(decimals=2) if (not peaks is None) and (len(peaks) > 0) else None
                self.threshold = np.nan_to_num(result["threshold"]).astype(int).tolist()
            elif not peaks is None: # Averaging, shouldn't get a valid measurement unless we got out of sync with the sensor
                raise AssertionError # and this should never happen since we are calling the process with data
        return {
            "distance": self.distance,
            "sweep": result["last_mean_sweep"].astype(int).tolist(),
            "thres": self.threshold
        }
    def __del__(self):
        self.client.stop_session()
        self.client.disconnect()
        print("Sensor disconnected")
