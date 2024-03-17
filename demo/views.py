from django.db.models import F
from django.http import HttpRequest, JsonResponse

from tracked_model import Cursor, get_changed_objects

from .models import MyModel


def get_changes(request: HttpRequest) -> JsonResponse:

    cursor = None
    if serialized_cursor := request.GET.get("cursor"):
        cursor = Cursor.model_validate_json(serialized_cursor)

    try:
        limit = int(request.GET.get("limit", "1"))
    except Exception:
        limit = 1

    qs = MyModel.objects.values("number", version=F("version_info__version"))
    changes, cursor = get_changed_objects(cursor=cursor, limit=limit, queryset=qs)

    return JsonResponse({"changes": changes, "cursor": cursor})
