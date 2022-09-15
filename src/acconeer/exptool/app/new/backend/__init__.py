# Copyright (c) Acconeer AB, 2022
# All rights reserved

from ._backend import Backend, ClosedTask
from ._backend_plugin import BackendPlugin
from ._message import (
    BackendPluginStateMessage,
    ConnectionStateMessage,
    GeneralMessage,
    Message,
    PluginStateMessage,
    StatusMessage,
)
from ._model import is_task
