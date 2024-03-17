from typing import Callable

import pytest
from django.db import transaction

from demo.models import MyModel


@pytest.mark.django_db(transaction=True)
def test_insert_and_update_separate_transactions(
    get_current_txid: Callable[[], int]
) -> None:
    """
    Test inserting an object in one transaction and then updating it in another
    """

    with transaction.atomic():
        first_txid = get_current_txid()
        model = MyModel.objects.create(number=1)
        assert hasattr(model, "version_info")
        version_info = model.version_info

        assert version_info.version == 1
        assert version_info.last_modified_txid == first_txid

    with transaction.atomic():
        second_txid = get_current_txid()
        assert second_txid != first_txid

        model.number = 2
        model.save(update_fields=["number"])

        version_info.refresh_from_db()
        assert version_info.version == 2
        assert version_info.last_modified_txid == second_txid


@pytest.mark.django_db()
def test_insert_and_update_same_transaction(current_txid: int) -> None:
    """
    Test inserting and updating an object in the same transaction
    """

    model = MyModel.objects.create(number=1)
    assert hasattr(model, "version_info")
    version_info = model.version_info

    assert version_info.version == 1
    assert version_info.last_modified_txid == current_txid

    model.number = 2
    model.save(update_fields=["number"])

    # Version should not be updated when making multiple changes in one transaction
    version_info.refresh_from_db()
    assert version_info.version == 1
    assert version_info.last_modified_txid == current_txid
