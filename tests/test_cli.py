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


def test_wttj_cli_defaults_and_optional_contract_filters(tmp_path, monkeypatch):
    from wttf import main

    monkeypatch.chdir(tmp_path)
    for name in ("WTTJ_QUERY", "WTTJ_CONTRACTS", "WTTJ_LIMIT", "WTTJ_MAX_PAGES"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://u:p@localhost/source")
    observed = []

    class Engine:
        def dispose(self):
            pass

    monkeypatch.setattr(main, "make_engine", lambda url: Engine())
    monkeypatch.setattr(
        main, "collect", lambda engine, client, **kwargs: observed.append(kwargs)
    )
    result = CliRunner().invoke(main.main)
    assert result.exit_code == 0, result.output
    assert observed[-1]["query"] == ""
    assert observed[-1]["contracts"] == ()
    (tmp_path / ".env").write_text(
        "WTTJ_QUERY=engineer\nWTTJ_CONTRACTS=full_time internship\n"
    )
    result = CliRunner().invoke(main.main)
    assert result.exit_code == 0, result.output
    assert observed[-1]["query"] == "engineer"
    assert observed[-1]["contracts"] == ("full_time", "internship")
    result = CliRunner().invoke(
        main.main, ["--contract", "FREELANCE", "--country", "ca"]
    )
    assert result.exit_code == 0, result.output
    assert observed[-1]["contracts"] == ("freelance",)
    assert observed[-1]["countries"] == ("CA",)
