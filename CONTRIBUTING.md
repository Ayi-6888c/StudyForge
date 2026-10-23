# Contributing to StudyForge

Useful contributions solve real learning problems, improve evidence, or protect existing work—not simply add more controls.

## Issues

- Use synthetic examples. Never submit private databases, cookies, passwords, recovery codes, API keys, student records, or unlicensed textbooks/papers.
- Provide version, OS, browser, reproducible steps, expected behavior and actual behavior. Remove personal paths and identifiers from screenshots/logs.
- Content corrections need province, year, candidate category, school, program, official URL and exact page/clause.
- Report sensitive vulnerabilities using [SECURITY.md](SECURITY.md).

## Development

1. Fork and make a focused branch; explain the user problem.
2. Add regressions. Preserve completed work, drafts, submissions, focus records and route history when adjusting plans.
3. Run `python scripts/run_checks.py` and `python scripts/release_check.py`.
4. Inspect actual staged files: `.gitignore` does not untrack secrets.
5. Open a PR with test results and limitations. UI screenshots must use synthetic learners.

See [development](docs/DEVELOPMENT.md) for browser tests and portable builds.

## Content and AI standards

Unofficial forecasts, chat screenshots and recalled questions are not official sources. Distinguish explicit permission, exclusion and unknowns. Keep reference years visible; similar major names do not establish eligibility. New provinces need independent policy evidence and learning adapters, not copies of Hubei assumptions. Follow [content requirements](docs/CONTENT_SOURCES.md); catalog updates must not silently replace personal plans.

AI assistance is welcome when disclosed and reviewed. Explain changes, verify sources and run tests. Model output is not a source, teaching review or execution evidence. Do not invent citations, users or test results.

## Contribution licensing

Original code and project documentation use [Apache-2.0](LICENSE). Contributions intentionally submitted for inclusion are handled under section 5 unless explicitly agreed otherwise in writing. Confirm your right to contribute and retain applicable attribution/change notices. External works retain their own rights; submitting a PR does not relicense them.
