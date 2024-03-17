from typing import Any, Callable

import pytest
import structlog
from django.apps.registry import Apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from .types import MigrateToFixture
from .utils import get_current_txid


@pytest.hookimpl()
def pytest_plugin_registered(plugin: Any, plugin_name: str) -> None:
    """
    Use structlog to format the logged messages
    """

    if plugin_name == "logging-plugin":
        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(),
            ],
        )
        plugin.report_handler.setFormatter(formatter)


@pytest.fixture
def current_txid(db: None) -> int:
    return get_current_txid()


@pytest.fixture
def migrate_to(db: None) -> MigrateToFixture:
    """
    This fixture provides a helper function to navigate to a specific migration
    """

    def migrate(app_label: str, migration_name: str | None) -> Apps:
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        if migration_name == "__latest__":
            target = executor.loader.graph.leaf_nodes(app_label)[0]
        elif migration_name == "__first__":
            target = executor.loader.graph.root_nodes(app_label)[0]
        elif migration_name:
            migration = executor.loader.get_migration_by_prefix(
                app_label, migration_name
            )
            target = (app_label, migration.name)
        else:
            target = (app_label, None)
        state = executor.migrate([target])
        return state.apps

    return migrate


@pytest.fixture(autouse=True)
def migrate_to_initial_migration(request: pytest.FixtureRequest) -> None:
    """
    This fixture will automatically migrate to the migration specified using
    the @pytest.mark.initial_migration(<app_label>, <migration>) marker.
    """

    if marker := request.node.get_closest_marker("initial_migration"):
        assert len(marker.args) == 2
        app_label, migration = marker.args
        assert isinstance(app_label, str)
        assert isinstance(migration, str | None)

        # Lazy-load the fixture to avoid requesting db setup on all tests
        migrate_to: Callable[[str, str | None], None]
        migrate_to = request.getfixturevalue("migrate_to")
        migrate_to(app_label, migration)
