# Security and data boundaries

Only the latest early release is maintained. There is no dedicated security team or guaranteed response time.

- The service binds to `127.0.0.1`. Local accounts are not production cloud tenants. Do not forward the port or expose it publicly.
- C execution defaults off. If enabled, code runs as your OS user, not in a sandbox. Run only trusted code; hosted assessment needs independent isolation.
- AI, source subscriptions and behavioral uploads are not automatically enabled. Explicit external assignment review sends the chosen work to that provider.
- Keep the entire data directory private: it includes password hashes, sessions, recovery state and learning records. Hashes do not make databases publishable.
- App recovery codes are not GitHub/OpenAI recovery codes. Keep API keys in environment variables, never source or issues.

## Reporting

If GitHub private vulnerability reporting is enabled, use the Security tab. Otherwise, request a private contact channel in an issue **without exploitation details or private data**. Never publish sessions, recovery codes or reproductions exposing student data. The maintainer should configure a private reporting channel before wider distribution; this document invents no contact address or SLA.

Release scans assist review; they are not a professional audit or zero-vulnerability guarantee. Isolation, input validation, updates and recovery need ongoing tests.
