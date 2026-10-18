"""Tests for the FastAPI backend — the HTTP/auth/routing layer. Agent logic
is tested elsewhere (test_agents.py, test_planning.py, test_conversation_graph.py);
here the turn graph is mocked so these tests exercise only what's new here:
routes, auth, and request/response shaping.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import support_triage.conversation as conversation_module
from support_triage.api import app


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Each test gets its own checkpoint file so tests don't share state.
    monkeypatch.setattr(
        "support_triage.api._CHECKPOINT_DB", str(tmp_path / "test_checkpoints.sqlite3")
    )
    return TestClient(app)


def test_health_requires_no_auth(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_message_requires_api_key(client):
    response = client.post("/tickets/T-1001/messages", json={"text": "hello"})
    assert response.status_code == 401


def test_message_rejects_wrong_api_key(client):
    response = client.post(
        "/tickets/T-1001/messages", json={"text": "hello"}, headers={"X-API-Key": "wrong"}
    )
    assert response.status_code == 401


def test_message_returns_completed_reply(client, monkeypatch):
    fake_turn_graph = SimpleNamespace(
        invoke=lambda _state: {"final_summary": "the answer", "proposed_actions": []}
    )
    monkeypatch.setattr(conversation_module, "_turn_graph", fake_turn_graph)

    response = client.post(
        "/tickets/T-1001/messages", json={"text": "hello"}, headers={"X-API-Key": "test-key"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["reply"] == "the answer"


def test_message_and_approve_flow(client, monkeypatch):
    proposed_action = {
        "sub_task": "close it",
        "tool": "close_ticket",
        "args": {"ticket_id": "T-1001", "reason": "resolved"},
        "reason": "resolved",
    }
    fake_turn_graph = SimpleNamespace(
        invoke=lambda _state: {
            "final_summary": "Proposing to close the ticket.",
            "proposed_actions": [proposed_action],
        }
    )
    monkeypatch.setattr(conversation_module, "_turn_graph", fake_turn_graph)

    calls = []
    fake_tool = SimpleNamespace(invoke=lambda args: calls.append(args) or "Ticket closed.")
    monkeypatch.setattr(conversation_module, "DESTRUCTIVE_TOOLS", {"close_ticket": fake_tool})

    headers = {"X-API-Key": "test-key"}
    msg_response = client.post(
        "/tickets/T-1001/messages", json={"text": "close it"}, headers=headers
    )
    assert msg_response.status_code == 200
    body = msg_response.json()
    assert body["status"] == "pending_approval"
    assert body["proposed_actions"] == [proposed_action]
    assert calls == []

    approve_response = client.post(
        "/tickets/T-1001/approve", json={"approved": True}, headers=headers
    )
    assert approve_response.status_code == 200
    body = approve_response.json()
    assert body["status"] == "completed"
    assert "Ticket closed." in body["reply"]
    assert calls == [{"ticket_id": "T-1001", "reason": "resolved"}]
