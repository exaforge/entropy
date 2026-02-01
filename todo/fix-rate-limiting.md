# Fix Rate Limiting for Simulation Phase

## Problem

The simulation hits 429 errors constantly because:

1. **Single rate limiter for two models.** Pass 1 (pivotal, e.g. `gpt-5`) and Pass 2 (routine, e.g. `gpt-5-mini`) share ONE `RateLimiter` instance, but OpenAI enforces limits *per model*. The limiter is keyed to `effective_model` (the pivotal model) — Pass 2's cheaper model gets no independent pacing.

2. **No concurrency cap when rate limiter is present.** When `rate_limiter` is set, the semaphore is skipped entirely (`reasoning.py:723`). All 500 agents get spawned as concurrent tasks immediately. The rate limiter's `acquire()` gates the API call, but 500 coroutines are all spinning in the `while True` loop competing for tokens — creating thundering herd behavior.

3. **Hardcoded token estimates.** Pass 1 estimates 800 tokens, Pass 2 estimates 200 tokens (`reasoning.py:451,499`). Actual Pass 1 prompts with persona + scenario + peer opinions can be 1500+ tokens. The TPM bucket drains faster than the limiter expects.

4. **`update_from_headers()` is dead code.** The method exists (`rate_limiter.py:172`) but is never called. API response headers with actual remaining limits are ignored.

5. **Anthropic TPM uses only OTPM, ignores ITPM.** `for_provider()` at `rate_limiter.py:233` does `limits.get("tpm", limits.get("otpm", 100_000))` — for Anthropic, this picks OTPM (8K at T1) and ignores ITPM (30K at T1). Input tokens are the dominant cost and should be tracked separately.

6. **Rate limit profiles are stale/wrong.** `rate_limits.py` has all OpenAI models at identical 500 RPM / 500K TPM for T1. In reality, gpt-5-mini has different higher-tier limits than gpt-5 (e.g., T2: 2M vs 1M TPM).

---

## Plan

### Step 1: Update `rate_limits.py` with accurate per-model profiles

Replace the current flat profiles with actual published limits.

**OpenAI models (source: [OpenAI rate limits](https://platform.openai.com/docs/guides/rate-limits), [Sep 2025 update](https://www.scriptbyai.com/rate-limits-openai-api/)):**

| Model | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|-------|--------|--------|--------|--------|
| gpt-5 | 500 RPM / 500K TPM | 5,000 RPM / 1M TPM | 5,000 RPM / 2M TPM | 10,000 RPM / 4M TPM |
| gpt-5-mini | 500 RPM / 500K TPM | 5,000 RPM / 2M TPM | 5,000 RPM / 4M TPM | 10,000 RPM / 10M TPM |
| gpt-5.1 | 500 RPM / 500K TPM | 5,000 RPM / 1M TPM | 5,000 RPM / 2M TPM | 10,000 RPM / 4M TPM |
| gpt-5.2 | 500 RPM / 500K TPM | 5,000 RPM / 1M TPM | 5,000 RPM / 2M TPM | 10,000 RPM / 4M TPM |

**Anthropic models (source: [Anthropic rate limits](https://docs.anthropic.com/en/api/rate-limits)):**

| Model | Tier 1 | Tier 2 | Tier 3 | Tier 4 |
|-------|--------|--------|--------|--------|
| claude-sonnet-4/4.5 | 50 RPM / 30K ITPM / 8K OTPM | 1,000 RPM / 450K / 90K | 2,000 RPM / 800K / 160K | 4,000 RPM / 2M / 400K |
| claude-haiku-4/4.5 | 50 RPM / 50K ITPM / 10K OTPM | 1,000 RPM / 450K / 90K | 2,000 RPM / 1M / 200K | 4,000 RPM / 4M / 800K |

Change the data structure so tier overrides are per-model, not just per-provider. Currently tiers are provider-level — they need to be model-level since gpt-5-mini T2 (2M TPM) differs from gpt-5 T2 (1M TPM).

**New structure:**

```python
RATE_LIMIT_PROFILES = {
    "openai": {
        "default": {
            1: {"rpm": 500, "tpm": 500_000},
            2: {"rpm": 5_000, "tpm": 1_000_000},
            3: {"rpm": 5_000, "tpm": 2_000_000},
            4: {"rpm": 10_000, "tpm": 4_000_000},
        },
        "gpt-5": {
            1: {"rpm": 500, "tpm": 500_000},
            2: {"rpm": 5_000, "tpm": 1_000_000},
            3: {"rpm": 5_000, "tpm": 2_000_000},
            4: {"rpm": 10_000, "tpm": 4_000_000},
        },
        "gpt-5-mini": {
            1: {"rpm": 500, "tpm": 500_000},
            2: {"rpm": 5_000, "tpm": 2_000_000},
            3: {"rpm": 5_000, "tpm": 4_000_000},
            4: {"rpm": 10_000, "tpm": 10_000_000},
        },
        "gpt-5.1": {
            1: {"rpm": 500, "tpm": 500_000},
            2: {"rpm": 5_000, "tpm": 1_000_000},
            3: {"rpm": 5_000, "tpm": 2_000_000},
            4: {"rpm": 10_000, "tpm": 4_000_000},
        },
        "gpt-5.2": {
            1: {"rpm": 500, "tpm": 500_000},
            2: {"rpm": 5_000, "tpm": 1_000_000},
            3: {"rpm": 5_000, "tpm": 2_000_000},
            4: {"rpm": 10_000, "tpm": 4_000_000},
        },
    },
    "anthropic": {
        "default": {
            1: {"rpm": 50, "itpm": 30_000, "otpm": 8_000},
            2: {"rpm": 1_000, "itpm": 450_000, "otpm": 90_000},
            3: {"rpm": 2_000, "itpm": 800_000, "otpm": 160_000},
            4: {"rpm": 4_000, "itpm": 2_000_000, "otpm": 400_000},
        },
        "claude-sonnet-4": { ... },   # same as default
        "claude-sonnet-4.5": { ... },  # same as default
        "claude-haiku-4": {
            1: {"rpm": 50, "itpm": 50_000, "otpm": 10_000},
            2: {"rpm": 1_000, "itpm": 450_000, "otpm": 90_000},
            3: {"rpm": 2_000, "itpm": 1_000_000, "otpm": 200_000},
            4: {"rpm": 4_000, "itpm": 4_000_000, "otpm": 800_000},
        },
        "claude-haiku-4.5": { ... },   # same as haiku-4
    },
    # "claude" alias → same as "anthropic"
}
```

Update `get_limits()` to look up `profile[model][tier]` instead of the current `profile[model]` + separate `profile["tiers"][tier]` pattern.

---

### Step 2: Split into two rate limiters (pivotal + routine)

**In `engine.py` `run_simulation()` (line 737-750):**

Create two `RateLimiter` instances:

```python
# Pivotal model rate limiter (Pass 1)
pivotal_limiter = RateLimiter.for_provider(
    provider=provider,
    model=effective_pivotal or effective_model,
    tier=rate_tier,
    rpm_override=rpm_override,
    tpm_override=tpm_override,
)

# Routine model rate limiter (Pass 2)
routine_model_name = effective_routine or effective_model
routine_limiter = RateLimiter.for_provider(
    provider=provider,
    model=routine_model_name,
    tier=rate_tier,
)
```

If both models resolve to the same model name, use a single shared limiter.

**In `SimulationEngine.__init__`:** Accept `rate_limiter` as a dict `{"pivotal": RateLimiter, "routine": RateLimiter}` or a new wrapper type.

**In `reasoning.py` `_reason_agent_two_pass_async()`:**
- Line 451: `await rate_limiter.pivotal.acquire(estimated_tokens=800)`
- Line 499: `await rate_limiter.routine.acquire(estimated_tokens=200)`

**In `reasoning.py` `batch_reason_agents()`:** Pass both limiters through.

---

### Step 3: Add concurrency cap alongside rate limiter

**In `reasoning.py` `batch_reason_agents()` (line 721-723):**

Currently:
```python
semaphore = asyncio.Semaphore(max_concurrency) if not rate_limiter else None
```

Change to always use a semaphore, sized from the rate limiter's `max_safe_concurrent`:

```python
if rate_limiter:
    max_concurrent = rate_limiter.pivotal.max_safe_concurrent
    semaphore = asyncio.Semaphore(max_concurrent)
else:
    semaphore = asyncio.Semaphore(max_concurrency)
```

This prevents the thundering herd: only N coroutines can be active at once, and within those N, the rate limiter further gates the actual API calls.

Always use `async with semaphore:` before calling `_reason_agent_two_pass_async`. Remove the current branch that skips the semaphore.

---

### Step 4: Expose `--rpm-override` and `--tpm-override` as CLI flags

**In `simulate.py`:** Add two new options:

```python
rpm_override: int | None = typer.Option(
    None, "--rpm-override", help="Override RPM limit (requests per minute)"
),
tpm_override: int | None = typer.Option(
    None, "--tpm-override", help="Override TPM limit (tokens per minute)"
),
```

These flow through to `run_simulation()` which already accepts them. Currently they're only read from config (`effective_rpm = config.simulation.rpm_override`). With CLI flags, they take precedence:

```python
effective_rpm = rpm_override or config.simulation.rpm_override
effective_tpm = tpm_override or config.simulation.tpm_override
```

---

### Step 5: Improve token estimation

**In `reasoning.py` `_reason_agent_two_pass_async()`:**

Replace hardcoded estimates with rough calculations:

```python
# Pass 1: estimate from prompt length (4 chars ≈ 1 token) + output
estimated_input = len(pass1_prompt) // 4
estimated_output = 300  # structured response is ~300 tokens
estimated_total = estimated_input + estimated_output
await rate_limiter.pivotal.acquire(estimated_tokens=estimated_total)
```

```python
# Pass 2: estimate from prompt length + output
estimated_input = len(pass2_prompt) // 4
estimated_output = 80
estimated_total = estimated_input + estimated_output
await rate_limiter.routine.acquire(estimated_tokens=estimated_total)
```

This won't be exact but will be much closer than the current 800/200 hardcoded values.

---

### Step 6: Handle Anthropic ITPM + OTPM properly

**In `rate_limiter.py`:**

For Anthropic, create a triple-bucket rate limiter (RPM + ITPM + OTPM) instead of dual-bucket (RPM + TPM).

Update `acquire()` to accept `estimated_input_tokens` and `estimated_output_tokens` separately:

```python
async def acquire(
    self,
    estimated_input_tokens: int = 600,
    estimated_output_tokens: int = 200,
) -> float:
```

For OpenAI (single TPM bucket), sum both into one check. For Anthropic (separate ITPM/OTPM), check each bucket independently.

Update `for_provider()` to detect Anthropic and create the third bucket when `itpm` is present in limits.

---

## Files to Change

| File | Change |
|------|--------|
| `entropy/core/rate_limits.py` | Restructure profiles, add per-model per-tier limits |
| `entropy/core/rate_limiter.py` | Triple bucket for Anthropic, split acquire signature |
| `entropy/simulation/reasoning.py` | Accept dual limiter, dynamic token estimates, always use semaphore |
| `entropy/simulation/engine.py` | Create dual rate limiters, pass both through |
| `entropy/cli/commands/simulate.py` | Add `--rpm-override`, `--tpm-override` CLI flags |

## Priority

Steps 1-3 fix the actual rate limiting failures. Steps 4-6 are improvements.

- **Must-have:** Steps 1, 2, 3 (fixes the 429 storm)
- **Should-have:** Step 4 (CLI ergonomics)
- **Nice-to-have:** Steps 5, 6 (accuracy improvements)
