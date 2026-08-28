"""Linux/openEuler end-to-end control-plane probe: handshake -> route -> close."""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from synapse.protocol.transport import TransportTimeout, UnixSocketListener, UnixSocketTransport


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "synapse-control.sock"
        events: list[dict] = []
        with UnixSocketListener(path) as listener:
            def peer() -> None:
                transport = listener.accept()
                hello = json.loads(transport.recv())
                events.append({"phase": "handshake", "agent": hello["agent"]})
                transport.send(json.dumps({"capabilities": ["route"]}).encode())
                routed = json.loads(transport.recv())
                events.append({"phase": "route", "receiver": routed["receiver"]})
                transport.close()

            thread = threading.Thread(target=peer)
            thread.start()
            client = UnixSocketTransport.connect(path)
            client.send(json.dumps({"agent": "planner"}).encode())
            discovered = json.loads(client.recv())
            client.send(json.dumps({"receiver": "executor", "action": "EXECUTE"}).encode())
            client.close()
            thread.join()
        timeout_path = Path(tmp) / "synapse-timeout.sock"
        with UnixSocketListener(timeout_path, timeout=0.01) as timeout_listener:
            timeout_client = UnixSocketTransport.connect(timeout_path)
            timeout_server = timeout_listener.accept()
            try:
                timeout_server.recv()
            except TransportTimeout:
                events.append({"phase": "timeout", "result": "explicit"})
            else:
                raise AssertionError("accepted peer did not inherit the receive timeout")
            finally:
                timeout_client.close()
                timeout_server.close()
        print(json.dumps({"events": events, "discovered": discovered, "exit_code": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
