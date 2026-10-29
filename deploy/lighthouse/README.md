# mamatch Lighthouse demo — upload and operating guide

This package is for Joe's Tencent Cloud International Lighthouse server:

- Public IP: `43.153.223.242`
- Region: Singapore
- Server image: Ubuntu 24.04 with Docker 29.6.1
- Website address after installation: `https://43.153.223.242.sslip.io`
- Data: fictional test information only

The package includes the complete bilingual website, seller/buyer/adviser/deal-manager areas, form database,
fictional seed records, an outer demo passcode, persistent PostgreSQL storage and persistent document uploads.
It contains no cloud password, database password, API key, local database or real business information.

## What the installer does

1. Uploads the application to `/opt/mamatch` on the Lighthouse server.
2. Generates separate random secrets for PostgreSQL and the outer demo passcode on the server.
3. Starts PostgreSQL 16, the website and Caddy with Docker.
4. Stores database records, uploaded files and HTTPS certificates in persistent Docker volumes.
5. Uses the free `sslip.io` hostname and Let’s Encrypt to enable HTTPS; Caddy renews the certificate automatically.
6. Publishes website ports `80` and `443`; PostgreSQL port `5432` is not exposed to the internet.
7. Prints the HTTPS website address and outer demo passcode when the health check passes.

Rerunning the installer updates the application while preserving the existing database, uploads and passcode.
When upgrading the original HTTP demo, it preserves a server-only backup of the previous settings as
`/opt/mamatch/.env.before-https`.

## Updating after a change — Git route (no re-upload)

Once the demo is installed, updates come from GitHub instead of uploading the folder:

```bash
git push
deploy/lighthouse/deploy.sh
```

`deploy.sh` logs in to the server, pulls only the changes into `/opt/mamatch-src`, rebuilds and checks health.
It reuses `/opt/mamatch/.env` and the existing Docker volumes, so the database, uploads and passcode stay.
Only what is pushed to GitHub is deployed. Pass a branch name to deploy something other than `main`.

One-time setup so it does not ask for the server password: run `ssh-copy-id ubuntu@43.153.223.242` and enter
the Lighthouse **ubuntu** password once.

## Upload from Joe's Mac — first install

1. Download `mamatch-lighthouse-demo.zip` and double-click it in Finder to extract it.
2. Open the extracted `mamatch-lighthouse-demo` folder.
3. Right-click `UPLOAD_TO_LIGHTHOUSE.command` and choose **Open**. If macOS warns you, confirm **Open** for this
   file you just received from Kimi. Do this only for the original package.
4. Read the server IP shown in the Terminal window. It must be `43.153.223.242`.
5. Type `YES` in capital letters and press Return.
6. The first time, macOS may ask whether to continue connecting. Type `yes` and press Return.
7. When asked for `ubuntu@43.153.223.242`'s password, type the Lighthouse **ubuntu** user password and press
   Return. Nothing appears while typing—this is normal. The script does not save or transmit it anywhere except
   the SSH login to your own server.
8. Wait for Docker to build and start the demo. The first build can take several minutes.
9. On success, save the displayed **Website** and **Outer demo passcode**. The website is
   `https://43.153.223.242.sslip.io`.

If you do not know the server password, use Lighthouse → `mamatch-demo` → **Reset Password**. Confirm that the
username is **ubuntu** (Ubuntu's default Lighthouse username), choose a new strong password, and keep it private.
Do not send it to Kimi or include it in a screenshot. Root login does not need to be enabled.

## Check the Lighthouse firewall if the page does not open

1. Open **Tencent Cloud → Lighthouse → Instances → mamatch-demo → Firewall**.
2. Confirm there are **Allow** rules for **TCP ports 80 and 443**, source **All IPv4 addresses / 0.0.0.0/0**.
3. Keep TCP `22` available for administration.
4. Do **not** add a public rule for PostgreSQL port `5432`, and do not open `ALL` ports.

Official firewall steps: https://www.tencentcloud.com/document/product/1103/41393

## Sign in and test

1. Open `https://43.153.223.242.sslip.io`.
2. Enter the generated outer demo passcode printed by the installer.
3. Open **Sell a business** and submit a uniquely named fictional company.
4. Sign in as the deal manager to verify that the new form record appears internally.
5. Try both `/en/` and `/zh/` and one mobile phone.

After the outer gate, these fictional accounts all use `demo-pass-2026`:

| Role | Email |
|---|---|
| Deal manager | `dm@demo.mamatch.test` |
| Seller | `seller.jade@demo.mamatch.test` |
| Verified buyer | `buyer.huadong@demo.mamatch.test` |
| Pending buyer | `buyer.pending@demo.mamatch.test` |
| Adviser | `adviser@demo.mamatch.test` |

## If you need the demo passcode again

Open the Lighthouse web terminal (`Login` / `OrcaTerm`) on the instance details page and run:

```bash
sudo bash /opt/mamatch/show_login.sh
```

## Useful operator commands

Run these only in the Lighthouse web terminal:

```bash
# See whether both containers are running
cd /opt/mamatch && sudo docker compose -f compose.lighthouse.yaml ps

# View recent logs without printing the secret environment file
cd /opt/mamatch && sudo docker compose -f compose.lighthouse.yaml logs --tail=100

# Restart without deleting form data
cd /opt/mamatch && sudo docker compose -f compose.lighthouse.yaml restart

# Stop the demo without deleting its data
cd /opt/mamatch && sudo docker compose -f compose.lighthouse.yaml stop

# Start it again
cd /opt/mamatch && sudo docker compose -f compose.lighthouse.yaml start
```

Never run `docker compose down -v`: `-v` deletes the database and upload volumes.

## Troubleshooting

| Message or symptom | What to do |
|---|---|
| `Permission denied` after password prompt | Check the server password or reset it in Lighthouse. No files were changed if login failed. |
| macOS will not open the command file | Right-click it → **Open**, rather than double-clicking. |
| `Missing Dockerfile` | Open the extracted package folder itself; do not move the command file elsewhere. |
| Website build is slow | Wait several minutes on the first run; dependencies and PostgreSQL must be downloaded. |
| Website is not ready and logs appear | Save the last error lines as text, without `.env` contents, and return them to Kimi. |
| Browser cannot connect | Confirm the instance is Running, the installer passed, and Lighthouse firewall allows TCP 80 and 443. |
| HTTPS certificate is not ready immediately | Wait two minutes and refresh. If it still fails, check Caddy logs and confirm both web ports are open. |
| Old demo passcode still works after update | Expected: repeat installations preserve the passcode and database. |
| Friends still have the old IP-only address | Ask them to use the new HTTPS address; HTTP requests should redirect automatically. |

## Demo limits and teardown

This is a functional demonstration with HTTPS, not a production launch. The demo accounts are public fixtures;
sign-in throttling, CSRF tokens, deal-manager MFA, malware scanning, monitored backups and legal review are not
complete. Use fictional data only. The free `sslip.io` hostname is a temporary testing dependency, not a substitute
for your own production domain.

To stop future charges, disable auto-renewal and delete/release the Lighthouse instance when finished. Check the
Billing Center afterward. Stopping containers alone does not stop Lighthouse subscription charges.
