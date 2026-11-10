# Controlled database upgrades and recovery rehearsal

## Versioned schema

Web startup and readiness checks are read-only: they require the expected Alembic head and validate
columns, type families/lengths, nullability, primary keys, foreign keys, unique constraints and indexes.
They never infer or add columns from runtime models. A missing/older/unknown revision or drift stops
startup/readiness. The operator explicitly runs `python -m mamatch.migrations upgrade`.

`0001_baseline` freezes the schema from main `cb393d5`; its historical schema module must not change
when application models change. `0002_audit_index` adds the audit timeline index and validates/enforces
existing required-column nullability. It refuses NULL data rather than guessing a repair. New model
changes require a new reviewed revision. No command drops the baseline or restores over live records.

For the existing Tencent database, `upgrade --adopt-existing` first checks the exact frozen baseline
structure and constraints (allowing old nullable declarations), stamps the baseline, and applies the
reviewed next revision. Partial/unknown legacy schemas are refused and require a separately reviewed
migration. This replaces the old generic “add every missing model column” helper. For a new local DB,
run `uv run mamatch init-db --seed`; `mamatch serve` now checks rather than creates the schema.

PostgreSQL migration/adoption runs inside one transaction with an advisory lock, a five-second DDL
lock timeout and a two-minute statement timeout. Failure rolls back DDL and the revision write. The
isolated rehearsal injects both a table creation and a bad revision write, forces failure through the
same migration wrapper, and verifies neither remains. SQLite development does not offer the same DDL
atomicity guarantees: keep a file backup before manual SQLite upgrades. Tencent uses PostgreSQL.

## Deployment gate

`deploy/lighthouse/deploy.sh <branch>` now:

1. Takes an exclusive host deployment lock and retains the prior application image as a rollback tag.
2. Builds the pushed GitHub image while the current application continues serving.
3. Runs `recovery_check.py`, creating a private backup and restoring it into a generated scratch DB.
4. Upgrades/verifies that scratch DB with the new image; checks constraints, serial sequences, synthetic
   file recovery and failed-upgrade rollback. It removes only its own generated scratch DB afterwards.
5. Only after that succeeds, runs the reviewed live migration and starts the new application image.
6. Requires application readiness. Any failed backup/rehearsal/migration stops deployment.

There is no automatic destructive schema rollback. New migrations must remain compatible with the
retained application image, or carry a separately reviewed maintenance/recovery plan. Backups and
rollback images are intentionally retained; this change does not silently prune recovery evidence.

## What each backup proves

Backups stay on Tencent under `/opt/mamatch/backups/<UTC-time>-<random>/` (directory 0700, files 0600).
An exported repeatable-read PostgreSQL snapshot is shared by the row manifest and `pg_dump -Fc`, so
concurrent sign-in/session updates do not cause a false comparison. The source snapshot is read-only.
The bundle contains `database.dump`, `uploads.tar`, and a passed `manifest.json`; failure creates a
`FAILED` marker and blocks release. It contains credentials/hashes and private deal data: do not publish
or copy it into a public repository, chat, or unprotected storage.

The manifest records row counts and SHA-256 digests for every public table, plus artifact checksums.
Only files referenced by the snapshot's document rows are archived; their immutable bytes must match
stored SHA-256 values. Restore uses a single transaction into a newly created, generated scratch DB,
compares every original table's counts/digests, extracts files into a scratch directory, and checks bytes.
A deliberately corrupted artifact must be rejected before restore. A synthetic file exercises file
recovery even when the current live pilot has no uploaded documents. Original registry/user records
are never rewritten for the rehearsal. New schema ledger/index changes occur only in migration steps.

The test restores within the existing private PostgreSQL container, with no new public port or cloud
resource. Scratch database names are generated and guarded; the utility has no live-restore option.
Use `sudo python3 deploy/lighthouse/recovery_check.py` from `/opt/mamatch-src` for an independent rehearsal
when the new image has already been built. Readiness and schema CLI commands can check the result.

## Recovery procedure and limits

A real recovery requires a new explicit instruction and an agreed maintenance window. First verify
artifact checksums and the passed manifest, restore to an isolated destination, verify data/files/schema,
then review application compatibility before any cutover. Never point `pg_restore --clean` at live data.
Retain `/opt/mamatch/.env` securely and separately: database passwords, the demo passcode and the MFA
encryption key are not inside the data bundle. Losing that key prevents recovery of enrolled MFA seeds.
This task keeps MFA disabled and external signing/VDR services deferred.

This is a tested same-server logical backup/recovery path, not off-host disaster recovery or point-in-time
recovery. A lost server could lose both data and these backups. Off-host storage, recurring schedules,
retention policy and credentials are not provisioned by this task and need a separate decision.

References: [Alembic connection sharing and existing-database baselines](https://alembic.sqlalchemy.org/en/latest/cookbook.html),
[PostgreSQL 16 snapshot dumps](https://www.postgresql.org/docs/16/app-pgdump.html),
[transactional restore](https://www.postgresql.org/docs/16/app-pgrestore.html).
