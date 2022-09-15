# Copyright (c) Acconeer AB, 2022
# All rights reserved

import h5py
import importlib_metadata

from acconeer.exptool import a121


def assert_record_equals(record_a, record_b):
    attrs = [
        "extended_metadata",
        "extended_results",
        "lib_version",
        "num_frames",
        "server_info",
        "session_config",
        "timestamp",
        "uuid",
    ]
    for attr in attrs:
        attr_a = getattr(record_a, attr)
        attr_b = getattr(record_b, attr)
        if attr == "extended_results":
            attr_a = list(attr_a)
            attr_b = list(attr_b)

        assert attr_a == attr_b, f".{attr} differs:\n{attr_a},\n{attr_b}"


def test_init_defaults_with_path(tmp_file_path):
    recorder = a121.H5Recorder(tmp_file_path)
    assert recorder.owns_file is True
    assert recorder.path == tmp_file_path

    with h5py.File(tmp_file_path, "r") as f:
        assert f["lib_version"][()].decode() == importlib_metadata.version("acconeer-exptool")
        assert f["generation"][()].decode() == "a121"


def test_init_defaults_with_file_object(tmp_file_path):
    with h5py.File(tmp_file_path, "x") as f:
        recorder = a121.H5Recorder(f)
        assert recorder.owns_file is False
        assert recorder.path is None
        assert f["lib_version"][()].decode() == importlib_metadata.version("acconeer-exptool")
        assert f["generation"][()].decode() == "a121"


def test_sample_whole_record(tmp_path, ref_record):
    filename = tmp_path / "empty.h5"
    recorder = a121.H5Recorder(
        filename,
        _lib_version=ref_record.lib_version,
        _timestamp=ref_record.timestamp,
        _uuid=ref_record.uuid,
    )

    recorder._start(
        client_info=ref_record.client_info,
        extended_metadata=ref_record.extended_metadata,
        server_info=ref_record.server_info,
        session_config=ref_record.session_config,
    )

    for extended_results in ref_record.extended_results:
        recorder._sample(extended_results)
    recorder._stop()

    with a121.open_record(filename) as record:
        assert_record_equals(record, ref_record)

    record = a121.load_record(filename)
    assert_record_equals(record, ref_record)
