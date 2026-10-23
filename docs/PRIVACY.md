# Local data and privacy

Data defaults to `app/data/`. Set `STUDYFORGE_DATA_DIR` before startup to choose another private location. Databases are excluded from Git/source archives.

- `platform.sqlite3`: accounts, password hashes, sessions, recovery state and catalog revisions.
- `studyforge.sqlite3` and `students/`: goals, plans, assignments, revision, courses, notes and drafts.
- `companion.sqlite3`: source caches, read state, Q&A and voluntarily submitted feedback.
- Browser LocalStorage: preferences and some unsent inputs. Save/export before migration.

Fresh installations have no previous owner's work. Unconfigured AI does not receive assignments. Source subscriptions and Windows reminders require opt-in. There is no built-in behavioral reporting.

Owners can view/reply to explicitly submitted feedback; submitting it does not automatically send chat history. Assistant/feedback export differs from main learning export. Full-machine backups contain all local accounts and must remain private.

For external assignment review, check provider, model, content sent and costs. Never commit keys or paste them into issues.

Local accounts are not OS isolation. Administrators and anyone with file permissions may access local data. Cloud identity, retention, consent, deletion and online privacy terms require separate design; these services are not claimed to exist.
