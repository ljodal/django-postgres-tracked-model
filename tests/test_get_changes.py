import pytest
from django.db.models import F

from demo.models import MyModel
from tracked_model import get_changed_objects


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
