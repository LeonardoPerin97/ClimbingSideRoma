from typing import Any

from django import template

from apps.climbs.grades import format_grade_index

register = template.Library()


@register.filter
def french_grade_from_index(value: Any) -> str:
    try:
        grade_index = int(value)
    except (TypeError, ValueError):
        return "—"
    return format_grade_index(grade_index)
