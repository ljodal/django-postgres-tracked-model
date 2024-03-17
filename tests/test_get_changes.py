from threading import Event, Thread

import pytest
import structlog
from django.db import transaction
from django.db.models import F

from demo.models import MyModel
from tracked_model import get_changed_objects

from .utils import get_current_txid, handle_exception, run_threads

log = structlog.get_logger(__name__)


@pytest.mark.django_db(transaction=True)
def test_get_changes() -> None:

    m1 = MyModel.objects.create(number=10)
    m2 = MyModel.objects.create(number=11)
    m1.number -= 1
    m1.save(update_fields=["number"])

    qs = MyModel.objects.values("id", "number", version=F("version_info__version"))

    changes, cursor = get_changed_objects(cursor=None, limit=1, queryset=qs)
    assert changes == [{"id": m2.id, "number": 11, "version": 1}]

    changes, cursor = get_changed_objects(cursor=cursor, limit=1, queryset=qs)
    assert changes == [{"id": m1.id, "number": 9, "version": 2}]

    changes, cursor = get_changed_objects(cursor=cursor, limit=1, queryset=qs)
    assert changes == []

    m1.number -= 1
    m1.save(update_fields=["number"])

    changes, cursor = get_changed_objects(cursor=cursor, limit=1, queryset=qs)
    assert changes == [{"id": m1.id, "number": 8, "version": 3}]


@pytest.mark.django_db(transaction=True)
def test_get_changes_with_concurrent_changes() -> None:
    """
    Test that the get changes function works with concurrent changes
    """

    qs = MyModel.objects.values(
        "id",
        "number",
        version=F("version_info__version"),
        txid=F("version_info__last_modified_txid"),
    )

    model_1_id = None
    model_2_id = None

    t1_txid = None
    t2_txid = None

    with transaction.atomic():
        model_1_id = MyModel.objects.create(number=10).id
        main_txid = get_current_txid()

    log.info(f"Main: Transaction ID: {main_txid}")

    main_event = Event()
    t1_event = Event()
    t2_event = Event()

    @handle_exception()
    def thread_1() -> None:
        nonlocal model_2_id, t1_txid

        log.info("T1: Waiting for T2")
        t1_event.wait(timeout=1)
        t1_event.clear()

        with transaction.atomic():
            log.info("T1: Creating model 2")
            model_2 = MyModel.objects.create(number=3)
            model_2_id = model_2.id
            t1_txid = get_current_txid()

            log.info(f"T1: Transaction ID: {t1_txid}")

        log.info("T1: Waiting for event")
        assert not main_event.is_set()
        t2_event.set()

        log.info("T1: Done!")

    @handle_exception()
    def thread_2() -> None:
        nonlocal t2_txid

        with transaction.atomic():
            t2_txid = get_current_txid()
            log.info(f"T2: Transaction ID: {t2_txid}")
            log.info("T2: Waiting for event")
            t1_event.set()
            assert t2_event.wait(timeout=1)
            t2_event.clear()
            assert model_2_id is not None
            MyModel.objects.filter(id=model_2_id).update(number=F("number") + 1)

            main_event.set()
            assert t2_event.wait(timeout=1)

        main_event.set()

        log.info("T2: Done!")

    threads = [
        Thread(name="1", target=thread_1, daemon=True),
        Thread(name="2", target=thread_2, daemon=True),
    ]

    with run_threads(threads):

        # Wait for the next main step
        log.info("Main: Waiting for main event 1")
        assert main_event.wait(timeout=1)
        main_event.clear()

        assert t1_txid is not None

        log.info("Main: Getting changed objects")
        changes, cursor = get_changed_objects(cursor=None, limit=10, queryset=qs)
        log.info("Main: Got changed objects")
        assert changes == [
            {"id": model_1_id, "number": 10, "version": 1, "txid": main_txid},
            {"id": model_2_id, "number": 3, "version": 1, "txid": t1_txid},
        ]
        assert cursor.xid_at is None
        assert cursor.xid_at_id is None
        assert cursor.xip_list == [t2_txid]
        assert cursor.xid_next == t1_txid + 1

        t2_event.set()

        # Wait for the next main step
        log.info("Main: Waiting for main event 2")
        assert main_event.wait(timeout=1)

        changes, cursor = get_changed_objects(cursor=cursor, limit=1, queryset=qs)
        assert changes == [
            {"id": model_2_id, "number": 4, "version": 2, "txid": t2_txid},
        ]
        assert cursor.xid_at == t2_txid
        assert cursor.xid_at_id == model_2_id
        assert cursor.xip_list == []
        assert cursor.xid_next == t1_txid + 1

        changes, cursor = get_changed_objects(cursor=cursor, limit=1, queryset=qs)
        assert changes == []
        assert cursor.xid_at is None
        assert cursor.xid_at_id is None
        assert cursor.xip_list == []
        assert cursor.xid_next == t1_txid + 1
