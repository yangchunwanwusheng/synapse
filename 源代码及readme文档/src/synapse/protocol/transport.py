"""Message transports for the SYNAPSE control plane.

The Unix implementation deliberately targets Linux/openEuler.  It uses an
AF_UNIX stream socket with an unsigned 32-bit network-order length prefix so a
receiver never mistakes stream chunks for complete messages.
"""
from __future__ import annotations

import os
import queue
import socket
import stat
import struct
import threading
from pathlib import Path
from typing import Protocol, runtime_checkable

_PREFIX = struct.Struct("!I")
DEFAULT_MAX_FRAME = 16 * 1024 * 1024


class TransportError(RuntimeError):
    """Base class for control-plane transport failures."""


class TransportClosed(TransportError):
    """The transport or its peer was closed."""


class FrameError(TransportError):
    """A truncated or invalid frame was received."""


class TransportTimeout(TransportError):
    """A transport operation exceeded its configured deadline."""


@runtime_checkable
class Transport(Protocol):
    """Blocking, message-oriented byte transport."""

    @property
    def transport_bytes(self) -> int: ...

    def send(self, payload: bytes) -> int: ...

    def recv(self) -> bytes: ...

    def close(self) -> None: ...


class InProcessTransport:
    """Queue-backed transport used by the existing in-process path and tests."""

    _SENTINEL = object()

    def __init__(
        self,
        incoming: queue.Queue,
        outgoing: queue.Queue,
        *,
        local_closed: threading.Event | None = None,
        peer_closed: threading.Event | None = None,
        state_lock: threading.Lock | None = None,
    ):
        self._incoming = incoming
        self._outgoing = outgoing
        self._local_closed = local_closed or threading.Event()
        self._peer_closed = peer_closed or threading.Event()
        self._state_lock = state_lock or threading.Lock()
        self._bytes = 0
        self._lock = threading.Lock()

    @classmethod
    def pair(cls) -> tuple["InProcessTransport", "InProcessTransport"]:
        left: queue.Queue = queue.Queue()
        right: queue.Queue = queue.Queue()
        left_closed = threading.Event()
        right_closed = threading.Event()
        state_lock = threading.Lock()
        return (
            cls(
                left,
                right,
                local_closed=left_closed,
                peer_closed=right_closed,
                state_lock=state_lock,
            ),
            cls(
                right,
                left,
                local_closed=right_closed,
                peer_closed=left_closed,
                state_lock=state_lock,
            ),
        )

    @property
    def transport_bytes(self) -> int:
        return self._bytes

    def send(self, payload: bytes) -> int:
        data = bytes(payload)
        with self._lock:
            with self._state_lock:
                if self._local_closed.is_set():
                    raise TransportClosed("transport is closed")
                if self._peer_closed.is_set():
                    raise TransportClosed("peer closed")
                self._outgoing.put(data)
                self._bytes += len(data)
        return len(data)

    def recv(self) -> bytes:
        if self._local_closed.is_set():
            raise TransportClosed("transport is closed")
        item = self._incoming.get()
        if item is self._SENTINEL:
            raise TransportClosed("peer closed")
        return item

    def close(self) -> None:
        with self._lock:
            with self._state_lock:
                if self._local_closed.is_set():
                    return
                self._local_closed.set()
                # Wake a receive already blocked on this endpoint and notify the peer.
                self._incoming.put(self._SENTINEL)
                self._outgoing.put(self._SENTINEL)


class UnixSocketListener:
    """Owns an AF_UNIX listening socket and its filesystem entry."""

    def __init__(self, path: str | os.PathLike[str], *, timeout: float = 5.0, backlog: int = 8):
        if not hasattr(socket, "AF_UNIX"):
            raise OSError("AF_UNIX is unavailable on this platform")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if backlog <= 0:
            raise ValueError("backlog must be positive")
        self.path = Path(path)
        self._timeout = timeout
        self._closed = False
        self._close_lock = threading.Lock()
        self._bound_identity: tuple[int, int] | None = None
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        try:
            self._sock.bind(os.fspath(self.path))
            bound = self.path.lstat()
            self._bound_identity = (bound.st_dev, bound.st_ino)
            os.chmod(self.path, 0o600)
            self._sock.listen(backlog)
        except BaseException:
            self._sock.close()
            self._remove_owned_socket()
            raise

    def accept(self, *, max_frame: int = DEFAULT_MAX_FRAME) -> "UnixSocketTransport":
        try:
            conn, _ = self._sock.accept()
        except socket.timeout as exc:
            raise TransportTimeout("accept timed out") from exc
        except OSError as exc:
            raise TransportClosed("listener is closed") from exc
        conn.settimeout(self._timeout)
        return UnixSocketTransport(conn, max_frame=max_frame)

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            self._sock.close()
            self._remove_owned_socket()

    def _remove_owned_socket(self) -> None:
        """Unlink only the socket inode created by this listener.

        A path may be replaced between bind and close.  Never remove that
        replacement merely because it has the same name.
        """
        try:
            current = self.path.lstat()
        except FileNotFoundError:
            return
        identity = (current.st_dev, current.st_ino)
        if self._bound_identity == identity and stat.S_ISSOCK(current.st_mode):
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def __enter__(self) -> "UnixSocketListener":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()


class UnixSocketTransport:
    """Length-prefixed AF_UNIX stream transport.

    Concurrent sends are serialized so a prefix and payload cannot interleave.
    There is intentionally no automatic reconnect/backpressure policy here;
    those are follow-up concerns and must be selected by the caller.
    """

    def __init__(self, sock: socket.socket, *, max_frame: int = DEFAULT_MAX_FRAME):
        if not 0 <= max_frame <= 0xFFFFFFFF:
            raise ValueError("max_frame must fit an unsigned 32-bit length prefix")
        self._sock = sock
        self._max_frame = max_frame
        self._closed = False
        self._bytes = 0
        self._send_lock = threading.Lock()
        self._recv_lock = threading.Lock()
        self._close_lock = threading.Lock()

    @classmethod
    def connect(
        cls,
        path: str | os.PathLike[str],
        *,
        timeout: float = 5.0,
        max_frame: int = DEFAULT_MAX_FRAME,
    ) -> "UnixSocketTransport":
        if not hasattr(socket, "AF_UNIX"):
            raise OSError("AF_UNIX is unavailable on this platform")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not 0 <= max_frame <= 0xFFFFFFFF:
            raise ValueError("max_frame must fit an unsigned 32-bit length prefix")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(os.fspath(path))
        except socket.timeout as exc:
            sock.close()
            raise TransportTimeout("connect timed out") from exc
        except OSError as exc:
            sock.close()
            raise TransportClosed(f"cannot connect to Unix socket {path}") from exc
        return cls(sock, max_frame=max_frame)

    @property
    def transport_bytes(self) -> int:
        return self._bytes

    def send(self, payload: bytes) -> int:
        data = bytes(payload)
        if len(data) > self._max_frame:
            raise FrameError(f"frame length {len(data)} exceeds limit {self._max_frame}")
        frame = _PREFIX.pack(len(data)) + data
        with self._send_lock:
            self._ensure_open()
            try:
                self._sock.sendall(frame)
            except socket.timeout as exc:
                # sendall may have written only part of the frame.  The stream
                # boundary is no longer recoverable, so do not allow reuse.
                self.close()
                raise TransportTimeout("send timed out") from exc
            except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                raise TransportClosed("peer is unavailable") from exc
            self._bytes += len(frame)
        return len(frame)

    def recv(self) -> bytes:
        with self._recv_lock:
            self._ensure_open()
            prefix = self._read_exact(_PREFIX.size, allow_clean_eof=True)
            size = _PREFIX.unpack(prefix)[0]
            if size > self._max_frame:
                raise FrameError(f"frame length {size} exceeds limit {self._max_frame}")
            try:
                return self._read_exact(size)
            except TransportTimeout:
                # The prefix has already been consumed. Reusing this byte stream
                # would interpret the remaining payload as a new prefix.
                self.close()
                raise

    def _read_exact(self, size: int, *, allow_clean_eof: bool = False) -> bytes:
        chunks: list[bytes] = []
        remaining = size
        while remaining:
            try:
                chunk = self._sock.recv(remaining)
            except socket.timeout as exc:
                if chunks:
                    self.close()
                raise TransportTimeout("receive timed out") from exc
            except (ConnectionResetError, OSError) as exc:
                raise TransportClosed("peer is unavailable") from exc
            if not chunk:
                if allow_clean_eof and remaining == size:
                    raise TransportClosed("peer closed")
                received = size - remaining
                raise FrameError(f"truncated frame: expected {size} bytes, received {received}")
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def _ensure_open(self) -> None:
        if self._closed:
            raise TransportClosed("transport is closed")

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()

    def __enter__(self) -> "UnixSocketTransport":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()
