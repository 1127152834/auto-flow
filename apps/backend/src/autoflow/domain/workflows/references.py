"""The shared, non-expression variable grammar used by drafts and runs."""

import re
import unicodedata

REFERENCE_PATTERN = re.compile(r"\$\{([^{}]*)\}|(?<![${])\{([^{}]*)\}(?!})")


def is_variable_name(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and (value[0] == "_" or unicodedata.category(value[0]).startswith("L"))
        and all(
            character == "_" or unicodedata.category(character)[0] in {"L", "N"}
            for character in value
        )
    )
