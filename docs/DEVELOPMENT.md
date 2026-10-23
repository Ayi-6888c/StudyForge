# Development, tests and packaging

## Core checks

```sh
python scripts/run_checks.py
python scripts/release_check.py
```

Core tests use standard-library, temporary synthetic accounts/databases. No real AI calls, external sources or Windows notifications. Run `python tests/regression_catalog.py` separately for the full major/offering matrix.

Release checks validate complete Apache-2.0 text, NOTICE, candidates, staged credentials/personal-path patterns, links and JSON. Historical `--allow-pending-license` mode does not allow corrupt licenses. Pattern scans supplement human review.

## Optional browser checks

```sh
python -m pip install -r requirements-ui.txt
python -m playwright install chromium
python tests/ui_smoke.py
```

With Edge on Windows, set `STUDYFORGE_BROWSER_CHANNEL=msedge`. Tests start an isolated service/synthetic learner, not your personal installation. Core tests do not require browser downloads.

## Windows portable build

Use a dedicated Windows virtual environment:

```powershell
python -m pip install -r requirements-build.txt
python scripts/build_windows.py
```

Ignored `dist/` holds outputs. Builds do not sign binaries or publish releases. Check bundled runtime/dependency notices, empty data, reminders and recovery before redistribution. Execution remains opt-in.

## Source archive

```sh
python scripts/build_source_archive.py
```

Only checked source candidates enter the archive. Verify `dist/SHA256SUMS.txt`, extract independently and rerun checks with fresh data.

## CI and content changes

Actions defines Ubuntu/Windows Python 3.11/3.12 checks and a manual Windows build. Dependencies use full commit pins, read-only contents and no publishing secrets. Inspect actual hosted results; local tests are not hosted evidence.

Validate structure and behavior after JSON changes. Never use private databases/cookies as fixtures. New provinces need independent rules and learning adapters, not merely a selectable name.
