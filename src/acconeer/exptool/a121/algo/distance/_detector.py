# Copyright (c) Acconeer AB, 2022
# All rights reserved

from __future__ import annotations

import copy
import enum
import warnings
from typing import Any, Dict, List, Optional, Tuple

import attrs
import h5py
import numpy as np
import numpy.typing as npt

from acconeer.exptool import a121
from acconeer.exptool.a121.algo import AlgoConfigBase

from ._aggregator import (
    Aggregator,
    AggregatorConfig,
    AggregatorContext,
    PeakSortingMethod,
    ProcessorSpec,
)
from ._processors import (
    DEFAULT_CFAR_ONE_SIDED,
    DEFAULT_FIXED_THRESHOLD_VALUE,
    DEFAULT_THRESHOLD_SENSITIVITY,
    MeasurementType,
    Processor,
    ProcessorConfig,
    ProcessorContext,
    ProcessorMode,
    ProcessorResult,
    ThresholdMethod,
    calculate_bg_noise_std,
    calculate_offset,
)


@attrs.frozen(kw_only=True)
class DetectorStatus:
    detector_state: DetailedStatus
    ready_to_calibrate_close_range: bool
    ready_to_record_threshold: bool
    ready_to_start: bool


class DetailedStatus(enum.Enum):
    OK = enum.auto()
    CLOSE_RANGE_CALIBRATION_MISSING = enum.auto()
    CLOSE_RANGE_CALIBRATION_CONFIG_MISMATCH = enum.auto()
    RECORDED_THRESHOLD_MISSING = enum.auto()
    RECORDED_THRESHOLD_CONFIG_MISMATCH = enum.auto()
    INVALID_DETECTOR_CONFIG_RANGE = enum.auto()


@attrs.frozen(kw_only=True)
class SubsweepGroupPlan:
    step_length: int = attrs.field()
    breakpoints: list[int] = attrs.field()
    profile: a121.Profile = attrs.field()
    hwaas: list[int] = attrs.field()


Plan = Dict[MeasurementType, List[SubsweepGroupPlan]]


@attrs.mutable(kw_only=True)
class DetectorContext:
    offset_m: Optional[float] = attrs.field(default=None)
    direct_leakage: Optional[npt.NDArray[np.complex_]] = attrs.field(default=None)
    phase_jitter_comp_reference: Optional[npt.NDArray[np.float_]] = attrs.field(default=None)
    recorded_thresholds_mean_sweep: Optional[List[npt.NDArray[np.float_]]] = attrs.field(
        default=None
    )
    recorded_thresholds_noise_std: Optional[List[List[np.float_]]] = attrs.field(default=None)
    bg_noise_std: Optional[List[List[float]]] = attrs.field(default=None)
    recorded_threshold_session_config_used: Optional[a121.SessionConfig] = attrs.field(
        default=None
    )
    close_range_session_config_used: Optional[a121.SessionConfig] = attrs.field(default=None)
    reference_temperature: Optional[int] = attrs.field(default=None)

    # TODO: Make recorded_thresholds Optional[List[Optional[npt.NDArray[np.float_]]]]


@attrs.mutable(kw_only=True)
class DetectorConfig(AlgoConfigBase):
    start_m: float = attrs.field(default=0.25)
    """Start point of measurement interval in meters."""

    end_m: float = attrs.field(default=3.0)
    """End point of measurement interval in meters."""

    max_step_length: Optional[int] = attrs.field(default=None)  # TODO: Check validity
    """Used to limit step length. If no argument is provided, the step length is automatically
    calculated based on the profile."""

    max_profile: a121.Profile = attrs.field(default=a121.Profile.PROFILE_5, converter=a121.Profile)
    """Specifies the longest allowed profile. If no argument is provided, the highest possible
    profile without interference of direct leakage is used to maximize SNR."""

    signal_quality: float = attrs.field(default=15.0)
    """Signal quality. High quality equals higher HWAAS and better SNR but increase power
    consumption."""

    threshold_method: ThresholdMethod = attrs.field(
        default=ThresholdMethod.CFAR,
        converter=ThresholdMethod,
    )
    """Threshold method"""

    peaksorting_method: PeakSortingMethod = attrs.field(
        default=PeakSortingMethod.HIGHEST_RCS,
        converter=PeakSortingMethod,
    )
    """Sorting method of estimated distances."""

    num_frames_in_recorded_threshold: int = attrs.field(default=100)
    """Number of frames used when calibrating threshold."""

    fixed_threshold_value: float = attrs.field(default=DEFAULT_FIXED_THRESHOLD_VALUE)
    """Value of fixed threshold."""

    threshold_sensitivity: float = attrs.field(default=DEFAULT_THRESHOLD_SENSITIVITY)
    """Sensitivity of threshold. High sensitivity equals low detection threshold, low sensitivity
    equals high detection threshold."""

    cfar_one_sided: bool = attrs.field(default=DEFAULT_CFAR_ONE_SIDED)
    """Use one sided CFAR threshold. Instead of determining the CFAR threshold from sweep
    amplitudes from distances both closer and a farther, use only closer. Helpful e.g. for fluid
    level in small tanks, where many multipath signal can apprear just after the main peak."""


@attrs.frozen(kw_only=True)
class DetectorResult:
    distances: Optional[npt.NDArray[np.float_]] = attrs.field(default=None)
    processor_results: list[ProcessorResult] = attrs.field()
    service_extended_result: list[dict[int, a121.Result]] = attrs.field()


class Detector:
    """Distance detector
    :param client: Client
    :param sensor_id: Sensor id
    :param detector_config: Detector configuration
    :param context: Detector context
    """

    MIN_DIST_M = 0.0
    MAX_DIST_M = 17.0
    MAX_MEASURABLE_DIST_M = {
        a121.PRF.PRF_19_5_MHz: 3.1,
        a121.PRF.PRF_13_0_MHz: 7.0,
        a121.PRF.PRF_8_7_MHz: 12.7,
        a121.PRF.PRF_6_5_MHz: 18.5,
    }
    MIN_LEAKAGE_FREE_DIST_M = {
        a121.Profile.PROFILE_1: 0.12,
        a121.Profile.PROFILE_2: 0.28,
        a121.Profile.PROFILE_3: 0.56,
        a121.Profile.PROFILE_4: 0.76,
        a121.Profile.PROFILE_5: 1.28,
    }
    MIN_NUM_POINTS_IN_ENVELOPE_FWHM_SPAN = 4.0
    VALID_STEP_LENGTHS = [1, 2, 3, 4, 6, 8, 12, 24]
    NUM_SUBSWEEPS_IN_SENSOR_CONFIG = 4

    MAX_HWAAS = 511
    MIN_HWAAS = 1
    HWAAS_MIN_DISTANCE = 1.0

    session_config: a121.SessionConfig
    processor_specs: List[ProcessorSpec]
    context: DetectorContext

    def __init__(
        self,
        *,
        client: a121.Client,
        sensor_id: int,
        detector_config: DetectorConfig,
        context: Optional[DetectorContext] = None,
    ) -> None:
        self.client = client
        self.sensor_id = sensor_id
        self.detector_config = detector_config
        self.started = False

        if context is None:
            self.context = DetectorContext()
        else:
            self.context = context

        self.aggregator: Optional[Aggregator] = None

        self.update_config(self.detector_config)

    def _validate_ready_for_calibration(self) -> None:
        if self.started:
            raise RuntimeError("Already started")
        if self.processor_specs is None:
            raise ValueError("Processor specification not defined")
        if self.session_config is None:
            raise ValueError("Session config not defined")

    def calibrate_close_range(self) -> None:
        """Calibrates the close range measurement parameters used when subtracting the direct
        leakage from the measured signal.

        The parameters calibrated are the direct leakage and a phase reference, used to reduce
        the amount of phase jitter, with the purpose of reducing the residual.
        """
        self._validate_ready_for_calibration()

        close_range_spec = self._filter_close_range_spec(self.processor_specs)
        spec = self._update_processor_mode(close_range_spec, ProcessorMode.LEAKAGE_CALIBRATION)

        # Note - Setup with full session_config to match the structure of spec
        extended_metadata = self.client.setup_session(self.session_config)
        assert isinstance(extended_metadata, list)

        aggregator = Aggregator(
            session_config=self.session_config,
            extended_metadata=extended_metadata,
            config=AggregatorConfig(),
            context=AggregatorContext(),
            specs=spec,
        )

        self.client.start_session()
        extended_result = self.client.get_next()
        assert isinstance(extended_result, list)
        aggregator_result = aggregator.process(extended_result=extended_result)
        self.client.stop_session()
        (processor_result,) = aggregator_result.processor_results
        self.context.direct_leakage = processor_result.direct_leakage
        assert processor_result.phase_jitter_comp_reference is not None
        self.context.phase_jitter_comp_reference = processor_result.phase_jitter_comp_reference
        self.context.close_range_session_config_used = self.session_config
        self.context.recorded_thresholds_mean_sweep = None
        self.context.recorded_thresholds_noise_std = None

    def record_threshold(self) -> None:
        """Calibrates the parameters used when forming the recorded threshold."""

        self._validate_ready_for_calibration()

        # TODO: Ignore/override threshold method while recording threshold

        specs_updated = self._update_processor_mode(
            self.processor_specs, ProcessorMode.RECORDED_THRESHOLD_CALIBRATION
        )

        self.calibrate_noise()

        specs = self._add_context_to_processor_spec(specs_updated)

        extended_metadata = self.client.setup_session(self.session_config)
        assert isinstance(extended_metadata, list)

        aggregator = Aggregator(
            session_config=self.session_config,
            extended_metadata=extended_metadata,
            config=AggregatorConfig(),
            context=AggregatorContext(),
            specs=specs,
        )

        aggregator_result = None
        self.client.start_session()
        for _ in range(self.detector_config.num_frames_in_recorded_threshold):
            extended_result = self.client.get_next()
            assert isinstance(extended_result, list)
            aggregator_result = aggregator.process(extended_result=extended_result)
        self.client.stop_session()

        assert aggregator_result is not None

        assert isinstance(extended_result, list)
        # Grab value from first group as it is the same for all.
        self.context.reference_temperature = extended_result[0][self.sensor_id].temperature

        self.context.recorded_thresholds_mean_sweep = []
        self.context.recorded_thresholds_noise_std = []
        for processor_result in aggregator_result.processor_results:
            # Since we know what mode the processor is running in
            assert processor_result.recorded_threshold_mean_sweep is not None
            assert processor_result.recorded_threshold_noise_std is not None
            self.context.recorded_thresholds_mean_sweep.append(
                processor_result.recorded_threshold_mean_sweep
            )
            self.context.recorded_thresholds_noise_std.append(
                processor_result.recorded_threshold_noise_std
            )
        self.context.recorded_threshold_session_config_used = self.session_config

    def calibrate_noise(self) -> None:
        """Estimates the standard deviation of the noise in each subsweep by setting enable_tx to
        False and collecting data, used to calculate the deviation.

        The calibration procedure can be done at any time as it is performed with Tx off, and is
        not effected by objects in front of the sensor.

        This function is called from the start() in the case of CFAR and Fixed threshold and from
        record_threshold() in the case of Recorded threshold. The reason for calling from
        record_threshold() is that it is used when calculating the threshold.
        """
        self._validate_ready_for_calibration()

        session_config = copy.deepcopy(self.session_config)

        for group in session_config.groups:
            group[self.sensor_id].sweeps_per_frame = 1
            for subsweep in group[self.sensor_id].subsweeps:
                subsweep.enable_tx = False
                subsweep.step_length = 1
                subsweep.start_point = 0
                # Set num_points to a high number to get sufficient number of data points to
                # estimate the standard deviation.
                subsweep.num_points = 500

        extended_metadata = self.client.setup_session(session_config)
        assert isinstance(extended_metadata, list)

        self.client.start_session()
        extended_result = self.client.get_next()
        assert isinstance(extended_result, list)
        self.client.stop_session()

        bg_noise_std = []
        for spec in self.processor_specs:
            bg_noise_std_in_subsweep = []
            result = extended_result[spec.group_index][spec.sensor_id]
            sensor_config = self.session_config.groups[spec.group_index][spec.sensor_id]
            subsweep_configs = sensor_config.subsweeps
            for idx in spec.subsweep_indexes:
                if not subsweep_configs[idx].enable_loopback:
                    subframe = result.subframes[idx]
                    subsweep_std = calculate_bg_noise_std(subframe, subsweep_configs[idx])
                    bg_noise_std_in_subsweep.append(subsweep_std)
            bg_noise_std.append(bg_noise_std_in_subsweep)
        self.context.bg_noise_std = bg_noise_std

    def calibrate_offset(self) -> None:
        """Estimates sensor offset error based on loopback measurement."""

        self._validate_ready_for_calibration()

        sensor_config = a121.SensorConfig(
            start_point=-30,
            num_points=50,
            step_length=1,
            profile=a121.Profile.PROFILE_1,
            hwaas=64,
            sweeps_per_frame=1,
            enable_loopback=True,
            phase_enhancement=True,
        )

        session_config = a121.SessionConfig({self.sensor_id: sensor_config})
        self.client.setup_session(session_config)
        self.client.start_session()
        result = self.client.get_next()
        self.client.stop_session()

        assert isinstance(result, a121.Result)

        self.context.offset_m = calculate_offset(result, sensor_config)

    @classmethod
    def get_detector_status(
        cls, config: DetectorConfig, context: DetectorContext, sensor_id: int
    ) -> DetectorStatus:
        """Returns the detector status along with the detector state."""

        if not cls._valid_detector_config_range(config=config):
            return DetectorStatus(
                detector_state=DetailedStatus.INVALID_DETECTOR_CONFIG_RANGE,
                ready_to_calibrate_close_range=False,
                ready_to_record_threshold=False,
                ready_to_start=False,
            )

        (
            session_config,
            _,
        ) = cls._detector_to_session_config_and_processor_specs(config=config, sensor_id=sensor_id)

        ready_to_record_threshold = False
        if cls._has_close_range_measurement(config):
            ready_to_calibrate_close_range = True
            if cls._close_range_calibrated(context):
                if session_config != context.close_range_session_config_used:
                    detector_state = DetailedStatus.CLOSE_RANGE_CALIBRATION_CONFIG_MISMATCH
                elif not cls._recorded_threshold_calibrated(context):
                    detector_state = DetailedStatus.RECORDED_THRESHOLD_MISSING
                    ready_to_record_threshold = True
                elif session_config != context.recorded_threshold_session_config_used:
                    detector_state = DetailedStatus.RECORDED_THRESHOLD_CONFIG_MISMATCH
                else:
                    detector_state = DetailedStatus.OK
                    ready_to_record_threshold = True
            else:
                detector_state = DetailedStatus.CLOSE_RANGE_CALIBRATION_MISSING
        else:
            ready_to_calibrate_close_range = False
            if cls._has_recorded_threshold_mode(config):
                ready_to_record_threshold = True
                if cls._recorded_threshold_calibrated(context):
                    if session_config != context.recorded_threshold_session_config_used:
                        detector_state = DetailedStatus.RECORDED_THRESHOLD_CONFIG_MISMATCH
                    else:
                        detector_state = DetailedStatus.OK
                else:
                    detector_state = DetailedStatus.RECORDED_THRESHOLD_MISSING
            else:
                detector_state = DetailedStatus.OK

        return DetectorStatus(
            detector_state=detector_state,
            ready_to_calibrate_close_range=ready_to_calibrate_close_range,
            ready_to_record_threshold=ready_to_record_threshold,
            ready_to_start=(detector_state == DetailedStatus.OK),
        )

    @classmethod
    def _valid_detector_config_range(cls, config: DetectorConfig) -> bool:
        return cls.MIN_DIST_M < config.start_m and config.end_m < cls.MAX_DIST_M

    @staticmethod
    def _close_range_calibrated(context: DetectorContext) -> bool:
        has_dl = context.direct_leakage is not None
        has_pjcr = context.phase_jitter_comp_reference is not None

        if has_dl != has_pjcr:
            raise RuntimeError

        return has_dl and has_pjcr

    @staticmethod
    def _recorded_threshold_calibrated(context: DetectorContext) -> bool:
        return (
            context.recorded_thresholds_mean_sweep is not None
            and context.recorded_thresholds_noise_std is not None
        )

    @classmethod
    def _has_close_range_measurement(self, config: DetectorConfig) -> bool:
        (
            _,
            specs,
        ) = self._detector_to_session_config_and_processor_specs(config=config, sensor_id=1)
        return MeasurementType.CLOSE_RANGE in [
            spec.processor_config.measurement_type for spec in specs
        ]

    @classmethod
    def _has_recorded_threshold_mode(self, config: DetectorConfig) -> bool:
        (
            _,
            processor_specs,
        ) = self._detector_to_session_config_and_processor_specs(config=config, sensor_id=1)
        return ThresholdMethod.RECORDED in [
            spec.processor_config.threshold_method for spec in processor_specs
        ]

    def start(
        self, recorder: Optional[a121.Recorder] = None, skip_calibration: bool = False
    ) -> None:
        """Method for setting up measurement session."""

        if self.started:
            raise RuntimeError("Already started")

        status = self.get_detector_status(self.detector_config, self.context, self.sensor_id)

        if not status.ready_to_start:
            raise RuntimeError("Not ready to start")

        if not skip_calibration:
            self.calibrate_noise()
            self.calibrate_offset()

        specs = self._add_context_to_processor_spec(self.processor_specs)
        extended_metadata = self.client.setup_session(self.session_config)
        assert isinstance(extended_metadata, list)
        assert self.context.offset_m is not None
        aggregator_config = AggregatorConfig(
            peak_sorting_method=self.detector_config.peaksorting_method
        )
        aggregator_context = AggregatorContext(offset_m=self.context.offset_m)
        self.aggregator = Aggregator(
            session_config=self.session_config,
            extended_metadata=extended_metadata,
            config=aggregator_config,
            context=aggregator_context,
            specs=specs,
        )

        if recorder is not None:
            if isinstance(recorder, a121.H5Recorder):
                algo_group = recorder.require_algo_group("distance_detector")
                _record_algo_data(
                    algo_group,
                    self.sensor_id,
                    self.detector_config,
                    self.context,
                )
            else:
                # Should never happen as we currently only have the H5Recorder
                warnings.warn("Will not save algo data")

        self.client.start_session(recorder)
        self.started = True

    def get_next(self) -> DetectorResult:
        """Called from host to get next measurement."""
        if not self.started:
            raise RuntimeError("Not started")

        assert self.aggregator is not None

        extended_result = self.client.get_next()
        assert isinstance(extended_result, list)

        aggregator_result = self.aggregator.process(extended_result=extended_result)

        return DetectorResult(
            distances=aggregator_result.estimated_distances,
            processor_results=aggregator_result.processor_results,
            service_extended_result=aggregator_result.service_extended_result,
        )

    def update_config(self, config: DetectorConfig) -> None:
        """Updates the session config and processor specification based on the detector
        configuration."""
        (
            self.session_config,
            self.processor_specs,
        ) = self._detector_to_session_config_and_processor_specs(
            config=config, sensor_id=self.sensor_id
        )

    def stop(self) -> Any:
        """Stops the measurement session."""
        if not self.started:
            raise RuntimeError("Already stopped")

        recorder_result = self.client.stop_session()

        self.started = False

        return recorder_result

    @classmethod
    def _detector_to_session_config_and_processor_specs(
        cls, config: DetectorConfig, sensor_id: int
    ) -> Tuple[a121.SessionConfig, list[ProcessorSpec]]:
        processor_specs = []
        groups = []
        group_index = 0

        plans = cls._create_group_plans(config)

        if MeasurementType.CLOSE_RANGE in plans:
            sensor_config = cls._close_subsweep_group_plans_to_sensor_config(
                plans[MeasurementType.CLOSE_RANGE]
            )
            groups.append({sensor_id: sensor_config})
            processor_specs.append(
                ProcessorSpec(
                    processor_config=ProcessorConfig(
                        threshold_method=ThresholdMethod.RECORDED,
                        measurement_type=MeasurementType.CLOSE_RANGE,
                        threshold_sensitivity=config.threshold_sensitivity,
                    ),
                    group_index=group_index,
                    sensor_id=sensor_id,
                    subsweep_indexes=[0, 1],
                )
            )
            group_index += 1

        if MeasurementType.FAR_RANGE in plans:
            (
                sensor_config,
                processor_specs_subsweep_indexes,
            ) = cls._far_subsweep_group_plans_to_sensor_config_and_subsweep_indexes(
                plans[MeasurementType.FAR_RANGE]
            )
            groups.append({sensor_id: sensor_config})

            processor_config = ProcessorConfig(
                threshold_method=config.threshold_method,
                fixed_threshold_value=config.fixed_threshold_value,
                threshold_sensitivity=config.threshold_sensitivity,
                cfar_one_sided=config.cfar_one_sided,
            )

            for subsweep_indexes in processor_specs_subsweep_indexes:
                processor_specs.append(
                    ProcessorSpec(
                        processor_config=processor_config,
                        group_index=group_index,
                        sensor_id=sensor_id,
                        subsweep_indexes=subsweep_indexes,
                    )
                )

        return (a121.SessionConfig(groups, extended=True), processor_specs)

    @classmethod
    def _create_group_plans(
        cls, config: DetectorConfig
    ) -> Dict[MeasurementType, List[SubsweepGroupPlan]]:
        """
        Create dictionary containing group plans for close and far range measurements.

        - Close range measurement: Add Subsweep group if the user defined starting point is
        effected by the direct leakage.
        - Transition region: Add group plans to bridge the gap between the start of the far range
        measurement region(either end of close range region or user defined start_m) and the
        shortest measurable distance with max_profile, free from direct leakage interference.
        - Add group plan with max_profile. Increase HWAAS as a function of distance to maintain
        SNR throughout the sweep.
        """
        plans = {}

        # Determine shortest direct leakage free distance per profile
        min_dist_m = cls._calc_leakage_free_min_dist(config)

        close_range_transition_m = min_dist_m[a121.Profile.PROFILE_1]

        # Add close range group plan if applicable
        if config.start_m < close_range_transition_m:
            plans[MeasurementType.CLOSE_RANGE] = cls._get_close_range_group_plan(
                close_range_transition_m, config
            )

        # Define transition group plans
        transition_subgroup_plans = cls._get_transition_group_plans(
            config, min_dist_m, MeasurementType.CLOSE_RANGE in plans
        )

        # The number of available subsweeps in the group with max profile.
        num_remaining_subsweeps = cls.NUM_SUBSWEEPS_IN_SENSOR_CONFIG - len(
            transition_subgroup_plans
        )

        # No neighbours if no close range measurement or transition groups defined.
        has_neighbouring_subsweep = (
            MeasurementType.CLOSE_RANGE in plans or len(transition_subgroup_plans) != 0
        )

        # Define group plans with max profile
        max_profile_subgroup_plans = cls._get_max_profile_group_plans(
            config, min_dist_m, has_neighbouring_subsweep, num_remaining_subsweeps
        )

        far_subgroup_plans = transition_subgroup_plans + max_profile_subgroup_plans

        if len(far_subgroup_plans) != 0:
            plans[MeasurementType.FAR_RANGE] = far_subgroup_plans

        return plans

    @classmethod
    def _get_close_range_group_plan(
        cls, transition_m: float, config: DetectorConfig
    ) -> list[SubsweepGroupPlan]:
        """Define the group plan for close range measurements.

        The close range measurement always use profile 1 to minimize direct leakage region.
        """
        profile = a121.Profile.PROFILE_1
        # No left neighbour as this is the first subsweep when close range measurement is
        # applicable.
        has_neighbour = (False, transition_m < config.end_m)
        return [
            cls._create_group_plan(
                profile, config, [config.start_m, transition_m], has_neighbour, True
            )
        ]

    @classmethod
    def _get_transition_group_plans(
        cls,
        config: DetectorConfig,
        min_dist_m: Dict[a121.Profile, float],
        has_close_range_measurement: bool,
    ) -> list[SubsweepGroupPlan]:
        """Define the transition segment group plans.

        The purpose of the transition group is to bridge the gap between the start point of the
        far measurement region and the point where max_profile can be used without interference
        of direct leakage.

        The transition region can consist of maximum two subsweeps, where the first utilize profile
        1 and the second profile 3. Whether both, one or none is used depends on the user provided
        detector config.
        """
        transition_profiles = [
            profile
            for profile in [a121.Profile.PROFILE_1, a121.Profile.PROFILE_3]
            if profile.value < config.max_profile.value
        ]
        transition_profiles.append(config.max_profile)

        transition_subgroup_plans: list = []

        for i in range(len(transition_profiles) - 1):
            profile = transition_profiles[i]
            next_profile = transition_profiles[i + 1]

            if config.start_m < min_dist_m[next_profile] and min_dist_m[profile] < config.end_m:
                start_m = max(min_dist_m[profile], config.start_m)
                end_m = min(config.end_m, min_dist_m[next_profile])
                has_neighbour = (
                    has_close_range_measurement or len(transition_subgroup_plans) != 0,
                    min_dist_m[next_profile] < end_m,
                )

                transition_subgroup_plans.append(
                    cls._create_group_plan(profile, config, [start_m, end_m], has_neighbour, False)
                )

        return transition_subgroup_plans

    @classmethod
    def _get_max_profile_group_plans(
        cls,
        config: DetectorConfig,
        min_dist_m: Dict[a121.Profile, float],
        has_neighbouring_subsweep: bool,
        num_remaining_subsweeps: int,
    ) -> list[SubsweepGroupPlan]:
        """Define far range group plans with max_profile

        Divide the measurement range from the shortest leakage free distance of max_profile to
        the end point into equidistance segments and assign HWAAS according to the radar equation
        to maintain SNR throughout the sweep.
        """

        if min_dist_m[config.max_profile] < config.end_m:
            subsweep_start_m = max([config.start_m, min_dist_m[config.max_profile]])
            breakpoints_m = np.linspace(
                subsweep_start_m,
                config.end_m,
                num_remaining_subsweeps + 1,
            ).tolist()

            return [
                cls._create_group_plan(
                    config.max_profile,
                    config,
                    breakpoints_m,
                    (has_neighbouring_subsweep, False),
                    False,
                )
            ]
        else:
            return []

    @classmethod
    def _create_group_plan(
        cls,
        profile: a121.Profile,
        config: DetectorConfig,
        breakpoints_m: list[float],
        has_neighbour: Tuple[bool, bool],
        is_close_range_measurement: bool,
    ) -> SubsweepGroupPlan:
        """Creates a group plan."""
        step_length = cls._limit_step_length(profile, config.max_step_length)
        breakpoints = cls._m_to_points(breakpoints_m, step_length)
        hwaas = cls._calculate_hwaas(profile, breakpoints, config.signal_quality, step_length)

        extended_breakpoints = cls._add_margin_to_breakpoints(
            profile=profile,
            step_length=step_length,
            base_bpts=breakpoints,
            has_neighbour=has_neighbour,
            config=config,
            is_close_range_measurement=is_close_range_measurement,
        )

        return SubsweepGroupPlan(
            step_length=step_length,
            breakpoints=extended_breakpoints,
            profile=profile,
            hwaas=hwaas,
        )

    @classmethod
    def _calc_leakage_free_min_dist(cls, config: DetectorConfig) -> Dict[a121.Profile, float]:
        """This function calculates the shortest leakage free distance per profile, for all profiles
        up to max_profile"""
        min_dist_m = {}
        for profile, min_dist in cls.MIN_LEAKAGE_FREE_DIST_M.items():
            min_dist_m[profile] = min_dist
            if config.threshold_method == ThresholdMethod.CFAR:
                step_length = cls._limit_step_length(profile, config.max_step_length)
                cfar_margin_m = (
                    Processor.calc_cfar_margin(profile, step_length)
                    * step_length
                    * Processor.APPROX_BASE_STEP_LENGTH_M
                )
                min_dist_m[profile] += cfar_margin_m

            if profile == config.max_profile:
                # All profiles up to max_profile has been added. Break and return result.
                break

        return min_dist_m

    @classmethod
    def _calculate_hwaas(
        cls, profile: a121.Profile, breakpoints: list[int], signal_quality: float, step_length: int
    ) -> list[int]:
        rlg_per_hwaas = Aggregator.RLG_PER_HWAAS_MAP[profile]
        hwaas = []
        for idx in range(len(breakpoints) - 1):
            processing_gain = Aggregator.calc_processing_gain(profile, step_length)
            subsweep_end_point_m = max(
                Processor.APPROX_BASE_STEP_LENGTH_M * breakpoints[idx + 1],
                cls.HWAAS_MIN_DISTANCE,
            )
            rlg = signal_quality + 40 * np.log10(subsweep_end_point_m) - np.log10(processing_gain)
            hwaas_in_subsweep = int(10 ** ((rlg - rlg_per_hwaas) / 10))
            hwaas.append(np.clip(hwaas_in_subsweep, cls.MIN_HWAAS, cls.MAX_HWAAS))
        return hwaas

    @classmethod
    def _add_margin_to_breakpoints(
        cls,
        profile: a121.Profile,
        step_length: int,
        base_bpts: list[int],
        has_neighbour: Tuple[bool, bool],
        config: DetectorConfig,
        is_close_range_measurement: bool,
    ) -> list[int]:
        """
        Add points to segment edges based on their position.

        1. Add one margin to each segment for distance filter initialization
        2. Add an additional margin to segments with neighbouring segments for segment overlap
        """

        margin_p = Processor.distance_filter_edge_margin(profile, step_length) * step_length
        left_margin = margin_p
        right_margin = margin_p

        if has_neighbour[0]:
            left_margin += margin_p

        if has_neighbour[1]:
            right_margin += margin_p

        if config.threshold_method == ThresholdMethod.CFAR and not is_close_range_measurement:
            cfar_margin = Processor.calc_cfar_margin(profile, step_length) * step_length
            left_margin += cfar_margin
            right_margin += cfar_margin

        bpts = copy.copy(base_bpts)
        bpts[0] -= left_margin
        bpts[-1] += right_margin

        return bpts

    @classmethod
    def _limit_step_length(cls, profile: a121.Profile, user_limit: Optional[int]) -> int:
        """
        Calculates step length based on user defined step length and selected profile.

        The step length must yield minimum MIN_NUM_POINTS_IN_ENVELOPE_FWHM_SPAN number of points
        in the span of the FWHM of the envelope.

        If the step length is <24, return the valid step length(defined by
        VALID_STEP_LENGTHS) that is closest to, but not longer than the limit.

        If the limit is 24<=, return the multiple of 24 that is
        closest, but not longer than the limit.
        """

        fwhm_p = Processor.ENVELOPE_FWHM_M[profile] / Processor.APPROX_BASE_STEP_LENGTH_M
        limit = int(fwhm_p / cls.MIN_NUM_POINTS_IN_ENVELOPE_FWHM_SPAN)

        if user_limit is not None:
            limit = min(user_limit, limit)

        if limit < cls.VALID_STEP_LENGTHS[-1]:
            idx_closest = np.sum(np.array(cls.VALID_STEP_LENGTHS) <= limit) - 1
            return int(cls.VALID_STEP_LENGTHS[idx_closest])
        else:
            return int((limit // cls.VALID_STEP_LENGTHS[-1]) * cls.VALID_STEP_LENGTHS[-1])

    @classmethod
    def _close_subsweep_group_plans_to_sensor_config(
        cls, plan_: List[SubsweepGroupPlan]
    ) -> a121.SensorConfig:
        (plan,) = plan_
        subsweeps = []
        subsweeps.append(
            a121.SubsweepConfig(
                start_point=0,
                num_points=1,
                step_length=1,
                profile=a121.Profile.PROFILE_4,
                hwaas=plan.hwaas[0],
                receiver_gain=15,
                phase_enhancement=True,
                enable_loopback=True,
            )
        )
        num_points = int((plan.breakpoints[1] - plan.breakpoints[0]) / plan.step_length)
        subsweeps.append(
            a121.SubsweepConfig(
                start_point=plan.breakpoints[0],
                num_points=num_points,
                step_length=plan.step_length,
                profile=plan.profile,
                hwaas=plan.hwaas[0],
                receiver_gain=5,
                phase_enhancement=True,
                prf=cls._select_prf(plan.breakpoints[1], plan.profile),
            )
        )
        return a121.SensorConfig(subsweeps=subsweeps, sweeps_per_frame=10)

    @classmethod
    def _far_subsweep_group_plans_to_sensor_config_and_subsweep_indexes(
        cls, subsweep_group_plans: list[SubsweepGroupPlan]
    ) -> Tuple[a121.SensorConfig, list[list[int]]]:
        subsweeps = []
        processor_specs_subsweep_indexes = []
        subsweep_idx = 0
        for plan in subsweep_group_plans:
            subsweep_indexes = []
            for bp_idx in range(len(plan.breakpoints) - 1):
                num_points = int(
                    (plan.breakpoints[bp_idx + 1] - plan.breakpoints[bp_idx]) / plan.step_length
                )
                subsweeps.append(
                    a121.SubsweepConfig(
                        start_point=plan.breakpoints[bp_idx],
                        num_points=num_points,
                        step_length=plan.step_length,
                        profile=plan.profile,
                        hwaas=plan.hwaas[bp_idx],
                        receiver_gain=10,
                        phase_enhancement=True,
                        prf=cls._select_prf(plan.breakpoints[bp_idx + 1], plan.profile),
                    )
                )
                subsweep_indexes.append(subsweep_idx)
                subsweep_idx += 1
            processor_specs_subsweep_indexes.append(subsweep_indexes)
        return (
            a121.SensorConfig(subsweeps=subsweeps, sweeps_per_frame=1),
            processor_specs_subsweep_indexes,
        )

    @classmethod
    def _select_prf(cls, breakpoint: int, profile: a121.Profile) -> a121.PRF:
        max_meas_dist_m = copy.copy(cls.MAX_MEASURABLE_DIST_M)

        if (
            a121.PRF.PRF_19_5_MHz in max_meas_dist_m
            and profile != a121.Profile.PROFILE_1
            and profile != a121.Profile.PROFILE_2
        ):
            del max_meas_dist_m[a121.PRF.PRF_19_5_MHz]

        breakpoint_m = breakpoint * Processor.APPROX_BASE_STEP_LENGTH_M
        viable_prfs = [
            prf for prf, max_dist_m in max_meas_dist_m.items() if breakpoint_m < max_dist_m
        ]
        return sorted(viable_prfs, key=lambda prf: prf.frequency)[-1]

    @classmethod
    def _m_to_points(cls, breakpoints_m: list[float], step_length: int) -> list[int]:
        bpts_m = np.array(breakpoints_m)
        start_point = int(bpts_m[0] / Processor.APPROX_BASE_STEP_LENGTH_M)
        num_steps = (bpts_m[-1] - bpts_m[0]) / (Processor.APPROX_BASE_STEP_LENGTH_M)
        bpts = num_steps / (bpts_m[-1] - bpts_m[0]) * (bpts_m - bpts_m[0]) + start_point
        return [(bpt // step_length) * step_length for bpt in bpts]

    @classmethod
    def _update_processor_mode(
        cls, processor_specs: list[ProcessorSpec], processor_mode: ProcessorMode
    ) -> list[ProcessorSpec]:
        updated_specs = []
        for spec in processor_specs:
            new_processor_config = attrs.evolve(
                spec.processor_config, processor_mode=processor_mode
            )
            updated_specs.append(attrs.evolve(spec, processor_config=new_processor_config))
        return updated_specs

    @classmethod
    def _filter_close_range_spec(cls, specs: list[ProcessorSpec]) -> list[ProcessorSpec]:
        NUM_CLOSE_RANGE_SPECS = 1
        close_range_specs = []
        for spec in specs:
            if spec.processor_config.measurement_type == MeasurementType.CLOSE_RANGE:
                close_range_specs.append(spec)
        if len(close_range_specs) != NUM_CLOSE_RANGE_SPECS:
            raise ValueError("Incorrect subsweep config for close range measurement")

        return close_range_specs

    def _add_context_to_processor_spec(
        self, processor_specs: list[ProcessorSpec]
    ) -> list[ProcessorSpec]:
        """
        Create and add processor context to processor specification.
        """

        assert self.context.bg_noise_std is not None

        updated_specs: List[ProcessorSpec] = []

        for idx, (spec, bg_noise_std) in enumerate(
            zip(processor_specs, self.context.bg_noise_std)
        ):
            if (
                self.context.recorded_thresholds_mean_sweep is not None
                or self.context.recorded_thresholds_noise_std is not None
            ):
                assert self.context.recorded_thresholds_mean_sweep is not None
                assert self.context.recorded_thresholds_noise_std is not None
                recorded_thresholds_mean_sweep = self.context.recorded_thresholds_mean_sweep[idx]
                recorded_threshold_noise_std = self.context.recorded_thresholds_noise_std[idx]
            else:
                recorded_thresholds_mean_sweep = None
                recorded_threshold_noise_std = None

            if (
                self.context.direct_leakage is not None
                or self.context.phase_jitter_comp_reference is not None
            ):
                direct_leakage = self.context.direct_leakage
                phase_jitter_comp_ref = self.context.phase_jitter_comp_reference
            else:
                direct_leakage = None
                phase_jitter_comp_ref = None

            context = ProcessorContext(
                recorded_threshold_mean_sweep=recorded_thresholds_mean_sweep,
                recorded_threshold_noise_std=recorded_threshold_noise_std,
                bg_noise_std=bg_noise_std,
                direct_leakage=direct_leakage,
                phase_jitter_comp_ref=phase_jitter_comp_ref,
                reference_temperature=self.context.reference_temperature,
            )
            updated_specs.append(attrs.evolve(spec, processor_context=context))

        return updated_specs


def _record_algo_data(
    algo_group: h5py.Group,
    sensor_id: int,
    detector_config: DetectorConfig,
    context: DetectorContext,
) -> None:
    algo_group.create_dataset(
        "sensor_id",
        data=sensor_id,
        track_times=False,
    )
    algo_group.create_dataset(
        "detector_config",
        data=detector_config.to_json(),
        dtype=a121._H5PY_STR_DTYPE,
        track_times=False,
    )

    context_group = algo_group.create_group("context")

    for k, v in attrs.asdict(context).items():
        if k in [
            "recorded_thresholds_mean_sweep",
            "recorded_thresholds_noise_std",
            "bg_noise_std",
        ]:
            continue

        if v is None:
            continue

        if isinstance(v, a121.SessionConfig):
            context_group.create_dataset(
                k,
                data=v.to_json(),
                dtype=a121._H5PY_STR_DTYPE,
                track_times=False,
            )
        elif isinstance(v, np.ndarray) or isinstance(v, float) or isinstance(v, int):
            context_group.create_dataset(k, data=v, track_times=False)
        else:
            raise RuntimeError(f"Unexpected {DetectorContext.__name__} field type '{type(v)}'")

    if context.recorded_thresholds_mean_sweep is not None:
        recorded_thresholds_mean_sweep_group = context_group.create_group(
            "recorded_thresholds_mean_sweep"
        )

        for i, v in enumerate(context.recorded_thresholds_mean_sweep):
            recorded_thresholds_mean_sweep_group.create_dataset(
                f"index_{i}", data=v, track_times=False
            )

    if context.recorded_thresholds_noise_std is not None:
        recorded_thresholds_std_group = context_group.create_group("recorded_thresholds_noise_std")

        for i, v in enumerate(context.recorded_thresholds_noise_std):
            recorded_thresholds_std_group.create_dataset(f"index_{i}", data=v, track_times=False)

    if context.bg_noise_std is not None:
        bg_noise_std_group = context_group.create_group("bg_noise_std")

        for i, v in enumerate(context.bg_noise_std):
            bg_noise_std_group.create_dataset(f"index_{i}", data=v, track_times=False)


def _load_algo_data(algo_group: h5py.Group) -> Tuple[int, DetectorConfig, DetectorContext]:
    sensor_id = algo_group["sensor_id"][()]
    config = DetectorConfig.from_json(algo_group["detector_config"][()])

    context_dict = {}
    context_group = algo_group["context"]

    unknown_keys = set(context_group.keys()) - set(attrs.fields_dict(DetectorContext).keys())
    if unknown_keys:
        raise Exception(f"Unknown field(s) in stored context: {unknown_keys}")

    field_map = {
        "offset_m": None,
        "direct_leakage": None,
        "reference_temperature": None,
        "phase_jitter_comp_reference": None,
        "recorded_threshold_session_config_used": a121.SessionConfig.from_json,
        "close_range_session_config_used": a121.SessionConfig.from_json,
    }
    for k, func in field_map.items():
        try:
            v = context_group[k][()]
        except KeyError:
            continue

        context_dict[k] = func(v) if func else v

    if "recorded_thresholds_mean_sweep" in context_group:
        mean_sweeps = _get_group_items(context_group["recorded_thresholds_mean_sweep"])
        context_dict["recorded_thresholds_mean_sweep"] = mean_sweeps

    if "recorded_thresholds_noise_std" in context_group:
        noise_stds = _get_group_items(context_group["recorded_thresholds_noise_std"])
        context_dict["recorded_thresholds_noise_std"] = noise_stds

    if "bg_noise_std" in context_group:
        bg_noise_std = _get_group_items(context_group["bg_noise_std"])
        context_dict["bg_noise_std"] = bg_noise_std

    context = DetectorContext(**context_dict)

    return sensor_id, config, context


def _get_group_items(group: h5py.Group) -> list[npt.NDArray]:
    group_items = []

    i = 0
    while True:
        try:
            v = group[f"index_{i}"][()]
        except KeyError:
            break

        group_items.append(v)
        i += 1
    return group_items
