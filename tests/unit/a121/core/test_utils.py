# Copyright (c) Acconeer AB, 2022
# All rights reserved

# type: ignore

import enum
import json

import packaging.version
import pytest

from acconeer.exptool.a121._core import utils


def test_convert_validate_int_ok_value():
    _ = utils.convert_validate_int(3)
    _ = utils.convert_validate_int(3.0)


def test_convert_validate_int_type_errors():
    with pytest.raises(TypeError):
        _ = utils.convert_validate_int("3")

    with pytest.raises(TypeError):
        _ = utils.convert_validate_int(3.5)


def test_convert_validate_int_boundaries():
    with pytest.raises(ValueError):
        _ = utils.convert_validate_int(0, min_value=1)

    with pytest.raises(ValueError):
        _ = utils.convert_validate_int(1, max_value=0)


def test_validate_float_ok_value():
    _ = utils.validate_float(3.1)
    _ = utils.validate_float(3.1, max_value=3.1)
    _ = utils.validate_float(3.1, min_value=3.1)
    _ = utils.validate_float(3.1, min_value=3.0, max_value=3.2)


def test_validate_float_type_errors():
    with pytest.raises(TypeError):
        _ = utils.validate_float("3.1")


def test_validate_float_boundaries():
    with pytest.raises(ValueError):
        _ = utils.validate_float(0.0, min_value=1.0)

    with pytest.raises(ValueError):
        _ = utils.validate_float(1.0, max_value=0.0)

    with pytest.raises(ValueError):
        _ = utils.validate_float(0.0, max_value=0.0, inclusive=False)

    with pytest.raises(ValueError):
        _ = utils.validate_float(0.1, min_value=0.0, max_value=0.1, inclusive=False)


class Wrappee:
    def __init__(self):
        self._rw_property = 10

    @property
    def ro_property(self) -> int:
        """RO docstring"""
        return 5

    @property
    def rw_property(self) -> int:
        """RW docstring"""
        return self._rw_property

    @rw_property.setter
    def rw_property(self, value) -> None:
        self._rw_property = value


class Wrapper:
    ro_property = utils.ProxyProperty[int](
        lambda wrapper: wrapper.get_first(), Wrappee.ro_property
    )
    rw_property = utils.ProxyProperty[int](
        lambda wrapper: wrapper.get_first(), Wrappee.rw_property
    )

    def __init__(self, wrappee):
        self.wrappees = [wrappee]

    def get_first(self):
        return self.wrappees[0]


def test_proxy_descriptor():
    wrappee = Wrappee()
    wrapper = Wrapper(wrappee)

    assert wrappee.ro_property == wrapper.ro_property == 5

    # The proxy property should repsect read-only
    with pytest.raises(AttributeError):
        wrapper.ro_property = 5

    assert wrapper.rw_property == wrappee.rw_property == 10

    wrapper.rw_property = 20
    assert wrapper.rw_property == wrappee.rw_property == 20

    wrappee.rw_property = 10
    assert wrapper.rw_property == wrappee.rw_property == 10


def test_proxy_descriptor_preserves_docstring():
    assert Wrappee.ro_property.__doc__ == Wrapper.ro_property.__doc__ == "RO docstring"


def test_proxy_descriptor_edge_cases():
    with pytest.raises(TypeError):

        class Wrapper2:
            wrong_type = utils.ProxyProperty[int](lambda wrapper: wrapper.get_first(), prop=3)


def test_unextend():
    argument = [{1: "test"}]
    assert utils.unextend(argument) == "test"


def test_unextend_bad_argument():
    argument = ["test"]
    with pytest.raises(ValueError):
        utils.unextend(argument)


def test_create_extended_structure():
    structure = [{2: "foo", 1: "bar"}, {1: "baz"}]
    items = utils.iterate_extended_structure(structure)
    recreated_structure = utils.create_extended_structure(items)

    assert [list(d.items()) for d in recreated_structure] == [list(d.items()) for d in structure]

    # Catch that we must start with group index 0
    with pytest.raises(ValueError):
        utils.create_extended_structure([(1, 0, "foo")])

    # Catch that we can't skip a group index
    with pytest.raises(ValueError):
        utils.create_extended_structure([(0, 0, "foo"), (2, 0, "bar")])

    # Catch duplicate sensor id in a group
    with pytest.raises(ValueError):
        utils.create_extended_structure([(0, 0, "foo"), (0, 0, "bar")])


def test_entity_json_encoder():
    SomeEnum = enum.Enum("SomeEnum", ["FOO", "BAR"])
    assert SomeEnum.FOO.value == 1

    dump_dict = {
        "some_enum_value": SomeEnum.BAR,
        "some_other_value": 123,
    }
    expected = {
        "some_enum_value": "BAR",
        "some_other_value": 123,
    }
    actual = json.loads(json.dumps(dump_dict, cls=utils.EntityJSONEncoder))

    assert actual == expected
    for k, expected_v in expected.items():
        assert type(actual[k]) is type(expected_v)


@pytest.mark.parametrize(
    ("raw", "version"),
    [
        ("a121-v1.2.3", "1.2.3"),
        ("a121-v1.2.3-rc4", "1.2.3rc4"),
        ("a121-v1.2.3-123-g0e03503be1", "1.2.4.dev123+g0e03503be1"),
        ("a121-v1.2.3-rc4-123-g0e03503be1", "1.2.3rc5.dev123+g0e03503be1"),
    ],
)
def test_parse_rss_version(raw, version):
    assert utils.parse_rss_version(raw) == packaging.version.Version(version)


def test_rss_version_order():
    correctly_ordered_versions = [
        "a121-v1.2.3",
        "a121-v1.2.3-1-g123",
        "a121-v1.2.3-2-g123",
        "a121-v1.2.4-rc1",
        "a121-v1.2.4-rc1-1-g123",
        "a121-v1.2.4-rc1-2-g123",
        "a121-v1.2.4-rc2",
        "a121-v1.2.4-rc2-1-g123",
        "a121-v1.2.4",
    ]
    correctly_ordered_versions = [utils.parse_rss_version(s) for s in correctly_ordered_versions]
    assert correctly_ordered_versions == sorted(correctly_ordered_versions)


@pytest.mark.parametrize(
    ("ticks", "minimum_tick", "expected_ticks"),
    [
        ([0], None, [0]),
        ([99], None, [99]),
        ([40, 60], None, [40, 60]),
        ([90, 0], None, [90, 100]),
        ([90, 10], None, [90, 110]),
        ([10], 0, [10]),
        ([10], 209, [210]),
        ([10], 210, [210]),
        ([10], 211, [310]),
        ([10, 90], 185, [210, 190]),
        ([10, 90], 195, [310, 290]),
    ],
)
def test_unwrap_ticks_normal_cases(ticks, minimum_tick, expected_ticks):
    expected = (expected_ticks, max(expected_ticks))
    assert utils.unwrap_ticks(ticks, minimum_tick, limit=100) == expected


def test_unwrap_ticks_special_cases():
    assert utils.unwrap_ticks([], None) == ([], None)

    with pytest.raises(Exception):
        utils.unwrap_ticks([-1], None, limit=100)

    with pytest.raises(Exception):
        utils.unwrap_ticks([100], None, limit=100)
