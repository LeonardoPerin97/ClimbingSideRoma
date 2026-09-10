from collections.abc import Sequence
from typing import Any

from django.conf import settings
from django.core.paginator import Page, Paginator
from django.db.models import QuerySet
from django.http import HttpRequest

SHOW_ALL_VALUE = "all"


def paginate(
    request: HttpRequest,
    object_list: QuerySet[Any] | Sequence[Any],
) -> tuple[Page[Any], bool]:
    """Return a standard page or a single page containing the complete result set."""
    standard_paginator = Paginator(object_list, settings.PAGINATION_PAGE_SIZE)
    show_all = request.GET.get("per_page") == SHOW_ALL_VALUE
    if show_all:
        all_items_paginator = Paginator(object_list, max(standard_paginator.count, 1))
        return all_items_paginator.get_page(1), True
    return standard_paginator.get_page(request.GET.get("page")), False
