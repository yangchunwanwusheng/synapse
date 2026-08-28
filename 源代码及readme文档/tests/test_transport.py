from __future__ import annotations

import socket
import stat
import struct
import threading

import pytest

from synapse.eval.metrics import Metrics
from synapse.protocol.messages import Message
from synapse.protocol.scheduler import Scheduler
from synapse.protocol.transport import (
    FrameError,
    InProcessTransport,
    TransportClosed,
    TransportTimeout,
    UnixSocketListener,
    UnixSocketTransport,
)


def test_inprocess_pair_and_repeated_close():
    sender, receiver = InProcessTransport.pair()
    assert sender.send(b"hello") == 5
    assert receiver.recv() == b"hello"
    sender.close()
    sender.close()
    with pytest.raises(TransportClosed):
        receiver.recv()


def test_inprocess_close_wakes_local_blocked_receiver():
    endpoint, peer = InProcessTransport.pair()
    result = []

    def receive() -> None:
        try:
            endpoint.recv()
        except TransportClosed:
            result.append("closed")

    thread = threading.Thread(target=receive)
    thread.start()
    endpoint.close()
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert result == ["closed"]
    peer.close()


def test_inprocess_send_detects_closed_peer():
    endpoint, peer = InProcessTransport.pair()
    peer.close()
    with pytest.raises(TransportClosed, match="peer"):
        endpoint.send(b"must not be silently queued")
    assert endpoint.transport_bytes == 0
    endpoint.close()


def test_scheduler_wraps_transport_and_counts_real_frame():
    class Agent:
        agent_id = "b"
        role = "worker"

    sender, receiver = InProcessTransport.pair()
    metrics = Metrics()
    msg = Message("m1", "a", "b", "ASK", text="你好")
    scheduler = Scheduler([Agent()], metrics=metrics, transport=sender)
    assert scheduler.send(msg).agent_id == "b"
    assert receiver.recv() == msg.to_wire().encode("utf-8")
    assert metrics.transport_bytes == len(msg.to_wire().encode("utf-8"))


def test_scheduler_does_not_count_failed_transport_as_delivered():
    class Agent:
        agent_id = "b"
        role = "worker"

    sender, receiver = InProcessTransport.pair()
    receiver.close()
    metrics = Metrics()
    scheduler = Scheduler([Agent()], metrics=metrics, transport=sender)
    with pytest.raises(TransportClosed):
        scheduler.send(Message("m1", "a", "b", "ASK", text="not delivered"))
    assert metrics.messages == 0
    assert metrics.transport_bytes == 0
    sender.close()


def test_scheduler_counts_unix_socket_frame_bytes():
    class Agent:
        agent_id = "b"
        role = "worker"

    left, right = socket.socketpair()
    sender = UnixSocketTransport(left)
    receiver = UnixSocketTransport(right)
    metrics = Metrics()
    msg = Message("m1", "a", "b", "ASK", text="framed")
    scheduler = Scheduler([Agent()], metrics=metrics, transport=sender)

    assert scheduler.send(msg).agent_id == "b"
    wire = msg.to_wire().encode("utf-8")
    assert receiver.recv() == wire
    assert metrics.transport_bytes == 4 + len(wire)
    sender.close()
    receiver.close()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="AF_UNIX required")
def test_unix_framing_concurrent_send_and_byte_conservation(tmp_path):
    path = tmp_path / "control.sock"
    with UnixSocketListener(path) as listener:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        client = UnixSocketTransport.connect(path)
        server = listener.accept()
        payloads = [f"message-{i}".encode() * 100 for i in range(12)]
        threads = [threading.Thread(target=client.send, args=(p,)) for p in payloads]
        for thread in threads:
            thread.start()
        received = [server.recv() for _ in payloads]
        for thread in threads:
            thread.join()
        assert sorted(received) == sorted(payloads)
        assert client.transport_bytes == sum(4 + len(p) for p in payloads)
        client.close()
        server.close()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="AF_UNIX required")
def test_missing_peer_and_accept_timeout(tmp_path):
    with pytest.raises(TransportClosed, match="cannot connect"):
        UnixSocketTransport.connect(tmp_path / "missing.sock", timeout=0.05)
    with UnixSocketListener(tmp_path / "idle.sock", timeout=0.01) as listener:
        with pytest.raises(TransportTimeout):
            listener.accept()


def test_invalid_transport_limits_fail_fast():
    left, right = socket.socketpair()
    with pytest.raises(ValueError, match="max_frame"):
        UnixSocketTransport(left, max_frame=-1)
    left.close()
    right.close()


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="AF_UNIX required")
def test_accepted_peer_inherits_receive_timeout(tmp_path):
    path = tmp_path / "timeout.sock"
    with UnixSocketListener(path, timeout=0.01) as listener:
        client = UnixSocketTransport.connect(path)
        server = listener.accept()
        with pytest.raises(TransportTimeout, match="receive"):
            server.recv()
        client.close()
        server.close()


def test_half_open_and_truncated_frame_faults():
    left, right = socket.socketpair()
    transport = UnixSocketTransport(left)
    right.sendall(struct.pack("!I", 8) + b"abc")
    right.close()
    with pytest.raises(FrameError, match="truncated"):
        transport.recv()
    transport.close()


def test_peer_death_and_idempotent_close():
    left, right = socket.socketpair()
    transport = UnixSocketTransport(left)
    right.close()
    with pytest.raises(TransportClosed):
        transport.recv()
    transport.close()
    transport.close()
    with pytest.raises(TransportClosed):
        transport.send(b"x")


def test_oversized_frame_is_rejected():
    left, right = socket.socketpair()
    transport = UnixSocketTransport(left, max_frame=3)
    with pytest.raises(FrameError, match="exceeds"):
        transport.send(b"four")
    transport.close()
    right.close()


def test_payload_timeout_closes_desynchronized_stream():
    left, right = socket.socketpair()
    left.settimeout(0.01)
    transport = UnixSocketTransport(left)
    right.sendall(struct.pack("!I", 8))
    with pytest.raises(TransportTimeout):
        transport.recv()
    with pytest.raises(TransportClosed):
        transport.recv()
    right.close()


def test_send_timeout_closes_desynchronized_stream():
    class TimeoutSocket:
        def __init__(self):
            self.closed = False

        def sendall(self, _frame):
            raise socket.timeout

        def shutdown(self, _how):
            pass

        def close(self):
            self.closed = True

    sock = TimeoutSocket()
    transport = UnixSocketTransport(sock)
    with pytest.raises(TransportTimeout, match="send"):
        transport.send(b"partially written frame")
    assert sock.closed
    assert transport.transport_bytes == 0
    with pytest.raises(TransportClosed):
        transport.send(b"must not reuse stream")


def test_partial_prefix_timeout_closes_desynchronized_stream():
    left, right = socket.socketpair()
    left.settimeout(0.01)
    transport = UnixSocketTransport(left)
    right.sendall(b"\x00\x00")
    with pytest.raises(TransportTimeout):
        transport.recv()
    with pytest.raises(TransportClosed):
        transport.recv()
    right.close()
