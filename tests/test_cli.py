from pathlib import Path

from click.testing import CliRunner
from dotenv import dotenv_values


def test_cli_loads_dotenv_before_resolving_options(tmp_path, monkeypatch):
    from bovie import main

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "BOVIE_LIMIT=7\nDATABASE_URL=mysql+pymysql://u:p@localhost/source\n"
    )
    monkeypatch.delenv("BOVIE_LIMIT", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    observed = []

    class Engine:
        def dispose(self):
            pass

    monkeypatch.setattr(main, "make_engine", lambda url: Engine())
    monkeypatch.setattr(
        main, "task", lambda params, engine: observed.append(params.limit)
    )
    result = CliRunner().invoke(main.cli)
    assert result.exit_code == 0, result.output
    assert observed == [7]


def test_example_environment_is_accepted(monkeypatch):
    from bovie import main

    values = dotenv_values(Path(__file__).parents[1] / ".env.example")
    for name, value in values.items():
        if value is not None:
            monkeypatch.setenv(name, value)

    class Engine:
        def dispose(self):
            pass

    observed = []
    monkeypatch.setattr(main, "make_engine", lambda url: Engine())
    monkeypatch.setattr(main, "task", lambda params, engine: observed.append(params))
    result = CliRunner().invoke(main.cli)
    assert result.exit_code == 0, result.output
    assert observed[0].limit == 25
    assert observed[0].countriesIds
