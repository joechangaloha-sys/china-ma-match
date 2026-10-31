# Personal-account MFA

Current decision (31 October 2026): Joe wants MFA prepared but not live. Tencent sets both
`MAMATCH_MFA_ENABLED=false` and `MAMATCH_MFA_REQUIRED=false`. MFA/activation routes return 404,
navigation links are hidden and no personal account/email/enrollment is needed. The scanner remains live.
Enable both flags only after a new activation instruction. Preserve the encryption key meanwhile.

`MAMATCH_MFA_REQUIRED=true` requires password plus authenticator enrollment/verification before a
non-demo account receives any business session. Existing sessions without the second factor are
rejected. Password-only enrollment challenges are limited to five minutes and cannot open business
routes. New buyer/adviser registrations and seller invitations use this same gate.

TOTP uses PyOTP, thirty-second steps and a one-step clock tolerance. The last accepted step is updated
atomically to reject replay. Challenges allow five attempts; ten failed MFA attempts in fifteen minutes
block further challenges for that account. Verification consumes a challenge once. Recovery codes have
80 random bits each, are stored only as account-bound hashes, and are consumed with conditional writes.
PostgreSQL row locks serialize attempts on a single challenge. Enrollment revokes existing sessions.

Seeds are encrypted using Fernet and `MAMATCH_MFA_ENCRYPTION_KEY`, a persistent, private server setting
separate from the database. Never regenerate this key during deployment or lose it during restore.
Protect off-host copies separately from database dumps. QR codes are rendered locally, never by an
external QR endpoint. Setup/recovery pages use no-store, no-referrer and restrictive CSP headers.
Activation bearer tokens are redacted from Uvicorn access logs; audit logs never store MFA codes/seeds.

The explicitly seeded shared fictional demo accounts are exempt only while `MAMATCH_DEMO_MODE=true`.
They cannot enroll a personal authenticator. This exemption is a server-owned flag set by the seed,
not inferred from an email suffix and not accepted on registration. They must never access real data.
A personal deal-manager account is created through a one-hour, single-use invitation, issued only by
the operator after Joe supplies the account email. The user must choose their own password, scan the
QR on their phone and submit their own code. Never enroll an agent-controlled authenticator for them.
Do not send account invitations by email without Joe's separate instruction to send a message.

If both the authenticator and recovery codes are lost, there is deliberately no public bypass/reset.
The operator must independently verify account ownership, invalidate all sessions and outstanding
challenges, clear the seed/recovery hashes, advance `mfa_version` and record the identity-reviewed reset
in the audit log before a fresh password-first enrollment. A recovery-code login alone does not disable MFA.

References: [PyOTP security guidance](https://pyauth.github.io/pyotp/),
[ClamAV local stream protocol](https://docs.clamav.net/manual/Usage/ClamdProtocol.html).
