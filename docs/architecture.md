# Architecture

Entropy has three phases, each mapping to a package under `entropy/`.

---

## Phase 1: Population Creation (`entropy/population/`)

The validity pipeline. This is where predictive accuracy is won or lost.

### 1. Sufficiency Check (`spec_builder/sufficiency.py`)

LLM validates the description has enough context (who, how many, where).

### 2. Attribute Selection (`spec_builder/selector.py`)

LLM discovers 25-40 attributes across 4 categories:
- `universal` — age, gender, income
- `population_specific` — specialty, seniority, commute method
- `context_specific` — scenario-relevant attitudes and behaviors
- `personality` — Big Five traits

Each attribute gets a type (`int`/`float`/`categorical`/`boolean`) and sampling strategy (`independent`/`derived`/`conditional`).

### 3. Hydration (`spec_builder/hydrator.py` -> `hydrators/`)

The most important step. Four sub-steps, each using different LLM tiers:

- **Independent** (`hydrators/independent.py`) — `agentic_research()` with web search finds real-world distributions with source URLs. This is the grounding layer.
- **Derived** (`hydrators/derived.py`) — `reasoning_call()` specifies deterministic formulas (e.g., `years_experience = age - 26`).
- **Conditional base** (`hydrators/conditional.py`) — `agentic_research()` finds base distributions for attributes that depend on others.
- **Conditional modifiers** (`hydrators/conditional.py`) — `reasoning_call()` specifies how attribute values shift based on other attributes. Type-specific: numeric gets `multiply`/`add`, categorical gets `weight_overrides`, boolean gets `probability_override`.

### 4. Constraint Binding (`spec_builder/binder.py`)

Topological sort (Kahn's algorithm, `utils/graphs.py`) resolves attribute dependencies into a valid sampling order. Raises `CircularDependencyError` with cycle path.

### 5. Sampling (`sampler/core.py`)

Iterates through `sampling_order`, routing each attribute by strategy. Supports 6 distribution types: normal, lognormal, uniform, beta, categorical, boolean. Hard constraints (min/max) are clamped post-sampling. Formula parameters evaluated via `utils/eval_safe.py` (restricted Python eval, whitelisted builtins only).

### 6. Network Generation (`network/`)

Hybrid algorithm: similarity-based edge probability with degree correction, calibrated via binary search to hit target avg_degree, then Watts-Strogatz rewiring (5%) for small-world properties.

Edge probability: `base_rate * sigmoid(similarity) * degree_factor_a * degree_factor_b`.

All network behavior is data-driven via `NetworkConfig`: attribute weights for similarity, edge type rules (priority-ordered condition expressions evaluated by `_eval_edge_condition()`), influence factors (ordinal/boolean/numeric), and degree multipliers. Config can be LLM-generated from a `PopulationSpec` (`config_generator.py`), loaded from YAML (`--network-config`), or auto-detected as `{population_stem}.network-config.yaml`. Empty config (no `-p` or `-c`) produces a flat network.

---

## Phase 2: Scenario Compilation (`entropy/scenario/`)

**Compiler** (`compiler.py`) orchestrates 5 steps: parse event -> generate exposure rules -> determine interaction model -> define outcomes -> assemble spec.

- **Event types**: product_launch, policy_change, pricing_change, technology_release, organizational_change, market_event, crisis_event
- **Exposure channels**: broadcast, targeted, organic — with per-timestep rules containing conditions and probabilities
- **Outcomes**: categorical (enum options), boolean, float (with range), open_ended
- Auto-configures simulation parameters based on population size (<500: 50 timesteps, <=5000: 100, >5000: 168)

---

## Phase 3: Simulation (`entropy/simulation/`)

### Engine (`engine.py`)

Per-timestep loop, decomposed into sub-functions:

1. **`_apply_exposures(timestep)`** — Apply seed exposures from scenario rules (`propagation.py`), then propagate through network via conviction-gated sharing (very_uncertain agents don't share). Uses pre-built adjacency list for O(1) neighbor lookups.

2. **`_reason_agents(timestep)`** — Select agents to reason (first exposure OR multi-touch threshold exceeded, default: 3 new exposures since last reasoning), build reasoning contexts, run two-pass async LLM reasoning (`reasoning.py`, rate-limiter-controlled):
   - **Pass 1** (pivotal model): Agent role-plays in first person with no categorical enums. Produces reasoning, public_statement, sentiment, conviction (0-100 integer, bucketed post-hoc), will_share. Memory trace (last 3 reasoning summaries) is fed back for re-reasoning agents.
   - **Pass 2** (routine model): A cheap model classifies the free-text reasoning into scenario-defined categorical/boolean/float outcomes. Position is extracted here — it is output-only, never used in peer influence.

3. **`_apply_state_updates(timestep, results, old_states)`** — Process reasoning results: conviction-based flip resistance (firm+ agents reject flips unless new conviction is moderate+), conviction-gated sharing, state persistence. State updates are batched via `batch_update_states()`.

4. Compute timestep summary, check stopping conditions (`stopping.py`) — Compound conditions like `"exposure_rate > 0.95 and no_state_changes_for > 10"`, convergence detection via sentiment variance.

### Two-Pass Reasoning

Single-pass reasoning caused 83% of agents to pick safe middle options (central tendency bias). Splitting role-play from classification fixes this — agents reason naturally in Pass 1, then a cheap model maps to categories in Pass 2.

### Conviction System

Agents output a 0-100 integer score on a free scale (with descriptive anchors: 0=no idea, 25=leaning, 50=clear opinion, 75=quite sure, 100=certain). `score_to_conviction_float()` buckets it immediately:

| Score Range | Float | Level | Meaning |
|-------------|-------|-------|---------|
| 0-15 | 0.1 | `very_uncertain` | Barely formed opinion |
| 16-35 | 0.3 | `leaning` | Tentative position |
| 36-60 | 0.5 | `moderate` | Reasonably confident |
| 61-85 | 0.7 | `firm` | Strong position |
| 86-100 | 0.9 | `absolute` | Unwavering |

Agents never see categorical labels or float values — only the 0-100 scale. On re-reasoning, memory traces show the bucketed label (e.g. "you felt *moderate* about this") via `float_to_conviction()`. Engine conviction thresholds reference `CONVICTION_MAP[ConvictionLevel.*]` constants, not hardcoded floats.

### Semantic Peer Influence

Agents see their neighbors' `public_statement` + sentiment tone, NOT position labels. This means influence is semantic — an agent can be swayed by a compelling argument, not just a categorical stance.

### Memory

Each agent maintains a 3-entry sliding window memory trace. Entries include the timestep, a summary of what they processed, and how it affected their thinking. This gives agents continuity across reasoning rounds without unbounded context growth.

### Persona System

`population/persona/` + `simulation/persona.py`: The `entropy persona` command generates a `PersonaConfig` via 5-step LLM pipeline (structure -> boolean -> categorical -> relative -> concrete phrasings). At simulation time, agents are rendered computationally using this config — no per-agent LLM calls.

Relative attributes (personality, attitudes) are positioned against population stats via z-scores ("I'm much more price-sensitive than most people"). Concrete attributes use format specs for proper number/time rendering.

**Trait salience**: When the scenario defines `decision_relevant_attributes`, those traits are grouped first in the persona under "Most Relevant to This Decision", ensuring the LLM focuses on what matters.

### Transaction Batching (`state.py`)

All writes within a timestep are wrapped in a single SQLite transaction via `state_manager.transaction()` context manager. Commits on success, rolls back on exception. Individual state methods (`record_exposure`, `update_agent_state`, `save_memory_entry`, `log_event`, `save_timestep_summary`) rely on the transaction boundary rather than committing individually.

### Rate Limiting (`core/rate_limiter.py`)

Token bucket rate limiter with dual RPM + TPM buckets. Provider-aware defaults auto-configured from `core/rate_limits.py` (Anthropic/OpenAI, tiers 1-4). Supports tier overrides via config or CLI flags.

### Cost Estimation (`simulation/estimator.py`)

`entropy estimate` runs a simplified SIR-like propagation model to predict LLM calls per timestep without making any API calls. Token counts estimated from persona size + scenario content. Pricing from `core/pricing.py` model database. Supports `--verbose` for per-timestep breakdown.

---

## LLM Integration (`entropy/core/llm.py`)

All LLM calls go through this file — never call providers directly elsewhere. Two-zone routing:

### Pipeline Zone (phases 1-2)

Configured via `entropy config set pipeline.*`:

| Function | Default Model | Tools | Use |
|----------|--------------|-------|-----|
| `simple_call()` | haiku / gpt-5-mini | none | Sufficiency checks, simple extractions |
| `reasoning_call()` | sonnet / gpt-5 | none | Attribute selection, hydration, scenario compilation |
| `agentic_research()` | sonnet / gpt-5 | web_search | Distribution hydration with real-world data |

### Simulation Zone (phase 3)

Configured via `entropy config set simulation.*`:

| Function | Default Model | Use |
|----------|--------------|-----|
| Pass 1 reasoning | pivotal model (gpt-5 / sonnet) | Agent role-play, freeform reaction |
| Pass 2 classification | routine model (gpt-5-mini / haiku) | Outcome extraction from narrative |

Two-pass model routing: Pass 1 uses `simulation.model` or `simulation.pivotal_model`. Pass 2 uses `simulation.routine_model`. CLI: `--model`, `--pivotal-model`, `--routine-model`.

### Provider Abstraction (`entropy/core/providers/`)

`LLMProvider` base class with `OpenAIProvider` and `ClaudeProvider` implementations. Factory functions `get_pipeline_provider()` and `get_simulation_provider()` read from `EntropyConfig`.

Base class provides `_retry_with_validation()` — shared validation-retry loop used by both providers' `reasoning_call()` and `agentic_research()`. Both providers implement `_with_retry()` / `_with_retry_async()` for transient API errors with exponential backoff (`2^attempt + random(0,1)` seconds, max 3 retries).

All calls use structured output (`response_format: json_schema`). Failed validations are fed back as "PREVIOUS ATTEMPT FAILED" prompts for self-correction.

---

## Data Models (`entropy/core/models/`)

All Pydantic v2. Key hierarchy:

- `population.py`: `PopulationSpec` -> `AttributeSpec` -> `SamplingConfig` -> `Distribution` / `Modifier` / `Constraint`
- `scenario.py`: `ScenarioSpec` -> `Event`, `SeedExposure` (channels + rules), `InteractionConfig`, `SpreadConfig`, `OutcomeConfig`
- `simulation.py`: `AgentState`, `ConvictionLevel`, `CONVICTION_MAP`, `MemoryEntry`, `ReasoningContext` (memory_trace, peer opinions), `ReasoningResponse` (reasoning, public_statement, sentiment, conviction, will_share, outcomes), `SimulationRunConfig`, `TimestepSummary`
- `network.py`: `Edge`, `NodeMetrics`, `NetworkMetrics`, `NetworkConfig`
- `validation.py`: `ValidationIssue`, `ValidationResult`

YAML serialization via `to_yaml()`/`from_yaml()` on `PopulationSpec`, `ScenarioSpec`, and `NetworkConfig`.

---

## Validation (`entropy/population/validator/`)

Two layers for population specs:
- **Structural** (`structural.py`): ERROR-level — type/modifier compatibility, range violations, distribution params, dependency cycles, condition syntax, formula references, duplicates, strategy consistency
- **Semantic** (`semantic.py`): WARNING-level — no-op detection, modifier stacking, categorical option reference validity

Scenario validation (`entropy/scenario/validator.py`): attribute reference validity, edge type references, probability ranges.

---

## Config (`entropy/config.py`)

`EntropyConfig` with `PipelineConfig` and `SimZoneConfig` zones. Resolution order: CLI flags > env vars > config file (`~/.config/entropy/config.json`) > defaults.

API keys always from env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

`SimZoneConfig` fields: `provider`, `model`, `pivotal_model`, `routine_model`, `max_concurrent`, `rate_tier`, `rpm_override`, `tpm_override`.

For package use: `from entropy.config import configure, EntropyConfig`.

---

## File Formats

| Format | Files | Notes |
|--------|-------|-------|
| YAML | Population specs, scenario specs, persona configs, network configs | Human-readable, version-controllable |
| JSON | Agents, networks, simulation results | Array of objects (`_id` field), streaming-friendly |
| SQLite | Simulation state | Indexed tables for agent_states, exposures, timeline |
| JSONL | Timeline | Streaming, crash-safe event log |

---

## Tests

pytest + pytest-asyncio. Fixtures in `tests/conftest.py` include seeded RNG (`Random(42)`), minimal/complex population specs, and sample agents. Twelve test files covering core logic, engine integration, scenario compiler, providers, rate limiter, CLI, and cost estimation.

CI: `.github/workflows/test.yml` — lint (ruff check + format) and test (pytest, matrix: Python 3.11/3.12/3.13) via `astral-sh/setup-uv@v4`.
