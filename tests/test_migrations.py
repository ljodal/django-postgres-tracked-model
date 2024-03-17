import pytest

from .types import MigrateToFixture


def test_backfill_versions(migrate_to: MigrateToFixture) -> None:
    """
    Test that backfilling version info for objects created before the triggers
    are added works.
    """

    apps = migrate_to("demo", "0001")

    MyModel = apps.get_model("demo", "MyModel")
    with pytest.raises(LookupError):
        apps.get_model("demo", "MyModelVersion")

    m1 = MyModel.objects.create(number=10)

    apps = migrate_to("demo", "0002")
    MyModel = apps.get_model("demo", "MyModel")
    apps.get_model("demo", "MyModelVersion")  # Should exist now

    m2 = MyModel.objects.create(number=20)
    assert hasattr(m2, "version_info")
    assert m2.version_info.version == 1

    apps = migrate_to("demo", "__latest__")

    m1 = MyModel.objects.get(id=m1.id)
    m2 = MyModel.objects.get(id=m2.id)

    assert hasattr(m1, "version_info")
    assert hasattr(m2, "version_info")
    assert m1.version_info.version == 1
    assert m2.version_info.version == 1
