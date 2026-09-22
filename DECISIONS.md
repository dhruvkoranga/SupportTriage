# Decision Approach

This file records the *why* behind every non-obvious technical choice in this project — not just
what we picked, but what we compared it against and when you'd want the other option instead.
Update it whenever a real tradeoff gets decided, not just when something is "interesting."

Format per decision: **Choice** → what we're using · **Alternatives considered** → what else was
on the table · **Why** → the reasoning · **Revisit if** → the condition under which this should
be reconsidered.

---

## 1. Multi-agent orchestration framework

**Choice:** [LangGraph](https://langchain-ai.github.io/langgraph/)

**Alternatives considered:** CrewAI, AutoGen

**Why:**
- LangGraph models the system as an explicit state graph (nodes = agents/tools, edges = routing
  logic). That maps directly onto the Triage → {Research, Diagnosis, Escalation} architecture —
  you can draw the graph and the code mirrors the drawing.
- It gives first-class support for exactly the harder phases of this project: **interrupts** for
  human-in-the-loop approval (Phase 4), and a **checkpointer** for multi-turn state persistence
  (Phase 3) — both are built into the framework rather than something you bolt on.
- It integrates natively with **LangSmith** for tracing (Phase 5), and with LangChain's chat-model
  abstraction, which is also how we keep the LLM provider swappable (see Decision 2).
- CrewAI is higher-level and faster to prototype with, but it's more opinionated about the
  agent-to-agent handoff pattern and gives you less control over routing logic — harder to show a
  deliberate, reasoned control flow in an interview setting. AutoGen leans toward open-ended
  multi-agent *conversation* (agents chatting with each other) rather than a directed pipeline
  with explicit approval gates, which is a worse fit for a triage/escalation workflow.

**Revisit if:** the project needs open-ended agent-to-agent negotiation rather than directed
routing (AutoGen's strength), or prototyping speed matters more than architectural legibility
(CrewAI's strength).

---

## 2. LLM provider strategy (dev vs. production)

**Choice:** Direct Anthropic API during development (Phases 1-5), via LangChain's `ChatAnthropic`
class. Swap to Snowflake Cortex (via `langchain-community`'s Cortex chat model) for Phase 6,
selected through a single factory function reading an environment variable — no per-agent code
changes required to switch.

**Alternatives considered:** Hand-rolled provider abstraction (our own interface wrapping both
SDKs); building every agent directly against the Snowflake Cortex SDK from day one.

**Why:**
- LangChain's `BaseChatModel` is *already* the abstraction layer we'd otherwise build ourselves —
  every agent talks to a `BaseChatModel`, never to `anthropic.Client` or a Snowflake connection
  directly. Swapping providers becomes a one-line change in a `get_chat_model()` factory instead
  of a custom adapter class. This is "simplicity first" applied to architecture: don't build an
  abstraction the framework already gives you for free.
- Developing against the Anthropic API directly is the fastest inner loop (no cloud account
  friction, cheapest to debug, best error messages) — so it's the right choice for Phases 1-5,
  where you're iterating on agent logic, not proving cloud integration.
- Snowflake Cortex is deliberately deferred to exactly the one place the project requirement asks
  for it (Phase 6's "one cloud AI platform" call).
- Model: default to `claude-sonnet-5` for agent reasoning (strong tool-use performance, current
  generation, ~5x cheaper than Opus-tier per token) — this is a multi-agent system that will make
  many calls per ticket, so per-token cost compounds. Reach for `claude-opus-5` only on a node
  where reasoning quality is the bottleneck (e.g., a "hard case" escalation path), not by default.

**Revisit if:** Cortex's LangChain integration turns out to lack a capability an agent needs
(e.g., certain tool-calling features) — in that case Phase 6 may need a thin custom
`BaseChatModel` subclass rather than the community one, but the factory-function seam stays the
same either way.

---

## 3. RAG vector store (Research Agent)

**Choice:** [Chroma](https://www.trychroma.com/) (via `langchain-chroma`), running embedded/local.

**Alternatives considered:** FAISS, pgvector

**Why:**
- Chroma persists to disk with zero external services to run — you `pip install` it and it works,
  which matters for a project you'll demo from a laptop.
- It supports metadata filtering out of the box (e.g., filter retrieved KB docs by product area
  or ticket category), which FAISS doesn't give you without extra bookkeeping.
- pgvector is the better choice if this were becoming a production service with an existing
  Postgres database to lean on — that's not the case here, and adding a Postgres dependency for a
  single agent's retrieval store would be more infrastructure than the problem needs.

**Revisit if:** the project grows a real Postgres-backed persistence layer for other reasons
(e.g., ticket history), at which point consolidating onto pgvector removes a moving part rather
than adding one.

---

## 4. Web framework (Phase 6 API layer)

**Choice:** FastAPI + Uvicorn

**Why:** Specified directly by the project brief. Worth noting *why* it's a good fit regardless:
native Pydantic integration (matches the structured-output/tool-schema validation already used in
Phases 2-4), async support (useful once the API is fanning out to multiple agent tool calls per
request), and automatic OpenAPI docs (useful for demoing the ticketing/log-search/DB tool
contracts).

---

## 5. Package management

**Choice:** `venv` + `requirements.txt`

**Alternatives considered:** Poetry, uv

**Why:** As your second Python project, `venv` + `requirements.txt` is the standard you'll see in
the most tutorials, other people's codebases, and interview take-homes — worth being fluent in
before reaching for a dependency manager with its own lockfile format and CLI. Poetry (or the
newer, much faster `uv`) is a legitimate upgrade once you're comfortable — `uv` in particular is
becoming the modern default because it's a drop-in `pip`/`venv` replacement that's 10-100x faster
— but switching build tooling isn't a problem this project has yet.

**Revisit if:** dependency resolution conflicts become painful, or you want lockfile-pinned,
reproducible installs (Poetry/uv's main advantage over bare `requirements.txt`).

---

## 6. Linting & formatting

**Choice:** [Ruff](https://docs.astral.sh/ruff/) (lint + format in one tool)

**Alternatives considered:** flake8 + black + isort (the traditional three-tool combo)

**Why:** Ruff reimplements flake8, isort, and black's formatting in a single Rust binary —
one config block, one command, and it's fast enough to run on every save without thinking about
it. The three-tool combo is still common in older codebases (worth recognizing if you see it
elsewhere), but there's no reason to start a new project on it today.

---

## 7. MCP (Model Context Protocol)

**Choice:** Official `mcp` Python SDK. Expose the **log-search tool** as an MCP server; consume
it via an MCP client from the Diagnosis agent.

**Why log search specifically:** it's a clean, self-contained tool (one input: a query/filter;
one output: matching log lines) that's genuinely useful to expose generically — a real MCP server
you could plug into Claude Desktop or another MCP host, not just a toy example. The ticketing API
and DB query tool stay as regular LangGraph/LangChain tools since the project only requires one
MCP round-trip and those two are more naturally scoped to this agent graph specifically.

---

## 8. Evaluation

**Choice:** [RAGAS](https://docs.ragas.io/) for the Research Agent's retrieval quality
(faithfulness, context precision/recall); a small custom trajectory-evaluation harness (asserts
against the LangGraph run's list of tool calls) for "did the agent call the right tools, in the
right order"; LangSmith for tracing/observability across the whole pipeline.

**Why:** RAGAS is the standard, purpose-built tool for RAG evaluation — no reason to hand-roll
faithfulness scoring. Trajectory evaluation has no equally dominant off-the-shelf tool for a
LangGraph-specific pipeline, so a small custom harness (a list of expected tool-call sequences per
test case, diffed against the actual run) is simpler than adopting a heavier eval framework for
one narrow check. LangSmith is the natural tracing choice given LangGraph is already a LangChain
project — first-party integration, no extra instrumentation code.

---

## 9. Auth (Phase 6)

**Choice:** Simple API-key (Bearer token) auth via FastAPI dependency injection, key stored in an
environment variable.

**Alternatives considered:** Full OAuth2/JWT with a user database

**Why:** This is a portfolio/interview project, not a multi-tenant production service — the
requirement is "basic auth + logging," and a full OAuth2 flow with user management would be
scope well beyond what's being demonstrated (and would violate the Simplicity First guideline in
[CLAUDE.md](CLAUDE.md)). API-key auth is still a real, correctly-implemented security boundary
worth showing, just sized to the problem.

**Revisit if:** this ever needs multiple distinct users/roles rather than one demo credential.
