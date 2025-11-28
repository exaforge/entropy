<!-- 20100bd4-6d7f-479e-b396-f92ce82b6481 1b44bd15-704d-44d8-97f5-07482b25297a -->
# Context Injection Architecture

## Problem Statement

### Current Limitations

1. **Wasted Compute**: Every new scenario re-researches the same demographics (age, income, location)
2. **No Reusability**: Can't reuse a "German Surgeons" base for multiple scenarios
3. **Clone vs Chaos**: No mechanism to link behavioral attributes to demographics while preserving variance

### What We're Building

A two-layer system where:

- **Layer 1 (Base)**: Identity attributes — researched once, cached, reusable
- **Layer 2 (Overlay)**: Behavioral attributes — scenario-specific, linked to base via formulas/modifiers

---

## CLI Commands

### Command 1: `entropy spec` (unchanged)

Single-pass generation for simple use cases.

```bash
entropy spec "500 German surgeons" -o surgeons.yaml
```

Still works. Creates a complete spec in one pass.

### Command 2: `entropy overlay` (new)

Layer a scenario on top of an existing base spec.

```bash
entropy overlay surgeons_base.yaml \
    --scenario "AI diagnostic tool adoption" \
    -o surgeons_ai_adoption.yaml
```

**Flow:**

1. Load `surgeons_base.yaml` as context
2. Discover NEW attributes for the scenario (not in base)
3. Research distributions, allowing dependencies on base attributes
4. Merge base + overlay into final spec

### Command 3: `entropy merge` (new, optional)

Manually merge two specs (for advanced users).

```bash
entropy merge base.yaml overlay.yaml -o merged.yaml
```

---

## File Changes

### 1. `entropy/spec.py` — Add Merge Capability

```python
class PopulationSpec(BaseModel):
    # ... existing fields ...
    
    def merge(self, overlay: "PopulationSpec") -> "PopulationSpec":
        """Merge an overlay spec into this base spec."""
        # Combine attributes (overlay can override)
        # Recompute sampling order with cross-layer dependencies
        # Merge sources and grounding summaries
```

### 2. `entropy/architect/selector.py` — Context-Aware Selection

```python
def select_attributes(
    description: str,
    size: int,
    geography: str | None = None,
    context: list[AttributeSpec] | None = None,  # NEW
    model: str = "gpt-5",
    reasoning_effort: str = "low",
) -> list[DiscoveredAttribute]:
```

**Prompt change:**

```
## Existing Context (DO NOT REDISCOVER)
The following attributes already exist in the base population:
- age (int)
- income (float)
- specialty (categorical)

Only discover NEW attributes relevant to: "{scenario}"
You may reference existing attributes in dependencies.
```

### 3. `entropy/architect/hydrator.py` — Context-Aware Hydration

```python
def hydrate_attributes(
    attributes: list[DiscoveredAttribute],
    description: str,
    geography: str | None = None,
    context: list[AttributeSpec] | None = None,  # NEW
    model: str = "gpt-5",
    reasoning_effort: str = "low",
) -> tuple[list[HydratedAttribute], list[str]]:
```

**Prompt change:**

```
## Read-Only Context Attributes
These attributes exist in the base population. You can:
- Use them in "formula" (derived strategy)
- Use them in "modifiers" (conditional strategy)
Do NOT define distributions for them.

Context:
- age (int): Agent's age in years
- income (float): Annual income in EUR
- specialty (categorical): Medical specialty
```

### 4. `entropy/architect/binder.py` — Cross-Layer Dependencies

Update topological sort to handle:

- Overlay attributes depending on base attributes
- Base attributes appearing in overlay formulas
```python
def bind_constraints(
    attributes: list[HydratedAttribute],
    context: list[AttributeSpec] | None = None,  # NEW
) -> tuple[list[AttributeSpec], list[str]]:
```


### 5. `entropy/cli.py` — New `overlay` Command

```python
@app.command("overlay")
def overlay_command(
    base_spec: Path = typer.Argument(..., help="Base population spec YAML"),
    scenario: str = typer.Option(..., "--scenario", "-s", help="Scenario description"),
    output: Path = typer.Option(..., "--output", "-o", help="Output merged spec"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmations"),
):
    """
    Layer scenario-specific attributes on a base population.
    
    Example:
        entropy overlay surgeons.yaml -s "AI adoption study" -o surgeons_ai.yaml
    """
```

---

## The Solving Matrix

| Problem | How It's Solved |

|---------|-----------------|

| Wasted compute on demographics | Base spec cached, only overlay researched |

| No reusability | Same base used for multiple scenarios |

| Clone problem (deterministic) | Overlay uses stochastic sampling with demographic nudges |

| Chaos problem (random) | Formulas/modifiers link behavior to identity |

| Cool Grandpa effect | Conditional distributions preserve outliers |

---

## Example Flow

### Step 1: Create Base (Once)

```bash
$ entropy spec "German surgeons" -o surgeons_base.yaml

✓ Found 32 attributes
✓ Researched distributions (89s, 45 sources)
✓ Saved to surgeons_base.yaml
```

**surgeons_base.yaml contains:**

- age, gender, income, location (universal)
- specialty, years_practice, hospital_type (population-specific)
- openness, conscientiousness, risk_tolerance (personality)

### Step 2: Layer Scenario (Fast)

```bash
$ entropy overlay surgeons_base.yaml \
    --scenario "New AI diagnostic tool adoption" \
    -o surgeons_ai.yaml

Loading base: surgeons_base.yaml (32 attributes)

✓ Found 6 NEW attributes for scenario
  • tech_optimism (float) — independent
  • ai_familiarity (categorical) — independent  
  • adoption_likelihood (float) ← depends on: age, tech_optimism, risk_tolerance
  • training_willingness (float) ← depends on: years_practice
  • peer_influence_susceptibility (float) ← depends on: hospital_type
  • early_adopter_score (float) — derived: tech_optimism * (1 - age/100) * risk_tolerance

✓ Researched distributions (23s, 12 sources)
✓ Merged: 32 base + 6 overlay = 38 total attributes
✓ Saved to surgeons_ai.yaml
```

### Step 3: Run Different Scenario (Reuse Base)

```bash
$ entropy overlay surgeons_base.yaml \
    --scenario "Response to hospital merger announcement" \
    -o surgeons_merger.yaml

# Different overlay, same base — no re-research of demographics
```

---

## Sampling Order Example

After merge, the binder computes a unified sampling order:

```
Base attributes (sampled first):
  age → gender → location → specialty → years_practice → income → risk_tolerance

Overlay attributes (sampled after, can reference base):
  tech_optimism → ai_familiarity → adoption_likelihood → early_adopter_score
                                          ↑
                              formula: f(age, tech_optimism, risk_tolerance)
```

---

## Files Summary

| File | Status | Changes |

|------|--------|---------|

| `spec.py` | Modify | Add `merge()` method |

| `selector.py` | Modify | Add `context` param, update prompt |

| `hydrator.py` | Modify | Add `context` param, update prompt |

| `binder.py` | Modify | Handle cross-layer deps in topo sort |

| `cli.py` | Modify | Add `overlay` command |

---

## Out of Scope

- Caching base specs to disk/DB (future)
- Version control for specs (future)
- Automatic scenario detection (future)

### To-dos

- [ ] Create project structure, pyproject.toml, .env.example
- [ ] Implement Pydantic models in models.py
- [ ] Implement config.py with Pydantic settings
- [ ] Implement SQLite CRUD operations in db.py
- [ ] Implement OpenAI client with web search in llm.py
- [ ] Implement research functions in search.py
- [ ] Implement full population pipeline in population.py
- [ ] Implement Typer CLI commands in cli.py
- [ ] Create placeholder files for Phase 2/3 (scenario.py, simulation.py, api.py)
- [ ] Add validate_situation_attributes() in llm.py using gpt-5-instant
- [ ] Update research prompt to clarify per-agent vs aggregate
- [ ] Call validation in search.py and filter out aggregate attributes
- [ ] Add CLI confirmation step with rich summary before generation
- [ ] Add live progress timer with elapsed time during research
- [ ] Create project structure, pyproject.toml, .env.example
- [ ] Implement Pydantic models in models.py
- [ ] Implement config.py with Pydantic settings
- [ ] Implement SQLite CRUD operations in db.py
- [ ] Implement OpenAI client with web search in llm.py
- [ ] Implement research functions in search.py
- [ ] Implement full population pipeline in population.py
- [ ] Implement Typer CLI commands in cli.py
- [ ] Create placeholder files for Phase 2/3 (scenario.py, simulation.py, api.py)
- [ ] Add merge() method to PopulationSpec in spec.py
- [ ] Add context param to select_attributes, update prompt
- [ ] Add context param to hydrate_attributes, update prompt
- [ ] Update bind_constraints for cross-layer dependencies
- [ ] Add entropy overlay command to cli.py