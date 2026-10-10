# Nexyra AgriSense

Nexyra provides source-attributed agricultural market observations, research-only price evaluation, and experimental agricultural event intelligence. The current build focuses on Maharashtra onion modal wholesale prices at 1-, 3-, and 7-calendar-day horizons.

## Current validation status

- Canonical prices: 291 observations through 2026-10-08; source availability times are unverified.
- Historical prices: 21,864 observations; the research FAQ series ends 2024-12-10.
- PIB articles: 18 unique identities with stored full-body representations; 0 human-reviewed articles.
- No production forecasting model is currently eligible or registered.
- Model B classifications are experimental rules. Model C is context-only and emits no numerical news adjustment.

## Run locally on Windows

From `C:\Nexyra`:

```powershell
.\scripts\run-dev.ps1
```

Open http://127.0.0.1:3000. The API health endpoint is http://127.0.0.1:8000/api/health. The script binds to loopback, checks port ownership and both services, refuses occupied ports, and stops only the service processes it launched when Ctrl+C is pressed.

See [developer setup](docs/nexyra_developer_setup.md) for installation, test, build, and data-import commands; [user guide](docs/nexyra_user_guide.md) for the dashboard and review workflow; [model-validation status](docs/nexyra_model_validation_status.md) for metrics and limitations; and [release-candidate report](docs/nexyra_release_candidate_report.md) for the final gate.

## Core boundaries

- Markets, varieties, grades, and source identities remain separate.
- Missing price dates are not interpolated.
- Historical replay is not prospective accuracy.
- Publication time, source first-seen time, and forecast origin are distinct.
- News evidence does not prove a causal price effect.
- No model is trained or registered by the review or source-import workflows.
- Do not expose local development or review APIs to a network.

The previous financial workspace remains available at `/legacy` and has not been redesigned in this phase.
