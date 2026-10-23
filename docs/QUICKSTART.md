# Quick start

Use Python 3.11/3.12. The local web server needs no third-party library; Windows reminders are optional. From the repository root:

```sh
python app/app.py --no-browser --port 8765
```

Open <http://127.0.0.1:8765/>. If occupied, choose another port or omit it for automatic assignment; the terminal prints the URL. The current student interface is Simplified Chinese.

## First-time setup

1. Set up your local account and keep its recovery code private.
2. Open admission goals; choose Hubei, your source major, target program and school. Other provinces do not yet have complete catalogs.
3. Check evidence and reference years before adopting a plan. Fresh accounts have no previous learner's records.
4. Answer independently, save your work, inspect feedback and revise.

## Optional capabilities

- Windows reminders: `python -m pip install -r requirements-windows.txt`, then explicitly enable reminders in settings. Scheduled tasks are not installed by default.
- C execution: configure a compiler, set `STUDYFORGE_ENABLE_CODE_EXECUTION=1` and restart. Default review is static; enabled execution is unsandboxed.
- Reference Q&A needs no model. Conversational AI is a disabled placeholder; startup does not download models.
- Existing assignment AI review requires provider configuration and a manual request. Check what is sent and provider costs. A ChatGPT subscription does not supply application API credit.

## Stop and troubleshoot

Use Ctrl+C or the owner's shutdown control. Closing the browser does not necessarily stop the server. Check PATH if Python is missing; change occupied ports. Reference Q&A works without a model.

Use recovery codes/backups rather than deleting databases to fix login. See [privacy](PRIVACY.md), [migration](MIGRATION.md) and [security](../SECURITY.md).
