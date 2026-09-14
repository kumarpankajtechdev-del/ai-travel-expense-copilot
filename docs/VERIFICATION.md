# Verification record

Checked on 14 September 2026 using Linux, Python 3.12.14 and Node 24.19.0.

| Check | Result |
| --- | --- |
| Python workflow/API/provider-contract suite | 32 tests passed |
| JavaScript DOM interaction suite | 3 tests passed |
| Ruff lint | Passed |
| Python wheel build | Passed; HTML, CSS and JS included |
| Empty virtual environment + locked runtime | 45 runtime distributions installed successfully |
| Dependency compatibility check | Passed |
| Wheel installation, launched outside source checkout | Passed |
| Editable installation from a clean copied source folder | Passed |
| HTTP smoke journey | Passed: health, assets, receipt review, confirmation, idempotency, analytics, citations and CSV |
| Process restart with saved data | Passed |

Clean environments were installed with uv using the pinned requirements and locally cached registry packages. Both the wheel and editable source paths were exercised. The included scripts/smoke.py reruns the installed-app HTTP check with disposable fictional data.

The JavaScript tests execute the real UI code against controlled API responses in jsdom. They check chart switching, receipt form submission, updated totals, text escaping and clearing stale results on errors. They do not verify browser rendering.

## Not verified here

- Visual browser interaction: the environment blocked the local preview URL.
- Real OpenAI or Anthropic completions: no user API credentials were used.
- Docker: no Docker runtime was available.
- Windows/macOS execution and Python versions other than 3.12.
- A deployed, authenticated or multi-user service.

One upstream Starlette/AnyIO deprecation warning appeared during Python tests; it did not cause failures.

This record describes observed checks, not a claim that software is perfect or that every environment/model will behave identically. No model-quality benchmark, latency SLA or business impact metric is claimed.
