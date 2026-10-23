# Publishing and release checklist

- [x] Confirm Apache-2.0, complete LICENSE/NOTICE and third-party boundaries.
- [ ] Run `python scripts/run_checks.py` and `python scripts/release_check.py`.
- [ ] Inspect candidates: no databases, sessions, backups, keys or personal paths.
- [ ] Extract and test sources with fresh data and no predefined real users/goals.
- [ ] Use synthetic screenshots; distinguish implemented features, historical rules and future work.
- [ ] Review staged changes and use the maintainer's actual GitHub identity.
- [ ] Publish the intended sources to the correct repository.
- [ ] Configure private security reporting, review settings and branch protection as appropriate.
- [ ] Inspect hosted Actions before creating a prerelease.

## Repository

Intended destination: [Ayi-6888c/StudyForge](https://github.com/Ayi-6888c/StudyForge). This checklist is guidance, not proof of completion or a grant application.

GitHub Desktop: add the local repository, inspect Changes, commit using your identity and publish/push to the intended destination. Review visibility.

Command line, once the correct remote is configured:

```sh
git status
git remote -v
git diff --cached --stat
git commit -m "Prepare StudyForge source release"
git push -u origin main
```

Push actual source files, not only a ZIP. `.gitignore` does not remove tracked private files.
