# Oracle single-VM production deployment

This configuration retains Postgres, registration UUIDs, browser retrieval and private source
artifacts. It is a single-server deployment with brief maintenance downtime, not high availability.
Use Ubuntu 24.04 ARM64, Docker Engine with Compose v2, Python 3.12+, Git and rsync.
The production stack is **standalone**: never merge it with `docker-compose.yml`.

## Hostname and Cloudflare

The example hostname is **molartep.cci.com**. You must control the `cci.com` DNS zone or have a
delegation for this subdomain. Otherwise select a hostname in a domain you control and change
`PUBLIC_HOSTNAME`; no frontend rebuild-specific API URL is needed.

In Cloudflare DNS for `cci.com`, create:

| Type | Name | Value | Proxy |
| --- | --- | --- | --- |
| A | `molartep` | Oracle VM public IPv4 address | **DNS only** (gray cloud) |

Do not create an AAAA record unless IPv6 is configured end to end. Remove conflicting records.
Allow time for DNS propagation before launching Caddy. Caddy obtains and renews public HTTPS
certificates; retain `/srv/cci/caddy`. No Cloudflare API token, Worker, Tunnel, or Origin Certificate
is needed. Restrictive CAA records must permit Caddy's selected public certificate authority.

**Keep the record DNS only with this configuration.** Orange-cloud proxying would make the
application see Cloudflare egress IPs and group unrelated users into the same request bucket.
Supporting it later requires explicit, maintained Cloudflare proxy trust in Caddy and an origin
firewall policy. Never trust arbitrary incoming `X-Forwarded-For`/`CF-Connecting-IP` headers.

## Oracle and host preparation

1. Allocate an Always Free eligible A1 VM within the account's actual allowances. A starting size
   is 2 OCPUs/12 GB, subject to console eligibility and capacity. Validate upstream access from its IP.
2. Mount a persistent data volume at `/srv/cci` via its UUID in `/etc/fstab`; verify reboot mounting.
   Preserve the boot-plus-block-volume free allowance. Prefer a stable public IP for DNS.
3. In the OCI security list/NSG and host firewall, allow inbound TCP 80 and 443 publicly. Restrict
   TCP 22 to your administrative IP. Do not open 5432, 8000, 5173, or Caddy's admin port 2019.
   Keep outbound HTTPS and DNS available. Docker-published ports require OCI filtering too; do not
   assume a host firewall alone controls them.
4. Install Docker Engine/Compose from official packages, Python 3.12 and rsync. Enable Docker at boot.
   Create a deployment user `cci` with Docker access (Docker access is effectively root access).
5. Clone the repository at `/opt/cci`, owned by `cci`. Create private directories:

   ```sh
   sudo install -d -m 700 -o cci -g cci /etc/cci /srv/cci /srv/cci-backups
   sudo install -d -m 700 -o cci -g cci /srv/cci/capital-markets
   sudo install -m 600 -o cci -g cci /opt/cci/.env.production.example /etc/cci/production.env
   ```

Do not change the mounted filesystem's ownership recursively once Postgres has initialized.
The deployment script initializes backend evidence-directory ownership; the Postgres entrypoint
initializes its own subdirectory. If custom mount paths are used, update systemd `RequiresMountsFor`.
Check that Docker's fixed proxy subnet `172.29.84.0/24` does not overlap your VCN/VPN/host routes;
if changing it, update Caddy's static IP and Uvicorn's trusted proxy IP together.

## Environment and initial deployment

Edit `/etc/cci/production.env` as the deployment user:

- Set `ACME_EMAIL` to your real email and confirm `PUBLIC_HOSTNAME`.
- Generate `POSTGRES_PASSWORD` with `openssl rand -hex 32`. Use exactly those 64 hex characters.
  It is interpolated into the internal database URL. Do not use the development password.
- Set `RELEASE_TAG` to the checkout's commit identifier (for example, `git rev-parse --short HEAD`).
  Keep this env-file tag current so reboots start the intended release.
- Confirm absolute `CCI_DATA_DIR` and `CCI_BACKUP_DIR`; keep backups outside the data directory.
- Optionally configure the server-only Socrata token. No secret belongs in a `VITE_` variable.

Do not shell-source this file. Run from `/opt/cci`, as `cci`:

```sh
python3 scripts/production.py validate
python3 scripts/production.py deploy --initial
```

`--initial` refuses an existing initialized database. The script builds both images, validates
backend settings and Caddy configuration, starts Postgres, applies migrations, and waits for the
API and web container health checks. Caddy's internal health check verifies its admin listener;
it does not prove public DNS or certificate issuance succeeded. Check public HTTPS separately:

```sh
curl --fail https://molartep.cci.com/
curl --fail https://molartep.cci.com/api/v1/parameters
```

Also open a deep-linked profile route, perform a bounded real RUES search, and verify capital-markets
source access. The imported RNVE directory is not seeded automatically: follow `capital-markets.md`
to import the official export administratively. Source failures must retain their existing meaning.

Only the web service publishes host ports. The API preserves `/api`, accepts forwarded client
addresses only from Caddy's fixed private IP, and disables public API docs. Postgres remains on
an internal Docker network. The web image contains only static assets and Caddy configuration.

## Public request controls

Production settings refuse wildcard hosts, development CORS origins, weak database passwords and
disabled request controls. Limits are fixed windows, per API process:

| Control | Default |
| --- | --- |
| All `/api/v1/*` requests per client | 120/minute |
| Searches per client | 30/minute |
| Manual refreshes per client | 6/minute |
| Manual refreshes per company, across clients and sources | Once per 60 seconds |
| Limiter entries | 10,000; new keys fail closed when full |

The company cooldown intentionally covers both Overview and all Capital Markets source selectors.
Normal cached reads are not blocked by that cooldown. Automatic first-load retrieval still uses
the existing cache/cooldown/connector limits. Returning 429 includes `Retry-After`; API responses
remain `no-store`. State is memory-only, bounded, and resets on restart. **Run one API worker**;
multiple replicas/workers would require a shared admission store. This is basic workload admission,
not an identity-based quota or comprehensive DDoS service. Users behind NAT share a client bucket.

No proxy access log is enabled, and Uvicorn access logging stays disabled. Docker logs rotate.
Private evidence and database files never enter the frontend build or static file root. Watch disk
growth: source history has no automatic deletion policy. Do not prune evidence referenced by DB rows.

## Updates and rollback

Check out a reviewed commit and set a new `RELEASE_TAG` in the private env file. Then:

```sh
python3 scripts/production.py deploy
```

Build and configuration failures occur before stopping the old release. During deployment,
web/API writers stop, a consistent database/evidence snapshot is saved, migrations run, then
services restart. A later failure leaves the writers stopped for investigation rather than
automatically starting an old application against a possibly changed schema. Do not run administrative
imports or another deployment/backup concurrently. Scripts take a local operations lock.

Keep old application images until a new release is verified; do not run indiscriminate image/volume
pruning. Database tag changes require separate review. Updating `POSTGRES_PASSWORD` in the env file
does not rotate an existing database role password: coordinate an explicit SQL password rotation.

If schema compatibility is confirmed, select the old image tag in the env file and start the old
backend/web without rebuilding. Otherwise restore the matching predeployment snapshot and deploy
the matching code. Do not assume `alembic downgrade` is a lossless rollback.

## Backups, verification, and recovery

```sh
python3 scripts/production.py backup
python3 scripts/production.py restore-check /srv/cci-backups/REPLACE_WITH_BACKUP_DIRECTORY
```

Backup briefly stops application writers, takes a custom-format Postgres dump and a private evidence
archive, then resumes only the services previously running. It verifies SHA-256 checksums, restores
the dump into a disposable, network-isolated Postgres container, compares Alembic revision and checks
evidence extraction. This container has no production volumes or published ports. Reserve sufficient
RAM/disk for restore verification. Partial backups have no completed manifest and are not valid.

Backups remain private (umask 077). Copy them off the VM; a directory on the same VM is not a recovery
strategy. To upload over SSH and apply local retention only after successful transfer:

```sh
python3 scripts/production.py backup --offsite backup@YOUR_BACKUP_HOST:/private/backups/cci/ --keep-days 14
```

Configure SSH keys and verified host keys for `cci` first. The destination must be private and have
adequate space; manage its retention separately. Local pruning preserves at least the latest two
completed snapshots. Offsite copy is optional in the command, but required before calling a deployment
recoverable. If upload or verification fails, no automatic retention deletion occurs. The snapshot
contains private source records; do not place it in a public bucket or commit it.

For an actual disaster recovery, restore on a fresh data directory/VM, not over the working database:

1. Copy a complete backup directory privately to the new machine; run `restore-check`.
2. Check out the recorded release (the manifest records the old backend image tag) and configure
   private env values. Build matching images. Start only the empty Postgres service, without migrations.
3. Use `docker compose ... exec -T db pg_restore -U cci -d cci --no-owner --no-privileges --exit-on-error`
   with `database.dump` redirected to stdin. Substitute your configured role/database names.
   Here `...` means `--env-file /etc/cci/production.env -f /opt/cci/compose.production.yml`, with
   `CCI_ENV_FILE=/etc/cci/production.env` exported (the path only, not secrets).
4. Extract `evidence.tar.gz` under the new `CCI_DATA_DIR` using Python `tarfile` with `filter="data"`;
   it contains the `capital-markets` directory. Restore ownership for the container's `cci` user.
5. Run a normal deployment to validate/apply only the matching or reviewed newer migrations. Verify
   profiles, evidence, browser runtime, public HTTPS and upstream retrieval before changing DNS.

## Boot and backup scheduling

After a successful initial deployment, install `cci.service`, `cci-backup.service`, and
`cci-backup.timer` from `deploy/systemd` into `/etc/systemd/system`, then:

```sh
sudo systemctl daemon-reload
sudo systemctl enable cci.service
```

The application unit requires the mounted data directory and starts already-built images. Docker
restart policies also recover services; systemd does not replace checking a failed/unhealthy service.
Docker starts before this unit, so configure Docker itself to require the data mount as well: create
`/etc/systemd/system/docker.service.d/cci-mount.conf` using the provided
`deploy/systemd/docker-cci-mount.conf`, and run `systemctl daemon-reload` again.
This dedicated VM must not start Docker before its data disk mounts.

For scheduled offsite backups, create `/etc/cci/backup.env`, mode 600 owned by `cci`, containing
`CCI_BACKUP_TARGET=backup@YOUR_BACKUP_HOST:/private/backups/cci/`. Test the backup service manually,
then enable `cci-backup.timer`. It runs around **03:15 America/Bogota** daily and catches missed runs.
Use `systemctl list-timers`, `systemctl status cci-backup.service`, and `journalctl -u cci-backup.service`
to check success. Run a VM reboot test and an off-VM recovery drill before announcing availability.

## Validation coverage and limits

CI runs a production smoke job on x86-64 and ARM64. It uses a local test hostname and local TLS CA,
verifies browser launch, SPA/static/API routing, disabled public readiness/docs, 429 responses,
private DB/API ports, recreation persistence, and real backup restoration. It makes no live government
requests. Public DNS, ACME certificate issuance, Oracle security rules, mount order and publisher
access from the Oracle IP remain deployment-time checks.
