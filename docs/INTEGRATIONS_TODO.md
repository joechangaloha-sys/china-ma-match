# External connections — deferred by user, 31 Oct 2026

Joe asked to set up external connections later and continue building offline. Do not create accounts,
purchase subscriptions, request secrets or enable live signatures/invitations until he resumes this work.
The intended account owner is a mainland China company; first-pilot signers are mainland companies and
individuals. Current provider choices are recommendations, not purchased or connected services.

## NDA e-signature

- [ ] Operating-company administrator opens/verifies the domestic Tencent eSign company account.
- [ ] Confirm third-party platform integration suitability, seller-company onboarding, scoped permissions
      and a written quote. e签宝 is the alternative if Tencent's terms/workflow are unsuitable.
- [ ] Create a dedicated sandbox application and agree a stable HTTPS callback address.
- [ ] Put test AppId, app-scoped SecretId/SecretKey, webhook verification token and encryption key into
      protected runtime secret storage. Never put credentials or identity documents in this repository.
- [ ] Counsel approves NDA parties, template, governing law, language precedence, term, representative
      authority and record-retention arrangements. Provider KYC is not a substitute for corporate authority.
- [ ] Implement the selected provider adapter: request, verify signed callbacks, decrypt if applicable,
      query authoritative status, implement transactional/idempotent processing, reconcile retries, reject stale/replayed/cross-mandate events and
      obtain the signed document hash plus retrievable evidence reference.
- [ ] Test sandbox cancellation, refusal, expiry, duplicate/out-of-order callbacks and amended parties.
- [ ] Separate production configuration, permissions, approval and acceptance tests before real use.

## Professional VDR

- [ ] Request a Docutone trial. Confirm mainland primary/backup storage, logs, CDN/caches, support access,
      MFA, participant groups, watermarking, view-only controls, expiry/revocation and audit/closing archive.
- [ ] Obtain a pilot quote: indicative scope is one room, three months, 5 GB, two administrators and
      20 outside participants. No budget or price has been approved.
- [ ] Verify API documentation, availability and pricing before promising automation. Docutone API access
      is unconfirmed. Ideals is an alternative; its documented API is an Enterprise add-on and mainland
      hosting remains to be confirmed in writing.
- [ ] Use a dedicated project administrator for a fictional room. Keep the user as account owner.
- [ ] Initially provision invitations manually after explicit seller scope approval; confirm provider-side
      access before marking a grant active. Record who provisioned it and a non-secret room reference.
- [ ] Later add narrowly scoped service credentials and actual provider-side expiry/revocation,
      reconciliation, isolation between buyer groups and audit export. A local revoked flag cannot revoke
      access in an external provider that has not acknowledged the operation.

## Hosting and operating prerequisites

- [ ] Agree the real-data location, overseas-access arrangements and production callback domain before
      any real identity information, signed NDA or confidential material enters the Singapore demo.
- [ ] Complete MFA, upload malware scanning, formal database migrations and legal/data-processing review.
- [ ] Decide retention and export of signed originals/evidence separately from VDR access expiry.

## Implemented while connections are deferred

- [x] Mock-only signing request/completion/cancellation, version/party binding and event deduplication.
- [x] Human signatory-authority review, explicit owner approval of room/role/expiry and separate provisioning.
- [x] Server-enforced expiry/revocation for fictional demo files, with an append-only workflow event log.
- [x] Bilingual isolated `/handoff` scenarios, internal workflow screen and `/internal/connections` checklist.

Mock evidence is never treated as a real electronic signature or as an external VDR acknowledgement.
No confidential files or signed PDFs are stored in the handoff ledger.
