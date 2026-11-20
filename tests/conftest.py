"""Test guard: any network connection to a host that is not local fails the test."""

import ipaddress
import socket

import pytest

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex


class NetworkBlocked(RuntimeError):
    pass


def _is_local(address) -> bool:
    if isinstance(address, (str, bytes)):  # AF_UNIX path
        return True
    host = address[0]
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _guarded_connect(self, address):
    if not _is_local(address):
        raise NetworkBlocked(f"test tried to open a network connection to {address!r}")
    return _real_connect(self, address)


def _guarded_connect_ex(self, address):
    if not _is_local(address):
        raise NetworkBlocked(f"test tried to open a network connection to {address!r}")
    return _real_connect_ex(self, address)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _guarded_connect_ex)
    yield



@pytest.fixture
def api():
    """A fresh TaskDesk server on 127.0.0.1 with seeded data."""
    from toolcut.taskdesk.server import TaskDeskServer

    with TaskDeskServer() as server:
        yield server
