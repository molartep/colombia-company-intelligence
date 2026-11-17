#!/usr/bin/env python3
"""Single-server production operations. Requires Python 3.12+, Docker Compose v2.

Never source the env file or print rendered Compose configuration (it contains secrets).
"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Production:
    def __init__(self, env_file):
        env_file = Path(env_file).resolve(strict=True)
        if env_file.stat().st_mode & 0o077:
            raise ValueError("Production env file must be private (chmod 600).")
        self.lock_path = env_file.with_suffix(".operations.lock")
        self.env = dict(os.environ, CCI_ENV_FILE=str(env_file))
        self.command = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(ROOT / "compose.production.yml"),
        ]
        rendered = self.compose("config", "--format", "json", capture_output=True)
        config = json.loads(rendered.stdout)
        settings = config["services"]["backend"]["environment"]
        database = config["services"]["db"]["environment"]
        if not re.fullmatch(r"[a-fA-F0-9]{64}", database["POSTGRES_PASSWORD"]):
            raise ValueError("POSTGRES_PASSWORD must be 64 generated hexadecimal characters.")
        for name in ("POSTGRES_USER", "POSTGRES_DB"):
            if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", database[name]):
                raise ValueError(f"{name} must be a simple lowercase SQL identifier.")
        if not re.fullmatch(
            r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
            settings["PUBLIC_HOSTNAME"],
        ):
            raise ValueError("PUBLIC_HOSTNAME must be a lowercase public DNS hostname.")
        email = config["services"]["web"]["environment"]["ACME_EMAIL"]
        if not re.fullmatch(r"[^\s{}@]+@[^\s{}@]+\.[^\s{}@]+", email) or "example.com" in email:
            raise ValueError("Set ACME_EMAIL to your real email address.")
        self.database = database
        self.release = config["services"]["backend"]["image"]
        self.data = Path(config["x-operations"]["data_dir"])
        if not self.data.is_absolute() or self.data == Path("/"):
            raise ValueError("CCI_DATA_DIR must be an absolute dedicated data directory.")
        self.web_image = config["services"]["web"]["image"]
        self.web_env = config["services"]["web"]["environment"]
        backup = config["x-operations"]["backup_dir"]
        self.backups = Path(backup)
        if not backup or not self.backups.is_absolute() or self.backups == Path("/"):
            raise ValueError("Set an absolute CCI_BACKUP_DIR outside CCI_DATA_DIR.")
        if self.backups.resolve().is_relative_to(self.data.resolve()):
            raise ValueError("Backups must be outside the application data directory.")

    @contextmanager
    def lock(self):
        with self.lock_path.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Another production operation holds the local lock.") from exc
            yield

    def compose(self, *args, **kwargs):
        return run([*self.command, *args], env=self.env, cwd=ROOT, **kwargs)

    def database_command(self, executable, *args, **kwargs):
        return self.compose(
            "exec",
            "-T",
            "db",
            executable,
            "-U",
            self.database["POSTGRES_USER"],
            "-d",
            self.database["POSTGRES_DB"],
            *args,
            **kwargs,
        )

    def snapshot(self):
        self.backups.mkdir(parents=True, exist_ok=True, mode=0o700)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
        target = self.backups / stamp
        target.mkdir(mode=0o700)
        # Caller stops writers first. Dump and artifacts represent one quiescent state.
        with (target / "database.dump").open("wb") as output:
            self.database_command("pg_dump", "--format=custom", "--no-owner", stdout=output)
        # Read through the backend UID; host deployment UID need not own container files.
        with (target / "evidence.tar.gz").open("wb") as output:
            self.compose(
                "run",
                "--rm",
                "--no-deps",
                "-T",
                "backend",
                "python",
                "-c",
                "import sys, tarfile; "
                "t = tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz'); "
                "t.add('/app/var/capital-markets', arcname='capital-markets'); t.close()",
                stdout=output,
            )
        revision = (
            self.database_command(
                "psql",
                "-Atc",
                "SELECT version_num FROM alembic_version",
                capture_output=True,
            )
            .stdout.decode()
            .strip()
        )
        container = (
            self.compose("ps", "-aq", "backend", capture_output=True).stdout.decode().strip()
        )
        previous_release = self.release
        if container:
            previous_release = (
                run(
                    ["docker", "inspect", "--format", "{{.Config.Image}}", container],
                    capture_output=True,
                )
                .stdout.decode()
                .strip()
            )
        manifest = {
            "created_at": datetime.now(UTC).isoformat(),
            "release": previous_release,
            "migration_revision": revision,
            "sha256": {
                name: digest(target / name) for name in ("database.dump", "evidence.tar.gz")
            },
        }
        (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"Backup complete: {target}. Copy this directory to private off-VM storage.")
        return target

    def backup(self):
        running = self.compose("ps", "--services", "--status", "running", capture_output=True)
        resume = [
            name for name in running.stdout.decode().splitlines() if name in ("web", "backend")
        ]
        self.compose("stop", "web", "backend")
        try:
            return self.snapshot()
        finally:
            if resume:
                self.compose("start", *resume)

    def deploy(self, initial):
        self.compose("build", "--pull", "backend", "web")
        # Validate Settings and the Caddyfile before stopping the existing release.
        self.compose(
            "run",
            "--rm",
            "--no-deps",
            "backend",
            "python",
            "-c",
            "from app.core.config import get_settings; get_settings()",
        )
        run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "-e",
                f"PUBLIC_HOSTNAME={self.web_env['PUBLIC_HOSTNAME']}",
                "-e",
                f"ACME_EMAIL={self.web_env['ACME_EMAIL']}",
                self.web_image,
                "caddy",
                "validate",
                "--config",
                "/etc/caddy/Caddyfile",
                "--adapter",
                "caddyfile",
            ]
        )
        check = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "-v",
                f"{self.data / 'postgres'}:/check:ro",
                "postgres:16-alpine",
                "test",
                "-f",
                "/check/PG_VERSION",
            ],
            capture_output=True,
            check=False,
        )
        if check.returncode not in (0, 1):
            raise ValueError("Could not inspect database initialization state.")
        initialized = check.returncode == 0
        if initial and initialized:
            raise ValueError("--initial cannot be used with an existing database.")
        if not initial and not initialized:
            raise ValueError("First deployment requires --initial and an empty database directory.")
        self.compose("stop", "web", "backend")
        # Do not recreate an existing DB before its backup (a tag update may restart it).
        if not initial:
            self.snapshot()
        self.compose("up", "-d", "--wait", "--wait-timeout", "120", "db")
        self.compose(
            "run",
            "--rm",
            "--no-deps",
            "--user",
            "root",
            "backend",
            "sh",
            "-c",
            "chown cci:cci /app/var/capital-markets",
        )
        self.compose("run", "--rm", "migrate")
        self.compose("up", "-d", "--wait", "--wait-timeout", "180", "backend", "web")
        self.compose(
            "exec",
            "-T",
            "backend",
            "python",
            "-c",
            "import urllib.request; "
            "urllib.request.urlopen('http://localhost:8000/ready', timeout=5)",
        )
        print("Stack ready. Verify public HTTPS and live sources before announcing the release.")


def restore_check(directory):
    """Restore only into a disposable isolated container, never a production DB."""
    directory = Path(directory).resolve(strict=True)
    manifest = json.loads((directory / "manifest.json").read_text())
    for name in ("database.dump", "evidence.tar.gz"):
        if digest(directory / name) != manifest["sha256"][name]:
            raise ValueError(f"Backup checksum mismatch: {name}")
    name = "cci-restore-" + uuid.uuid4().hex[:12]
    try:
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--network",
                "none",
                "--tmpfs",
                "/var/lib/postgresql/data",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "--health-cmd",
                "pg_isready -h 127.0.0.1 -U postgres",
                "--health-interval",
                "1s",
                "--health-retries",
                "60",
                "postgres:16-alpine",
            ],
            capture_output=True,
        )
        # A bounded readiness wait; no production ports or volume mounts.
        run(
            [
                "docker",
                "exec",
                name,
                "sh",
                "-c",
                "i=0; until pg_isready -h 127.0.0.1 -U postgres; do i=$((i+1)); "
                "[ $i -lt 60 ] || exit 1; sleep 1; done",
            ],
            capture_output=True,
        )
        with (directory / "database.dump").open("rb") as source:
            run(
                [
                    "docker",
                    "exec",
                    "-i",
                    name,
                    "pg_restore",
                    "-U",
                    "postgres",
                    "-d",
                    "postgres",
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                ],
                stdin=source,
            )
        result = run(
            [
                "docker",
                "exec",
                name,
                "psql",
                "-U",
                "postgres",
                "-Atc",
                "SELECT version_num FROM alembic_version",
            ],
            capture_output=True,
        )
        if result.stdout.decode().strip() != manifest["migration_revision"]:
            raise ValueError("Restored migration revision differs from the backup.")
        with tempfile.TemporaryDirectory(prefix="cci-evidence-check-") as temp:
            with tarfile.open(directory / "evidence.tar.gz") as archive:
                archive.extractall(temp, filter="data")
            if not (Path(temp) / "capital-markets").is_dir():
                raise ValueError("Evidence archive is missing capital-markets directory.")
        print(
            "Restore check passed: checksums, PostgreSQL restore, "
            "migration revision, evidence extraction."
        )
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default="/etc/cci/production.env")
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("validate")
    deploy = sub.add_parser("deploy")
    deploy.add_argument("--initial", action="store_true")
    backup = sub.add_parser("backup")
    backup.add_argument(
        "--offsite",
        help="Private rsync-over-SSH destination, e.g. backup@host:/backups/cci/",
    )
    backup.add_argument("--keep-days", type=int, default=14)
    restore = sub.add_parser("restore-check")
    restore.add_argument("directory")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        if args.operation == "restore-check":
            restore_check(args.directory)
            return
        production = Production(args.env_file)
        with production.lock():
            if args.operation == "validate":
                print("Production configuration valid; secrets were not printed.")
            elif args.operation == "deploy":
                production.deploy(args.initial)
            else:
                if args.keep_days < 1:
                    raise ValueError("--keep-days must be positive.")
                target = production.backup()
                restore_check(target)
                if args.offsite:
                    if args.offsite.startswith("-") or ":" not in args.offsite:
                        raise ValueError("--offsite must be an rsync SSH destination.")
                    cutoff = datetime.now(UTC) - timedelta(days=args.keep_days)
                    complete = sorted(
                        p
                        for p in production.backups.iterdir()
                        if p.is_dir()
                        and not p.is_symlink()
                        and re.fullmatch(r"[0-9]{8}T[0-9]{6}-[a-f0-9]{8}", p.name)
                        and (p / "manifest.json").is_file()
                    )
                    # Transfer prior deployment snapshots and failed uploads before pruning.
                    run(
                        [
                            "rsync",
                            "-a",
                            "-e",
                            "ssh -oBatchMode=yes -oConnectTimeout=15",
                            "--",
                            *(str(p) for p in complete),
                            args.offsite,
                        ]
                    )
                    # Retention runs only after successful off-VM transfer; keep at least two.
                    for old in complete[:-2]:
                        created = datetime.fromisoformat(
                            json.loads((old / "manifest.json").read_text())["created_at"]
                        )
                        if created < cutoff:
                            shutil.rmtree(old)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        # Never echo command arguments, rendered configuration, or env contents.
        if isinstance(exc, subprocess.CalledProcessError):
            parser.exit(
                1,
                "Operation failed. Inspect service state before resuming; "
                "deployment writers may be stopped.\n",
            )
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
