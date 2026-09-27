"""CLI entry point: the multi-turn conversation graph (Plan -> triage each
sub-task -> aggregate), with memory persisted per ticket_id.

Usage:
    # Single-shot: one ticket, one turn
    python -m support_triage.main "Order 4821 seems stuck, what's wrong?" [ticket_id]

    # Interactive: multi-turn conversation, memory persists across inputs
    python -m support_triage.main

ticket_id doubles as the conversation's thread_id, so re-running a single
ticket with the same ticket_id continues that ticket's conversation.
Defaults to T-1001, a ticket that already exists in ticketing.py.
"""

import sys

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from support_triage.conversation_graph import build_conversation_graph

_DEFAULT_TICKET_ID = "T-1001"
_CHECKPOINT_DB = "support_triage_checkpoints.sqlite3"


def _ask_approval(payload: dict) -> bool:
    print("\n--- Human approval required before this can proceed ---")
    print(payload["draft_summary"])
    print("\nProposed action(s):")
    for action in payload["proposed_actions"]:
        print(f"  - {action['tool']}({action['args']}) — {action['reason']}")
    answer = input("\nApprove? (y/n): ").strip().lower()
    return answer in {"y", "yes"}


def _run_turn(graph, config: dict, ticket_id: str, ticket_text: str) -> str:
    result = graph.invoke({"ticket_id": ticket_id, "messages": [("human", ticket_text)]}, config)

    snapshot = graph.get_state(config)
    while snapshot.next:
        payload = snapshot.tasks[0].interrupts[0].value
        approved = _ask_approval(payload)
        # {"approved": bool}, not a bare bool — see conversation.py's run_turn_node.
        result = graph.invoke(Command(resume={"approved": approved}), config)
        snapshot = graph.get_state(config)

    return result["messages"][-1].content


def _run_single_shot(ticket_text: str, ticket_id: str) -> None:
    with SqliteSaver.from_conn_string(_CHECKPOINT_DB) as checkpointer:
        graph = build_conversation_graph(checkpointer)
        config = {"configurable": {"thread_id": ticket_id}}
        print(_run_turn(graph, config, ticket_id, ticket_text))


def _run_interactive() -> None:
    ticket_id = input(f"Ticket ID [{_DEFAULT_TICKET_ID}]: ").strip() or _DEFAULT_TICKET_ID
    print(f"Starting conversation for ticket {ticket_id}. Type 'exit' to quit.\n")

    with SqliteSaver.from_conn_string(_CHECKPOINT_DB) as checkpointer:
        graph = build_conversation_graph(checkpointer)
        config = {"configurable": {"thread_id": ticket_id}}

        while True:
            ticket_text = input("You: ").strip()
            if ticket_text.lower() in {"exit", "quit"}:
                break
            print(f"\nAgent: {_run_turn(graph, config, ticket_id, ticket_text)}\n")


def main() -> None:
    load_dotenv()
    if len(sys.argv) < 2:
        _run_interactive()
        return

    ticket_text = sys.argv[1]
    ticket_id = sys.argv[2] if len(sys.argv) > 2 else _DEFAULT_TICKET_ID
    _run_single_shot(ticket_text, ticket_id)


if __name__ == "__main__":
    main()
