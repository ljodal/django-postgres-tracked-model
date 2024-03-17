from typing import Callable

from django.apps.registry import Apps

MigrateToFixture = Callable[[str, str], Apps]
