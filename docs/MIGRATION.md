# Move the application or data

Neither sources nor study data must live on the system drive. Move related data together and retain a verified backup.

1. Save drafts; export the account and any necessary full-machine backup.
2. Stop the server. Do not copy a single SQLite file while a writer is active.
3. Copy the complete private data directory. Retain the old copy; do not overwrite anyone else's files.
4. Set `STUDYFORGE_DATA_DIR`, start the same version, and verify accounts, goals, work and plans.
5. Unsent LocalStorage inputs do not automatically travel with SQLite. Save/export first.
6. Update shortcuts. If Windows reminders point to the old location, save reminder settings again from the new location.

PowerShell startup example; this does not itself migrate files:

```powershell
$env:STUDYFORGE_DATA_DIR = 'D:\StudyForge-data'
python app/app.py
```

Accounts and catalog revisions are part of a full migration; one student database is insufficient. Source rollback does not delete data, but older code may not understand newer records. Test on an independent copy, not your only learning record.
