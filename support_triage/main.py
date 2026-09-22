"""Manual CLI entry point: run a single ticket through the triage graph.

Usage:
    python -m support_triage.main "My order has been stuck in PROCESSING for 3 days"
"""

import sys

from dotenv import load_dotenv

from support_triage.graph import build_graph


def main() -> None:
    load_dotenv()
    if len(sys.argv) < 2:
        print('Usage: python -m support_triage.main "<ticket text>"')
        raise SystemExit(1)

    ticket_text = sys.argv[1]
    graph = build_graph()
    result = graph.invoke({"ticket_text": ticket_text})

    print(f"Category: {result['category']}")
    print(f"Reasoning: {result['classification_reasoning']}")
    print("---")
    print(result["agent_output"])


if __name__ == "__main__":
    main()
