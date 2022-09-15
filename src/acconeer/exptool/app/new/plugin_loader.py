# Copyright (c) Acconeer AB, 2022
# All rights reserved

from __future__ import annotations

from .app_model import PluginSpec


def load_default_plugins() -> list[PluginSpec]:
    from acconeer.exptool.a121.algo.distance._detector_plugin import DISTANCE_DETECTOR_PLUGIN
    from acconeer.exptool.a121.algo.presence._detector_plugin import PRESENCE_DETECTOR_PLUGIN
    from acconeer.exptool.a121.algo.sparse_iq._plugin import SPARSE_IQ_PLUGIN
    from acconeer.exptool.a121.algo.virtual_button._plugin import VIRTUAL_BUTTON_PLUGIN

    return [
        SPARSE_IQ_PLUGIN,
        DISTANCE_DETECTOR_PLUGIN,
        PRESENCE_DETECTOR_PLUGIN,
        VIRTUAL_BUTTON_PLUGIN,
    ]
