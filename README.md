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
- **Research Agent** — retrieval-augmented generation over internal docs/knowledge base.
- **Diagnosis Agent** — calls real tools: log search (via MCP), a mock DB query tool, a mock
  ticketing API.
- **Escalation Agent** — drafts a human-readable summary and pauses for human approval before any
  high-risk action (e.g., closing a ticket).

See [DECISIONS.md](DECISIONS.md) for why each technology was chosen and what the alternatives
were.

## Tech stack

| Layer | Choice |
|---|---|
| Orchestration | LangGraph |
| LLM (dev) | Anthropic API (`claude-sonnet-5`) via `langchain-anthropic` |
| LLM (prod, Phase 6) | Snowflake Cortex via `langchain-community` |
| RAG vector store | Chroma |
| Tool protocol | MCP (log-search tool) + direct LangChain tools (ticketing API, DB query) |
| API layer | FastAPI |
| Evaluation | RAGAS (retrieval) + custom trajectory evaluation (tool-call correctness) |
| Tracing | LangSmith |

## Phase roadmap

- [ ] **Phase 1 — Core agent framework**: LangGraph wiring; Triage agent classifies and routes to
      2-3 specialist agents with distinct tools.
- [ ] **Phase 2 — Tool use**: mock ticketing API, log-search function, DB query tool; one tool
      requiring structured function calling; one tool exposed as an MCP server + consumed via MCP
      client.
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

# Configure secrets (create a .env file — never commit this)
# ANTHROPIC_API_KEY=sk-ant-...
```

A `.env.example` will be added once Phase 1 introduces the first agent that needs a key — see
[DECISIONS.md](DECISIONS.md) for how the LLM provider is kept swappable between Anthropic and
Snowflake Cortex.

## Suggested GitHub checkpoints

Each checkpoint below is a natural, self-contained, reviewable unit of work — a good point to
stop, review the diff together, and get a go-ahead for `git commit` / `git push` (Claude reviews
and confirms readiness; you run the actual git commands — see [CLAUDE.md](CLAUDE.md#2-git-workflow)).

1. **Project scaffold** *(this checkpoint)* — `CLAUDE.md`, `README.md`, `DECISIONS.md`,
   `requirements.txt`, `.gitignore`. Nothing runs yet; this just establishes intent and decisions
   before code exists.
2. **Phase 1 complete** — Triage agent + specialist agents wired via LangGraph; a query can flow
   end-to-end through the graph (even with simple/mocked agent logic).
3. **Phase 2 complete** — real tool calls (ticketing API, log search, DB query) plus the MCP
   server/client pair.
4. **Phase 3 complete** — multi-turn state persists across a conversation; the planning step is
   visible in agent output.
5. **Phase 4 complete** — human-in-the-loop approval gate and guardrails are demonstrably blocking
   an unconfirmed destructive action.
6. **Phase 5 complete** — evaluation harness runs and produces a report; LangSmith traces are
   visible for a sample run.
7. **Phase 6 complete** — FastAPI backend serves the pipeline behind basic auth, with at least one
   live Snowflake Cortex call, and logging in place.

Within a large phase, feel free to commit sub-steps (e.g., "add Research agent" then "add
Diagnosis agent") rather than waiting for the whole phase — smaller, reviewable diffs are
generally better than one big one.
