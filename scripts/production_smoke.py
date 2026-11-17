"""CI-only production-stack checks, using synthetic local data and a local TLS CA.

Run on a disposable Linux Docker host with ports 80/443 free. Never use on the VM.
"""

import json
import os
import secrets
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    return subprocess.run(args, check=True, cwd=ROOT, **kwargs)


def main():
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="cci-production-smoke-") as temp:
        work = Path(temp)
        (work / "data" / "capital-markets").mkdir(parents=True)
        env_file = work / "production.env"
        env_file.write_text(
            "PUBLIC_HOSTNAME=cci.test\nACME_EMAIL=ci@cci.test\nRELEASE_TAG=ci\n"
            f"CCI_DATA_DIR={work}/data\nCCI_BACKUP_DIR={work}/backups\n"
            f"POSTGRES_USER=cci\nPOSTGRES_DB=cci\nPOSTGRES_PASSWORD={secrets.token_hex(32)}\n"
        )
        env = dict(os.environ, CCI_ENV_FILE=str(env_file))
        caddy = work / "Caddyfile"
        caddy.write_text(
            (ROOT / "frontend/Caddyfile")
            .read_text()
            .replace("{$PUBLIC_HOSTNAME} {", "{$PUBLIC_HOSTNAME} {\n    tls internal")
        )
        override = work / "smoke.json"
        override.write_text(
            json.dumps(
                {
                    "services": {
                        "web": {
                            "volumes": [
                                {
                                    "type": "bind",
                                    "source": str(caddy),
                                    "target": "/etc/caddy/Caddyfile",
                                    "read_only": True,
                                }
                            ]
                        }
                    }
                }
            )
        )
        compose = [
            "docker",
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(ROOT / "compose.production.yml"),
            "-f",
            str(override),
        ]

        def dc(*args, **kwargs):
            return run([*compose, *args], env=env, **kwargs)

        try:
            run(
                [
                    sys.executable,
                    "scripts/production.py",
                    "--env-file",
                    str(env_file),
                    "validate",
                ]
            )
            dc("build", "backend", "web")
            dc("up", "-d", "--wait", "db")
            dc(
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
            dc("run", "--rm", "migrate")
            dc("up", "-d", "--wait", "--wait-timeout", "180", "backend", "web")
            dc(
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                "import asyncio\nfrom playwright.async_api import async_playwright\n"
                "async def check():\n"
                " async with async_playwright() as p:\n"
                "  b = await p.chromium.launch(channel='chromium', headless=True)\n"
                "  await b.close()\n"
                "asyncio.run(check())",
            )
            dc(
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                "from pathlib import Path; "
                "Path('/app/var/capital-markets/synthetic.txt').write_text('synthetic evidence')",
            )
            # Caddy uses a CI-only internal CA. Public deployment always uses normal validation.
            context = ssl._create_unverified_context()
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({}),
                urllib.request.HTTPSHandler(context=context),
            )

            def fetch(path):
                try:
                    return opener.open("https://cci.test" + path, timeout=10)
                except urllib.error.HTTPError as response:
                    return response

            assert fetch("/").status == 200
            assert fetch("/companies/00000000-0000-0000-0000-000000000001").status == 200
            html = fetch("/").read().decode()
            import re

            asset = re.search(r'src="(/assets/[^\"]+\.js)"', html).group(1)
            assert "immutable" in fetch(asset).headers["Cache-Control"]
            assert fetch("/assets/missing.js").status == 404
            assert fetch("/docs").status == 404
            assert fetch("/ready").status == 404
            assert fetch("/api/v1/unknown").status == 404
            assert fetch("/api/v1/parameters").status == 200
            for _ in range(120):
                result = fetch("/api/v1/parameters")
                result.close()
            result = fetch("/api/v1/parameters")
            assert result.status == 429 and int(result.headers["Retry-After"]) > 0
            config = json.loads(dc("config", "--format", "json", capture_output=True).stdout)
            assert not config["services"]["backend"].get("ports")
            assert not config["services"]["db"].get("ports")
            run(
                [
                    sys.executable,
                    "scripts/production.py",
                    "--env-file",
                    str(env_file),
                    "backup",
                ]
            )
            # A container recreation must retain both DB and evidence, without upstream calls.
            dc("up", "-d", "--force-recreate", "--wait", "db", "backend")
            dc(
                "exec",
                "-T",
                "backend",
                "python",
                "-c",
                "from pathlib import Path; "
                "assert Path('/app/var/capital-markets/synthetic.txt').read_text() "
                "== 'synthetic evidence'",
            )
            print(
                "Production smoke passed: TLS, SPA/API routing, limits, "
                "browser runtime, persistence, backup restore."
            )
        finally:
            dc("down", "-v", "--remove-orphans")
            # PostgreSQL owns its bind mount as a container UID; clean it using that image.
            run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{work}:/cleanup",
                    "postgres:16-alpine",
                    "sh",
                    "-c",
                    "rm -rf /cleanup/data /cleanup/backups",
                ]
            )


if __name__ == "__main__":
    main()
