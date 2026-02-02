# Implementation Plan: Simulation Unit & Integration Tests (Parts 1-3)

Branch: `validation/simulation-unit-tests`

## Overview

Three new test files, one extended conftest, zero LLM calls. Each section below is a test class with exact test methods, the function under test, and what's being asserted. Follows existing patterns: pytest classes, `_make_*` helpers, `tmp_path` for SQLite, fixtures from conftest.

---

## File 1: `tests/test_conviction.py`

Tests the conviction system in isolation. Functions under test live in `entropy/core/models/simulation.py`.

### Imports

```python
import pytest
from entropy.core.models import (
    ConvictionLevel,
    CONVICTION_MAP,
    CONVICTION_REVERSE_MAP,
    conviction_to_float,
    float_to_conviction,
    score_to_conviction_float,
)
```

### Class: `TestScoreToConvictionFloat`

Tests `score_to_conviction_float()` — the 0-100 → float bucketing.

| Test Method | Input | Expected Output | Notes |
|---|---|---|---|
| `test_very_uncertain_low_boundary` | `0` | `0.1` | Bottom of range |
| `test_very_uncertain_high_boundary` | `15` | `0.1` | Top of very_uncertain bucket |
| `test_leaning_low_boundary` | `16` | `0.3` | Transition point |
| `test_leaning_high_boundary` | `35` | `0.3` | Top of leaning bucket |
| `test_moderate_low_boundary` | `36` | `0.5` | |
| `test_moderate_high_boundary` | `60` | `0.5` | |
| `test_firm_low_boundary` | `61` | `0.7` | |
| `test_firm_high_boundary` | `85` | `0.7` | |
| `test_absolute_low_boundary` | `86` | `0.9` | |
| `test_absolute_high_boundary` | `100` | `0.9` | |
| `test_none_returns_none` | `None` | `None` | |
| `test_float_input_accepted` | `50.0` | `0.5` | Score can be float |
| `test_midpoint_values` | `25, 50, 75` | `0.3, 0.5, 0.7` | Typical values |

Could also use `@pytest.mark.parametrize` for the boundary pairs to reduce boilerplate.

### Class: `TestFloatToConviction`

Tests `float_to_conviction()` — float → nearest level string.

| Test Method | Input | Expected Output |
|---|---|---|
| `test_exact_values` | `0.1, 0.3, 0.5, 0.7, 0.9` | Each maps to its ConvictionLevel |
| `test_nearest_rounding` | `0.2` | `"very_uncertain"` (closer to 0.1) or `"leaning"` (closer to 0.3) — verify actual behavior |
| `test_none_returns_none` | `None` | `None` |
| `test_zero` | `0.0` | `"very_uncertain"` (nearest to 0.1) |
| `test_one` | `1.0` | `"absolute"` (nearest to 0.9) |

### Class: `TestConvictionToFloat`

Tests `conviction_to_float()` — level string → float.

| Test Method | Input | Expected |
|---|---|---|
| `test_all_levels` | Each `ConvictionLevel` value | Matches `CONVICTION_MAP` |
| `test_none_returns_none` | `None` | `None` |
| `test_invalid_string` | `"invalid"` | `None` |

### Class: `TestConvictionMaps`

Tests `CONVICTION_MAP` and `CONVICTION_REVERSE_MAP` consistency.

| Test Method | What |
|---|---|
| `test_map_has_five_levels` | `len(CONVICTION_MAP) == 5` |
| `test_reverse_map_roundtrip` | Every value in CONVICTION_MAP is a key in CONVICTION_REVERSE_MAP and vice versa |
| `test_values_are_ordered` | `very_uncertain < leaning < moderate < firm < absolute` |
| `test_engine_constants_match` | Import engine's `_FIRM_CONVICTION`, `_MODERATE_CONVICTION`, `_SHARING_CONVICTION_THRESHOLD` and verify they match `CONVICTION_MAP` values |

---

## File 2: `tests/test_propagation.py`

Tests exposure propagation and network spreading. Functions under test in `entropy/simulation/propagation.py`.

### Imports

```python
import random
from datetime import datetime

import pytest

from entropy.core.models import ExposureRecord, SimulationEventType
from entropy.core.models.scenario import (
    Event, EventType, ExposureChannel, ExposureRule,
    InteractionConfig, InteractionType, OutcomeConfig,
    ScenarioMeta, ScenarioSpec, SeedExposure, SimulationConfig,
    SpreadConfig, TimestepUnit, ShareModifier,
)
from entropy.simulation.propagation import (
    apply_seed_exposures,
    calculate_share_probability,
    evaluate_exposure_rule,
    get_channel_credibility,
    get_neighbors,
    propagate_through_network,
)
from entropy.simulation.state import StateManager
```

### Fixtures (local to file)

- `rng`: `random.Random(42)` — or reuse from conftest
- `ten_agents`: 10 agents with `_id` "a0"-"a9" and attributes `age`, `role`
- `linear_network`: Chain a0→a1→a2→...→a9 (9 edges)
- `star_network`: Hub a0, spokes a1-a9 (9 edges)
- `disconnected_network`: a0-a1 connected, a2-a9 isolated (1 edge)
- `base_scenario`: Reuse `minimal_scenario` pattern from test_engine.py with configurable rules
- `_make_scenario(**overrides)`: Helper to create scenario with custom seed_exposure rules, spread config

### Class: `TestEvaluateExposureRule`

Tests `evaluate_exposure_rule(rule, agent, timestep)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_matching_timestep_and_condition` | rule timestep=0, when="true", agent any, timestep=0 | `True` |
| `test_wrong_timestep` | rule timestep=0, timestep=1 | `False` |
| `test_condition_filters_agent` | rule when="age > 40", agent age=30 | `False` |
| `test_condition_matches_agent` | rule when="age > 40", agent age=50 | `True` |
| `test_always_true_condition` | rule when="true" | `True` for any agent |

### Class: `TestGetChannelCredibility`

Tests `get_channel_credibility(scenario, channel_name)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_existing_channel` | Channel "broadcast" with credibility_modifier=0.8 | `0.8` |
| `test_missing_channel_returns_default` | Channel name not in scenario | `1.0` |

### Class: `TestApplySeedExposures`

Tests `apply_seed_exposures(timestep, scenario, agents, state_manager, rng)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_all_agents_exposed_broadcast` | prob=1.0, when="true", 10 agents | Returns 10, all agents aware |
| `test_no_exposure_wrong_timestep` | Rule for timestep=5, called at timestep=0 | Returns 0 |
| `test_conditional_exposure` | when="role == 'senior'", 3 seniors out of 10 | Returns 3, only seniors aware |
| `test_probabilistic_exposure` | prob=0.5, seeded rng | Returns between 0 and 10, deterministic with seed |
| `test_credibility_calculation` | event.credibility=0.9, channel.credibility_modifier=0.8 | Exposure records have credibility=0.72 |
| `test_multiple_rules_same_timestep` | Two rules at timestep=0, different conditions | Both applied, agents can get multiple exposures |
| `test_already_aware_agent_gets_new_exposure` | Expose agent twice | exposure_count=2, still one aware agent |

### Class: `TestGetNeighbors`

Tests `get_neighbors(network, agent_id)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_hub_of_star` | Star network, agent "a0" | 9 neighbors |
| `test_spoke_of_star` | Star network, agent "a1" | 1 neighbor (a0) |
| `test_isolated_agent` | Disconnected network, agent "a5" | 0 neighbors |
| `test_bidirectional` | Edge source=a0, target=a1 | a0 sees a1, a1 sees a0 |

### Class: `TestCalculateShareProbability`

Tests `calculate_share_probability(agent, edge_data, spread_config, rng)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_base_probability` | No modifiers, base=0.3 | Returns 0.3 |
| `test_modifier_multiply` | Modifier when="true", multiply=2.0, add=0 | Returns 0.6 |
| `test_modifier_add` | Modifier when="true", multiply=1.0, add=0.1 | Returns 0.4 |
| `test_modifier_clamp_upper` | Modifier pushes prob to 1.5 | Returns 1.0 |
| `test_modifier_clamp_lower` | Modifier pushes prob negative | Returns 0.0 |
| `test_condition_not_met` | Modifier when="age > 100", agent age=30 | Returns base (0.3) |
| `test_edge_type_in_context` | Modifier when="edge_type == 'mentor'", edge type="mentor" | Modifier applied |

### Class: `TestPropagateThrough Network`

Tests `propagate_through_network(...)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_single_sharer_linear_chain` | a0 shares, linear chain, prob=1.0 | a1 exposed (one hop only, a2 not exposed this timestep) |
| `test_hub_sharer_star_network` | a0 shares, star network, prob=1.0 | All 9 spokes exposed |
| `test_no_sharers_no_propagation` | No agents have will_share=True | Returns 0 |
| `test_conviction_gated_sharing` | This is tested at engine level — here just test that `get_sharers()` returns empty when no sharers in DB |
| `test_peer_credibility_is_085` | a0 shares to a1 | Exposure record has credibility=0.85 |
| `test_already_aware_still_gets_exposure` | a1 already aware, a0 shares | a1 gets new exposure (exposure_count increments), for multi-touch |
| `test_adjacency_list_used` | Pass adjacency dict, verify no `get_neighbors()` fallback (check exposures match adjacency structure) |
| `test_probabilistic_sharing` | share_prob=0.5, seeded rng, many edges | Deterministic subset exposed |

**Important setup detail:** For propagation tests, agents need to already be in the `will_share=True` state in the StateManager before calling `propagate_through_network()`. This means:
1. Create StateManager with agents
2. Record an exposure for the sharer agent
3. Update the sharer's state to `will_share=True`
4. Then call `propagate_through_network()`

---

## File 3: `tests/test_stopping.py`

Tests stopping condition evaluation. Functions under test in `entropy/simulation/stopping.py`.

### Imports

```python
import pytest

from entropy.core.models import TimestepSummary
from entropy.core.models.scenario import SimulationConfig, TimestepUnit
from entropy.simulation.stopping import (
    evaluate_comparison,
    evaluate_condition,
    evaluate_convergence,
    evaluate_no_state_changes,
    evaluate_stopping_conditions,
    parse_comparison,
)
from entropy.simulation.state import StateManager
```

### Fixtures

- `_make_summary(**overrides)`: Factory for `TimestepSummary` with sensible defaults
- `_make_summaries(n, **shared_overrides)`: Creates a list of n summaries for sliding window tests
- `_make_config(**overrides)`: Factory for `SimulationConfig` with defaults

### Class: `TestParseComparison`

Tests `parse_comparison(condition)`.

| Test Method | Input | Expected |
|---|---|---|
| `test_greater_than` | `"exposure_rate > 0.95"` | `("exposure_rate", ">", 0.95)` |
| `test_less_than` | `"average_sentiment < 0.0"` | `("average_sentiment", "<", 0.0)` |
| `test_greater_equal` | `"exposure_rate >= 1.0"` | `("exposure_rate", ">=", 1.0)` |
| `test_equal` | `"state_changes == 0"` | `("state_changes", "==", 0.0)` |
| `test_not_equal` | `"exposure_rate != 0.0"` | `("exposure_rate", "!=", 0.0)` |
| `test_invalid_format` | `"not a condition"` | `None` |
| `test_whitespace_handling` | `"  exposure_rate  >  0.95  "` | `("exposure_rate", ">", 0.95)` |

### Class: `TestEvaluateNoStateChanges`

Tests `evaluate_no_state_changes(condition, recent_summaries)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_stable_for_threshold` | `"no_state_changes_for > 10"`, 11 summaries with state_changes=0 | `True` |
| `test_not_stable_enough` | `"no_state_changes_for > 10"`, 10 summaries with state_changes=0 | `False` (need >10, not ==10) |
| `test_recent_change_breaks_stability` | 15 summaries, last one has state_changes=1 | `False` |
| `test_empty_summaries` | No summaries | `False` |

### Class: `TestEvaluateConvergence`

Tests `evaluate_convergence(recent_summaries, window, tolerance)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_stable_distribution` | 5 summaries, identical position_distribution `{"adopt": 70, "reject": 30}` | `True` |
| `test_shifting_distribution` | 5 summaries with varying distributions | `False` |
| `test_insufficient_window` | 3 summaries, window=5 | `False` (not enough data) |
| `test_custom_tolerance` | 5 summaries with small drift, tolerance=0.1 | `True` (within tolerance) |
| `test_empty_position_distribution` | Summaries with empty dicts | Handle gracefully (False or True — verify actual behavior) |

### Class: `TestEvaluateStoppingConditions`

Tests the top-level `evaluate_stopping_conditions(timestep, config, state_manager, recent_summaries)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_max_timesteps_reached` | timestep=99, max_timesteps=100 | `(True, "max_timesteps")` or similar reason string |
| `test_before_max_timesteps` | timestep=50, max_timesteps=100, no conditions | `(False, None)` |
| `test_exposure_rate_condition_met` | Condition `"exposure_rate > 0.95"`, state_manager with 96% aware | `(True, ...)` |
| `test_exposure_rate_condition_not_met` | Condition `"exposure_rate > 0.95"`, state_manager with 50% aware | `(False, None)` |
| `test_compound_condition_both_met` | (depends on whether compound `and` is supported at the `evaluate_condition` level — read the code to confirm) |
| `test_no_stop_conditions` | Config with empty `stop_conditions` list, timestep < max | `(False, None)` |

**Note:** These tests require a StateManager with agents initialized and some in aware state. Use `tmp_path` for SQLite DB, initialize agents, record exposures to set up desired exposure_rate.

---

## File 4: `tests/test_memory_traces.py`

Tests memory trace storage and retrieval, plus the `get_agents_to_reason()` multi-touch logic. Functions under test in `entropy/simulation/state.py`.

### Fixtures

- `state_mgr(tmp_path)`: Creates StateManager with 5 agents, returns it
- `_make_memory_entry(**overrides)`: Factory for `MemoryEntry`

### Class: `TestMemoryTraceSliding Window`

Tests `save_memory_entry()` and `get_memory_traces()`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_single_entry` | Save 1 memory entry for agent | `get_memory_traces()` returns 1 entry |
| `test_three_entries_retained` | Save 3 entries | All 3 returned, ordered oldest→newest |
| `test_fourth_entry_evicts_oldest` | Save 4 entries | Only latest 3 returned |
| `test_fifth_entry_still_three` | Save 5 entries | Still 3, earliest 2 evicted |
| `test_entries_ordered_by_timestep` | Save entries at timesteps 3, 1, 2 | Returned in order 1, 2, 3 |
| `test_separate_agents` | Save entries for agent_a and agent_b | Each agent has independent trace |

### Class: `TestGetAgentsToReason`

Tests `get_agents_to_reason(timestep, threshold)`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_never_reasoned_aware_agent` | Agent aware (has exposure), never reasoned (last_reasoning_timestep=-1) | Agent in result list |
| `test_unaware_agent_excluded` | Agent not exposed | Not in result list |
| `test_multi_touch_below_threshold` | Agent reasoned at t=0, got 2 new exposures (threshold=3) | Not in result list |
| `test_multi_touch_at_threshold` | Agent reasoned at t=0, got 3 new exposures (threshold=3) | In result list |
| `test_multi_touch_above_threshold` | Agent reasoned at t=0, got 5 new exposures (threshold=3) | In result list |
| `test_recently_reasoned_no_new_exposures` | Agent reasoned at t=5, no new exposures since | Not in result list |

**Setup notes:** Multi-touch tests require:
1. Initialize agents
2. Record initial exposure (makes agent aware)
3. Update agent state with `last_reasoning_timestep` set
4. Record additional exposures after that timestep
5. Call `get_agents_to_reason(current_timestep, threshold)`

### Class: `TestStateManagerAggregations`

Tests analytics queries that aren't covered in existing `test_simulation.py`.

| Test Method | Setup | Expected |
|---|---|---|
| `test_get_sentiment_variance` | 5 agents with sentiments [0.1, 0.3, 0.5, 0.7, 0.9] | Returns correct variance |
| `test_get_sentiment_variance_none_when_no_data` | No agents with sentiment | Returns `None` |
| `test_get_average_conviction` | 5 agents with varied convictions | Returns correct mean |
| `test_get_population_count` | 10 agents initialized | Returns 10 |

---

## File 5: `tests/test_reasoning_prompts.py`

Tests prompt construction and schema generation. Functions under test in `entropy/simulation/reasoning.py`. No LLM calls — just string/dict construction.

### Imports

```python
import pytest

from entropy.core.models import (
    ExposureRecord, MemoryEntry, PeerOpinion,
    ReasoningContext, AgentState,
    float_to_conviction,
)
from entropy.core.models.scenario import (
    OutcomeConfig, OutcomeDefinition, OutcomeType,
    # ... scenario models for build_pass2_schema
)
from entropy.simulation.reasoning import (
    build_pass1_prompt,
    build_pass1_schema,
    build_pass2_prompt,
    build_pass2_schema,
    _get_primary_position_outcome,
    _sentiment_to_tone,
)
```

### Fixtures

- `_make_context(**overrides)`: Factory for `ReasoningContext` with default persona, event, exposure
- `_make_scenario(**overrides)`: Factory reusing pattern from test_engine.py

### Class: `TestBuildPass1Prompt`

Tests `build_pass1_prompt(context, scenario)`.

| Test Method | What's Asserted |
|---|---|
| `test_persona_included` | Context persona string appears in output |
| `test_event_content_included` | `scenario.event.content` appears in output |
| `test_event_source_included` | `scenario.event.source` appears in output |
| `test_seed_exposure_shows_channel` | Exposure with no `source_agent_id` → "You heard about this via {channel}" |
| `test_network_exposure_shows_peer` | Exposure with `source_agent_id` set → "Someone in your network told you" |
| `test_no_memory_section_on_first_reasoning` | Empty `memory_trace` → no "Your Previous Thinking" section |
| `test_memory_trace_included` | 2 memory entries → "Your Previous Thinking" section with conviction labels via `float_to_conviction()` |
| `test_peer_opinions_included` | 2 `PeerOpinion` entries → "What People Around You Are Saying" section with `public_statement` |
| `test_peer_opinions_use_sentiment_tone_not_position` | Peer with position="reject" → position does NOT appear in prompt; sentiment tone does |
| `test_anti_hedging_instructions` | Prompt contains "Do NOT hedge" or similar anti-central-tendency language |

### Class: `TestBuildPass1Schema`

Tests `build_pass1_schema()`.

| Test Method | What's Asserted |
|---|---|
| `test_has_required_fields` | Schema has: reasoning, public_statement, reasoning_summary, sentiment, conviction, will_share |
| `test_sentiment_range` | Sentiment field has minimum=-1, maximum=1 |
| `test_conviction_range` | Conviction field has minimum=0, maximum=100, type=integer |
| `test_will_share_is_boolean` | will_share has type=boolean |

### Class: `TestBuildPass2Prompt`

Tests `build_pass2_prompt(reasoning_text, scenario)`.

| Test Method | What's Asserted |
|---|---|
| `test_reasoning_text_included` | Input reasoning text appears in output |
| `test_classification_instruction` | Contains "classify" or similar |
| `test_outcomes_described` | Outcome descriptions from scenario appear |

### Class: `TestBuildPass2Schema`

Tests `build_pass2_schema(outcomes)`.

| Test Method | Setup | What's Asserted |
|---|---|---|
| `test_categorical_outcome` | OutcomeDefinition type=CATEGORICAL, options=["a","b","c"] | Schema has enum field |
| `test_boolean_outcome` | OutcomeDefinition type=BOOLEAN | Schema has boolean field |
| `test_float_outcome` | OutcomeDefinition type=FLOAT, range=[0,10] | Schema has number field with min/max |
| `test_open_ended_outcome` | OutcomeDefinition type=OPEN_ENDED | Schema has string field |
| `test_multiple_outcomes` | 3 different outcomes | All appear in schema |
| `test_no_outcomes_returns_none` | Empty OutcomeConfig | Returns `None` |

### Class: `TestHelpers`

| Test Method | Function | Input | Expected |
|---|---|---|---|
| `test_sentiment_very_negative` | `_sentiment_to_tone` | `-0.9` | `"strongly opposed"` or similar |
| `test_sentiment_negative` | `_sentiment_to_tone` | `-0.3` | `"skeptical"` or similar |
| `test_sentiment_neutral` | `_sentiment_to_tone` | `0.0` | `"neutral"` |
| `test_sentiment_positive` | `_sentiment_to_tone` | `0.5` | `"positive"` |
| `test_sentiment_very_positive` | `_sentiment_to_tone` | `0.9` | `"enthusiastic"` |
| `test_primary_position_outcome` | `_get_primary_position_outcome` | Scenario with required categorical | Returns outcome name |
| `test_primary_position_no_categorical` | `_get_primary_position_outcome` | Scenario with only boolean outcomes | Returns `None` |

---

## File 6: `tests/test_integration_timestep.py`

Integration tests for the full timestep loop with mocked LLM calls. Tests the engine's `_execute_timestep()` and `run()` methods.

### Imports

```python
import random
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from entropy.core.models import (
    AgentState, ConvictionLevel, CONVICTION_MAP,
    ExposureRecord, ReasoningResponse, SimulationRunConfig,
    TimestepSummary,
)
from entropy.core.models.scenario import (
    # ... all scenario model imports from test_engine.py
)
from entropy.simulation.engine import SimulationEngine
```

### Fixtures

- `ten_agents`: 10 agents with _id "a0"-"a9", varied attributes
- `chain_network`: a0→a1→a2→...→a9
- `scenario_with_targeted_seed`: Seed rule exposes only a0 at timestep 0 (when=`"_id == 'a0'"` or similar condition that matches only one agent)
- `engine_factory(scenario, agents, network, tmp_path)`: Helper that creates a `SimulationEngine` with given params, returns engine

### Class: `TestSingleTimestepE2E`

Tests `_execute_timestep()` with mocked `batch_reason_agents`.

| Test Method | Setup | What's Asserted |
|---|---|---|
| `test_seed_then_reason_then_update` | Scenario seeds a0 at t=0. Mock `batch_reason_agents` returns canned response for a0. | After timestep 0: a0 is aware, has position, has memory entry. a1 not yet aware. |
| `test_propagation_after_reasoning` | After t=0 (a0 reasoned, will_share=True), run t=1. | a1 gets network exposure from a0 (one hop in chain). a2 still unaware. |
| `test_timeline_events_logged` | Run t=0. | Timeline has SEED_EXPOSURE event for a0, AGENT_REASONED event for a0. |
| `test_timestep_summary_computed` | Run t=0 with 1 seed exposure. | Summary has new_exposures=1, agents_reasoned=1, exposure_rate=0.1 (1/10). |
| `test_transaction_wraps_timestep` | Mock an exception in reasoning. | State is rolled back — no partial updates visible. |

**Mocking strategy:** Patch `entropy.simulation.engine.batch_reason_agents` (the import in engine.py). The mock returns a list of `(agent_id, ReasoningResponse)` tuples. Use `_make_reasoning_response()` helper.

### Class: `TestMultiTimestepDynamics`

Tests `engine.run()` over multiple timesteps with mocked LLM.

| Test Method | Setup | What's Asserted |
|---|---|---|
| `test_information_cascade_through_chain` | Chain network, seed a0 at t=0, share_prob=1.0. Mock returns will_share=True, moderate conviction. | Over timesteps, exposure propagates a0→a1→a2→...→a9. After 10 timesteps, all agents aware. |
| `test_exposure_rate_monotonically_increases` | Same as above. | Each timestep summary has exposure_rate >= previous. |
| `test_re_reasoning_with_memory` | a0 reasoned at t=0, gets 3 new network exposures by t=3. Mock returns different sentiment on re-reason. | a0 re-reasons at t=3 (multi-touch threshold=3). Memory trace fed back. New state differs from t=0 state. |
| `test_stopping_condition_triggers` | Config with stop_condition `"exposure_rate > 0.5"`. | Simulation stops before max_timesteps. `SimulationSummary.stopped_reason` is set. |
| `test_isolated_agent_never_exposed` | Chain a0-a8, a9 isolated (no edges). Seed only a0. | After all timesteps, a9 still unaware. |

**Mocking detail for cascade test:** The mock for `batch_reason_agents` needs to be dynamic — it receives a list of contexts and must return a response for each. Use `side_effect` that inspects the input contexts and returns appropriate `_make_reasoning_response()` for each agent:

```python
def mock_batch_reason(contexts, scenario, config, max_concurrency=50, rate_limiter=None):
    return [
        (ctx.agent_id, _make_reasoning_response(will_share=True))
        for ctx in contexts
    ]
```

### Class: `TestIsolatedAgent`

Tests single-agent behavior with no network effects.

| Test Method | Setup | What's Asserted |
|---|---|---|
| `test_single_agent_reasons_once` | 1 agent, empty network, seed at t=0. | Agent reasons exactly once (mock called once). No propagation. |
| `test_no_peer_opinions_in_context` | 1 agent, no neighbors. | `ReasoningContext.peer_opinions` is empty list. |

---

## Additions to `tests/conftest.py`

New shared fixtures needed across multiple new test files:

```python
@pytest.fixture
def ten_agents():
    """Ten agents with varied attributes for propagation/integration tests."""
    agents = []
    roles = ["junior", "mid", "senior"]
    for i in range(10):
        agents.append({
            "_id": f"a{i}",
            "age": 25 + i * 5,
            "role": roles[i % 3],
        })
    return agents


@pytest.fixture
def linear_network(ten_agents):
    """Chain network: a0-a1-a2-...-a9."""
    edges = [
        {"source": f"a{i}", "target": f"a{i+1}", "type": "colleague"}
        for i in range(9)
    ]
    return {
        "meta": {"node_count": 10},
        "nodes": [{"id": f"a{i}"} for i in range(10)],
        "edges": edges,
    }


@pytest.fixture
def star_network(ten_agents):
    """Star network: a0 is hub, a1-a9 are spokes."""
    edges = [
        {"source": "a0", "target": f"a{i}", "type": "colleague"}
        for i in range(1, 10)
    ]
    return {
        "meta": {"node_count": 10},
        "nodes": [{"id": f"a{i}"} for i in range(10)],
        "edges": edges,
    }
```

---

## Execution Order

Implement in this order due to dependency:

1. **`conftest.py` additions** — shared fixtures needed by everything else
2. **`test_conviction.py`** — standalone, no dependencies on other new code
3. **`test_stopping.py`** — standalone, tests pure functions with simple inputs
4. **`test_propagation.py`** — depends on conftest network fixtures
5. **`test_memory_traces.py`** — depends on conftest agent fixtures
6. **`test_reasoning_prompts.py`** — depends on conftest fixtures, tests string output
7. **`test_integration_timestep.py`** — depends on all of the above being green, uses mocked LLM

---

## What's NOT in scope

- No live LLM calls (that's Part 4+)
- No changes to production code (unless a test reveals a bug, which should be noted but not fixed in this PR)
- No new production modules (metrics.py, scenario library — that's Part 7 infrastructure)
- No async tests for `_reason_agent_two_pass_async` — the async mock setup is complex and the sync `reason_agent()` path covers the same logic; async can be added later
- No performance/scale tests (100+ agents) — keep tests fast for CI

## Test Count Summary

| File | Classes | Tests | Lines (est.) |
|---|---|---|---|
| `test_conviction.py` | 4 | ~18 | ~150 |
| `test_propagation.py` | 5 | ~22 | ~400 |
| `test_stopping.py` | 4 | ~16 | ~250 |
| `test_memory_traces.py` | 3 | ~16 | ~250 |
| `test_reasoning_prompts.py` | 5 | ~22 | ~350 |
| `test_integration_timestep.py` | 3 | ~12 | ~350 |
| conftest additions | — | — | ~30 |
| **Total** | **24** | **~106** | **~1780** |
