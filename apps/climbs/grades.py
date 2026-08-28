from django.db.models import Case, IntegerField, Value, When

FRENCH_GRADE_BASES = (
    "4a",
    "4a+",
    "4b",
    "4b+",
    "4c",
    "4c+",
    "5a",
    "5a+",
    "5b",
    "5b+",
    "5c",
    "5c+",
    "6a",
    "6a+",
    "6b",
    "6b+",
    "6c",
    "6c+",
    "7a",
    "7a+",
    "7b",
    "7b+",
    "7c",
    "7c+",
    "8a",
    "8a+",
    "8b",
    "8b+",
    "8c",
    "8c+",
    "9a",
    "9a+",
    "9b",
    "9b+",
    "9c",
)

FRENCH_GRADE_CHOICES = tuple((grade, grade) for grade in FRENCH_GRADE_BASES)
FRENCH_GRADE_INDEX = {grade: index for index, grade in enumerate(FRENCH_GRADE_BASES)}


def grade_order_expression(
    field_name: str = "official_grade",
    *,
    default_value: int | None = None,
) -> Case:
    fallback = len(FRENCH_GRADE_BASES) if default_value is None else default_value
    return Case(
        *[
            When(**{field_name: grade}, then=Value(index))
            for index, grade in enumerate(FRENCH_GRADE_BASES)
        ],
        default=Value(fallback),
        output_field=IntegerField(),
    )


def encode_perceived_grade(base_grade: str, decimal: int) -> int:
    if base_grade not in FRENCH_GRADE_INDEX:
        raise ValueError("Unknown French grade.")
    if not 0 <= decimal <= 9:
        raise ValueError("The decimal grade must be between 0 and 9.")
    return FRENCH_GRADE_INDEX[base_grade] * 10 + decimal


def format_perceived_grade(value: int) -> str:
    if value < 0:
        raise ValueError("Unknown encoded French grade.")
    base_index, decimal = divmod(value, 10)
    try:
        base_grade = FRENCH_GRADE_BASES[base_index]
    except IndexError as exc:
        raise ValueError("Unknown encoded French grade.") from exc
    return f"{base_grade}.{decimal}"


def format_grade_index(value: int | None) -> str:
    if value is None or value < 0 or value >= len(FRENCH_GRADE_BASES):
        return "—"
    return FRENCH_GRADE_BASES[value]
