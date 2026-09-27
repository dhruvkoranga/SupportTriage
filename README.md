# Multi-Agent Support Triage System

A multi-agent AI system that automates the reasoning pattern used in real enterprise support
triage: an agent that classifies an incoming ticket, routes it to specialists that research
documentation, diagnose against live systems, and — where risk is high — hand off to a human for
approval. Built with evaluation and guardrails from day one, not bolted on at the end.

## Architecture

```
Conversation turn (persisted memory, keyed by ticket_id)
        |
   Planning Agent (breaks the message into sub-tasks)
        |
   fan-out (one branch per sub-task, run in parallel)
        |
   +----+----+-------------+
Research    Diagnosis    Escalation      <- Triage classifies each sub-task
 Agent       Agent         Agent            into one of these three, per branch
   |            |             |
   +----+----+-------------+
        |
   Aggregate (combine sub-task results into one reply)
```

- **Planning Agent** — breaks a message into one or more self-contained sub-tasks (most messages
  are a single sub-task; only genuinely multi-part requests split further).
- **Triage Agent** — classifies each sub-task and routes it, run once per sub-task.
- **Research Agent** — retrieval over an internal knowledge base (keyword search for now; Chroma
  RAG upgrade pending — see the note below).
- **Diagnosis Agent** — a genuine tool-calling loop: decides for itself whether to search logs
  (via a real MCP server/client round trip) or query the orders database (sqlite), based on the
  ticket.
- **Escalation Agent** — looks up the ticket, logs an internal note, and *proposes* a destructive
  action (closing a ticket, issuing a refund) if the ticket clearly warrants one — but never
  executes it. The only code that actually calls those tools is a separate approval step, gated
  behind a real human decision (see [DECISIONS.md](DECISIONS.md#14-human-approval-propose-dont-execute-and-where-interrupt-actually-has-to-live)).
  A ticket the Triage agent isn't confident about is also routed here automatically, even if
  nothing about it looks high-risk — abstaining and asking a human beats guessing.

Conversation memory persists per `ticket_id`, across separate runs — the whole pipeline above runs
once per turn, wrapped by an outer graph that owns only the conversation history (see
[DECISIONS.md](DECISIONS.md#11-planningmemory-architecture-two-graphs-not-one) for why this is two
graphs, not one). If Escalation proposed a destructive action, that same outer graph pauses the
entire conversation — via a real LangGraph `interrupt()`, not a prompt asking the model to hold
off — until a human approves or rejects it.

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
| Multi-turn memory | LangGraph `SqliteSaver` checkpointer, keyed by `ticket_id` |
| Sub-task fan-out | LangGraph `Send` API (parallel branches, `operator.add` reducer to merge) |
| Human approval | LangGraph `interrupt()`/`Command(resume=...)`, pausing the checkpointed graph |
| API layer | FastAPI |
| Evaluation | RAGAS (retrieval) + custom trajectory evaluation (tool-call correctness) |
| Tracing | LangSmith |

## Phase roadmap

- [x] **Phase 1 — Core agent framework**: LangGraph wiring; Triage agent classifies and routes to
      3 specialist agents with distinct tools.
- [x] **Phase 2 — Tool use**: real sqlite DB query tool, mock ticketing API, structured
      function-calling tool loop (Diagnosis agent chooses its own tools), log search exposed as a
      real MCP server + consumed via MCP client.
- [x] **Phase 3 — Memory & planning**: multi-turn conversation state persisted per ticket via a
      LangGraph checkpointer; a Planning agent that breaks a message into sub-tasks, run in
      parallel via the `Send` API and combined by an Aggregate step.
- [x] **Phase 4 — Human-in-the-loop + guardrails**: the conversation pauses for real human approval
      (LangGraph `interrupt()`) before any destructive action; the tools that action only ever get
      called from that one approval step, never from the agent that proposes them; low-confidence
      tickets are automatically escalated rather than guessed at.
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
# Single-shot: one message, one reply. The optional second argument is the
# ticket ID, which doubles as the conversation's thread ID (defaults to T-1001).
python -m support_triage.main "How do I reset a user's password?"
python -m support_triage.main "Order 4821 payments keep timing out, what's going on?"
python -m support_triage.main "Please cancel and refund order #55 immediately" T-1002

# Re-running the same ticket ID continues that ticket's conversation —
# memory persists across separate CLI invocations, not just within one process:
python -m support_triage.main "What is the status of order 4821?" T-1002
python -m support_triage.main "What about order 55 instead?" T-1002   # resolves "instead" using turn 1's context

# Interactive: multi-turn conversation in one session (type 'exit' to quit)
python -m support_triage.main
```

A multi-part message ("How do I reset a password, and also what's the status of order 4821?")
gets split by the Planning agent into separate sub-tasks, each triaged independently, then
combined into one reply.

A high-risk request pauses for your approval before anything happens:

```bash
python -m support_triage.main "Please refund order 55 for $20, I was double charged" T-1002
# -> shows the proposed action and asks "Approve? (y/n):" before issue_refund ever runs
```

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
- [x] **4. Phase 3 complete** — multi-turn state persists across a conversation; the planning step
      is visible in agent output.
- [x] **5. Phase 4 complete** — human-in-the-loop approval gate and guardrails are demonstrably
      blocking an unconfirmed destructive action.
- [ ] **6. Phase 5 complete** — evaluation harness runs and produces a report; LangSmith traces are
      visible for a sample run.
- [ ] **7. Phase 6 complete** — FastAPI backend serves the pipeline behind basic auth, with at
      least one live Snowflake Cortex call, and logging in place.

Within a large phase, feel free to commit sub-steps (e.g., "add Research agent" then "add
Diagnosis agent") rather than waiting for the whole phase — smaller, reviewable diffs are
generally better than one big one.
