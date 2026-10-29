# mamatch Tencent Cloud demo — complete upload guide

**For the Tencent Cloud operator.** Upload `mamatch-tencent-demo.zip` to CloudBase CloudRun, connect it to the
private PostgreSQL database, enter the settings below, and publish. The ZIP already contains the complete website,
Dockerfile, fictional-data seed, bilingual pages, role portals, forms, health checks and local verification tools.
You do **not** need Joe's computer, local database, Git history, Python virtual environment or cloud credentials.

This is a **functional demonstration, not a production launch**. Use fictional data only. No custom domain, ICP
filing, real business data or production-security approval is included.

## 1. What you need before starting

Have these ready:

- [ ] Tencent Cloud account with real-name verification and billing enabled.
- [ ] CloudBase environment ID (`ENV_ID`) and its region.
- [ ] Permission to create/update CloudBase CloudRun services in that environment.
- [ ] A TencentDB for PostgreSQL instance in the same region, reachable from CloudRun through a private VPC path.
- [ ] PostgreSQL private host, port (normally `5432`), database name, application username and password.
- [ ] A new random outer demo passcode, at least 12 characters; 24+ random characters recommended.
- [ ] The clean `mamatch-tencent-demo.zip` supplied with this guide.

Recommended account hygiene: enable MFA and login/operation protection on the root account; use a least-privilege
CAM sub-account for deployment; set billing/budget alerts. Never send root passwords, API keys, the database
password or the full database URL to Joe or Kimi. Enter them only in Tencent's console.

Official account walkthrough: https://cloud.tencent.com/document/product/378/125818

## 2. Prepare CloudBase and PostgreSQL if they do not exist

Skip this section if the cloud administrator already created them.

### CloudBase

1. Open **CloudBase / 云开发** and create an environment named `mamatch-demo` in the intended mainland China region.
2. Record its environment ID. Start with the smallest suitable test configuration shown in the console.
3. Enable CloudRun for the environment if Tencent prompts you to do so.

### TencentDB for PostgreSQL

1. Create a small PostgreSQL instance in the **same region** and a VPC/subnet CloudRun can reach.
2. Leave **public network access disabled**. Do not open port `5432` to `0.0.0.0/0`. Permit only the required
   private CloudRun/VPC path.
3. Enable automatic backups.
4. Create database `mamatch_demo` and a dedicated application user. The user needs to connect and create/use the
   application tables in this demo database; do not use the database administrator account for the website.
5. Record the private connection details securely. The application creates its tables and fictional seed records
   automatically on first startup; no separate SQL import is needed.

Database networking/backup guidance: https://intl.cloud.tencent.com/ind/document/product/1008/56706

## 3. Upload the ZIP through the console — recommended first deployment

1. Open **CloudBase → CloudRun / 云托管** in the correct environment.
2. Choose **Create Service**, then **Local Code / 本地代码** and **Upload code package / 上传代码包**.
3. Select `mamatch-tencent-demo.zip`. Upload the ZIP directly; do not add another parent folder around its files.
   `Dockerfile` is already at the ZIP root.
4. Use these service settings:

| Setting | Required demo value |
|---|---|
| Service name | `mamatch-demo` |
| Deployment type | Container, source-code/Dockerfile build |
| Dockerfile | `Dockerfile` |
| Container port | `8080` |
| Public access | Enabled for this passcode-protected test only |
| Minimum instances | `0`, if available |
| Maximum instances | `1` — required while startup seeding is enabled |
| CPU/memory | Smallest available size suitable for a Python web demo |
| Logs | Standard output / `stdout` |
| VPC | The private path that reaches PostgreSQL |
| Liveness/health path | `/health/live`, if the console exposes this setting |
| Readiness path | `/health/ready`, if available |

5. Enter every environment variable from section 4. Do not put secrets in the ZIP, Dockerfile or Git.
6. Create/publish the service and watch the build and runtime logs. The container builds from Python 3.12, runs as
   a non-root user, listens on `0.0.0.0:8080`, initializes PostgreSQL and loads fictional examples.
7. When the revision is healthy, copy the assigned **HTTPS default URL**. Continue with section 6 acceptance tests.

Console upload is documented by Tencent here:
https://docs.cloudbase.net/en/ai/agent-development/deployment/cloud-run
and CloudRun's local-code/Dockerfile support is summarized here:
https://cloud.tencent.com/document/product/1243/46250

## 4. Required CloudRun environment variables

Enter these as runtime environment variables in the CloudRun service/version settings.

| Variable | Value |
|---|---|
| `MAMATCH_DEMO_MODE` | `true` |
| `MAMATCH_DEMO_ACCESS_KEY` | Your new random outer demo passcode |
| `MAMATCH_DEMO_ACCESS_HOURS` | `12` |
| `MAMATCH_SEED_DEMO` | `true` |
| `MAMATCH_SECURE_COOKIES` | `true` for the Tencent HTTPS URL |
| `MAMATCH_DATABASE_URL` | `postgresql+psycopg://USER:PASSWORD@PRIVATE_HOST:5432/mamatch_demo` |
| `MAMATCH_UPLOAD_DIR` | `/app/data/uploads` |
| `MAMATCH_LLM` | `off` |
| `MAMATCH_PUBLIC_URL` | Leave blank for the first deployment; complete section 7 afterward |
| `MAMATCH_FORWARDED_ALLOW_IPS` | `*` for the managed CloudRun proxy |
| `PORT` | `8080` |

A placeholder-only copy is included as `deploy/tencent-cloud/demo.env.example`.

**Database URL encoding:** replace `USER`, `PASSWORD`, `PRIVATE_HOST` and the database name separately. If the
username or password contains reserved characters such as `@`, `:`, `/`, `#`, `%` or `&`, percent-encode that
component before inserting it. Do not percent-encode the whole URL. Python can encode a value locally:

```bash
python -c 'import urllib.parse; print(urllib.parse.quote(input("Value: "), safe=""))'
```

Generate a random outer demo passcode locally:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(24))'
```

Use a different secret for PostgreSQL. The outer demo passcode is not the same as the application role passwords.

## 5. Optional: command-line redeployment

Use this only **after** the service exists and its VPC/environment variables have been configured. The first
console upload is simpler because creation and configuration happen together.

On the operator's own computer, install Node.js and the CloudBase CLI, then authenticate through the browser:

```bash
npm install -g @cloudbase/cli
tcb --version
tcb login
```

Unzip the bundle, enter its root, and run:

```bash
./deploy/tencent-cloud/deploy_demo.sh --check
./deploy/tencent-cloud/deploy_demo.sh <ENV_ID>
```

The helper checks the required files and runs:

```bash
tcb cloudrun deploy --env-id <ENV_ID> --service-name mamatch-demo --port 8080 --source <BUNDLE_ROOT> --wait
```

Review the environment ID and any confirmation prompt carefully. The script contains no credentials and never
prints or asks for the database password. For an existing service, verify in the console that the new revision
retains the intended VPC and environment settings.

CLI references:
https://cloud.tencent.com/document/product/876/41539
https://docs.cloudbase.net/cli-v1/cloudrun/deploy

## 6. Acceptance checklist — do this before handing over

Replace `https://YOUR-DEFAULT-URL` with the actual HTTPS URL, without a trailing slash.

### Automated endpoint checks

```bash
export DEMO_URL="https://YOUR-DEFAULT-URL"
curl -sS "$DEMO_URL/health/live"
# Expected: {"status":"ok"}

curl -sS "$DEMO_URL/health/ready"
# Expected: {"status":"ready"}

curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' "$DEMO_URL/"
# Expected before entering the passcode: 303 and a /demo-access URL

curl -sS -D - -o /dev/null "$DEMO_URL/demo-access" | grep -i 'x-robots-tag'
# Expected: noindex, nofollow, noarchive
```

### Browser workflow checks

- [ ] Opening the root URL redirects to the demo passcode page.
- [ ] An incorrect passcode does not unlock the site.
- [ ] The correct passcode unlocks the site and persists for the configured session duration.
- [ ] The fictional-data warning is visible on every page.
- [ ] `/zh` shows Chinese and `/en` shows English; switching languages preserves the current section.
- [ ] Public opportunities show anonymised fictional sellers, not buyer information.
- [ ] Keyword and detailed opportunity search work.
- [ ] A fictional seller intake submission succeeds at `/en/sell` or `/zh/sell`.
- [ ] Sign in as the demo deal manager and confirm that the new seller submission appears internally. This proves
      form writes reach PostgreSQL rather than a local SQLite file.
- [ ] Seller, verified-buyer, pending-buyer and adviser accounts open only their permitted portals.
- [ ] Test one 375 px-wide mobile viewport; navigation and listing cards remain usable without page-wide sideways
      scrolling.

### Fictional role sign-ins

After passing the outer gate, all these fixture accounts use password `demo-pass-2026`:

| Role | Email |
|---|---|
| Deal manager | `dm@demo.mamatch.test` |
| Seller | `seller.jade@demo.mamatch.test` |
| Verified buyer | `buyer.huadong@demo.mamatch.test` |
| Pending buyer | `buyer.pending@demo.mamatch.test` |
| Adviser | `adviser@demo.mamatch.test` |

These are intentionally public demo fixtures, not production credentials. Never reuse them with real data.

## 7. Set the public URL and verify persistence

1. In CloudRun service/version settings, set `MAMATCH_PUBLIC_URL` to the exact assigned HTTPS default URL, with no
   trailing slash. Publish a new configuration revision. This makes share links and QR codes point to the demo.
2. Submit a uniquely named fictional seller record and note its name.
3. Create/redeploy a revision using the same database.
4. Confirm the record still appears internally and `/health/ready` remains `{"status":"ready"}`.
5. Keep maximum instances at `1` while `MAMATCH_SEED_DEMO=true`; this avoids concurrent startup seed races.

## 8. Troubleshooting

| Symptom | Most likely cause and action |
|---|---|
| Build says Dockerfile is missing | The ZIP was repacked with an extra parent folder. Use the supplied ZIP directly; `Dockerfile` must be at archive root. |
| Container exits with a demo-passcode error | Set `MAMATCH_DEMO_MODE=true` and a `MAMATCH_DEMO_ACCESS_KEY` of at least 12 characters. |
| `/health/live` works but `/health/ready` returns 503 | The database is unreachable. Check private host/port, database name, credentials, CloudRun VPC attachment and PostgreSQL security group. |
| Database authentication fails | Check the dedicated username/database and correctly percent-encode reserved password characters. |
| Healthy revision but browser returns 503 | Confirm port `8080`, public access, traffic assigned to the healthy revision, and the runtime logs. |
| Login succeeds but the browser returns to the passcode page | Use the HTTPS URL and keep `MAMATCH_SECURE_COOKIES=true`; check that the browser accepts cookies. |
| Share links/QR codes show a local address | Set `MAMATCH_PUBLIC_URL` to the assigned HTTPS URL and publish a new revision. |
| Uploaded document disappears after a revision | Expected demo limitation: local container files are ephemeral. Do not upload important documents; durable COS is not yet implemented. |
| Default URL shows a Tencent interstitial or has access limits | Expected default-domain development/test behavior. It is not a production-domain substitute. |
| Static CSS is missing | Confirm the original ZIP was used and the build logs show the complete Dockerfile build. |

For build errors, inspect **CloudRun → Deployment/Build Logs**. For startup or request errors, inspect **Runtime
Logs**. Do not publish screenshots containing environment-variable values.

## 9. Updating, rollback and teardown

- **Update code:** upload a new ZIP as a new revision or use the CLI helper. Keep the same environment variables,
  VPC and database; then repeat section 6.
- **Rollback:** use CloudRun's version/traffic controls to send traffic back to the previous healthy revision.
  Because this demo creates tables additively, still test the old revision against the current demo schema.
- **Stop charges:** scale down/delete CloudRun, then delete PostgreSQL and any retained backups/snapshots according
  to the console prompts. Remove remaining CloudBase, log, storage and networking resources. Deleting only the web
  service does not stop managed-database charges. Check Billing afterward.

## 10. Demo boundaries and operator handoff

- Fictional companies, buyers, documents and transactions only.
- `noindex` is not authentication; the outer passcode is only a demonstration access barrier.
- Local uploads are ephemeral until private COS storage is implemented.
- Production still requires CSRF protection, deal-manager MFA, sign-in throttling, durable/scanned uploads,
  database migrations, monitored recovery, security testing, legal review and applicable ICP/compliance work.
- Tencent default domains are for development/testing and can have frequency, functionality, stability and browser
  interstitial limitations. Production browser access requires a properly filed custom domain.

Default-domain policy: https://docs.cloudbase.net/service/introduce

When acceptance passes, give Joe only:

1. The HTTPS demo URL.
2. The outer demo passcode, through a separate appropriate channel.
3. The service name, environment ID, region and revision name.
4. Any unresolved issue from this checklist.

Do not hand over or copy the database administrator credentials into the website handoff.
