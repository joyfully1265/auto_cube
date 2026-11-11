"""Input-device abstractions used by the controllers.

Re-exported from :mod:`usb_loopback.client.io_interface` so there is a single
definition of the ``KeySender``/``MouseSender`` contracts.
"""

from usb_loopback.client.io_interface import (  # noqa: F401
    KeySender,
    MouseSender,
    SocketKeySender,
    SocketMouseSender,
    create_key_sender,
    create_mouse_sender,
)

__all__ = [
    "KeySender",
    "MouseSender",
    "SocketKeySender",
    "SocketMouseSender",
    "create_key_sender",
    "create_mouse_sender",
]
