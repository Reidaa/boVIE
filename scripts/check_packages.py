"""Install each app's wheels alone and check its deployable interface."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SERVICES = {
    "collector-business-france": (
        "collector-business-france",
        "collector_business_france.main",
        ["source-migrate"],
        ["nextcord", "notification_store"],
    ),
    "collector-wttj": (
        "collector-wttj",
        "collector_wttj.main",
        ["source-migrate"],
        ["nextcord", "collector_business_france", "notification_store"],
    ),
    "discord-intake": (
        "discord-intake",
        "discord_intake.main",
        ["notification-migrate"],
        ["httpx", "nextcord", "source_store"],
    ),
    "discord-sender": (
        "discord-sender",
        "discord_sender.main",
        ["notification-migrate"],
        ["nats", "nextcord", "source_store"],
    ),
    "nats-setup": (
        "nats-setup",
        "nats_setup.main",
        [],
        ["sqlalchemy", "httpx", "source_store", "notification_store"],
    ),
}


def check(roots: list[Path]):
    dists = sorted(path for root in roots for path in root.glob("*/dist"))
    links = [argument for dist in dists for argument in ("--find-links", str(dist))]
    # Workspace wheels keep one version across builds; never reuse a cached copy.
    refresh = [
        argument
        for dist in dists
        for wheel in dist.glob("*.whl")
        for argument in ("--refresh-package", wheel.name.split("-")[0])
    ]
    environment = os.environ.copy()
    for key in ("DATABASE_URL", "DISCORD_WEBHOOK_URL", "PYTHONPATH"):
        environment.pop(key, None)
    for service, (command, module, migrations, forbidden) in SERVICES.items():
        wheel = [
            path
            for dist in dists
            for path in dist.glob(
                f"bovie_{service.replace('-', '_')}-*-py3-none-any.whl"
            )
        ]
        if len(wheel) != 1:
            raise ValueError(f"Expected exactly one {service} wheel in {dists}")
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
                    *links,
                    *refresh,
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
            if service == "collector-business-france":
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
    check([Path(argument).resolve() for argument in sys.argv[1:]])
