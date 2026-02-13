# Baselines (Tracked)

This note tracks baseline evidence currently available for the frozen mini benchmark tag `mini-ready12-seed42-p3-20260212-235715`.

## 1) Direct LLM Baseline (Measured)

Source artifact (private run): `extropy-ds/minibench/direct-dual12-20260211-184557.json`.

Setup:
- Model/provider: `gpt-5-mini` on `azure_openai`
- Sample size: `n=12` agents per study
- Prompting mode used for baseline comparison: `current` (single-shot direct response)

| Study | Direct LLM baseline pred | Ground-truth target | Extropy pred (frozen run) | Direct LLM status | Extropy status |
|---|---:|---:|---:|---|---|
| apple-att-privacy | 58.3% deny_tracking | 75-80% | 76.7% | MISS | PASS |
| bud-light-boycott | 41.7% maintain_bud_light | 80-90% (~85%) | 85.8% | MISS | PASS |
| netflix-password-sharing | 83.3% maintain_relationship (comply) | >80% | 94.2% | PASS | PASS |
| x-premium-adoption | 41.7% subscribe_to_premium | 0.5-1.5% | 0.8% | MISS | PASS |

Interpretation:
- Direct LLM baseline is currently measured on **4 studies**, not all 12.
- In this measured subset, Extropy outperforms direct LLM in 3 studies and ties/pass-matches in 1.
- This baseline should be treated as **preliminary** due to small `n=12` and partial study coverage.

## 2) Survey Baseline (Availability)

Survey-style baseline context exists in many `ground-truth.md` files, but quality varies by study. The table below tracks whether a usable survey anchor is present.

| Study | Survey baseline availability | Notes |
|---|---|---|
| apple-att-privacy | YES | Explicit survey/industry opt-in expectations present |
| bud-light-boycott | YES | Stated boycott intent and polling context present |
| netflix-password-sharing | YES | Borrower intent polling context present |
| spotify-price-hike | YES | Stated cancellation-intent survey ranges present |
| plant-based-meat | YES | Stated willingness/try rates present |
| threads-launch | YES | Stated interest-to-try polling present |
| nyc-congestion-pricing | YES | Polling opposition and self-reported behavior-change intent present |
| london-ulez-expansion-2023 | PARTIAL | Polling context present; behavior target not fully survey-native |
| reddit-api-protest | LIMITED | Mostly organizer commitments/public actions, limited formal survey basis |
| snapchat-plus-launch | LIMITED | Mostly platform disclosures/market reporting, weak survey anchor |
| netflix-ad-tier-launch | LIMITED | Primarily earnings/industry reporting, weak explicit survey baseline |
| x-premium-adoption | PARTIAL | Mixed survey-style interest context and market estimates |

## Fairness Constraints for Baseline Claims

Use these constraints in public writeups:
- Do not claim “full 12-study direct-LLM baseline win” yet; measured direct-LLM baseline is currently partial.
- Label survey comparisons as **contextual anchors** unless metric definitions are fully normalized to simulation outcomes.
- Keep benchmark headline based on frozen Extropy-vs-ground-truth table; baseline deltas should be marked with coverage.
