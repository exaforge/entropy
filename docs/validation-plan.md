# Simulation Phase Validation Plan

Proving that entropy's simulation produces reliable, valid, and differentiated results.

This plan draws on:
- Roadmap items 4.1-4.4 (backtesting, central tendency, cost calibration, experiments)
- Arxiv papers: opinion consensus in LLM networks, social digital twins, GTA, Sentipolis, AMBER
- Competitor validation benchmarks: Aaru's EY replication (0.90 Spearman), Societies.io's LinkedIn R²=0.78
- Current test coverage gaps identified in the codebase

---

## Part 1: Deterministic Unit-Level Validation

Goal: prove each simulation sub-system works correctly in isolation, with zero LLM calls.

### 1.1 Conviction Bucketing

Test `score_to_conviction_float()` and `float_to_conviction()` roundtrips across all bucket boundaries.

- [ ] Boundary values: 0, 15, 16, 35, 36, 60, 61, 85, 86, 100
- [ ] Out-of-range inputs: -1, 101, 0.5
- [ ] Verify `CONVICTION_MAP[ConvictionLevel.*]` matches the bucketing logic

**Why first:** flip resistance and sharing gating both depend on correct bucketing. If this is wrong, everything downstream is wrong.

### 1.2 Network Propagation

Test `propagate_through_network()` with controlled adjacency lists and deterministic RNG.

- [ ] Linear chain (A→B→C): verify single-hop propagation per timestep
- [ ] Star graph (hub + spokes): verify hub exposure reaches all neighbors
- [ ] Conviction-gated sharing: agent with conviction ≤ 0.1 (very_uncertain) should never propagate
- [ ] Share probability modifiers: verify `calculate_share_probability()` applies multiply/add correctly
- [ ] Credibility assignment: verify peer credibility = 0.85
- [ ] Already-aware agents don't get re-exposed through same channel

### 1.3 Stopping Conditions

Test `evaluate_stopping_conditions()` with synthetic `TimestepSummary` sequences.

- [ ] Max timesteps: stops at boundary
- [ ] Exposure rate threshold: `"exposure_rate > 0.95"` triggers correctly
- [ ] No-state-changes: `"no_state_changes_for > 10"` with exactly 10 vs 11 stable timesteps
- [ ] Convergence detection: stable position distribution (< 5% variance over 5 timesteps)
- [ ] Compound conditions with `and`
- [ ] Sentiment variance stopping

### 1.4 State Manager Integrity

Test `StateManager` under adversarial conditions.

- [ ] Memory trace sliding window: insert 5 entries, verify only latest 3 retained
- [ ] `get_agents_to_reason()` multi-touch threshold: agent with 2 new exposures (threshold=3) should NOT reason; agent with 3 should
- [ ] Batch update atomicity: partial failure in `batch_update_states()` rolls back entirely
- [ ] Concurrent read/write safety under asyncio

### 1.5 Flip Resistance Logic

Test `_apply_state_updates()` flip resistance matrix exhaustively.

- [ ] Firm agent (0.7) + weak new conviction (0.3) + position change → REJECT flip
- [ ] Firm agent (0.7) + moderate new conviction (0.5) + position change → ACCEPT flip
- [ ] Absolute agent (0.9) + moderate new conviction (0.5) + position change → ACCEPT flip
- [ ] Leaning agent (0.3) + any new conviction + position change → ACCEPT flip (no resistance)
- [ ] Same position, different conviction → no flip resistance check needed

---

## Part 2: Reasoning Pipeline Validation

Goal: verify the two-pass architecture produces correct outputs, isolated from LLM behavior.

### 2.1 Prompt Construction

Test `build_pass1_prompt()` and `build_pass2_prompt()` produce well-formed prompts.

- [ ] First-time reasoning: no memory trace section, no peer opinions section
- [ ] Re-reasoning with memory: memory trace includes conviction label ("you felt *moderate* about this")
- [ ] Peer influence formatting: public_statement + sentiment tone, NOT position label
- [ ] Exposure history: correctly distinguishes network ("someone in your network") vs seed channel
- [ ] Persona inclusion: full persona text appears in prompt

### 2.2 Schema Construction

Test `build_pass1_schema()` and `build_pass2_schema()`.

- [ ] Pass 1 schema has: reasoning, public_statement, reasoning_summary, sentiment [-1,1], conviction [0,100], will_share
- [ ] Pass 2 schema correctly maps categorical outcomes to enums
- [ ] Pass 2 schema correctly maps boolean, float, open_ended outcomes
- [ ] Pass 2 with no outcomes → empty schema → no Pass 2 call

### 2.3 Two-Pass Integration (Mocked LLM)

Test `_reason_agent_two_pass_async()` with mocked `simple_call_async()`.

- [ ] Pass 1 produces ReasoningResponse with correct conviction bucketing
- [ ] Pass 2 classifies into categorical outcomes correctly
- [ ] Pass 2 failure is non-fatal (returns Pass 1 data with no outcomes)
- [ ] Rate limiter acquisition: pivotal bucket for Pass 1, routine bucket for Pass 2
- [ ] Retry logic: transient failure on attempt 1, success on attempt 2

### 2.4 Batch Reasoning

Test `batch_reason_agents()` concurrency behavior.

- [ ] Stagger interval calculation: 500 RPM → 120ms between launches
- [ ] Semaphore limiting: max_safe_concurrent respected
- [ ] All agents get results (no dropped tasks)
- [ ] Rate limiter stats populated after batch

---

## Part 3: Integration Tests (Full Timestep Loop)

Goal: verify the three-phase timestep loop works end-to-end with mocked LLM.

### 3.1 Single Timestep E2E

Run `_execute_timestep()` with a 10-agent population, simple network, and mocked LLM.

- [ ] Phase 1: seed exposure creates awareness for targeted agents
- [ ] Phase 2: newly aware agents get reasoned (mocked two-pass)
- [ ] Phase 3: state updates applied, memory entries saved, timeline events logged
- [ ] Transaction commits on success; all state visible after timestep

### 3.2 Multi-Timestep Dynamics

Run full `engine.run()` for 5-10 timesteps with mocked LLM returning deterministic responses.

- [ ] Information cascade: exposure spreads from seed agents through network over timesteps
- [ ] Re-reasoning: agents exposed to 3+ new peers re-reason with memory trace
- [ ] Stopping condition: simulation stops when configured condition is met (not just max timesteps)
- [ ] Aggregation: `TimestepSummary` values are monotonically reasonable (exposure_rate never decreases)

### 3.3 Isolated Agent Test

Single agent, no network, single seed exposure.

- [ ] Agent reasons exactly once
- [ ] No propagation occurs (no neighbors)
- [ ] Final state reflects single reasoning output
- [ ] Useful as baseline for understanding LLM contribution vs. network contribution

---

## Part 4: LLM Behavior Validation (Live Calls, Small Scale)

Goal: test whether the LLM reasoning layer produces meaningful, non-degenerate outputs. This is where the arxiv papers are most relevant.

### 4.1 Anti-Central-Tendency Check

**From roadmap 4.2.** Run a polarizing scenario with ~50 agents, real LLM calls.

Validation criteria (from the central tendency fix):
- [ ] Most popular position < 60% (no single option dominates)
- [ ] Least popular position > 0% (all options represented)
- [ ] Conviction std > 20 (across raw 0-100 scores)
- [ ] "cautious" appears in < 40% of reasoning text
- [ ] Sentiment std > 0.35

**Scenarios to use:**
1. **Obvious acceptance:** "Free premium upgrade for loyal customers" → expect near-universal positive response
2. **Polarizing:** "Mandatory return-to-office policy for remote workers" → expect genuine split
3. **Niche impact:** "Hospital switching to new surgical robot system" (German surgeon population) → expect domain-specific reasoning

### 4.2 LLM Prior Dominance Test

**Inspired by [Kayaalp et al., 2026](https://arxiv.org/abs/2601.21540).** Their finding: LLM agents converge to topic-biased attractors regardless of network structure. Entropy needs to verify its agents are actually influenced by persona + network, not just LLM priors.

Test protocol:
- [ ] **Same scenario, different populations**: Run identical event with (a) young tech workers and (b) retired traditionalists. Outcome distributions should differ significantly. If they don't, LLM priors are dominating persona context.
- [ ] **Same population, different networks**: Run identical population+scenario with (a) dense network (avg_degree=10) and (b) sparse network (avg_degree=2). If results are identical, network structure isn't contributing.
- [ ] **Peer influence ablation**: Run with peers' public_statements included vs. excluded from reasoning prompts. Measure delta in outcome distributions.

Metric: Jensen-Shannon divergence between outcome distributions across conditions. JSD > 0.05 indicates meaningful differentiation.

### 4.3 Persona Sensitivity Test

**Inspired by [GTA, CHI 2026](https://arxiv.org/abs/2401.xxx) finding that demographic grounding reproduces socioeconomic patterns.**

- [ ] Generate 100 agents, render personas, compare reasoning outputs by demographic segment
- [ ] Verify: high-income agents respond differently to pricing changes than low-income agents
- [ ] Verify: personality traits (Big Five) produce observable reasoning differences
- [ ] Metric: segment-level outcome distributions should have statistically significant differences (chi-squared, p < 0.05)

### 4.4 Temporal Dynamics Validation

**Entropy's key differentiator vs. competitors.** Neither Aaru nor Societies.io does multi-timestep belief evolution.

- [ ] Run 50-timestep simulation, plot conviction trajectory per agent
- [ ] Verify: agents don't all converge to same conviction at same rate (which would indicate cargo-culting)
- [ ] Verify: network-exposed agents shift earlier than broadcast-only agents (information flow matters)
- [ ] Verify: re-reasoning agents show conviction drift (not just repeating first opinion)
- [ ] Metric: Granger causality test between exposure events and conviction shifts

---

## Part 5: Calibration & Ground Truth (The Hard Part)

Goal: compare simulation outputs to real-world outcomes. This is what makes or breaks entropy's credibility.

### 5.1 Toy Scenarios with Known Answers

**From roadmap 4.1.** Design scenarios where the expected outcome is obvious, then verify entropy agrees.

| Scenario | Expected Result | Pass Criteria |
|----------|----------------|---------------|
| Free upgrade for loyal customers | >80% acceptance | Top position = accept, >80% |
| 50% price increase, no new features | >60% negative | Sentiment mean < -0.2 |
| Mandatory unpaid overtime | >70% opposition | Opposition > 70%, sentiment < -0.3 |
| Paid sabbatical program announced | >70% positive | Sentiment mean > 0.3 |

These aren't rigorous backtests — they're sanity checks. If entropy can't get directional calls right on obvious scenarios, nothing else matters.

### 5.2 Historical Scenario Replication

**From roadmap 4.1.** Pick 2-3 past events with known quantitative outcomes.

Candidates:
1. **COVID-19 mask mandate compliance** (well-studied, [Koaik et al.](https://arxiv.org/abs/2601.06111) used this domain) — simulate US population response to mask mandates, compare to actual compliance survey data
2. **iPhone pricing change reaction** — Apple's 2023 price increase, compare to actual sales/sentiment data
3. **Remote work policy shifts** — return-to-office mandates at major tech companies, compare to reported compliance/attrition

For each:
- [ ] Build population spec matching the real-world demographic
- [ ] Build scenario spec matching the actual event
- [ ] Run simulation (3x with different seeds for variance estimation)
- [ ] Compare: outcome distribution vs. real-world survey/behavioral data
- [ ] Metric: Spearman rank correlation on outcome ordering (target: ρ > 0.7, Aaru benchmark: 0.90)

### 5.3 Convergence Testing (Run Stability)

**From roadmap 4.1.** Same configuration, different random seeds → results should be similar.

- [ ] Run same scenario 5x with seeds 1-5
- [ ] Measure inter-run variance on: outcome distribution, average sentiment, average conviction
- [ ] Pass criteria: coefficient of variation < 0.15 for all metrics
- [ ] If variance is too high: investigate whether it's sampling variance (population generation) or reasoning variance (LLM non-determinism)

### 5.4 Sensitivity Analysis

**From roadmap 4.1.** Vary one parameter, check results move in expected direction.

- [ ] **Price sensitivity**: same population, scenario with $10 vs $50 vs $100 price point → adoption should decrease monotonically
- [ ] **Network density**: same population+scenario, avg_degree 2 vs 5 vs 10 → information spread rate should increase with density
- [ ] **Population size**: 100 vs 500 vs 1000 agents → results should converge (lower inter-run variance at larger N)
- [ ] **Timestep count**: 50 vs 100 vs 200 → outcomes should stabilize (diminishing marginal change)

### 5.5 Calibration Layer (Future)

**Inspired by [Koaik et al.](https://arxiv.org/abs/2601.06111)'s calibration approach.** Their per-dimension linear mapping improved RMSE from 78.32 to 25.75.

This is NOT in scope for the initial validation plan, but documented as a future direction:
- Learn a simple linear mapping: `y_real = α * y_sim + β` per outcome dimension
- Train on historical scenarios where ground truth exists
- Evaluate on held-out scenarios with strict temporal separation
- Entropy's advantage: the grounding pipeline should produce agents that need less calibration than ungrounded approaches

---

## Part 6: Comparative & Ablation Studies

Goal: understand what each component of entropy contributes to output quality.

### 6.1 Two-Pass vs. Single-Pass Reasoning

- [ ] Run same scenario with two-pass (current) vs. single-pass (Pass 1 only, extract position from free text)
- [ ] Measure: central tendency metrics from 4.1
- [ ] Expected: two-pass produces wider outcome distributions, higher conviction variance

### 6.2 Network Effect Contribution

- [ ] Run same population+scenario with real network vs. flat network (no edges)
- [ ] Measure: outcome distribution delta, convergence speed, sentiment clustering
- [ ] Expected: networked simulation shows opinion clustering by community; flat shows uniform distribution
- [ ] This directly addresses whether entropy's temporal network simulation adds value over Aaru/Societies' single-pass approach

### 6.3 Persona Richness Ablation

- [ ] Full persona (PersonaConfig with z-scores, trait salience) vs. minimal persona (name + 3 demographics)
- [ ] Measure: reasoning quality (human eval), outcome variance, segment differentiation
- [ ] Expected: richer personas produce more differentiated, domain-specific reasoning

### 6.4 Provider Comparison

**From roadmap 4.4.**

- [ ] Same scenario: OpenAI (gpt-5-mini) vs. Claude (haiku) for agent reasoning
- [ ] Measure: outcome distributions, reasoning length, cost, central tendency metrics
- [ ] This informs default provider recommendations

---

## Part 7: Infrastructure Required

What needs to be built to execute this plan.

### 7.1 Test Harness for Live Simulations

A lightweight wrapper that:
- Runs a simulation with specified config
- Captures all outputs (results dir, SQLite state, JSONL timeline)
- Computes validation metrics automatically
- Supports multiple runs with different seeds
- Outputs a structured report (JSON) for comparison

### 7.2 Metric Functions

New module: `entropy/validation/metrics.py` (or `tests/validation/`)

```python
def central_tendency_check(results_dir) -> dict:
    """Check anti-central-tendency criteria."""

def outcome_divergence(results_a, results_b) -> float:
    """Jensen-Shannon divergence between two runs' outcome distributions."""

def run_stability(results_dirs: list) -> dict:
    """Coefficient of variation across multiple runs."""

def segment_differentiation(results_dir, segment_attr) -> dict:
    """Chi-squared test for outcome differences across segments."""

def temporal_dynamics(results_dir) -> dict:
    """Conviction trajectory analysis, Granger causality."""
```

### 7.3 Scenario Library

Pre-built scenarios for validation testing:

```
tests/scenarios/
├── toy_obvious_accept.yaml      # Free upgrade (sanity check)
├── toy_obvious_reject.yaml      # Unpaid overtime (sanity check)
├── polarizing_rto.yaml          # Return to office (splits expected)
├── pricing_sensitivity/
│   ├── price_10.yaml
│   ├── price_50.yaml
│   └── price_100.yaml
└── historical/
    ├── covid_mask_mandate.yaml
    └── ...
```

### 7.4 Results Comparison Tool

**From roadmap I.4.** `entropy diff results_a/ results_b/` — needed for ablation studies.

---

## Execution Order

Sequenced by dependency and impact:

| Phase | Effort | LLM Calls | Priority |
|-------|--------|-----------|----------|
| **1. Deterministic unit tests** (Part 1) | Low | Zero | Immediate — fills test gaps |
| **2. Reasoning pipeline tests** (Part 2) | Low | Zero (mocked) | Immediate — validates core logic |
| **3. Integration tests** (Part 3) | Medium | Zero (mocked) | Next — validates timestep loop |
| **4. Anti-central-tendency** (Part 4.1) | Medium | ~5K calls | High — proves the fix works |
| **5. LLM prior dominance** (Part 4.2) | Medium | ~10K calls | High — addresses arxiv concern |
| **6. Toy scenarios** (Part 5.1) | Low | ~2K calls | High — basic sanity |
| **7. Convergence testing** (Part 5.3) | Medium | ~10K calls | High — proves reliability |
| **8. Sensitivity analysis** (Part 5.4) | Medium | ~15K calls | Medium — proves coherence |
| **9. Historical replication** (Part 5.2) | High | ~20K calls | Medium — proves accuracy |
| **10. Ablation studies** (Part 6) | High | ~30K calls | Lower — proves design |
| **11. Calibration layer** (Part 5.5) | High | ~50K calls | Future — production accuracy |

Parts 1-3 are pure code, no API costs. Parts 4-6 require live LLM calls. The toy scenarios (Part 5.1) are the cheapest real test and should run immediately after the unit tests pass.

---

## Success Criteria

For entropy's simulation to be considered validated:

1. **All deterministic tests pass** (Parts 1-3) — no bugs in the machinery
2. **Central tendency fix confirmed** (Part 4.1) — all 5 criteria met
3. **Persona sensitivity demonstrated** (Part 4.2-4.3) — JSD > 0.05 across populations, p < 0.05 across segments
4. **Toy scenarios correct** (Part 5.1) — directional accuracy on all 4 obvious scenarios
5. **Run stability confirmed** (Part 5.3) — CV < 0.15 across 5 seeds
6. **Sensitivity monotonic** (Part 5.4) — price/density/size all move in expected direction
7. **Historical replication credible** (Part 5.2) — Spearman ρ > 0.7 on at least 1 scenario

If criteria 1-6 pass, entropy's simulation is mechanically sound and behaviorally reasonable. Criterion 7 is the stretch goal that proves predictive accuracy.
