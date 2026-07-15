from __future__ import annotations

from types import SimpleNamespace

from local_ai_bridge.web import server


def test_windows_client_abort_is_recognized() -> None:
    error = ConnectionAbortedError(10053, "client closed the socket")
    assert server._is_client_disconnect(error) is True


def test_get_ignores_client_disconnect_during_response(monkeypatch) -> None:
    handler = object.__new__(server.BridgeHandler)
    handler.path = "/"
    handler.headers = {}
    handler.client_address = ("127.0.0.1", 50000)
    handler.server = SimpleNamespace(
        state=object(),
        server_address=("127.0.0.1", 8765),
    )
    handler.close_connection = False
    handler._client_ip = lambda: "127.0.0.1"
    handler._send_route_response = lambda _response: (_ for _ in ()).throw(
        ConnectionAbortedError(10053, "client closed the socket")
    )
    monkeypatch.setattr(server, "dispatch_get_request", lambda *_args: object())

    handler.do_GET()

    assert handler.close_connection is True
