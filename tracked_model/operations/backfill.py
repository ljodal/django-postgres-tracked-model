from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.operations.base import Operation
from django.db.migrations.state import ProjectState

BACKFILL_QUERY_SQL = """\
INSERT INTO {version_table} (object_id)
SELECT id FROM {tracked_table}
ON CONFLICT (object_id) DO NOTHING;
"""


class BackfillModelVersion(Operation):
    reduces_to_sql = True
    reversible = True

    def __init__(self, tracked_model: str) -> None:
        self.tracked_model = tracked_model

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        pass

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:

        tracked_model = from_state.apps.get_model(app_label, self.tracked_model)
        field = tracked_model._meta.get_field("version_info")
        version_model = field.related_model

        tracked_table = tracked_model._meta.db_table
        version_table = version_model._meta.db_table

        context = {"tracked_table": tracked_table, "version_table": version_table}
        sql = BACKFILL_QUERY_SQL.format(**context)

        schema_editor.execute(sql)

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        pass

    def describe(self) -> str:
        return f"Backfill version info for {self.tracked_model}"

    @property
    def migration_name_fragment(self) -> str:
        return f"backfill_version_info_for_{self.tracked_model.lower()}"
