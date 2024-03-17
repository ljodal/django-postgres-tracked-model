from django.db import models
from django.db.models.functions import Now

from .expressions import AdjustedTxidCurrent


class ModelVersion(models.Model):
    """
    Side-table to track the latest version of a model
    """

    # NOTE: This field should be addeed by subclasses
    object_id = models.IntegerField()

    version = models.IntegerField(db_default=1)  # type: ignore[call-arg]
    last_modified_txid = models.BigIntegerField(db_default=AdjustedTxidCurrent())  # type: ignore[call-arg]
    last_modified_at = models.DateTimeField(db_default=Now())  # type: ignore[call-arg]

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["last_modified_txid", "object_id"]),
        ]
