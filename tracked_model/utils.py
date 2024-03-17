from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast, overload

from django.db import connections, models, transaction
from django.db.models import F

from .cursor import Cursor, Snapshot
from .expressions import ChangedObjectsSubquery

if TYPE_CHECKING:
    from django.db.models.query import _QuerySet

    from .models import ModelVersion

T = TypeVar("T")
M = TypeVar("M", bound=models.Model)


@overload
def tracked(model_cls: None = ...) -> Callable[[type[M]], type[M]]: ...


@overload
def tracked(model_cls: type[M]) -> type[M]: ...


def tracked(model_cls: type[M] | None = None) -> Callable[[type[M]], type[M]] | type[M]:

    def decorator(model_cls: type[M]) -> type[M]:

        from .models import ModelVersion

        model_name = f"{model_cls.__name__}Version"
        fk_field: Any = models.OneToOneField(
            to=model_cls,
            related_name="version_info",
            on_delete=models.CASCADE,
            primary_key=True,
        )

        version_model = type(
            model_name,
            (ModelVersion,),
            {"object": fk_field, "__module__": model_cls.__module__},
        )
        model_cls.Version = version_model  # type: ignore[attr-defined]

        return model_cls

    if model_cls is None:
        return decorator

    return decorator(model_cls)


_SNAPSHOT_SQL = """\
SELECT
    (SELECT COALESCE(ARRAY_AGG(txid), ARRAY[]::bigint[]) FROM
        (SELECT txid_offset() + txid_snapshot_xip(txid_current_snapshot())) AS _(txid)
    ) AS xip_list,
    (SELECT txid_offset() + txid_snapshot_xmin(txid_current_snapshot())) AS xmin,
    (SELECT txid_offset() + txid_snapshot_xmax(txid_current_snapshot())) AS xmax
"""


@transaction.atomic(durable=True)
def get_changed_objects(
    *, cursor: Cursor | None, limit: int = 100, queryset: "_QuerySet[M, T]"
) -> tuple[list[T], Cursor]:
    """
    Get changed objects. If a cursor is provided only updates since that
    cursor was issued will be included, otherwise we'll start from the
    beginning and issue a new cursor.
    """

    if cursor is None:
        cursor = Cursor(xid_next=1, xip_list=[])

    model = queryset.model
    field = model._meta.get_field("version_info")
    assert isinstance(field, models.OneToOneRel)
    version_model = cast("type[ModelVersion]", field.related_model)

    connection = connections[queryset.db]
    with connection.cursor() as conn:
        # TODO: Avoid using a separate query for this
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        conn.execute(_SNAPSHOT_SQL)
        xip_list, xmin, xmax = conn.fetchone()
        snapshot = Snapshot(xip_list=xip_list, xmin=xmin, xmax=xmax)

    changed_objects = ChangedObjectsSubquery(
        model_cls=version_model, limit=limit, cursor=cursor
    )

    qs = queryset.filter(pk__in=changed_objects).annotate(
        _object_id=F("pk"),
        _last_modified_txid=F("version_info__last_modified_txid"),
    )

    last_modified_txid, last_object_id = None, None
    objects = []
    for obj in qs:
        if hasattr(obj, "__dict__"):
            last_object_id = obj.__dict__.pop("_object_id")
            last_modified_txid = obj.__dict__.pop("_last_modified_txid")
        elif isinstance(obj, dict):
            last_modified_txid = obj.pop("_last_modified_txid")
            last_object_id = obj.pop("_object_id")
        elif isinstance(obj, tuple):
            *row, last_object_id, last_modified_txid = obj
            obj = cast(T, tuple(row))
        else:
            raise ValueError(f"Unexpected type returned from queryset: {type(obj)}")

        objects.append(obj)

    next_cursor = cursor.next_cursor(
        snapshot=snapshot,
        last_modified_txid=last_modified_txid,
        last_object_id=last_object_id,
        has_more=len(objects) >= limit,
    )

    return objects, next_cursor
