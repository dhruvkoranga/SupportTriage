# CLAUDE.md

Guidance for Claude Code (and any other AI assistant) working in this repository.

## 1. Project Overview

**Multi-Agent Support Triage System** — a system that mirrors real enterprise support triage
(the kind of manual investigation done for e-commerce/enterprise support tickets today), rebuilt
as an agentic AI system: agents that reason over enterprise data, call tools, hit real systems,
and hand off between specialized roles, with evaluation and guardrails built in from day one
rather than bolted on afterward.

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

### Why this project exists
It sits close enough to real support-triage work (deep domain understanding) while being built
as a genuine multi-agent system (agents, tools, memory, guardrails, evaluation) rather than a
single prompt-and-response wrapper. The target narrative: *"I automated the reasoning pattern I
use every day at work."*

### Phase roadmap
See [README.md](README.md) for the full phase breakdown, current status, and setup instructions.
See [DECISIONS.md](DECISIONS.md) for the reasoning behind every non-obvious technical choice
(framework, vector store, LLM provider strategy, auth, etc.) — read it before assuming a library
choice is arbitrary.

Summary:
- **Phase 1** — Core agent framework (LangGraph, Triage agent + 2-3 specialist agents)
- **Phase 2** — Tool use: mock ticketing API, log search, DB query tool, one MCP server + client
- **Phase 3** — Multi-turn state/memory + a planning step
- **Phase 4** — Human-in-the-loop approval + guardrails against destructive actions
- **Phase 5** — Evaluation (RAGAS / LLM-as-judge, trajectory evaluation) + LangSmith tracing
- **Phase 6** — FastAPI backend, Snowflake Cortex for at least one model call, basic auth + logging

---

## 2. Git Workflow

**Never run `git commit` or `git push` in this repository unless explicitly told to for that
specific action.** The user commits and pushes themselves. Your job is to:

1. Make the changes.
2. Summarize what changed and why, in plain terms.
3. Explicitly say the change looks ready for commit (or flag what still needs work) — the user
   is waiting for this go/no-go before they commit.

Suggested GitHub checkpoints (natural, review-worthy commit points) are listed in
[README.md](README.md#suggested-github-checkpoints) — treat each one as a point to pause and ask
"ready for a commit?" rather than plowing ahead into the next phase.

---

## 3. Behavioral Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. These bias toward caution over speed
— for genuinely trivial tasks (renaming a variable, fixing a typo), use judgment and don't apply
this level of ceremony.

### 3.1 Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 3.2 Simplicity First
Minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3.3 Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### 3.4 Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] -> verify: [check]
2. [Step] -> verify: [check]
3. [Step] -> verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require
constant clarification.
