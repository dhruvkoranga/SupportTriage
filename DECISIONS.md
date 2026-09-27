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

**Choice:** Free, local Ollama (`ChatOllama`, `llama3.1:8b`) is the default for day-to-day
development. The Anthropic API (`ChatAnthropic`, `claude-sonnet-5`) is available via the same
factory for quality comparisons. Snowflake Cortex (via `langchain-community`) arrives for
Phase 6. All three are selected through a single factory function reading `LLM_PROVIDER` — no
per-agent code changes required to switch.

*(Revised from the original plan of defaulting to the Anthropic API. Since this project is for
learning, not production, avoiding per-token cost during iteration was the deciding factor — see
below. Also revised once already since: started on `llama3.2:3b`, which failed a basic grounding
test — see "Revisit if" below for what happened and why `llama3.1:8b` is the default now.)*

**Alternatives considered:** Direct Anthropic API as the default (the original plan); Google
Gemini free tier; Groq free tier; a hand-rolled provider abstraction instead of leaning on
LangChain's.

**Why:**
- LangChain's `BaseChatModel` is *already* the abstraction layer we'd otherwise build ourselves —
  every agent talks to a `BaseChatModel`, never to `ollama.Client`, `anthropic.Client`, or a
  Snowflake connection directly. Swapping providers becomes a one-line change in a
  `get_chat_model()` factory instead of a custom adapter class. This is "simplicity first" applied
  to architecture: don't build an abstraction the framework already gives you for free — and it's
  exactly what made adding a third provider here a five-line change, not a rewrite.
- Ollama over the cloud free tiers (Gemini, Groq) because the hardware (RTX 5060 laptop GPU, 24GB
  RAM) runs a small model fast, and local means zero cost forever with no account, rate limits, or
  quota to track — the right tradeoff for a project centered on iterating and learning, not on
  proving cloud-scale throughput. It also doubles as a look at local LLM deployment, which cloud
  free tiers wouldn't teach.
- Anthropic stays wired in (not removed) because a 3B local model will sometimes misclassify or
  give shallow specialist answers — being able to flip `LLM_PROVIDER=anthropic` for a side-by-side
  comparison is a genuinely useful debugging and learning tool, not just a production fallback.
- Snowflake Cortex is deliberately deferred to exactly the one place the project requirement asks
  for it (Phase 6's "one cloud AI platform" call).

**What actually happened:** `llama3.2:3b` was the first default (it was already pulled locally).
Live-testing the Research agent exposed a real grounding failure: given a prompt whose context
*directly* contained the answer (the correct KB article, verified independently), the model still
replied "I don't have that information." Not a code bug — the retrieved context and prompt were
both confirmed correct. Pulled `llama3.1:8b` (~4.9GB, still free) and reran the identical prompt;
it grounded correctly and gave the right answer. `llama3.1:8b` is now the default.

**Revisit again if:** `llama3.1:8b` shows the same kind of failure on a harder prompt (e.g. a
Diagnosis-agent case with noisier log context) — the fix is the same lever, a bigger local model
(`qwen2.5:14b` is the next step up), before reaching for a paid default. Also revisit if Cortex's
LangChain integration turns out to lack a capability an agent needs (e.g., certain tool-calling
features) — in that case Phase 6 may need a thin custom `BaseChatModel` subclass rather than the
community one, but the factory-function seam stays the same either way.

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

**Choice:** Official `mcp` Python SDK, pinned to `2.2.0` (not `1.1.2` as originally guessed in
`requirements.txt` before Phase 2 — see below). Expose the **log-search tool** as an MCP server
(`support_triage/mcp_integration/server.py`); consume it via a synchronous MCP client
(`support_triage/mcp_integration/client.py`) from the Diagnosis agent, spawned as a stdio
subprocess.

**Why log search specifically:** it's a clean, self-contained tool (one input: a query/filter;
one output: matching log lines) that's genuinely useful to expose generically — a real MCP server
you could plug into Claude Desktop or another MCP host, not just a toy example. The ticketing API
and DB query tool stay as regular LangChain tools since the project only requires one MCP
round-trip and those two are more naturally scoped to this agent graph specifically.

**A version-pinning lesson worth keeping:** `requirements.txt` had guessed `mcp==1.1.2` back at
project scaffolding, before any code existed. That version doesn't have `FastMCP` (the simple
decorator-based server API) at all — it was added later, then **renamed to `MCPServer`** in the
2.x line (`from mcp.server.mcpserver import MCPServer`, not `mcp.server.fastmcp`). Rather than
trust a guessed pin or a possibly-stale tutorial, I installed the package fresh and introspected
the actual installed classes (`inspect.signature(...)`) to confirm the real API before writing
server/client code against it — the two are genuinely different APIs, not just a renamed import.

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

---

## 10. Which agents get a full tool-calling loop

**Choice:** The Diagnosis agent gets a genuine agentic tool-calling loop
(`support_triage/tool_loop.py`): the model is bound to two tools (log search, DB query) and
decides for itself which one(s) to call, based on the ticket. The Escalation agent does **not**
get this — it calls the ticketing API tools directly in fixed Python code (always `get_ticket`,
always `add_internal_note`), then makes one plain LLM call to phrase the summary.

**Alternatives considered:** Give every tool-using agent the same `bind_tools` + loop treatment,
for consistency.

**Why:** Diagnosis's job is genuinely open-ended — a ticket might need logs, might need order
data, might need both, and which one is relevant isn't knowable in advance. That's exactly what
tool-calling loops are for: letting the model decide. Escalation's job is a fixed procedure — look
up the ticket, log why it was escalated, summarize for a human — every single time, regardless of
ticket content. Giving it a tool-selection loop wouldn't add capability, only latency (extra model
round-trips) and a new way for the model to skip a step it should always take. Not every agent
needs the same amount of "agent" in it — this is the same lesson as Phase 1's escalation node not
needing an LLM call at all, applied one level up.

**Revisit if:** Escalation's procedure stops being fixed — e.g. if Phase 4 adds a case where it
should conditionally check something else first. At that point it may earn a real tool loop too.

---

## 11. Planning/memory architecture: two graphs, not one

**Choice:** Phase 3 is two separate compiled graphs, not one. An **inner "turn" graph**
(`planning_graph.py`: plan -> fan-out over sub-tasks via LangGraph's `Send` API -> aggregate) is
compiled **without** a checkpointer and reuses the entire Phase 1/2 pipeline
(`support_triage/graph.py`, `TriageState`) unchanged, invoked as a black box once per sub-task. An
**outer "conversation" graph** (`conversation_graph.py`: a single node wrapping the inner graph)
is compiled **with** a checkpointer and owns the only thing that should actually persist across
turns: `messages`.

**Alternatives considered:** One flat graph with everything (planning, fan-out, aggregation, and
memory) in a single checkpointed `StateGraph`.

**Why:** The core Triage -> specialist pipeline from Phase 1/2 already works and is already
tested — reusing it as an opaque function call (`core_graph.invoke(...)`) inside
`run_subtask_node` means Phase 3 adds zero risk of regressing it, and keeps the fan-out logic from
needing to know anything about triage/specialist internals. Splitting the checkpointing boundary
this way — rather than checkpointing one big flat state — is what makes per-turn scratch fields
(`sub_tasks`, `subtask_results`) safe to use `Annotated[..., operator.add]` reducers on: the
inner graph never persists between calls, so there's nothing for those reducers to leak *into*
across turns. See #12 for what happens when you get this wrong.

**Revisit if:** the inner turn graph needs its own multi-step memory (e.g. a sub-task that
depends on a previous sub-task's result within the same turn) — at that point it might warrant a
proper LangGraph subgraph composition instead of a plain function call.

---

## 12. A real bug: reducer fields need a boundary that resets them

**What happened:** The first version of Phase 3 was the one-flat-graph design from #11's
"alternatives considered" — `PlanningState` had `messages`, `sub_tasks`, and `subtask_results` all
in the same checkpointed schema. Turn 1 (single ticket) worked fine. Turn 2, in the *same*
conversation thread, produced a summary that mixed in details from Turn 1's ticket that were never
mentioned in Turn 2 at all — reproducible every time, not model noise.

**Root cause:** `subtask_results: Annotated[list[SubtaskResult], operator.add]` needs to
accumulate *within* one turn, to correctly merge the results of concurrent `Send`-spawned
branches. But a reducer only ever combines — it has no notion of "start fresh here." Since the
checkpointer persists the whole schema for the life of the thread, Turn 1's `subtask_results`
were still sitting in state when Turn 2's fan-out ran, and Turn 2 silently appended to them instead
of starting empty. `aggregate_node` then summarized *both* turns' results as if they belonged to
one request.

**Fix:** Moved `sub_tasks` / `subtask_results` out of the checkpointed schema entirely, into the
inner turn graph's state (#11), which never persists between calls — there's nothing left to leak
because nothing survives past one `.invoke()`. `messages` stays in the outer, checkpointed schema,
where accumulating forever is exactly the correct behavior.

**The general lesson:** a reducer field is safe to checkpoint only if "accumulate forever" is
actually the behavior you want for that field's entire lifetime. If a field is really per-turn (or
per-request, or per-anything-shorter-than-the-checkpoint's-lifetime) scratch space, it belongs in
a boundary that gets torn down and rebuilt each time — an uncheckpointed subgraph invocation, not
a field in the persisted schema.

---

## 13. Two smaller Phase 3 findings worth remembering

**Rephrasing a question into a command silently changed its triage category.** The Planning
node's job is to rewrite a ticket into self-contained sub-tasks — its first version rewrote "How
do I reset a user's password?" into "Reset a user's password." Same request, but an imperative
sentence reads as a command to *act*, not a question to *answer*, and Triage consistently (not
randomly) classified it as `escalation` instead of `research`. Fixed by explicitly instructing the
Planning prompt to preserve the original phrasing's mood (question stays a question). Small
wording choices in an intermediate agent's output can change a downstream agent's behavior in
ways that have nothing to do with either prompt being "wrong" in isolation.

**A category definition that only covers the negative case invites inconsistent classification.**
The original `diagnosis` category was defined as "something is broken" — but a plain status
lookup ("what's the status of order 55?") doesn't say anything is broken, so the model
inconsistently split between `diagnosis` and `research` on identical repeated input. Fixed by
redefining `diagnosis` positively ("anything about a specific order/account — including plain
status lookups, not just things that are broken") instead of relying on the model to infer that a
lookup implicitly belongs there. This kind of gap is exactly what Phase 5's evaluation harness is
meant to catch systematically, rather than one hand-run example at a time.

---

## 14. Human approval: propose-don't-execute, and where interrupt() actually has to live

**Choice:** `close_ticket` and `issue_refund` exist as real tools (`ticketing.py`), but
`escalation_node` never calls them — it only reads the model's requested tool call (name + args)
off the response and returns it as a `ProposedAction`. The only code in the entire project that
ever calls `.invoke()` on these two tools is `conversation.py`'s `approve_and_finalize_node`, and
only after a human approves via a real LangGraph `interrupt()`.

**Why "propose, don't execute" is a code-level guardrail, not a prompt-level one:** the system
prompt also tells the model not to call these tools speculatively — but a prompt is a request, not
a constraint; models don't always follow instructions. The actual guarantee here doesn't depend on
the model behaving: even if the model's `tool_calls` field contains a destructive request,
`escalation_node`'s code has no line anywhere that would execute it. There is exactly one call
site for these tools in the whole codebase, and it's gated behind `interrupt()`. Tested directly,
not just asserted — see `test_escalation_node_never_directly_invokes_destructive_tools` and the
approve/reject tests in `test_conversation_graph.py`.

**Where interrupt() has to be called — a real finding, verified empirically:** `escalation_node`
runs several nesting levels below the checkpointed graph (`conversation_graph` → `run_pipeline_node`
→ the uncheckpointed turn graph → the uncheckpointed core graph → `escalation_node`). Calling
`interrupt()` *while* that nested chain is still executing does correctly pause the whole call
stack (the exception propagates through plain `.invoke()` calls like any Python exception) — but
**resuming it does not work**: `Command(resume=...)` only works for a node that belongs directly
to the graph holding the checkpointer. A node several `.invoke()` calls deep has no way to resume
mid-function; each nested call starts a brand-new, memoryless execution every time. Verified with a
minimal repro before writing any real code (see the three empirical smoke tests run for this
phase). The fix: the nested pipeline only ever returns *data* (a `ProposedAction`, never a paused
state) — `interrupt()` itself is called directly inside `approve_and_finalize_node`, a real node of
the checkpointed `conversation_graph`, after the nested work has already fully returned.

**Revisit if:** a future phase needs an approval gate to pause *mid-investigation* rather than
after it completes (e.g., "should I even look at this order?") — that would need the interrupt to
live inside the nested pipeline itself, which this project's structure specifically doesn't
support, and would need a different design (e.g., giving the inner graph its own checkpointer too).

---

## 15. A second real bug: resuming re-ran the entire pipeline

**What happened:** The first version of `run_turn_node` did the expensive nested pipeline call
*and* the `interrupt()` call in the same node. That's the version described in #14 as broken for a
different reason than expected: live-testing showed that approving a proposal caused the **entire
multi-agent pipeline to run a second time** — Planning, Triage, and every specialist agent, all
over again — before the approval was even processed. Worse, on one run this doubled LLM call chain
hit a real transient failure (a `with_structured_output()` call returned `None`), crashing the
approval step entirely.

**Root cause:** LangGraph resumes a node by re-executing its *whole function* from the top — the
resume value is threaded back in only at the specific `interrupt()` call site. If everything
before that call site is expensive and non-deterministic (an LLM pipeline), resuming pays for it
again, and there's no guarantee the second run produces the same proposal the human actually
approved.

**Fix:** split the one node into two — `run_pipeline_node` (runs the nested pipeline, stages its
result in plain, non-reducer `ConversationState` fields) and `approve_and_finalize_node` (reads
the staged result, calls `interrupt()`, executes on approval). LangGraph only re-executes the node
that was actually interrupted; the pipeline node already completed and its output was already
checkpointed, so it never re-runs. Verified with an isolated repro before touching the real code,
then locked in with a regression test asserting the pipeline function is called exactly once
across a full pause/approve/resume cycle.

**The general lesson (a sibling to #12's):** anything expensive or non-deterministic must complete
and be safely checkpointed *before* a node calls `interrupt()`, in an earlier node — never
alongside it in the same one. `interrupt()` marks a true "pause here, resume here" boundary only
for whatever's in its own node; anything upstream, resume pays for all over again.

---

## 16. A LangGraph gotcha worth remembering: `Command(resume=False)` doesn't work

**What happened:** `Command(resume=True)` worked immediately; `Command(resume=False)` raised
`EmptyInputError: Received empty Command input` — a rejection couldn't even be submitted.

**Root cause:** `langgraph/pregel/io.py`'s `map_command` checks `if cmd.resume:` (a truthy check),
not `if cmd.resume is not None:`. A bare `False` is falsy, so it's silently treated as "no resume
value provided at all," not as "resume with the value `False`." Confirmed directly against the
installed package's source, not guessed — see `test_command_resume_with_bare_false_is_a_known_langgraph_pitfall`.

**Fix:** resume with a non-empty dict instead of a bare bool — `Command(resume={"approved": False})`
is truthy regardless of what's inside it, so it survives the check. `approve_and_finalize_node`
unpacks `decision["approved"]` rather than using `interrupt()`'s return value directly.

**Revisit if:** upgrading `langgraph` past this pinned version — if the upstream check is ever
fixed to `is not None`, the dict wrapper becomes unnecessary (harmless to keep, but removable).

---

## 17. Abstention: a `confident` field, not a separate mechanism

**Choice:** `TriageClassification` gets a `confident: bool` field. When `False`, `triage_node`
overrides the category to `escalation` regardless of what the model predicted — reusing the
*existing* Escalation path rather than building a separate "uncertain" flow.

**Why:** routing low-confidence tickets to Escalation is a genuine "abstain and let a human decide"
behavior, but it doesn't need new machinery — Escalation already means "a human looks at this
before anything happens." Since `escalation_node` only proposes a destructive tool call when the
ticket clearly warrants one, a genuinely ambiguous ticket naturally produces zero proposed actions
and just falls through to a plain summary — the right behavior, achieved without escalation_node
needing to know or care *why* it was invoked.

**A known rough edge, left as-is rather than chased:** live-testing an intentionally vague ticket
("I have a problem," on a ticket record about a payment failure) showed the model *did* propose
`close_ticket` — a more confident action than the vague complaint actually justified, despite the
system prompt saying only to propose an action when the request is explicit. This didn't break
anything: the system still paused, a human still had to approve, and rejecting it left nothing
changed — which is the entire point of the guardrail in #14. It's a reminder that a guardrail's
job is to catch imperfect upstream judgment, not to assume the judgment upstream is already
correct. Tightening this further is exactly the kind of thing Phase 5's evaluation work is for,
not something worth hand-chasing example by example (same conclusion as #13).
