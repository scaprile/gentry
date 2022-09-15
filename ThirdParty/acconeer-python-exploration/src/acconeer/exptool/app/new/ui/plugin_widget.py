# Copyright (c) Acconeer AB, 2022
# All rights reserved

from __future__ import annotations

import importlib.resources
import logging
from typing import Any, Optional

import qtawesome as qta

from PySide6 import QtCore
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import pyqtgraph as pg

from acconeer.exptool.app import resources  # type: ignore[attr-defined]
from acconeer.exptool.app.new._enums import PluginFamily
from acconeer.exptool.app.new.app_model import AppModel, PluginSpec
from acconeer.exptool.app.new.pluginbase import PlotPluginBase, PluginSpecBase


log = logging.getLogger(__name__)


class PluginSelectionButton(QPushButton):
    plugin: PluginSpec

    def __init__(self, plugin: PluginSpecBase, parent: QWidget) -> None:
        super().__init__(parent)

        self.plugin = plugin

        self.setText(plugin.title)
        self.setStyleSheet("text-align: left; font-weight: bold;")
        self.setCheckable(True)


class PluginSelectionButtonGroup(QButtonGroup):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.setExclusive(True)

    def addButton(self, button: PluginSelectionButton) -> None:
        super().addButton(button)

    def checkedButton(self) -> PluginSelectionButton:
        button = super().checkedButton()
        assert isinstance(button, PluginSelectionButton)
        return button

    def buttons(self) -> list[PluginSelectionButton]:
        buttons = super().buttons()
        assert isinstance(buttons, list)
        assert all(isinstance(e, PluginSelectionButton) for e in buttons)
        return buttons


class PluginSelection(QWidget):
    def __init__(self, app_model: AppModel, parent: QWidget) -> None:
        super().__init__(parent)

        self.app_model = app_model

        app_model.sig_notify.connect(self._on_app_model_update)

        self.setLayout(QVBoxLayout(self))
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(11)

        group_boxes = {}
        for family in PluginFamily:
            group_box = QGroupBox(self)
            group_box.setTitle(family.value)
            group_box.setHidden(True)
            group_box.setLayout(QVBoxLayout(group_box))
            self.layout().addWidget(group_box)
            group_boxes[family] = group_box

        self.button_group = PluginSelectionButtonGroup(self)
        self.button_group.buttonClicked.connect(self._on_load_click)

        for plugin in app_model.plugins:
            assert isinstance(plugin, PluginSpecBase)
            group_box = group_boxes[plugin.family]
            group_box.setHidden(False)

            button = PluginSelectionButton(plugin, group_box)
            self.button_group.addButton(button)
            group_box.layout().addWidget(button)

            if plugin.description:
                label = QLabel(group_box)
                label.setText(plugin.description)
                label.setWordWrap(True)
                group_box.layout().addWidget(label)

        self.unload_button = QPushButton("Deselect", self)
        self.unload_button.setStyleSheet("text-align: left;")
        self.unload_button.setFlat(True)
        self.unload_button.clicked.connect(self._on_unload_click)
        self.layout().addWidget(self.unload_button)

    def _on_load_click(self):
        plugin = self.button_group.checkedButton().plugin
        self.app_model.load_plugin(plugin)

    def _on_unload_click(self):
        self.app_model.load_plugin(None)

    def _on_app_model_update(self, app_model: AppModel) -> None:
        plugin: Optional[PluginSpec] = app_model.plugin

        if plugin is None:
            self.button_group.setExclusive(False)

            for button in self.button_group.buttons():
                button.setChecked(False)

            self.button_group.setExclusive(True)
        else:
            buttons = self.button_group.buttons()
            button = next(b for b in buttons if b.plugin == plugin)
            button.setChecked(True)

        self.unload_button.setEnabled(plugin is not None)

        self.setEnabled(app_model.plugin_state.is_steady)


class PlotPlaceholder(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setLayout(QHBoxLayout(self))

        self.layout().addStretch(1)

        icon_widget = qta.IconWidget()
        icon_widget.setIconSize(QtCore.QSize(36, 36))
        icon_widget.setIcon(qta.icon("ph.arrow-left-bold", color="#4d5157"))
        self.layout().addWidget(icon_widget)

        label = QLabel("Select a module to begin", self)
        label.setStyleSheet("font-size: 20px;")
        label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout().addWidget(label)

        self.layout().addStretch(1)


class PluginPlotArea(QFrame):
    _FPS = 60

    def __init__(self, app_model: AppModel, parent: QWidget) -> None:
        super().__init__(parent)

        self.app_model = app_model

        self.child_widget = PlotPlaceholder()
        self.plot_plugin: Optional[PlotPluginBase] = None

        self.setObjectName("PluginPlotArea")
        self.setStyleSheet("QFrame#PluginPlotArea {background: #fff; border: 0;}")
        self.setFrameStyle(0)

        self.setLayout(QVBoxLayout(self))
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.layout().addWidget(self.child_widget)

        self.startTimer(int(1000 / self._FPS))

        app_model.sig_load_plugin.connect(self._on_app_model_load_plugin)
        if isinstance(app_model.plugin, PluginSpecBase):
            self._on_app_model_load_plugin(app_model.plugin)
        elif app_model.plugin is not None:
            raise RuntimeError(f"{type(app_model.plugin)} is not a PluginSpecBase.")

    def timerEvent(self, event: QtCore.QTimerEvent) -> None:
        if self.plot_plugin is None:
            return

        self.plot_plugin.draw()

    def _on_app_model_load_plugin(self, plugin: Optional[PluginSpecBase]) -> None:
        log.debug(
            f"{self.__class__.__name__} is going to replace its plot_plugin "
            + f"({self.plot_plugin.__class__.__name__}) in favour of {plugin}"
        )
        self.plot_plugin = None
        self.child_widget.deleteLater()

        if plugin is None:
            self.child_widget = PlotPlaceholder()
        else:
            self.child_widget = pg.GraphicsLayoutWidget()
            self.plot_plugin = plugin.create_plot_plugin(
                app_model=self.app_model,
                plot_layout=self.child_widget.ci,
            )

        self.layout().addWidget(self.child_widget)


class ControlPlaceholder(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setLayout(QGridLayout(self))

        with importlib.resources.path(resources, "icon-black.svg") as path:
            icon = QSvgWidget(str(path), self)

        icon.setMaximumSize(60, 60)
        icon.renderer().setAspectRatioMode(QtCore.Qt.KeepAspectRatio)
        effect = QGraphicsOpacityEffect(icon)
        effect.setOpacity(0.1)
        icon.setGraphicsEffect(effect)

        self.layout().addWidget(icon)


class PluginControlArea(QWidget):
    def __init__(self, app_model: AppModel, parent: QWidget) -> None:
        super().__init__(parent)

        self.app_model = app_model
        self.app_model.sig_load_plugin.connect(self._on_app_model_load_plugin)

        self.child_widget: QWidget = ControlPlaceholder()
        self.view_plugin: Optional[Any] = None

        self.setLayout(QVBoxLayout(self))
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.layout().addWidget(self.child_widget)

        if isinstance(app_model.plugin, PluginSpecBase):
            self._on_app_model_load_plugin(app_model.plugin)
        elif app_model.plugin is not None:
            raise RuntimeError(f"{type(app_model.plugin)} is not a PluginSpecBase.")

    def _on_app_model_load_plugin(self, plugin_spec: Optional[PluginSpecBase]) -> None:
        log.debug(
            f"{self.__class__.__name__} is going to replace its view_plugin"
            + f"({self.view_plugin.__class__.__name__}) in favour of {plugin_spec}"
        )
        self.view_plugin = None
        self.child_widget.deleteLater()

        if plugin_spec is None:
            self.child_widget = ControlPlaceholder()
        else:
            self.child_widget = QWidget()
            self.view_plugin = plugin_spec.create_view_plugin(
                app_model=self.app_model,
                view_widget=self.child_widget,
            )

        self.layout().addWidget(self.child_widget)
