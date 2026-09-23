"""Manual CLI entry point: run a single ticket through the triage graph.

Usage:
    python -m support_triage.main "My order has been stuck in PROCESSING for 3 days" [ticket_id]

ticket_id defaults to T-1001, a ticket that already exists in the mock
ticketing store (see ticketing.py) — only used by the Escalation path.
"""

import sys

from dotenv import load_dotenv

from support_triage.graph import build_graph

_DEFAULT_TICKET_ID = "T-1001"


def main() -> None:
    load_dotenv()
    if len(sys.argv) < 2:
        print('Usage: python -m support_triage.main "<ticket text>" [ticket_id]')
        raise SystemExit(1)

    ticket_text = sys.argv[1]
    ticket_id = sys.argv[2] if len(sys.argv) > 2 else _DEFAULT_TICKET_ID
    graph = build_graph()
    result = graph.invoke({"ticket_text": ticket_text, "ticket_id": ticket_id})

    print(f"Category: {result['category']}")
    print(f"Reasoning: {result['classification_reasoning']}")
    print("---")
    print(result["agent_output"])


if __name__ == "__main__":
    main()
