import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models

import tracked_model.models
from tracked_model.operations import AddVersionTracking


class Migration(migrations.Migration):

    dependencies = [
        ("demo", "0001_initial"),
        ("tracked_model", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="MyModelVersion",
            fields=[
                ("version", models.IntegerField(db_default=1)),  # type: ignore[call-arg]
                (
                    "last_modified_txid",
                    models.BigIntegerField(
                        db_default=tracked_model.expressions.AdjustedTxidCurrent()  # type: ignore[call-arg]
                    ),
                ),
                (
                    "last_modified_at",
                    models.DateTimeField(
                        db_default=django.db.models.functions.datetime.Now()  # type: ignore[call-arg]
                    ),
                ),
                (
                    "object",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="version_info",
                        serialize=False,
                        to="demo.mymodel",
                    ),
                ),
            ],
            options={
                "abstract": False,
                "indexes": [
                    models.Index(
                        fields=["last_modified_txid", "object_id"],
                        name="demo_mymode_last_mo_b642ff_idx",
                    )
                ],
            },
        ),
        AddVersionTracking(tracked_model="MyModel", version_model="MyModelVersion"),
    ]
