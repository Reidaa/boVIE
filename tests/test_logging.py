from io import StringIO

from loguru import logger

from bovie.logging import configure_logging


def test_error_logs_use_stderr_only():
    stdout = StringIO()
    stderr = StringIO()

    configure_logging(debug=False, stdout=stdout, stderr=stderr)
    logger.info("info message")
    logger.error("error message")
    logger.remove()

    assert "info message" in stdout.getvalue()
    assert "error message" not in stdout.getvalue()
    assert "error message" in stderr.getvalue()
    assert "info message" not in stderr.getvalue()
