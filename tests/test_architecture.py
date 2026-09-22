"""Keep deployable services independent as the workspace grows."""

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_workspace_imports_follow_declared_dependencies():
    projects = {}
    for manifest in [
        *ROOT.glob("services/*/pyproject.toml"),
        *ROOT.glob("packages/*/pyproject.toml"),
    ]:
        config = tomllib.loads(manifest.read_text())
        projects[config["tool"]["uv"]["build-backend"]["module-name"]] = (
            manifest.parent,
            config["project"],
        )
    for module, (directory, project) in projects.items():
        for path in (directory / "src").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    imports = [node.module or ""]
                else:
                    continue
                for imported in imports:
                    target = imported.split(".")[0]
                    if target == module or target not in projects:
                        continue
                    target_dir, target_project = projects[target]
                    assert target_dir.parent.name == "packages", (
                        f"{path} imports deployable service {target}; use a library or events"
                    )
                    assert target_project["name"] in project["dependencies"], (
                        f"{path} imports undeclared workspace dependency {target}"
                    )


def test_services_do_not_depend_on_other_services():
    manifests = list(ROOT.glob("services/*/pyproject.toml"))
    names = {tomllib.loads(path.read_text())["project"]["name"] for path in manifests}
    for path in [*manifests, *ROOT.glob("packages/*/pyproject.toml")]:
        project = tomllib.loads(path.read_text())["project"]
        assert not names.intersection(project["dependencies"]), path
