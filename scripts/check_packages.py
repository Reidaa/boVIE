"""Install each app's wheels alone and check its deployable interface.

Also run each uv script with only the dependencies in its inline metadata.
"""

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
        ["collector-store-migrate"],
        ["nextcord", "discord_store"],
    ),
    "collector-wttj": (
        "collector-wttj",
        "collector_wttj.main",
        ["collector-store-migrate"],
        ["nextcord", "collector_business_france", "discord_store"],
    ),
    "discord-intake": (
        "discord-intake",
        "discord_intake.main",
        ["discord-store-migrate"],
        ["httpx", "nextcord", "collector_store"],
    ),
    "discord-sender": (
        "discord-sender",
        "discord_sender.main",
        ["discord-store-migrate"],
        ["nats", "nextcord", "collector_store"],
    ),
}
# Operator scripts run with `uv run` and declare their dependencies inline (PEP 723).
SCRIPTS = [Path(__file__).with_name("nats_setup.py")]


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
                    "collector_store"
                    if migration == "collector-store-migrate"
                    else "discord_store"
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


def check_scripts():
    """Fail when a script imports a package that its inline metadata omits."""
    environment = os.environ.copy()
    # PYTHONPATH could expose workspace modules that the script does not declare.
    environment.pop("PYTHONPATH", None)
    for script in SCRIPTS:
        with tempfile.TemporaryDirectory(prefix=f"bovie-{script.stem}-") as temporary:
            subprocess.run(
                ["uv", "run", "--script", str(script), "--help"],
                check=True,
                cwd=temporary,
                env=environment,
                stdout=subprocess.DEVNULL,
            )
        print(json.dumps({"script": script.name, "isolated_run": "passed"}), flush=True)


if __name__ == "__main__":
    check([Path(argument).resolve() for argument in sys.argv[1:]])
    check_scripts()
