from django.db.models import options

from .cursor import Cursor
from .utils import get_changed_objects, tracked

__all__ = ["get_changed_objects", "tracked", "Cursor"]

if "track_version" not in options.DEFAULT_NAMES:
    options.DEFAULT_NAMES = tuple(options.DEFAULT_NAMES) + ("track_version",)
