import pytest
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, select

from tests.test_storage import event


def test_failed_delivery_insert_rolls_back_inbox(discord_db):
    from discord_store import Delivery, Inbox, accept

    def fail_delivery(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO deliveries"):
            raise RuntimeError("injected failure before delivery insert")

    sqlalchemy_event.listen(discord_db, "before_cursor_execute", fail_delivery)
    try:
        with pytest.raises(RuntimeError):
            accept(discord_db, event())
    finally:
        sqlalchemy_event.remove(discord_db, "before_cursor_execute", fail_delivery)
    with discord_db.connect() as conn:
        for model in (Delivery, Inbox):
            assert conn.scalar(select(func.count()).select_from(model)) == 0
