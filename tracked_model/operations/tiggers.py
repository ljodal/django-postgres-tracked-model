from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.operations.base import Operation
from django.db.migrations.state import ProjectState

CREATE_INSERT_TRIGGER_FUNCTION_SQL = """\
CREATE OR REPLACE FUNCTION insert_{version_table}() RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO {version_table} (object_id, last_modified_txid)
    SELECT id, txid_current() FROM inserted;
    RETURN NULL;
END; $$
LANGUAGE plpgsql;
"""

CREATE_UPDATE_TRIGGER_FUNCTION_SQL = """\
CREATE OR REPLACE FUNCTION update_{version_table}() RETURNS TRIGGER AS $$
BEGIN
    UPDATE {version_table} SET
        version = version + 1,
        last_modified_txid = txid_current(),
        last_modified_at = now()
    FROM
        updated
    WHERE {version_table}.object_id = updated.id
      AND last_modified_txid != txid_current();
    RETURN NULL;
END; $$
LANGUAGE plpgsql;
"""

CREATE_INSERT_TRIGGER_SQL = """\
CREATE OR REPLACE TRIGGER insert_version_info
    AFTER INSERT ON {tracked_table}
    REFERENCING NEW TABLE AS inserted
    FOR EACH STATEMENT
    EXECUTE PROCEDURE insert_{version_table}();
"""

CREATE_UPDATE_TRIGGER_SQL = """\
CREATE OR REPLACE TRIGGER update_version_info
    AFTER UPDATE ON {tracked_table}
    REFERENCING OLD TABLE AS updated
    FOR EACH STATEMENT
    EXECUTE PROCEDURE update_{version_table}();
"""

DROP_INSERT_TRIGGER_FUNCTION_SQL = """\
DROP FUNCTION IF EXISTS update_{version_table}();
"""

DROP_UPDATE_TRIGGER_FUNCTION_SQL = """\
DROP FUNCTION IF EXISTS update_{version_table}();
"""

DROP_INSERT_TRIGGER_SQL = """\
DROP TRIGGER IF EXISTS insert_version_info ON {tracked_table};
"""

DROP_UPDATE_TRIGGER_SQL = """\
DROP TRIGGER IF EXISTS update_version_info ON {tracked_table};
"""


def _add_trigger_sql(tracked_table: str, version_table: str) -> list[str]:

    context = {"version_table": version_table, "tracked_table": tracked_table}

    # TODO: Parametrize pk column name
    return [
        CREATE_INSERT_TRIGGER_FUNCTION_SQL.format(**context),
        CREATE_UPDATE_TRIGGER_FUNCTION_SQL.format(**context),
        CREATE_INSERT_TRIGGER_SQL.format(**context),
        CREATE_UPDATE_TRIGGER_SQL.format(**context),
    ]


def _drop_trigger_sql(tracked_table: str, version_table: str) -> list[str]:

    context = {"version_table": version_table, "tracked_table": tracked_table}

    return [
        DROP_INSERT_TRIGGER_SQL.format(**context),
        DROP_UPDATE_TRIGGER_SQL.format(**context),
        DROP_INSERT_TRIGGER_FUNCTION_SQL.format(**context),
        DROP_UPDATE_TRIGGER_FUNCTION_SQL.format(**context),
    ]


class AddVersionTracking(Operation):
    """
    This operation adds a trigger that updates the version model associated
    with the specified model class.
    """

    reduces_to_sql = True
    reversible = True

    def __init__(self, tracked_model: str, version_model: str) -> None:
        self.tracked_model = tracked_model
        self.version_model = version_model

    def state_forwards(self, app_label: str, state: ProjectState) -> None:
        state.alter_model_options(
            app_label, self.tracked_model.lower(), {"track_version": True}
        )

    def database_forwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:

        tracked_model = from_state.apps.get_model(app_label, self.tracked_model)
        version_model = from_state.apps.get_model(app_label, self.version_model)

        tracked_table = tracked_model._meta.db_table
        version_table = version_model._meta.db_table

        queries = _add_trigger_sql(tracked_table, version_table)

        for query in queries:
            schema_editor.execute(query)

    def database_backwards(
        self,
        app_label: str,
        schema_editor: BaseDatabaseSchemaEditor,
        from_state: ProjectState,
        to_state: ProjectState,
    ) -> None:
        tracked_model = from_state.apps.get_model(app_label, self.tracked_model)
        version_model = from_state.apps.get_model(app_label, self.version_model)

        tracked_table = tracked_model._meta.db_table
        version_table = version_model._meta.db_table

        queries = _drop_trigger_sql(tracked_table, version_table)

        for query in queries:
            schema_editor.execute(query)

    def describe(self) -> str:
        return f"Add version tracking trigger to {self.tracked_model}"

    @property
    def migration_name_fragment(self) -> str:
        return f"add_version_tracking_to_{self.tracked_model.lower()}"
