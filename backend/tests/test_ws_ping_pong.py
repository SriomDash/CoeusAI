import pytest
from fastapi.testclient import TestClient

from backend.main import app


def test_ws_ping_pong():
    client = TestClient(app)

    with client.websocket_connect("/chat/ws") as ws:
        first = ws.receive_json()
        assert first["message"] == "connected"

       
        ws.send_text("ping")

       
        msg = ws.receive_json()
        assert msg["type"] == "pong"
        assert msg["status"] == "healthy"


def test_ws_health_message():
    client = TestClient(app)

    with client.websocket_connect("/chat/ws") as ws:
        _ = ws.receive_json()  

        ws.send_text("health")
        msg = ws.receive_json()
        assert msg["type"] == "health"
        assert msg["status"] == "healthy"