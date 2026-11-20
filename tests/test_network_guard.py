"""The conftest guard fails any test that opens a non-local connection."""

import socket

import pytest
from conftest import NetworkBlocked


def test_guard_blocks_a_remote_connection():
    """Broken case: without the guard this test would try to reach 192.0.2.1 (TEST-NET-1)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(NetworkBlocked):
            sock.connect(("192.0.2.1", 80))
    finally:
        sock.close()


def test_guard_allows_loopback():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client.connect(server.getsockname())
    finally:
        client.close()
        server.close()
