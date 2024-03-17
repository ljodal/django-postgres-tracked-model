from typing import TYPE_CHECKING, Any, Self, Sequence, cast

from django.core.exceptions import EmptyResultSet
from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import Value
from django.db.models.expressions import BaseExpression, Col, Combinable
from django.db.models.sql import Query
from django.db.models.sql.compiler import SQLCompiler

from .cursor import Cursor

if TYPE_CHECKING:
    from .models import ModelVersion


class AdjustedTxidCurrent(models.Func):
    function = "adjusted_txid_current"


class ChangedObjectsSubquery(BaseExpression, Combinable):
    template = """\
        SELECT object_id FROM ({queries}) as _changes
        ORDER BY priority, last_modified_txid, object_id \
        LIMIT %s \
    """
    contains_aggregate = False
    empty_result_set_value = None
    subquery = True

    def __init__(
        self,
        model_cls: type["ModelVersion"],
        cursor: Cursor,
        limit: int,
    ) -> None:
        super().__init__()

        self.limit = limit

        self.model_cls = model_cls

        # First priority is remaining changes from the current transaction
        if cursor.xid_at:
            changes_1 = (
                model_cls._default_manager.filter(
                    last_modified_txid=cursor.xid_at,
                    object_id__gt=cursor.xid_at_id,
                )
                .order_by("last_modified_txid", "object_id")
                .values("last_modified_txid", "object_id", priority=Value(1))
            )[:limit].query
        else:
            changes_1 = model_cls._default_manager.none().query
        changes_1.subquery = True

        # Next any changes from the in-progress transactions
        if cursor.xip_list:
            changes_2 = (
                model_cls._default_manager.filter(
                    last_modified_txid__in=cursor.xip_list
                )
                .order_by("last_modified_txid", "object_id")
                .values("last_modified_txid", "object_id", priority=Value(2))
            )[:limit].query
        else:
            changes_2 = model_cls._default_manager.none().query
        changes_2.subquery = True

        # Finally changes from later transactions
        changes_3 = (
            model_cls._default_manager.filter(last_modified_txid__gte=cursor.xid_next)
            .order_by("last_modified_txid", "object_id")
            .values("last_modified_txid", "object_id", priority=Value(3))
        )[:limit].query
        changes_3.subquery = True

        self.queries = [changes_1, changes_2, changes_3]

    def get_source_expressions(self) -> list[Query]:
        return self.queries

    def set_source_expressions(self, exprs: Sequence[Combinable]) -> None:
        assert len(exprs) == 3, "Exprs must be a list of three Query objects"
        self.queries = cast(list[Query], exprs)

    def _resolve_output_field(self) -> Any:
        return self.model_cls._meta.pk

    def copy(self) -> Self:
        clone = super().copy()
        clone.queries = [query.clone() for query in clone.queries]
        return clone

    @property
    def external_aliases(self) -> dict[str, bool]:
        return {
            key: value
            for query in self.queries
            for (key, value) in query.external_aliases.items()
        }

    def get_external_cols(self) -> list[Col]:
        return [
            col
            for query in self.queries
            for col in query.get_external_cols()  # type: ignore[attr-defined]
        ]

    def as_sql(
        self, compiler: SQLCompiler, connection: BaseDatabaseWrapper
    ) -> tuple[str, list[int | str]]:

        connection.ops.check_expression_support(self)

        queries, params = [], []
        for i, query in enumerate(self.queries):
            try:
                sql, sql_params = query.as_sql(compiler, connection)
            except EmptyResultSet:
                continue

            queries.append(f"(SELECT * FROM {sql} AS _{i + 1})")
            params += sql_params

        queries_sql = " UNION ALL ".join(queries)

        sql = self.template.format(queries=queries_sql)
        return sql, params + [self.limit]

    def get_group_by_cols(self) -> list[BaseExpression]:
        return [
            col
            for query in self.queries
            for col in query.get_group_by_cols(wrapper=self)  # type: ignore[call-arg]
        ]
