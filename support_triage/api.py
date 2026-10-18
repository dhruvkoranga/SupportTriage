"""FastAPI backend exposing the conversation graph over HTTP.

Run with:
    uvicorn support_triage.api:app --reload

Every route except /health requires an `X-API-Key` header matching API_KEY
(see .env.example) — see DECISIONS.md #9 for why API-key auth, not OAuth2,
is the right-sized choice here.
"""

import logging
import os
import time
from dataclasses import asdict

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel

from support_triage.conversation_graph import build_conversation_graph
from support_triage.conversation_runner import TurnOutcome, send_message, submit_approval

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("support_triage.api")

_CHECKPOINT_DB = "support_triage_checkpoints.sqlite3"

app = FastAPI(title="Support Triage API")


def require_api_key(x_api_key: str = Header(default="")) -> None:
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(500, "Server misconfigured: API_KEY is not set")
    if x_api_key != expected:
        raise HTTPException(401, "Invalid or missing API key")


class MessageRequest(BaseModel):
    text: str


class ApprovalRequest(BaseModel):
    approved: bool


class TurnResponse(BaseModel):
    status: str
    reply: str | None = None
    draft_summary: str | None = None
    proposed_actions: list[dict] | None = None

    @classmethod
    def from_outcome(cls, outcome: TurnOutcome) -> "TurnResponse":
        return cls(**asdict(outcome))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/tickets/{ticket_id}/messages", response_model=TurnResponse)
def post_message(
    ticket_id: str, body: MessageRequest, _auth: None = Depends(require_api_key)
) -> TurnResponse:
    start = time.monotonic()
    # A fresh checkpointer connection per request — simplest safe option for
    # a demo backend; avoids sharing one sqlite3 connection across concurrent
    # requests (see DECISIONS.md #20).
    with SqliteSaver.from_conn_string(_CHECKPOINT_DB) as checkpointer:
        graph = build_conversation_graph(checkpointer)
        config = {"configurable": {"thread_id": ticket_id}}
        outcome = send_message(graph, config, ticket_id, body.text)

    logger.info(
        "ticket_id=%s event=message status=%s duration_ms=%.0f",
        ticket_id,
        outcome.status,
        (time.monotonic() - start) * 1000,
    )
    return TurnResponse.from_outcome(outcome)


@app.post("/tickets/{ticket_id}/approve", response_model=TurnResponse)
def post_approval(
    ticket_id: str, body: ApprovalRequest, _auth: None = Depends(require_api_key)
) -> TurnResponse:
    start = time.monotonic()
    with SqliteSaver.from_conn_string(_CHECKPOINT_DB) as checkpointer:
        graph = build_conversation_graph(checkpointer)
        config = {"configurable": {"thread_id": ticket_id}}
        outcome = submit_approval(graph, config, body.approved)

    logger.info(
        "ticket_id=%s event=approve approved=%s status=%s duration_ms=%.0f",
        ticket_id,
        body.approved,
        outcome.status,
        (time.monotonic() - start) * 1000,
    )
    return TurnResponse.from_outcome(outcome)
