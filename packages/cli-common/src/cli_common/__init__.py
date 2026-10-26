"""Entrypoint environment loading and redacted failure logging."""

import sys
import traceback

import click
from dotenv import load_dotenv
from loguru import logger


def configure_logging(debug: bool = False):
    """Send errors to stderr and everything else to stdout.

    Railway shows every stderr line as an error, so normal logs must not use it.
    """
    load_dotenv(".env", override=False)
    error = logger.level("ERROR").no
    logger.remove()
    logger.add(
        sys.stdout,
        level="DEBUG" if debug else "INFO",
        filter=lambda record: record["level"].no < error,
        diagnose=False,
    )
    logger.add(sys.stderr, level=error, diagnose=False)


def log_failure(error: Exception, operation: str):
    # Keep stack frames without exception messages or local values containing secrets.
    logger.error(
        "{} failed ({}).\n{}",
        operation,
        type(error).__name__,
        "".join(traceback.format_tb(error.__traceback__)),
    )


class EnvironmentCommand(click.Command):
    """Load the working directory's .env before Click resolves envvar options."""

    def parse_args(self, ctx, args):
        load_dotenv(".env", override=False)
        return super().parse_args(ctx, args)
