from contextlib import contextmanager
from threading import Thread, current_thread
from typing import Iterator

import structlog
from django.db import connection

log = structlog.get_logger(__name__)


@contextmanager
def handle_exception() -> Iterator[None]:
    thread = current_thread()
    try:
        yield
    except Exception as e:
        log.exception(f"T{thread.name}: Got an exception in thread")
    finally:
        connection.close()
        log.info(f"T{thread.name}: Closed connection")


@contextmanager
def run_threads(threads: list[Thread]) -> Iterator[None]:
    for thread in threads:
        log.info(f"Main: Starting thread {thread.name}")
        thread.start()
    try:
        yield
    finally:
        for thread in threads:
            log.info(f"Main: Waiting for thread {thread.name} to stop")
            thread.join(timeout=2)

        for thread in threads:
            if thread.is_alive():
                log.info(f"Main: Failed to stop thread {thread.name}")
            else:
                log.info(f"Main: Thread {thread.name} has stopped")


def get_current_txid() -> int:
    assert connection.in_atomic_block
    with connection.cursor() as cursor:
        cursor.execute("select adjusted_txid_current();")
        row = cursor.fetchone()
        assert isinstance(row[0], int)
        return row[0]
