# Copyright (c) Acconeer AB, 2022
# All rights reserved

from __future__ import annotations

import logging
from typing import Any, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from acconeer.exptool import a121
from acconeer.exptool.a121._core import Criticality

from . import pidgets
from .sensor_config_editor import SensorConfigEditor
from .utils import VerticalGroupBox


log = logging.getLogger(__name__)


class SessionConfigEditor(QWidget):
    _session_config: Optional[a121.SessionConfig]
    _server_info: Optional[a121.ServerInfo]

    _sensor_id_pidget: pidgets.UpdateableComboboxParameterWidget

    sig_update = Signal(object)

    SPACING = 15

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

        self._server_info = None

        self._session_config = None

        self.setLayout(QVBoxLayout(self))
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.session_group_box = VerticalGroupBox("Session parameters", parent=self)
        self.session_group_box.layout().setSpacing(self.SPACING)
        self.layout().addWidget(self.session_group_box)

        self._sensor_id_pidget = pidgets.SensorIdParameterWidgetFactory(items=[]).create(self)
        self._sensor_id_pidget.sig_parameter_changed.connect(self._update_sensor_id)
        self.session_group_box.layout().addWidget(self._sensor_id_pidget)

        self._update_rate_pidget = pidgets.OptionalFloatParameterWidgetFactory(
            name_label_text="Update rate:",
            limits=(0.1, 1e4),
            decimals=1,
            init_set_value=10.0,
            suffix="Hz",
            checkbox_label_text="Limit",
        ).create(self)
        self._update_rate_pidget.sig_parameter_changed.connect(self._update_update_rate)
        self.session_group_box.layout().addWidget(self._update_rate_pidget)

        self._sensor_config_editor = SensorConfigEditor(self)
        self._sensor_config_editor.sig_update.connect(self._broadcast)
        self.layout().addWidget(self._sensor_config_editor)

    def set_data(self, session_config: Optional[a121.SessionConfig]) -> None:
        self._session_config = session_config
        if session_config is not None:
            self._sensor_config_editor.set_data(session_config.sensor_config)

    def sync(self) -> None:
        self._update_ui()
        self._sensor_config_editor.sync()

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled and self._session_config is not None)

    def _broadcast(self) -> None:
        self.sig_update.emit(self._session_config)

    def _handle_validation_results(self, results: list[a121.ValidationResult]) -> None:
        if results == []:
            self._update_rate_pidget.set_note_text(None)
            self._sensor_id_pidget.set_note_text(None)
            return

        for result in results:
            self._handle_validation_result(result)

    def _handle_validation_result(self, result: a121.ValidationResult) -> None:
        if self._session_config is None:
            raise RuntimeError(
                "SessionConfigEditor's config is None while ValidationResults are being handled."
            )

        if result.aspect == "update_rate":
            self._update_rate_pidget.set_note_text(result.message, result.criticality)
        elif result.aspect == "sensor_id":
            self._sensor_id_pidget.set_note_text(result.message, result.criticality)

    def _update_update_rate(self, value: Any) -> None:
        if self._session_config is None:
            raise TypeError("SessionConfig is None")

        try:
            self._session_config.update_rate = value
        except Exception as e:
            self._update_rate_pidget.set_note_text(e.args[0], Criticality.ERROR)
        else:
            self._handle_validation_results(self._session_config._collect_validation_results())

        self._broadcast()

    def _update_sensor_id(self, value: Any) -> None:
        if self._session_config is None:
            raise TypeError("SessionConfig is None")

        try:
            self._session_config.sensor_id = value
        except Exception as e:
            self._sensor_id_pidget.set_note_text(e.args[0], Criticality.ERROR)
        else:
            self._handle_validation_results(self._session_config._collect_validation_results())

        self._broadcast()

    def _update_ui(self) -> None:
        if self._session_config is None:
            log.debug("could not update ui as SessionConfig is None")
            return

        self._update_rate_pidget.set_parameter(self._session_config.update_rate)
        self._sensor_id_pidget.set_parameter(self._session_config.sensor_id)

    def update_available_sensor_list(self, server_info: Optional[a121.ServerInfo]) -> None:
        self._sensor_id_pidget.update_available_sensor_list(server_info)
