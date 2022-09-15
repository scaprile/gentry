# Copyright (c) Acconeer AB, 2022
# All rights reserved

from __future__ import annotations

import abc

from PySide6.QtWidgets import QVBoxLayout, QWidget

from acconeer.exptool.app.new.app_model import AppModel, ViewPluginInterface
from acconeer.exptool.app.new.backend import GeneralMessage
from acconeer.exptool.app.new.ui import utils

from .ui_plugin_base import UiPluginBase


class ViewPluginBase(UiPluginBase, abc.ABC, ViewPluginInterface):
    def __init__(self, app_model: AppModel, view_widget: QWidget) -> None:
        super().__init__(app_model)
        self.__app_model = app_model
        self.__app_model.sig_message_view_plugin.connect(self.handle_message)

        self.__view_widget = view_widget
        self.__view_widget.setLayout(QVBoxLayout())

        self._sticky_widget = QWidget()
        self._scrolly_widget = QWidget()

        self.__view_widget.layout().addWidget(self._sticky_widget)
        self.__view_widget.layout().addWidget(utils.HorizontalSeparator())
        self.__view_widget.layout().addWidget(
            utils.ScrollAreaDecorator(
                utils.TopAlignDecorator(
                    self._scrolly_widget,
                )
            )
        )

    def stop_listening(self) -> None:
        super().stop_listening()
        self.__app_model.sig_message_view_plugin.disconnect(self.handle_message)

    @property
    def sticky_widget(self) -> QWidget:
        """The sticky widget. The sticky area is located at the top."""
        return self._sticky_widget

    @property
    def scrolly_widget(self) -> QWidget:
        """The scrolly widget. The scrolly area is located below the sticky area"""
        return self._scrolly_widget

    @abc.abstractmethod
    def handle_message(self, message: GeneralMessage) -> None:
        pass
