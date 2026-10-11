"""Tests for the deploy script's resilient policy client and connect helper."""

import os
import socket
import sys
import threading
import time

import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from franka_control.scripts.deploy_policy import (  # noqa: E402
    ResilientPolicyClient,
    _wait_for_policy_server,
)


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class _FakePolicy:
    """client_factory product: fails infer() while ``fail`` is True."""

    def __init__(self, fail: bool):
        self.fail = fail

    def get_server_metadata(self) -> dict:
        return {"policy": "fake"}

    def infer(self, obs: dict) -> dict:
        if self.fail:
            raise ConnectionError("websocket closed")
        return {"actions": obs["tag"]}


def _client(factory, retry_timeout: float = 5.0) -> ResilientPolicyClient:
    """ResilientPolicyClient with the network parts replaced by fakes."""
    return ResilientPolicyClient(
        host="127.0.0.1",
        port=0,
        connect_timeout=0.1,
        retry_timeout=retry_timeout,
        client_factory=factory,
        wait_for_server=lambda timeout: None,
    )


class TestResilientPolicyClient:
    def test_reconnects_and_refreshes_observation(self):
        created = []

        def factory():
            policy = _FakePolicy(fail=not created)  # first instance fails
            created.append(policy)
            return policy

        client = _client(factory)
        assert client.connect() == {"policy": "fake"}

        tags = []

        def obs_builder():
            tags.append(len(tags))
            return {"tag": len(tags)}

        result = client.infer(obs_builder)
        assert result["actions"] == 2      # retried with a refreshed observation
        assert len(created) == 2           # reconnected with a fresh client
        assert tags == [0, 1]              # obs rebuilt once per attempt

    def test_fails_fast_with_zero_retry_timeout(self):
        client = _client(lambda: _FakePolicy(fail=True), retry_timeout=0.0)
        client.connect()
        started = time.monotonic()
        with pytest.raises(RuntimeError, match="unreachable"):
            client.infer(lambda: {"tag": 0})
        assert time.monotonic() - started < 1.0

    def test_gives_up_after_retry_timeout(self):
        created = []

        def factory():
            policy = _FakePolicy(fail=True)
            created.append(policy)
            return policy

        client = _client(factory, retry_timeout=1.0)
        client.connect()
        with pytest.raises(RuntimeError, match="unreachable after 1s"):
            client.infer(lambda: {"tag": 0})
        assert len(created) >= 2  # it did reconnect before giving up

    def test_server_traceback_fails_fast(self):
        # openpi raises RuntimeError when the server answers with an error
        # traceback (e.g. an obs-key mismatch): no retry, raise immediately.
        calls = []

        class _ErrPolicy:
            def get_server_metadata(self) -> dict:
                return {}

            def infer(self, obs: dict) -> dict:
                calls.append(1)
                raise RuntimeError("Error in inference server:\nKeyError: 'state'")

        client = _client(lambda: _ErrPolicy(), retry_timeout=30.0)
        client.connect()
        with pytest.raises(RuntimeError, match="KeyError"):
            client.infer(lambda: {"tag": 0})
        assert len(calls) == 1  # fail fast: exactly one attempt, no retries


class TestWaitForPolicyServer:
    def test_times_out_with_clear_message(self):
        port = _find_free_port()  # nothing listening
        with pytest.raises(TimeoutError, match="unreachable"):
            _wait_for_policy_server("127.0.0.1", port, timeout=0.3)

    def test_returns_once_port_opens(self):
        port = _find_free_port()
        srv = socket.socket()

        def listen():
            time.sleep(0.2)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", port))
            srv.listen(1)

        thread = threading.Thread(target=listen)
        thread.start()
        try:
            _wait_for_policy_server("127.0.0.1", port, timeout=3.0)
        finally:
            thread.join()
            srv.close()
