"""Install each service's wheels alone and check its deployable interface."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SERVICES = {
    "business-france": (
        "bovie",
        "bovie.main",
        ["source-migrate"],
        ["nats", "nextcord", "notification_store"],
    ),
    "wttj": (
        "wttf",
        "wttf.main",
        ["source-migrate"],
        ["nats", "nextcord", "bovie", "notification_store"],
    ),
    "outbox-relay": (
        "outbox-relay",
        "outbox_relay.main",
        ["source-migrate"],
        ["httpx", "nextcord", "notification_store"],
    ),
    "notification-intake": (
        "notification-intake",
        "notification_intake.main",
        ["notification-migrate"],
        ["httpx", "nextcord", "source_store"],
    ),
    "discord-delivery": (
        "discord-delivery",
        "discord_delivery.main",
        ["notification-migrate"],
        ["nats", "nextcord", "source_store"],
    ),
    "broker-setup": (
        "broker-setup",
        "broker_setup.main",
        [],
        ["sqlalchemy", "httpx", "source_store", "notification_store"],
    ),
}


def check(wheels: Path):
    environment = os.environ.copy()
    for key in ("DATABASE_URL", "DISCORD_WEBHOOK_URL", "PYTHONPATH"):
        environment.pop(key, None)
    for service, (command, module, migrations, forbidden) in SERVICES.items():
        wheel = list(
            wheels.glob(f"bovie_{service.replace('-', '_')}-*-py3-none-any.whl")
        )
        if len(wheel) != 1:
            raise ValueError(f"Expected exactly one {service} wheel in {wheels}")
        with tempfile.TemporaryDirectory(prefix=f"bovie-{service}-") as temporary:
            directory = Path(temporary)
            venv = directory / ".venv"
            subprocess.run(
                ["uv", "venv", "--python", sys.executable, str(venv)], check=True
            )
            python = venv / "bin/python"
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    str(python),
                    "--find-links",
                    str(wheels),
                    str(wheel[0]),
                ],
                check=True,
            )
            blocked = forbidden + [
                entry[1].split(".")[0]
                for name, entry in SERVICES.items()
                if name != service
            ]
            probe = f"""
import importlib, importlib.util
importlib.import_module({module!r})
for module in {blocked!r}:
    assert importlib.util.find_spec(module) is None, f'Unexpected dependency: {{module}}'
"""
            for migration in migrations:
                owner = (
                    "source_store"
                    if migration == "source-migrate"
                    else "notification_store"
                )
                probe += f"""
from importlib.resources import files
assert list((files({owner!r}) / 'migrations' / 'versions').iterdir())
importlib.import_module({(owner + ".migrate")!r})
"""
            subprocess.run(
                [str(python), "-I", "-c", probe],
                check=True,
                cwd=directory,
                env=environment,
            )
            for entrypoint in [command, *migrations]:
                subprocess.run(
                    [str(venv / "bin" / entrypoint), "--help"],
                    check=True,
                    cwd=directory,
                    env=environment,
                    stdout=subprocess.DEVNULL,
                )
            if service == "business-france":
                subprocess.run(
                    [str(venv / "bin" / command), "--version"],
                    check=True,
                    cwd=directory,
                    env=environment,
                )
            print(
                json.dumps(
                    {
                        "service": service,
                        "isolated_install": "passed",
                        "commands": [command, *migrations],
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    check(Path(sys.argv[1]).resolve())
