"""
Single-agent state machine for the AI mock-interview LiveKit agent.

Per spec step 3: **do NOT spin up a second agent.** Instead we run ONE
`Interviewer(Agent)` whose `instructions` system prompt is mutated at
runtime, and the orchestrator on top of that runs the FSM with the
time-based fallback watchdog.

Stage transitions, watchdog-driven force advance, and ALL
`generate_reply(...)` calls are serialized through a single
`asyncio.Lock` so two concurrent callers can never produce overlapping
utterances — exactly the "smooth, no interruptions, no conflicts, no
repetitive prompts" guarantee the spec calls for.

The complete state-machine invariants are locked down by
`tests/test_state_machine.py`.
"""

from __future__ import annotations

import asyncio
import dataclasses
import enum
import time
from typing import List, Optional

from livekit.agents import Agent, AgentSession


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------


# The LiveKit AgentSession event that signals "the user has finished
# speaking — the user's transcribed turn is now committed". The exact
# name varies across LiveKit Agents patch releases; documented
# alternates are `user_input_transcribed` and `conversation_item_added`.
USER_TURN_EVENT = "user_speech_committed"


# ---------------------------------------------------------------------------
# Stage declarations
# ---------------------------------------------------------------------------


class Stage(enum.Enum):
    SELF_INTRODUCTION = "self_introduction"
    PAST_EXPERIENCE = "past_experience"


@dataclasses.dataclass(frozen=True)
class StageConfig:
    """Immutable, declarative description of one interview stage."""

    name: Stage
    instructions: str                       # System prompt the LLM uses in this stage.
    opening_prompt: str                     # First utterance the agent should produce.
    fallback_timeout_s: float               # Idle seconds before the watchdog nudges.
    fallback_prompt: str                    # Watchdog utterance to nudge the user.
    max_turns: int                          # Soft cap for the natural-advance heuristic.
    transition_phrase: str = ""            # Single-shot bridge utterance (empty if final).
    hard_timeout_nudges: int = 2            # Force advance after N nudges w/o user reply.


STAGES: List[StageConfig] = [
    StageConfig(
        name=Stage.SELF_INTRODUCTION,
        instructions=(
            "You are conducting STAGE 1 of 2 of a mock interview: "
            "SELF-INTRODUCTION. Be warm, conversational, and concise. Ask the "
            "candidate to introduce themselves — name, current role, and a "
            "quick career snapshot — and add at most ONE light follow-up. "
            "Once they have covered the basics, signal that you are ready to "
            "move on to the next stage. Never re-greet; never repeat the "
            "introduction prompt. Keep spoken replies brief and free of "
            "markdown, emojis, and unusual punctuation."
        ),
        opening_prompt=(
            "Greet the candidate warmly and ask them to introduce themselves — "
            "their name, current role, and a quick career summary."
        ),
        fallback_timeout_s=45.0,
        fallback_prompt=(
            "The candidate has been quiet. Gently nudge them: 'Whenever you're "
            "ready, feel free to share your name, current role, and a quick "
            "career snapshot.'"
        ),
        max_turns=4,
        transition_phrase=(
            "Thanks for the intro — that's really helpful. Let's keep things "
            "moving and dive deeper into your hands-on experience now."
        ),
        hard_timeout_nudges=2,
    ),
    StageConfig(
        name=Stage.PAST_EXPERIENCE,
        instructions=(
            "You are conducting STAGE 2 of 2 of a mock interview: "
            "PAST EXPERIENCE. Ask the candidate to walk through a recent "
            "project in detail — scope, their specific contributions, "
            "technical decisions, challenges, and outcomes. Probe depth with "
            "1-2 targeted follow-ups on architecture, trade-offs, and "
            "lessons learned. Give brief, constructive feedback at the end "
            "of each answer. Never repeat the Stage 1 greeting. Keep spoken "
            "replies brief and free of markdown, emojis, and unusual "
            "punctuation."
        ),
        opening_prompt=(
            "Walk me through one recent project you're proud of — what you "
            "owned, the trade-offs you made, and the outcome."
        ),
        fallback_timeout_s=90.0,
        fallback_prompt=(
            "The candidate has gone quiet. Soft re-prompt: 'Take your "
            "time — feel free to describe the project in as much detail "
            "as you'd like, including your specific contributions.'"
        ),
        max_turns=6,
        transition_phrase="",  # final stage
        hard_timeout_nudges=2,
    ),
]


# ---------------------------------------------------------------------------
# Single Interviewer Agent (no second agent spun up)
# ---------------------------------------------------------------------------


class Interviewer(Agent):
    """The one and only voice agent for the interview.

    Its `instructions` are mutated by the orchestrator at stage
    transitions. LiveKit re-reads `instructions` whenever
    `session.update_agent(self)` is called with this instance, so the
    LLM sees the refreshed system prompt without us ever spinning up a
    second Agent — exactly the spec in step 3.

    NOTE: Verify with `lk agent dev` that `update_agent(agent)` in
    your installed LiveKit Agents patch actually re-reads
    `self.instructions`. If it doesn't, append a system message
    directly to `session.chat_ctx.messages` from the orchestrator.
    """

    def __init__(self, stages: List[StageConfig]) -> None:
        if not stages:
            raise ValueError("`stages` must contain at least one StageConfig.")
        super().__init__(instructions=stages[0].instructions)
        self._stages = list(stages)

    @property
    def stages(self) -> List[StageConfig]:
        return list(self._stages)

    async def switch_stage(self, index: int) -> None:
        """Mutate `self.instructions` to the new stage's prompt.

        Called by `InterviewOrchestrator` BEFORE
        `session.update_agent(self)` so LiveKit sees the new system
        prompt when it re-reads the chat context.
        """
        if not 0 <= index < len(self._stages):
            raise IndexError(f"Stage index out of range: {index}")
        await self.update_instructions(self._stages[index].instructions)


# ---------------------------------------------------------------------------
# Orchestrator (FSM with time-based + hard-timeout fallback watchdog)
# ---------------------------------------------------------------------------


class InterviewOrchestrator:
    """Drives the multi-stage interview inside ONE shared `AgentSession`.

    Guarantees (the user-facing spec):

    - **No second agent spun up.** Stage transitions mutate the one
      `Interviewer` agent's `instructions` in place.
    - **Time-based fallback.** If the user goes silent for
      `stage.fallback_timeout_s`, the watchdog injects a gentle
      `fallback_prompt`.
    - **Hard-timeout forced advance.** After
      `stage.hard_timeout_nudges` consecutive nudges with no user
      reply, the watchdog FORCES the stage transition — so the
      workflow keeps progressing even if the candidate never
      responds (e.g. demo disconnects, mic off, etc.).
    - **Single-shot transitions.** Every `generate_reply(...)` call
      site, every advance, every enter-stage runs under one
      `asyncio.Lock`, so concurrent callers cannot overlap
      utterances, repeat a prompt, or fire a transition twice.
    """

    def __init__(
        self,
        session: AgentSession,
        agent: Interviewer,
        stages: List[StageConfig] = STAGES,
    ) -> None:
        if len(agent.stages) != len(stages):
            raise ValueError(
                "Agent and orchestrator must be initialized with the same stages."
            )
        self._session = session
        self._agent = agent
        self._stages = list(stages)
        self._stage_index: int = 0
        self._turn_count: int = 0
        self._stage_started_at: float = 0.0
        self._last_user_input_at: float = 0.0
        self._completed: bool = False
        # serialized mutex for all state mutation + generate_reply.
        self._transition_lock = asyncio.Lock()
        self._watchdog_task: Optional[asyncio.Task] = None
        # how many nudges we've fired in the current stage since the
        # last user reply; reset to 0 on any on_user_turn().
        self._consecutive_nudges: int = 0

    # -- public read-only properties --------------------------------------

    @property
    def current_stage(self) -> StageConfig:
        return self._stages[self._stage_index]

    @property
    def stage_index(self) -> int:
        return self._stage_index

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def consecutive_nudges(self) -> int:
        return self._consecutive_nudges

    # -- public entry points ----------------------------------------------

    async def start(self) -> None:
        """Enter Stage 0 once. Idempotent."""
        if self._stage_started_at == 0.0:
            async with self._transition_lock:
                await self._enter_stage_locked(0)

    async def on_user_turn(self) -> None:
        """Hooked from `session.on(USER_TURN_EVENT)` (see constant).

        Resets the silence timer + nudge counter, increments the
        per-stage turn counter, and — under the lock — checks the
        natural-advance heuristic so user turns cannot race with the
        watchdog.
        """
        self._last_user_input_at = time.monotonic()
        self._turn_count += 1
        async with self._transition_lock:
            if self._completed:
                return
            self._consecutive_nudges = 0  # user is active again
            await self._maybe_advance_locked()

    async def force_advance(self) -> None:
        """External hook (e.g. a UI button) to manually advance stages."""
        async with self._transition_lock:
            await self._advance_body()

    # -- FSM internals ----------------------------------------------------

    async def _enter_stage_locked(self, index: int) -> None:
        """Enter a stage. MUST be called with `_transition_lock` held."""
        stage = self._stages[index]
        # Mutate the (single) agent's instructions FIRST so LiveKit
        # sees the fresh system prompt when we re-bind below.
        await self._agent.switch_stage(index)
        # Re-bind the same agent instance — LiveKit re-reads its
        # `instructions` and rebuilds the chat context's system
        # message. No second agent is ever spun up.
        self._session.update_agent(self._agent)
        # Reset bookkeeping for this stage.
        self._stage_index = index
        self._turn_count = 0
        self._consecutive_nudges = 0
        self._stage_started_at = time.monotonic()
        self._last_user_input_at = time.monotonic()
        # Cancel + re-arm the silence watchdog for the new stage's
        # timeout, before speaking the opening prompt.
        self._rearm_watchdog()
        # Speak the stage opening prompt exactly once.
        await self._session.generate_reply(instructions=stage.opening_prompt)

    async def _maybe_advance_locked(self) -> None:
        """Natural-advance heuristic. Caller MUST hold the lock."""
        stage = self.current_stage
        if not stage.transition_phrase:
            return  # final stage — no transition configured
        age = time.monotonic() - self._stage_started_at
        enough_turns = self._turn_count >= max(2, stage.max_turns // 2)
        enough_time = age >= stage.fallback_timeout_s * 0.5
        if enough_turns and enough_time:
            await self._advance_body()

    async def _advance_body(self) -> None:
        """Perform one stage advance. Caller MUST hold the lock.

        This wraps the bridge utterance + the new stage entry inside
        ONE critical section so a concurrent caller can never observe
        a half-applied stage boundary.
        """
        if self._completed:
            return
        stage = self.current_stage
        if not stage.transition_phrase:
            # Already in the final stage with nothing to transition to.
            self._completed = True
            self._cancel_watchdog()
            return
        # Single-shot bridge: cancel the watchdog first so the
        # bridge utterance itself isn't double-fired by a stale
        # timer, then speak it exactly once.
        self._cancel_watchdog()
        await self._session.generate_reply(
            instructions=stage.transition_phrase
        )
        self._stage_index += 1
        if self._stage_index >= len(self._stages):
            self._completed = True
            return
        await self._enter_stage_locked(self._stage_index)

    # -- watchdog (time-based + hard-timeout fallback) -----------------

    def _rearm_watchdog(self) -> None:
        self._cancel_watchdog()
        self._watchdog_task = asyncio.create_task(self._watchdog_loop())

    def _cancel_watchdog(self) -> None:
        if self._watchdog_task is not None and not self._watchdog_task.done():
            self._watchdog_task.cancel()

    async def _watchdog_loop(self) -> None:
        """Background task: every 2 s, check whether the candidate has
        gone silent for `stage.fallback_timeout_s`. If so, fire the
        stage's `fallback_prompt` exactly once per idle window; after
        `stage.hard_timeout_nudges` consecutive nudges, FORCE the
        stage transition so the workflow is guaranteed to progress.
        """
        try:
            while not self._completed:
                await asyncio.sleep(2.0)
                await self._tick_watchdog_once()
        except asyncio.CancelledError:
            return

    async def _tick_watchdog_once(self) -> bool:
        """One watchdog iteration (no waiting). Acquires the lock so
        its `generate_reply` cannot overlap with anything else.

        Returns True iff a hard-timeout forced stage advance fired in
        this tick. Used by tests to verify the hard-timeout path.
        """
        if self._completed:
            return False
        async with self._transition_lock:
            if self._completed:
                return False
            idle_for = time.monotonic() - self._last_user_input_at
            stage = self.current_stage
            if idle_for < stage.fallback_timeout_s:
                # Not yet idle enough — no nudge.
                return False
            # Reset the idle timer so we don't double-fire within the
            # same idle window.
            self._last_user_input_at = time.monotonic()
            await self._session.generate_reply(
                instructions=stage.fallback_prompt
            )
            self._consecutive_nudges += 1
            # Hard-timeout forced advance: if we've nudged N times
            # without a user reply, force the stage transition so
            # the workflow is guaranteed to keep progressing.
            if (
                stage.transition_phrase
                and self._consecutive_nudges >= stage.hard_timeout_nudges
            ):
                await self._advance_body()
                # The orchestrator may have wrapped to a new stage;
                # reset nudge counter for the new stage.
                self._consecutive_nudges = 0
                return True
        return False
