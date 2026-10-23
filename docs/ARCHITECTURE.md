# Architecture and boundaries

```text
Local browser (HTML/CSS/JavaScript)
  -> Loopback-only Python HTTP server
       -> student_platform: accounts, sessions, versioned admissions catalog
       -> exam_engine: learning packs, plans, practice, delayed revision
       -> learning_tools / customer_workspace: courses, notes, drafts, recovery
       -> companion: source discovery, reference Q&A, feedback
       -> desktop_notifications: optional Windows reminders
```

`app/` contains server modules and static assets. Students have separate learning databases. The platform database stores accounts/catalog versions; an auxiliary database stores messages, Q&A and feedback. Databases are initialized at runtime, not shipped in source archives.

Key datasets are `hubei_catalog.json`, `exam_packs.json`, `question_bank.json` and `news_registry.json`. Adopted routes are snapshots separate from the active catalog; source updates do not silently replace personal plans.

## Engineering constraints

- Loopback sessions and Host/Origin checks are not internet-facing identity. Initialize the owner on your own machine.
- Accounts share an OS process: database separation is not OS isolation.
- Code execution defaults off and remains unsandboxed when enabled.
- Background source checks require a running service and network; failures preserve caches and errors.
- Headlines are review candidates, not automatically accepted rule changes.
- Modules reflect incremental development, not a fully packaged service layer. Protect behavior with regressions before refactoring.

A hosted service additionally needs HTTPS, identity, isolated storage and judging, queues, reviewed publishing, rate limits, backups and deletion/export flows. This is not a one-command cloud deployment.
