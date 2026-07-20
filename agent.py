"""
Entrypoint for the AI mock-interview LiveKit agent.

A single `Interviewer(Agent)` runs the entire two-stage interview — no
second agent is ever spun up. The orchestrator mutates the agent's
`instructions` at stage boundaries; LiveKit re-reads them on the next
LLM turn via `session.update_agent(agent)`.

A Tavus virtual avatar (Phoenix-3 PRO for lowest latency) provides
real-time 2D/3D rendering and is started BEFORE the agent audio is
piped, so lip-sync stays in lockstep with TTS.

Step 4's requirements are met by the orchestrator's
`_watchdog_loop()` — an `asyncio` task running alongside the
conversation that injects a per-stage `fallback_prompt` after the
configured silence window.

Step 3's requirement (no second agent) is met by mutating the single
agent's `instructions` rather than swapping to a different `Agent`
subclass.

Run modes:

    uv run agent.py dev         # development — connects to LiveKit Cloud
    uv run agent.py start       # production
    uv run agent.py console     # terminal-only (no LiveKit room)
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    TurnHandlingOptions,
    inference,
)
from livekit.plugins import tavus
from livekit.plugins import openai as lk_openai
from interview import (
    USER_TURN_EVENT,
    Interviewer,
    InterviewOrchestrator,
    STAGES,
)

# Load credentials from `.env.local` (preferred, gitignored) and fall
# back to `.env`.
load_dotenv(".env.local")
load_dotenv()


def _tavus_face_id() -> str:
    """Read the avatar replica/face id from env, accepting either name.

    In Tavus's data model a "Phoenix-3 PRO face" IS the replica — what
    LiveKit's plugin calls `replica_id`. We accept both names so the
    user's preferred env var works.
    """
    face_id = (
        os.environ.get("TAVUS_FACE_ID")
        or os.environ.get("TAVUS_REPLICA_ID")
    )
    if not face_id:
        raise RuntimeError(
            "Missing Tavus face (replica) id. Set TAVUS_FACE_ID (preferred) "
            "or TAVUS_REPLICA_ID in .env.local. Tavus recommends a Phoenix-3 "
            "PRO replica for the lowest end-to-end streaming latency."
        )
    return face_id


server = AgentServer()


@server.rtc_session(agent_name="ai-mock-interview")
async def entrypoint(ctx: JobContext) -> None:
    # 1. ---------- Voice pipeline (STT → LLM → TTS) --------------------
    # LiveKit Inference — zero external API keys beyond LiveKit Cloud.
    # Cartesia Sonic-3 is the lowest-latency TTS in the inference
    # catalog, which keeps lip-sync tight with the Tavus avatar.
    session = AgentSession(
        stt=inference.STT(model="deepgram/nova-3", language="multi"),
        llm=lk_openai.LLM(
        model="llama-3.1-8b-instant",
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ.get("GROQ_API_KEY"),
    ),
        tts=inference.TTS(model="cartesia/sonic-3"),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
        ),
        # Gentle interruption handling: allow the user to interject
        # naturally, but LiveKit's VAD+TurnDetector filters out the
        # short spurious interruptions during back-channeling.
        allow_interruptions=True,
        # TODO: tune `min_interruption_words` (or `min_interruption_duration_ms`)
        # if your VAD/TurnDetector is over-eager at cutting the interviewer.
    )

    # 2. ---------- Tavus virtual avatar (Phoenix-3 PRO face) -------------
    # MUST be started BEFORE piping agent audio so the avatar's
    # lip-sync stays in lockstep with TTS. Phoenix-3 PRO replicas give
    # the lowest end-to-end streaming latency.
    avatar = tavus.AvatarSession(
        replica_id=_tavus_face_id(),
        persona_id=os.environ["TAVUS_PERSONA_ID"],
        avatar_participant_name=os.environ.get(
            "TAVUS_AVATAR_NAME", "Tavus-avatar-agent"
        ),
    )
    await avatar.start(session, room=ctx.room)

    # 3. ---------- Start session + the single-agent orchestrator --------
    # The SAME `Interviewer` instance runs both stages; its
    # `instructions` get swapped at stage boundaries.
    interviewer = Interviewer(STAGES)
    await session.start(room=ctx.room, agent=interviewer)

    orch = InterviewOrchestrator(session, interviewer, STAGES)
    await orch.start()  # enters Stage 0 + arms the time-based fallback.

    # Drive stage transitions from user-turn events. `USER_TURN_EVENT`
    # is the LiveKit Agents 1.5 signal that a user turn has been
    # committed by VAD + STT. If your patch uses different naming,
    # adjust `USER_TURN_EVENT` in `interview.py`. Documented alternates:
    # `user_input_transcribed`, `conversation_item_added`.
    @session.on(USER_TURN_EVENT)
    async def _on_user_turn(_event) -> None:
        await orch.on_user_turn()


if __name__ == "__main__":
    # Run modes: `python agent.py dev` | `... start` | `... console`
    agents.cli.run_app(server)
