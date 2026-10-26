from loguru import logger


def test_errors_go_to_stderr_and_the_rest_to_stdout(capsys):
    # Railway shows every stderr line as an error, so normal logs use stdout.
    from cli_common import configure_logging

    configure_logging(debug=True)
    logger.debug("debug message")
    logger.info("info message")
    logger.error("error message")
    logger.remove()

    captured = capsys.readouterr()
    assert "debug message" in captured.out
    assert "info message" in captured.out
    assert "error message" not in captured.out
    assert "error message" in captured.err
    assert "info message" not in captured.err


def test_debug_messages_are_hidden_by_default(capsys):
    from cli_common import configure_logging

    configure_logging()
    logger.debug("debug message")
    logger.remove()
    assert "debug message" not in capsys.readouterr().out
