# Entropy — Open Issues & Roadmap

## Code Cleanup (Completed)

The following were identified and fixed during the pre-public audit:

- [x] Removed 4 dead functions from `simulation/aggregation.py` and `simulation/propagation.py`
- [x] Fixed SQL injection risk in `simulation/state.py` (`get_agents_by_condition` removed)
- [x] Removed redundant local imports in `simulation/engine.py` and `simulation/reasoning.py`
- [x] Fixed O(n^2) agent lookups via `agents.index(agent)` in 3 locations
- [x] Replaced `outcome.type.value == "string"` with proper `OutcomeType` enum comparisons (9 locations)
- [x] Narrowed broad `except Exception` handlers in `scenario/compiler.py`
