# Benchmark Reproducibility Pack

This folder publishes a **sanitized, frozen benchmark pack** for Extropy validation without exposing private `extropy-ds` study internals.

## Frozen Run

- Run tag: `mini-ready12-seed42-p3-20260212-235715`
- Scope: 12-study mini benchmark
- Provider/model profile: Azure OpenAI with `gpt-5-mini` (pivotal + routine)
- Fixture profile: mini (`N=120` agents per study), seed `42`, max timesteps `12`

## Included Artifacts

- `artifacts/mini-ready12-seed42-p3-20260212-235715/mini-ready12-seed42-p3-20260212-235715.groundtruth-12table.md`
  - Final 12-row scored table (study, target, prediction, error, status, mapping type).
- `artifacts/mini-ready12-seed42-p3-20260212-235715/mini-ready12-seed42-p3-20260212-235715.groundtruth-analysis.md`
  - Scored subset analysis, coverage diagnostics, miss triage.
- `artifacts/mini-ready12-seed42-p3-20260212-235715/mini-ready12-seed42-p3-20260212-235715.summary.txt`
  - Summary snapshot for the frozen run.
- `artifacts/mini-ready12-seed42-p3-20260212-235715/blocked_studies.txt`
  - Studies excluded from this benchmark due to leakage risk.
- `artifacts/mini-ready12-seed42-p3-20260212-235715/leakage-readiness.md`
  - Readiness and leakage triage matrix used for inclusion/exclusion.

## Mapping and Scoring Policy

- **Direct mapping**: simulation outcome aligns 1:1 with reported real-world metric.
- **Proxy mapping**: predefined, documented conversion aligns simulation output with how external reporting is published.
- Pass/fail is scored against each study's predeclared target band/rule. Error is shown in percentage points to boundary.

## Verification

Validate artifact integrity from repo root:

```bash
shasum -a 256 -c docs/benchmark/MANIFEST.sha256
```

## What Is Not Included

- Private study configs and raw generated configs from `extropy-ds`
- API keys, private prompts, and private run logs
- Any restricted source material not suitable for public release
