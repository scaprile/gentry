# Copyright (c) Acconeer AB, 2022
# All rights reserved

import numpy as np
import numpy.testing as npt
import pytest

from acconeer.exptool import a121
from acconeer.exptool.a121.algo import distance


def test_get_subsweep_configs():
    sensor_config = a121.SensorConfig(
        subsweeps=[
            a121.SubsweepConfig(profile=a121.Profile.PROFILE_1),
            a121.SubsweepConfig(profile=a121.Profile.PROFILE_2),
            a121.SubsweepConfig(profile=a121.Profile.PROFILE_3),
        ],
    )

    actual_subsweeps = distance.Processor._get_subsweep_configs(sensor_config, [1, 0])
    actual = [c.profile for c in actual_subsweeps]
    expected = [a121.Profile.PROFILE_2, a121.Profile.PROFILE_1]
    assert actual == expected


def test_get_profile():
    actual = distance.Processor._get_profile(
        [
            a121.SubsweepConfig(profile=a121.Profile.PROFILE_2),
            a121.SubsweepConfig(profile=a121.Profile.PROFILE_2),
        ]
    )
    assert actual == a121.Profile.PROFILE_2

    with pytest.raises(Exception):
        distance.Processor._get_profile(
            [
                a121.SubsweepConfig(profile=a121.Profile.PROFILE_2),
                a121.SubsweepConfig(profile=a121.Profile.PROFILE_2),
                a121.SubsweepConfig(profile=a121.Profile.PROFILE_3),
            ]
        )


def test_get_start_point():
    actual = distance.Processor._get_start_point(
        [
            a121.SubsweepConfig(start_point=100),
            a121.SubsweepConfig(start_point=150),
        ]
    )
    assert actual == 100


def test_get_num_points():
    actual = distance.Processor._get_num_points(
        [
            a121.SubsweepConfig(num_points=100),
            a121.SubsweepConfig(num_points=150),
        ]
    )
    assert actual == 250


def test_validate_range():
    distance.Processor._validate_range(
        [
            a121.SubsweepConfig(
                start_point=100,
                num_points=3,
                step_length=2,
            ),
            a121.SubsweepConfig(
                start_point=106,
                num_points=4,
                step_length=2,
            ),
        ]
    )

    with pytest.raises(Exception):
        distance.Processor._validate_range(
            [
                a121.SubsweepConfig(
                    start_point=100,
                    num_points=3,
                    step_length=2,
                ),
                a121.SubsweepConfig(
                    start_point=100,
                    num_points=4,
                    step_length=2,
                ),
            ]
        )


def test_apply_phase_jitter_compensation():
    frame = np.array([0 + 0, 1 + 1j, 2 + 2j, 3 + 3j])
    context = distance.ProcessorContext(
        direct_leakage=frame, phase_jitter_comp_ref=np.array([0.0])
    )
    lb_angle = np.array([np.pi / 2])

    actual_adjuster_frame = distance.Processor._apply_phase_jitter_compensation(
        context=context, frame=frame, lb_angle=lb_angle
    )
    assert actual_adjuster_frame[0] == 0.0 + 0.0j
    assert actual_adjuster_frame[1] == 2.0 + 0.0j
    assert actual_adjuster_frame[2] == 4.0 + 0.0j
    assert actual_adjuster_frame[3] == 6.0 + 0.0j


def test_get_distance_filter_coeffs():
    (actual_B, actual_A) = distance.Processor.get_distance_filter_coeffs(a121.Profile.PROFILE_1, 1)

    assert actual_B[0] == pytest.approx(0.00844269, 0.01)
    assert actual_B[1] == pytest.approx(0.01688539, 0.01)
    assert actual_B[2] == pytest.approx(0.00844269, 0.01)

    assert actual_A[0] == pytest.approx(1.0, 0.01)
    assert actual_A[1] == pytest.approx(-1.72377617, 0.01)
    assert actual_A[2] == pytest.approx(0.75754694, 0.01)

    (actual_B, actual_A) = distance.Processor.get_distance_filter_coeffs(a121.Profile.PROFILE_5, 6)
    assert actual_B[0] == pytest.approx(0.00490303, 0.01)
    assert actual_B[1] == pytest.approx(0.00980607, 0.01)
    assert actual_B[2] == pytest.approx(0.00490303, 0.01)

    assert actual_A[0] == pytest.approx(1.0, 0.01)
    assert actual_A[1] == pytest.approx(-1.79238564, 0.01)
    assert actual_A[2] == pytest.approx(0.81199778, 0.01)


def test_find_peaks():
    abs_sweep = np.array([1, 2, 3, 2, 1, 1, 1, 1, 1, 2, 3, 2, 1, 1, 1])
    threshold = np.ones_like(abs_sweep)
    actual_found_peaks = distance.Processor._find_peaks(abs_sweep=abs_sweep, threshold=threshold)

    assert actual_found_peaks[0] == 2
    assert actual_found_peaks[1] == 10


def test_interpolate_peaks():
    abs_sweep = np.array([1, 2, 3, 2, 1])
    peak_idxs = [2]
    start_point = 0
    step_length = 1
    step_length_m = 0.0025

    (actual_est_dists, actual_est_ampls) = distance.Processor.interpolate_peaks(
        abs_sweep=abs_sweep,
        peak_idxs=peak_idxs,
        start_point=start_point,
        step_length=step_length,
        step_length_m=step_length_m,
    )

    assert actual_est_dists[0] == pytest.approx(0.005, 0.0001)
    assert actual_est_ampls[0] == pytest.approx(3, 0.0001)

    abs_sweep = np.array([1, 3, 3, 1])
    peak_idxs = [1]
    start_point = 0
    step_length = 1
    step_length_m = 0.0025

    (actual_est_dists, actual_est_ampls) = distance.Processor.interpolate_peaks(
        abs_sweep=abs_sweep,
        peak_idxs=peak_idxs,
        start_point=start_point,
        step_length=step_length,
        step_length_m=step_length_m,
    )

    assert actual_est_dists[0] == pytest.approx(0.00375, 0.0001)
    assert actual_est_ampls[0] == pytest.approx(3.25, 0.01)


def test_distance_filter_edge_margin():
    profile = a121.Profile.PROFILE_3
    step_length = 4

    actual_filter_edge_margin = distance.Processor.distance_filter_edge_margin(
        profile=profile, step_length=step_length
    )

    assert actual_filter_edge_margin == 15


def test_calculate_cfar_threshold():

    abs_sweep = np.ones(30)
    abs_sweep[4:6] = 2
    idx_cfar_pts = 2 + np.arange(0, 3)
    num_stds = 1
    one_sided = False

    actual_threshold = distance.Processor._calculate_cfar_threshold(
        abs_sweep=abs_sweep,
        idx_cfar_pts=idx_cfar_pts,
        num_stds=num_stds,
        one_side=one_sided,
        abs_noise_std=np.array([0.0]),
    )
    actual_threshold = actual_threshold[~np.isnan(actual_threshold)]
    threshold = np.array(
        [
            1.0,
            1.0,
            1.1666,
            1.3333,
            1.3333,
            1.1666,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
            1.0,
        ]
    )
    npt.assert_almost_equal(actual_threshold, threshold, decimal=4)


def test_calc_cfar_guard_half_length():
    profile = a121.Profile.PROFILE_3
    step_length = 4
    actual_guard_half_length = distance.Processor._calc_cfar_guard_half_length(
        profile=profile, step_length=step_length
    )
    assert actual_guard_half_length == 28


def test_calc_cfar_window_length():
    profile = a121.Profile.PROFILE_3
    step_length = 2
    actual_margin = distance.Processor._calc_cfar_window_length(
        profile=profile, step_length=step_length
    )
    assert actual_margin == 7
