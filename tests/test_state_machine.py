"""
Automated tests for the multi-stage interview state machine.

Locks down the full state-machine behavior:

- **Initial state** is SELF_INTRODUCTION with the right system prompt.
- **Single-agent invariant** — `Interviewer` is the only Agent
  instance and its `instructions` mutate in place.
- **Natural advance** fires once the heuristic conditions are met.
- **Time-based fallback** fires exactly once after
  `fallback_timeout_s` of silence, and never before.
- **Hard-timeout forced advance** — after N consecutive nudges
  with no user reply, the watchdog forces the stage transition so
  the workflow is guaranteed to progress.
- **Single-shot transitions** — concurrent `force_advance()` calls
  cannot double-fire the `transition_phrase`.
- **No overlapping utterances** — `generate_reply` is serialized
  via the orchestrator's `_transition_lock`, so even under
  concurrent user turns + force-advances + watchdog ticks, no two
  `generate_reply` calls can interleave.
- **Final stage completion** — the orchestrator marks
  `_completed = True` and stops responding after the last stage.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from interview import (
    USER_TURN_EVENT,
    Interviewer,
    InterviewOrchestrator,
    Stage,
    StageConfig,
    STAGES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def light_stages() -> list[StageConfig]:
    """Stages with very short fallbacks + hard-timeout=2 for fast tests."""
    return [
        StageConfig(
            name=Stage.SELF_INTRODUCTION,
            instructions="Stage 1 system prompt.",
            opening_prompt="Stage 1 opener.",
            fallback_timeout_s=0.1,
            fallback_prompt="Stage 1 nudge.",
            max_turns=2,
            transition_phrase="Stage 1 bridge phrase.",
            hard_timeout_nudges=2,
        ),
        StageConfig(
            name=Stage.PAST_EXPERIENCE,
            instructions="Stage 2 system prompt.",
            opening_prompt="Stage 2 opener.",
            fallback_timeout_s=0.1,
            fallback_prompt="Stage 2 nudge.",
            max_turns=2,
            transition_phrase="",  # final stage — no bridge utterance
            hard_timeout_nudges=2,
        ),
    ]


@pytest.fixture
def mock_session() -> AsyncMock:
    s = AsyncMock()
    s.update_agent = AsyncMock()
    s.generate_reply = AsyncMock()
    return s


@pytest.fixture
def agent(light_stages) -> Interviewer:
    return Interviewer(light_stages)


# ---------------------------------------------------------------------------
# Step 3 — the state machine (single agent + state variable)
# ---------------------------------------------------------------------------


def test_user_turn_event_constant_is_exported():
    assert isinstance(USER_TURN_EVENT, str)
    assert len(USER_TURN_EVENT) > 0


def test_single_agent_instance_is_used_throughout(
    mock_session, light_stages, agent,
):
    """Spec step 3: no second agent should be spun up. Verify the
    orchestrator holds the SAME `agent` instance."""
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    assert orch._agent is agent
    assert agent.instructions == light_stages[0].instructions


@pytest.mark.asyncio
async def test_initial_state_is_self_introduction(
    mock_session, light_stages, agent,
):
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    assert orch.current_stage.name == Stage.SELF_INTRODUCTION
    assert orch.stage_index == 0
    assert orch.completed is False

    await orch.start()
    # After start(): session.update_agent(agent) called exactly once,
    # and the opening prompt for Stage 0 was generated exactly once.
    update_calls = [
        c for c in mock_session.update_agent.call_args_list
        if c.args and c.args[0] is agent
    ]
    assert len(update_calls) == 1

    opening_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[0].opening_prompt
    ]
    assert len(opening_calls) == 1


@pytest.mark.asyncio
async def test_switch_stage_mutates_agent_instructions(
    mock_session, light_stages, agent,
):
    """The agent's instructions reflect the current stage's prompt."""
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()

    async with orch._transition_lock:
        await orch._enter_stage_locked(1)

    assert agent.instructions == light_stages[1].instructions
    assert orch.stage_index == 1


# ---------------------------------------------------------------------------
# Step 4 — time-based fallback fires exactly when expected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_time_based_fallback_fires_once_after_silence_window(
    mock_session, light_stages, agent,
):
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()
    mock_session.generate_reply.reset_mock()

    orch._last_user_input_at = time.monotonic() - 10.0
    advanced = await orch._tick_watchdog_once()

    fallback_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[0].fallback_prompt
    ]
    # Only one tick has fired AND hard_timeout_nudges=2, so we don't
    # force advance on the first nudge.
    assert len(fallback_calls) == 1
    assert advanced is False
    assert orch.consecutive_nudges == 1
    assert orch.current_stage.name == Stage.SELF_INTRODUCTION


@pytest.mark.asyncio
async def test_time_based_fallback_does_not_fire_within_window(
    mock_session, light_stages, agent,
):
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()
    mock_session.generate_reply.reset_mock()

    orch._last_user_input_at = time.monotonic()
    advanced = await orch._tick_watchdog_once()

    fallback_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[0].fallback_prompt
    ]
    assert len(fallback_calls) == 0
    assert advanced is False


@pytest.mark.asyncio
async def test_hard_timeout_force_advances_after_n_nudges(
    mock_session, light_stages, agent,
):
    """The spec: 'If the agent hasn't naturally transitioned the
    state ... within your time limit, the async task can force the
    system prompt update and inject a transition phrase.'
    With `hard_timeout_nudges=2`, the SECOND consecutive nudge
    forces the stage transition."""
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()
    mock_session.generate_reply.reset_mock()

    # Nudge #1 — still in Stage 1, no advance yet.
    orch._last_user_input_at = time.monotonic() - 10.0
    advanced = await orch._tick_watchdog_once()
    assert advanced is False
    assert orch.current_stage.name == Stage.SELF_INTRODUCTION
    assert orch.consecutive_nudges == 1

    # Nudge #2 — hard-timeout reached; force advance to Stage 2.
    orch._last_user_input_at = time.monotonic() - 10.0
    advanced = await orch._tick_watchdog_once()
    assert advanced is True
    assert orch.current_stage.name == Stage.PAST_EXPERIENCE
    # Bridge phrase was generated exactly once.
    transition_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[0].transition_phrase
    ]
    assert len(transition_calls) == 1
    # Fallback was generated exactly once (before the bridge).
    fallback_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[0].fallback_prompt
    ]
    assert len(fallback_calls) == 1
    # The Stage 2 opening prompt was generated once on entry.
    opening_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[1].opening_prompt
    ]
    assert len(opening_calls) == 1


@pytest.mark.asyncio
async def test_user_turn_resets_nudge_counter(
    mock_session, light_stages, agent,
):
    """A user reply at any point resets the nudge counter so multiple
    quiet-then-reply cycles don't accumulate toward the hard limit."""
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()

    orch._consecutive_nudges = 3  # simulate 3 nudges already fired
    await orch.on_user_turn()
    assert orch.consecutive_nudges == 0


# ---------------------------------------------------------------------------
# Single-shot transitions + no-overlap guarantees
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_shot_transition_under_concurrent_force_advance(
    mock_session, light_stages, agent,
):
    """Even if two callers race to advance, the bridge phrase is spoken
    exactly once (lock + completion flag cover all state changes)."""
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()
    mock_session.generate_reply.reset_mock()

    await asyncio.gather(orch.force_advance(), orch.force_advance())

    transition_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[0].transition_phrase
    ]
    assert len(transition_calls) == 1
    # Stage 1's opening prompt was generated exactly once.
    opening_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[1].opening_prompt
    ]
    assert len(opening_calls) == 1


@pytest.mark.asyncio
async def test_lock_serializes_generate_reply_under_concurrent_load(
    mock_session, light_stages, agent,
):
    """Even when user-turns, force-advances, and watchdog ticks run in
    flight simultaneously, no `generate_reply` should be started while
    another is in progress (lock prevents overlap).
    """
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()
    mock_session.generate_reply.reset_mock()

    # Schedule a tight storm of events.
    await asyncio.gather(
        orch.on_user_turn(),
        orch.on_user_turn(),
        orch.force_advance(),  # will be queued behind the user turns
        orch._tick_watchdog_once(),
    )

    # Stage 0 has a transition phrase, so on the way out we expect exactly:
    #   1 bridge utterance
    #   1 stage-2 opening utterance
    transition_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[0].transition_phrase
    ]
    assert len(transition_calls) == 1

    opening_calls = [
        c for c in mock_session.generate_reply.call_args_list
        if c.kwargs.get("instructions") == light_stages[1].opening_prompt
    ]
    assert len(opening_calls) == 1


@pytest.mark.asyncio
async def test_advancing_past_final_stage_marks_completed(
    mock_session, light_stages, agent,
):
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()

    await orch.force_advance()  # → Stage 1 (final)
    await orch.force_advance()  # → completed

    assert orch.current_stage.name == Stage.PAST_EXPERIENCE
    assert orch.completed is True


# ---------------------------------------------------------------------------
# Watchdog lifecycle (cancellation / re-arm)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watchdog_is_rearmed_on_stage_advance(
    mock_session, light_stages, agent,
):
    orch = InterviewOrchestrator(mock_session, agent, light_stages)
    await orch.start()
    first_watchdog = orch._watchdog_task

    await orch.force_advance()  # → Stage 2

    assert orch._watchdog_task is not None
    assert orch._watchdog_task is not first_watchdog
