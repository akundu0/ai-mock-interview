# ai-mock-interview

A voice-AI mock-interview agent built on
[LiveKit Agents](https://docs.livekit.io/agents/) with a
[Tavus](https://www.tavus.io/) virtual avatar (Phoenix-3 PRO). The
agent runs **two interview stages inside a single `AgentSession`**,
orchestrated by a tiny state machine that keeps the LLM in ONE agent
instance and mutates its `instructions` at stage boundaries.

A Vercel-deployable Next.js browser client lives in
[`frontend/`](./frontend/) and lets candidates join the interview
from any browser.

## Project structure

```
.
├── .env.example               # Credential template (cp → .env.local)
├── .gitignore
├── README.md                   # ← you are here
├── agent.py                    # LiveKit worker entrypoint
├── interview.py                # Interviewer Agent + FSM orchestrator
├── pyproject.toml              # Python project metadata & dependencies
├── requirements.txt            # pip-locked dependency list
├── uv.lock                     # uv lockfile
├── docs/
│   └── API_KEYS.md             # Step-by-step API key walkthrough
├── tests/
│   └── test_state_machine.py   # pytest-asyncio FSM tests
└── frontend/                   # Vercel-deployable Next.js client
    ├── .env.example
    ├── README.md
    ├── next.config.js
    ├── package.json
    ├── tsconfig.json
    └── app/
        ├── layout.tsx
        ├── page.tsx
        └── api/
            └── token/
                └── route.ts    # Server-minted LiveKit access tokens
```

Only the files tracked in version control are shown — any local or generated
artifacts (`.venv/`, `__pycache__/`, `node_modules/`, etc.) are excluded.

## What's inside

| Path | What it does |
|---|---|
| `agent.py` | LiveKit worker entrypoint — voice pipeline + Tavus avatar + orchestrator wiring |
| `interview.py` | Single `Interviewer` Agent + `InterviewOrchestrator` FSM (stage state variable + time-based fallback watchdog) |
| `tests/test_state_machine.py` | pytest-asyncio tests that lock down the FSM behaviour |
| `frontend/` | Vercel-deployable Next.js app — LiveKit React components + server-minted access tokens |
| `docs/API_KEYS.md` | Step-by-step walkthrough: LiveKit Cloud + Tavus API key + Phoenix-3 PRO + LiveKit-transport persona |
| `pyproject.toml` / `requirements.txt` | Python deps (runtime + `[dev]` extra) |

## Prerequisites

- Python **≥ 3.10**
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`
- A [LiveKit Cloud](https://cloud.livekit.io/) project — supplies
  `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
- A [Tavus](https://platform.tavus.io/) account with
  - an API key (`TAVUS_API_KEY`),
  - a **Phoenix-3 PRO replica** (`TAVUS_FACE_ID` or
    `TAVUS_REPLICA_ID`),
  - a **persona** configured with `pipeline_mode=echo` and a
    transport layer whose `transport_type` is `livekit`
    (`TAVUS_PERSONA_ID`).

For the walkthrough — see [`docs/API_KEYS.md`](./docs/API_KEYS.md).

## Setup

```bash
# 1. Install + activate the runtime env
uv sync                       # or:  pip install -r requirements.txt
uv sync --extra dev           # adds pytest + pytest-asyncio

# 2. Copy and fill in credentials
cp .env.example .env.local

# 3. Run the agent
uv run agent.py dev           # development — connects to LiveKit Cloud
uv run agent.py console       # terminal-only mode (no room)
uv run agent.py start         # production mode

# 4. Run the test suite (locks down the FSM behaviour)
uv run pytest                 # or:  python -m pytest
```

## Running the browser demo

```bash
# 1. In one terminal: the agent
uv run agent.py dev

# 2. In another terminal: the Next.js frontend
cd frontend
npm install
npm run dev
# → open http://localhost:3000
```

## Deploying the frontend to Vercel

See [`frontend/README.md`](./frontend/README.md) — the short version:

1. Push the repo to GitHub.
2. Import `frontend/` as the project root in Vercel.
3. Set **server** env vars (`LIVEKIT_URL`, `LIVEKIT_API_KEY`,
   `LIVEKIT_API_SECRET`) and the **client** env var
   (`NEXT_PUBLIC_LIVEKIT_URL`) in *Settings → Environment Variables*.
4. Deploy.

## Architecture

### Single-agent invariant (step 3)

There is exactly one `Agent` instance — `Interviewer` — running
through the whole interview. Stage transitions do NOT spin up a
second agent; they mutate `agent.instructions` in place and call
`session.update_agent(agent)` so LiveKit re-reads the new system
prompt. The LLM thread of conversation stays continuous: no resets,
no repeated greetings, no conflicting instructions.

### State machine

`InterviewOrchestrator` keeps a single state variable
(`self._stage_index`) and a `StageConfig` table (`interview.STAGES`).
Natural advance fires when both heuristic conditions are true:

- the user has spoken at least `max(2, max_turns // 2)` turns, AND
- the stage has been active for at least
  `fallback_timeout_s * 0.5` seconds.

The transition is spoke once (`transition_phrase` is single-shot)
and the new stage's opening prompt fires immediately after.

### Time-based fallback (step 4)

`InterviewOrchestrator._watchdog_loop` runs as an `asyncio.Task`
alongside the conversation. Every 2 s, if the user has been silent
for `stage.fallback_timeout_s` seconds, it speaks the stage's
`fallback_prompt` to nudge them and resets the timer. The task is
cancelled at every stage advance and re-armed on entry to the new
stage, so the watchdog never overlaps with the natural-advance
path and never double-fires inside one idle window. The whole
advance is also wrapped in `asyncio.Lock` so concurrent
`force_advance()` calls can never double-trigger the bridge phase.

### Stage-transition matrix

| Stage | `fallback_timeout_s` | `max_turns` | `transition_phrase` |
|---|---|---|---|
| Self-introduction | 45 s | 4 | "Thanks for the intro… let's transition to Stage 2…" |
| Past experience  | 90 s | 6 | *(final — no transition)* |

### Test coverage (step 5)

`tests/test_state_machine.py` locks the FSM down:

- `test_single_agent_instance_is_used_throughout` — the same
  `agent` instance is in use across stages (no second agent
  spun up).
- `test_initial_state_is_self_introduction` — Stage 0 enters with
  the right opening prompt and one `update_agent` call.
- `test_time_based_fallback_fires_after_silence_window` — the
  watchdog fires *exactly once* after `fallback_timeout_s`.
- `test_time_based_fallback_does_not_fire_within_window` —
  zero fallback calls inside the window.
- `test_natural_advance_when_heuristic_conditions_met` —
  advance when turn count + age thresholds are met.
- `test_single_shot_transition_under_concurrent_force_advance` —
  two concurrent `force_advance()` calls produce exactly one
  bridge utterance.
- `test_advancing_past_final_stage_marks_completed` — the
  orchestrator marks `_completed = True` after the last stage.
- `test_watchdog_is_rearmed_on_stage_advance` — the watchdog
  task is replaced (the old one is cancelled) at stage
  boundaries.

## Next steps

- Tune `min_interruption_words` / VAD thresholds to taste — the
  defaults are conservative for a slow, smooth interview cadence.
- Add Stage 3 (closing / wrap-up) by appending a `StageConfig` to
  `interview.STAGES`. The orchestrator picks it up with no other
  changes.
- Wire recording (LiveKit Egress + per-stage transcript dumps)
  so each interview produces an asynchronous-replay artifact.
