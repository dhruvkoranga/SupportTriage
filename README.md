# Multi-Agent Support Triage System

A multi-agent AI system that automates the reasoning pattern used in real enterprise support
triage: an agent that classifies an incoming ticket, routes it to specialists that research
documentation, diagnose against live systems, and — where risk is high — hand off to a human for
approval. Built with evaluation and guardrails from day one, not bolted on at the end.

## Architecture

```
User query (bug report / support ticket)
        |
   Triage Agent (classifies & routes)
        |
   +----+----+-------------+
Research    Diagnosis    Escalation
 Agent       Agent         Agent
   |            |             |
(RAG over    (calls tools:   (drafts summary,
 docs/KB)     logs, DB       requests human
              query, API)    approval)
```

- **Triage Agent** — classifies the incoming ticket and plans sub-tasks before routing.
- **Research Agent** — retrieval over an internal knowledge base (keyword search for now; Chroma
  RAG upgrade pending — see the note below).
- **Diagnosis Agent** — a genuine tool-calling loop: decides for itself whether to search logs
  (via a real MCP server/client round trip) or query the orders database (sqlite), based on the
  ticket.
- **Escalation Agent** — looks up the ticket via the mock ticketing API, logs an internal note,
  and drafts a human-readable summary — pausing for human approval before any high-risk action
  (e.g., closing a ticket or issuing a refund; those tools don't exist yet on purpose, see
  [DECISIONS.md](DECISIONS.md#7-mcp-model-context-protocol)).

See [DECISIONS.md](DECISIONS.md) for why each technology was chosen and what the alternatives
were.

## Tech stack

| Layer | Choice |
|---|---|
| Orchestration | LangGraph |
| LLM (dev, default) | Ollama, local + free (`llama3.1:8b`) via `langchain-ollama` |
| LLM (dev, optional) | Anthropic API (`claude-sonnet-5`) via `langchain-anthropic` |
| LLM (prod, Phase 6) | Snowflake Cortex via `langchain-community` |
| RAG vector store | Chroma |
| Tool protocol | MCP (log-search tool) + direct LangChain tools (ticketing API, DB query) |
| API layer | FastAPI |
| Evaluation | RAGAS (retrieval) + custom trajectory evaluation (tool-call correctness) |
| Tracing | LangSmith |

## Phase roadmap

- [x] **Phase 1 — Core agent framework**: LangGraph wiring; Triage agent classifies and routes to
      3 specialist agents with distinct tools.
- [x] **Phase 2 — Tool use**: real sqlite DB query tool, mock ticketing API, structured
      function-calling tool loop (Diagnosis agent chooses its own tools), log search exposed as a
      real MCP server + consumed via MCP client.
- [ ] **Phase 3 — Memory & planning**: multi-turn conversation state across the whole pipeline; a
      planning step that breaks a vague request into sub-tasks before acting.
- [ ] **Phase 4 — Human-in-the-loop + guardrails**: Escalation agent pauses for human approval
      before high-risk actions; guardrails block destructive actions without confirmation; the
      agent can say "I'm not confident, escalating to human."
- [ ] **Phase 5 — Evaluation & observability**: RAGAS/LLM-as-judge for retrieval; trajectory
      evaluation for the agent; LangSmith tracing.
- [ ] **Phase 6 — Production shape**: FastAPI backend; Snowflake Cortex for at least one model
      call; basic auth + logging.

## Setup

```bash
# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install Ollama (https://ollama.com) and pull the default model — one-time, ~5GB
ollama pull llama3.1:8b

# Configure environment (copy the example and edit if needed — defaults work out of the box)
cp .env.example .env
```

No API key is required by default — LLM_PROVIDER=ollama runs entirely locally and free. Set
LLM_PROVIDER=anthropic in .env (and add an ANTHROPIC_API_KEY) if you want to compare output
quality against a paid model — see [DECISIONS.md](DECISIONS.md#2-llm-provider-strategy-dev-vs-production).

### Try it

```bash
python -m support_triage.main "How do I reset a user's password?"
python -m support_triage.main "Order 4821 payments keep timing out, what's going on?"
python -m support_triage.main "Please cancel and refund order #55 immediately" T-1002
```

The third argument (ticket ID) is optional and only used by the Escalation path — it must match
an existing entry in the mock ticketing store (`T-1001` or `T-1002`, see `ticketing.py`).

> **Note:** the full `requirements.txt` includes `chromadb`, which needs Microsoft's Visual C++
> Build Tools to compile on Windows. The Research agent's Chroma-backed RAG upgrade is
> deliberately deferred until that's installed — it's not blocking any Phase 1 or 2 functionality
> in the meantime, since Research currently uses plain keyword search.

## Suggested GitHub checkpoints

Each checkpoint below is a natural, self-contained, reviewable unit of work — a good point to
stop, review the diff together, and get a go-ahead for `git commit` / `git push` (Claude reviews
and confirms readiness; you run the actual git commands — see [CLAUDE.md](CLAUDE.md#2-git-workflow)).

- [x] **1. Project scaffold** — `CLAUDE.md`, `README.md`, `DECISIONS.md`, `requirements.txt`,
      `.gitignore`. Nothing runs yet; this just establishes intent and decisions before code
      exists.
- [x] **2. Phase 1 complete** — Triage agent + specialist agents wired via LangGraph; a query can
      flow end-to-end through the graph.
- [x] **3. Phase 2 complete** — real tool calls (ticketing API, log search, DB query) plus the MCP
      server/client pair.
- [ ] **4. Phase 3 complete** — multi-turn state persists across a conversation; the planning step
      is visible in agent output.
- [ ] **5. Phase 4 complete** — human-in-the-loop approval gate and guardrails are demonstrably
      blocking an unconfirmed destructive action.
- [ ] **6. Phase 5 complete** — evaluation harness runs and produces a report; LangSmith traces are
      visible for a sample run.
- [ ] **7. Phase 6 complete** — FastAPI backend serves the pipeline behind basic auth, with at
      least one live Snowflake Cortex call, and logging in place.

Within a large phase, feel free to commit sub-steps (e.g., "add Research agent" then "add
Diagnosis agent") rather than waiting for the whole phase — smaller, reviewable diffs are
generally better than one big one.
