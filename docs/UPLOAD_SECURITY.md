# Upload quarantine and pilot sessions

Every new upload enters `quarantined`; additive migration also quarantines existing files.
File extension, bounded size and conservative content/package checks run before persistence.
Quarantined bytes live outside static assets with random storage names and mode 0600.
A source SHA256 and a scan SHA256 bind the result to the saved bytes. Downloads, extraction,
financial-field confirmation, evidence review and data-room inclusion recheck this binding.
Existing buyer/mandate approval checks still apply. Scanning never grants disclosure permission.

The private deal-manager queue is `/en/internal/upload-security` or `/zh/internal/upload-security`.
Only a deal manager can request a scan. The optional trusted local executable is configured via
`MAMATCH_CLAMSCAN_PATH=/usr/bin/clamscan`; never point it at user-controlled storage.
The deployment operator must build a scanner-capable web image (the default demo image does not include ClamAV), mount a maintained local signature database, and arrange fresh signature updates. The Lighthouse Compose file forwards the optional path from its environment file.
No file is sent to an external scanning service. Scanner absence, signatures older than two days,
timeout, resource-limit alert, threat, malformed package or integrity change cannot produce a clean result.
Results are audited; there is no manual clean override. A clean result does not guarantee a file is safe.
The Tencent review environment deliberately has no scanner configured: all uploads remain quarantined.
No provider account or external connection was created. Do not enable real uploads until the local
scanner/signature updater and operational monitoring are configured and tested with EICAR fixtures.

Text extraction follows a clean scan in a separate process with a 15-second timeout, ten-second CPU
limit, 100-page cap and 200,000-character output cap. Linux deployment also enforces a 512 MiB address
space limit; macOS development uses the CPU/time/output limits. Unsupported extraction yields no text.
Office macros, embedded objects, external relationship links, encrypted ZIP entries and excessive
package expansion are rejected conservatively. These checks are not a replacement for the scanner.

Authenticated sessions expire after thirty idle minutes or twelve hours from sign-in. Legacy sessions
without a last-seen timestamp require a fresh sign-in. `/account/sessions` lets each signed-in user revoke
all of their own sessions, including the current one, with CSRF protection and an audit event. Existing
role and matter checks, account lockout window and session-bound CSRF checks remain in force.
Request bodies are bounded before form/CSRF parsing, even without Content-Length.
MFA and a managed migration process remain prerequisites for a real-data pilot.
